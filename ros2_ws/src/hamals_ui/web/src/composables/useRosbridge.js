import { ref, shallowRef, computed } from 'vue'
import ROSLIB from 'roslib'
import { liveState, manualAllowed } from './liveState.js'
import { createMapFeed } from './occupancyGrid.js'

export function useRosbridge(url, transport = ROSLIB) {
  const raw = shallowRef(null)
  const plcState = shallowRef(null)
  const missionState = shallowRef(null)
  const connected = ref(false)
  const physicalMode = ref('unknown')
  const cameraIsBack = ref(false)
  const ros = shallowRef(null)
  const receivedAt = ref(null)
  const now = ref(Date.now())
  const mapFeed = createMapFeed()
  const mapReady = ref(false)
  const savePending = ref(false)
  const saveResult = ref(null)
  const state = computed(() => liveState(raw.value, connected.value, receivedAt.value, now.value))
  let stateTopic, modeTopic, cameraTopic, mapTopic, plcTopic, missionTopic, cmdTopic, motionTopic, forkTopic, reconnectTimer, ageTimer, stopped = true
  let lastStamp = null
  let finishSave = null

  function saveMap() {
    if (!connected.value || !ros.value?.isConnected || stopped || !mapReady.value || savePending.value) {
      return Promise.resolve({ success: false, message: 'Kaydedilecek harita yok veya ROS bağlantısı yok.' })
    }
    savePending.value = true
    saveResult.value = null
    const client = ros.value
    return new Promise(resolve => {
      const timer = setTimeout(() => finish({ success: false, message: 'Harita kaydetme zaman aşımına uğradı.' }), 35000)
      function finish(result) {
        if (finishSave !== finish) return
        clearTimeout(timer)
        finishSave = null
        savePending.value = false
        saveResult.value = result
        resolve(result)
      }
      finishSave = finish
      try {
        const service = new transport.Service({ ros: client, name: '/map/save', serviceType: 'std_srvs/srv/Trigger' })
        service.callService(new transport.ServiceRequest({}),
          response => finish({ success: response.success === true, message: response.message || '' }),
          error => finish({ success: false, message: String(error || 'Servis çağrısı başarısız.') }))
      } catch (error) {
        finish({ success: false, message: String(error) })
      }
    })
  }

  function publish(topic, type, data) {
    if (!connected.value || !ros.value?.isConnected || stopped) return false
    // Reuse a non-reconnecting publisher: never replay queued motion commands.
    if (topic !== '/ui/cmd' || type !== 'std_msgs/String') return false
    cmdTopic.publish(new transport.Message(data))
    return true
  }
  function sendCmd(cmd) {
    if (['start_mission', 'pause_mission', 'resume_mission', 'cancel_mission'].includes(cmd.type) && plcState.value?.transport !== 'mock') return false
    const current = liveState(raw.value, connected.value, receivedAt.value, Date.now())
    if (['switch_mode', 'estop', 'estop_ack'].includes(cmd.type)) return false
    if (cmd.type === 'switch_camera') {
      if (typeof cmd.payload?.is_up !== 'boolean') return false
      const sent = publish('/ui/cmd', 'std_msgs/String', { data: JSON.stringify(cmd) })
      if (sent) cameraIsBack.value = cmd.payload.is_up
      return sent
    }
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
      mapReady.value = false
      lastStamp = null
      physicalMode.value = 'unknown'
      plcState.value = null
      missionState.value = null
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
      cameraTopic = new transport.Topic({ ros: client, name: '/fork/is_up', messageType: 'std_msgs/msg/Bool' })
      cameraTopic.subscribe(msg => {
        if (client !== ros.value || stopped || !connected.value || typeof msg.data !== 'boolean') return
        cameraIsBack.value = msg.data
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
      plcTopic = new transport.Topic({ ros: client, name: '/plc/state', messageType: 'hamals_interfaces/msg/PlcState' })
      plcTopic.subscribe(msg => {
        if (client !== ros.value || stopped || !connected.value) return
        plcState.value = msg
      })
      missionTopic = new transport.Topic({ ros: client, name: '/mission/state', messageType: 'hamals_interfaces/msg/MissionState' })
      missionTopic.subscribe(msg => {
        if (client !== ros.value || stopped || !connected.value) return
        missionState.value = msg
      })
      mapTopic = new transport.Topic({ ros: client, name: '/map', messageType: 'nav_msgs/msg/OccupancyGrid' })
      mapTopic.subscribe(msg => {
        if (client !== ros.value || stopped || !connected.value) return
        mapFeed.push(msg)
        mapReady.value = mapFeed.latest === msg
      })
    })
    function lost() {
      if (client !== ros.value || lostHandled) return
      lostHandled = true
      stopMotion() // Best effort only; a closed socket cannot deliver a stop.
      connected.value = false
      mapReady.value = false
      finishSave?.({ success: false, message: 'ROS bağlantısı kesildi.' })
      physicalMode.value = 'unknown'
      receivedAt.value = null
      plcState.value = null
      missionState.value = null
      if (stateTopic) stateTopic.unsubscribe()
      if (modeTopic) modeTopic.unsubscribe()
      if (cameraTopic) cameraTopic.unsubscribe()
      if (mapTopic) mapTopic.unsubscribe()
      if (plcTopic) plcTopic.unsubscribe()
      if (missionTopic) missionTopic.unsubscribe()
      stateTopic = modeTopic = cameraTopic = mapTopic = plcTopic = missionTopic = null
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
    cameraTopic?.unsubscribe()
    mapTopic?.unsubscribe()
    plcTopic?.unsubscribe()
    missionTopic?.unsubscribe()
    stateTopic = modeTopic = cameraTopic = mapTopic = plcTopic = missionTopic = null
    motionTopic = forkTopic = null
    connected.value = false
    plcState.value = null
    missionState.value = null
    mapReady.value = false
    finishSave?.({ success: false, message: 'ROS bağlantısı kesildi.' })
    physicalMode.value = 'unknown'
    ros.value?.close()
    ros.value = null
  }
  return { state, plcState, missionState, physicalMode, cameraIsBack, connected, ros, mapFeed, mapReady, savePending, saveResult, saveMap, connect, disconnect, publish, sendCmd }
}
