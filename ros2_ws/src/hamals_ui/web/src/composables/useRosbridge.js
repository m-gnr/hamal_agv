import { ref, shallowRef, computed } from 'vue'
import ROSLIB from 'roslib'
import { liveState, manualAllowed } from './liveState.js'

export function useRosbridge(url, transport = ROSLIB) {
  const raw = shallowRef(null)
  const connected = ref(false)
  const ros = shallowRef(null)
  const receivedAt = ref(null)
  const now = ref(Date.now())
  const state = computed(() => liveState(raw.value, connected.value, receivedAt.value, now.value))
  let stateTopic, cmdTopic, reconnectTimer, ageTimer, stopped = true
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
    if (current.meta.stale) return false
    if (['switch_mode', 'estop', 'estop_ack'].includes(cmd.type)) return false
    if (cmd.type === 'teleop' || cmd.type === 'lift') {
      if (!manualAllowed(current)) return false
      cmd = { ...cmd, payload: { ...cmd.payload, state_ts: current.meta.ts } }
    }
    return publish('/ui/cmd', 'std_msgs/String', { data: JSON.stringify(cmd) })
  }
  function stopMotion() {
    sendCmd({ type: 'teleop', payload: { linear: 0, angular: 0 } })
  }
  function open() {
    if (stopped) return
    const client = new transport.Ros({ url })
    ros.value = client
    client.on('connection', () => {
      if (stopped || client !== ros.value) return
      receivedAt.value = null
      lastStamp = null
      connected.value = true
      cmdTopic = new transport.Topic({ ros: client, name: '/ui/cmd', messageType: 'std_msgs/String', reconnect_on_close: false })
      stateTopic = new transport.Topic({ ros: client, name: '/ui/state', messageType: 'std_msgs/String', reconnect_on_close: false })
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
      if (client !== ros.value) return
      stopMotion() // Best effort only; a closed socket cannot deliver a stop.
      connected.value = false
      receivedAt.value = null
      if (stateTopic) stateTopic.unsubscribe()
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
    connected.value = false
    ros.value?.close()
    ros.value = null
  }
  return { state, connected, ros, connect, disconnect, publish, sendCmd }
}
