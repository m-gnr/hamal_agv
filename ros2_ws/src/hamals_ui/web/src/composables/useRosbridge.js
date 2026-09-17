import { ref, shallowRef, computed } from 'vue'
import ROSLIB from 'roslib'
import { liveState, manualAllowed } from './liveState.js'

export function useRosbridge(url, transport = ROSLIB) {
  const raw = shallowRef(null)
  const connected = ref(false)
  const physicalMode = ref('unknown')
  const ros = shallowRef(null)
  const receivedAt = ref(null)
  const now = ref(Date.now())
  const state = computed(() => liveState(raw.value, connected.value, receivedAt.value, now.value))
  let stateTopic, modeTopic, cmdTopic, motionTopic, forkTopic, reconnectTimer, ageTimer, stopped = true
  let lastStamp = null

  function publish(topic, type, data) {
    if (!connected.value || !ros.value?.isConnected || stopped) return false
    // Reuse a non-reconnecting publisher: never replay queued motion commands.
    if (topic !== '/ui/cmd' || type !== 'std_msgs/String') return false
    cmdTopic.publish(new transport.Message(data))
    return true
  }
  function sendCmd(cmd) {
    const current = liveState(raw.value, connected.value, receivedAt.value, Date.now())
    if (['switch_mode', 'estop', 'estop_ack'].includes(cmd.type)) return false
    if (cmd.type === 'teleop') {
      const { linear, angular } = cmd.payload || {}
      if (!Number.isFinite(linear) || !Number.isFinite(angular)) return false
      if ((linear !== 0 || angular !== 0) && !manualAllowed(physicalMode.value, connected.value)) return false
      if (!connected.value || !ros.value?.isConnected || stopped || !motionTopic) return false
      motionTopic.publish(new transport.Message({
        linear: { x: linear, y: 0, z: 0 }, angular: { x: 0, y: 0, z: angular },
      }))
      return true
    }
    if (cmd.type === 'lift') {
      if (!manualAllowed(physicalMode.value, connected.value) || !ros.value?.isConnected || stopped || !forkTopic) return false
      const action = { up: 'UP', down: 'DOWN', stop: 'STOP' }[cmd.payload?.action]
      if (!action) return false
      forkTopic.publish(new transport.Message({ data: action }))
      return true
    }
    if (current.meta.stale) return false
    return publish('/ui/cmd', 'std_msgs/String', { data: JSON.stringify(cmd) })
  }
  function stopMotion() {
    sendCmd({ type: 'teleop', payload: { linear: 0, angular: 0 } })
  }
  function open() {
    if (stopped) return
    const client = new transport.Ros({ url })
    let lostHandled = false
    ros.value = client
    client.on('connection', () => {
      if (stopped || lostHandled || connected.value || client !== ros.value) return
      receivedAt.value = null
      lastStamp = null
      physicalMode.value = 'unknown'
      connected.value = true
      // yous: reconnect_on_close:false KALDIRILDI — roslib 1.4.0 bug'ı subscribe/advertise'da
      //       "Cannot read properties of undefined (reading 'encoder')" fırlatıyor (callOnConnection this-binding kaybı).
      // eski: cmdTopic  = ...'std_msgs/String', reconnect_on_close: false })
      // eski: stateTopic = ...'std_msgs/String', reconnect_on_close: false })
      cmdTopic = new transport.Topic({ ros: client, name: '/ui/cmd', messageType: 'std_msgs/String' })
      motionTopic = new transport.Topic({ ros: client, name: '/cmd_vel/manual_teleop', messageType: 'geometry_msgs/msg/Twist' })
      forkTopic = new transport.Topic({ ros: client, name: '/mcu/fork_cmd', messageType: 'std_msgs/msg/String' })
      modeTopic = new transport.Topic({ ros: client, name: '/switch/mode', messageType: 'std_msgs/msg/String' })
      modeTopic.subscribe(msg => {
        if (client !== ros.value || stopped || !connected.value) return
        if (msg.data !== 'manual' && msg.data !== 'auto') return
        if (physicalMode.value === 'manual' && msg.data === 'auto') stopMotion()
        physicalMode.value = msg.data
      })
      stateTopic = new transport.Topic({ ros: client, name: '/ui/state', messageType: 'std_msgs/String' })
      stateTopic.subscribe(msg => {
        if (client !== ros.value || stopped) return
        try {
          const parsed = JSON.parse(msg.data)
          if (!parsed || typeof parsed !== 'object') return
          // Repeated snapshots do not renew freshness.
          if (!Number.isFinite(parsed.meta?.ts) || parsed.meta.ts === lastStamp) return
          lastStamp = parsed.meta.ts
          raw.value = parsed
          receivedAt.value = Date.now()
          now.value = Date.now()
        } catch { /* malformed state cannot refresh the lease */ }
      })
    })
    function lost() {
      if (client !== ros.value || lostHandled) return
      lostHandled = true
      stopMotion() // Best effort only; a closed socket cannot deliver a stop.
      connected.value = false
      physicalMode.value = 'unknown'
      receivedAt.value = null
      if (stateTopic) stateTopic.unsubscribe()
      if (modeTopic) modeTopic.unsubscribe()
      motionTopic = forkTopic = null
      if (!stopped && !reconnectTimer) reconnectTimer = setTimeout(() => {
        reconnectTimer = null
        client.removeAllListeners()
        client.close()
        open()
      }, 3000)
    }
    client.on('error', lost)
    client.on('close', lost)
  }
  function connect() {
    if (!stopped) return
    stopped = false
    ageTimer = setInterval(() => { now.value = Date.now() }, 100)
    open()
  }
  function disconnect() {
    stopMotion()
    stopped = true
    clearTimeout(reconnectTimer)
    clearInterval(ageTimer)
    stateTopic?.unsubscribe()
    modeTopic?.unsubscribe()
    motionTopic = forkTopic = null
    connected.value = false
    physicalMode.value = 'unknown'
    ros.value?.close()
    ros.value = null
  }
  return { state, physicalMode, connected, ros, connect, disconnect, publish, sendCmd }
}
