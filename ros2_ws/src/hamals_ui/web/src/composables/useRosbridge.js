/**
 * Connects to rosbridge WebSocket and subscribes to /ui/state.
 * Falls back gracefully — state stays null until first message arrives.
 */

import { ref, readonly } from 'vue'
import ROSLIB from 'roslib'

export function useRosbridge(url) {
  const state = ref(null)
  const connected = ref(false)
  const ros = ref(null)          // exposed so other composables can subscribe to extra topics
  let stateTopic = null

  function connect() {
    ros.value = new ROSLIB.Ros({ url })

    ros.value.on('connection', () => {
      connected.value = true
      stateTopic = new ROSLIB.Topic({
        ros: ros.value,
        name: '/ui/state',
        messageType: 'std_msgs/String',
      })
      stateTopic.subscribe((msg) => {
        try {
          state.value = JSON.parse(msg.data)
        } catch {
          // malformed JSON — ignore
        }
      })
    })

    ros.value.on('error', () => { connected.value = false })
    ros.value.on('close', () => {
      connected.value = false
      ros.value = null
      // Attempt reconnect after 3s
      setTimeout(connect, 3000)
    })
  }

  function publish(topic, type, data) {
    if (!ros.value || !connected.value) return
    const t = new ROSLIB.Topic({ ros: ros.value, name: topic, messageType: type })
    t.publish(new ROSLIB.Message(data))
  }

  function disconnect() {
    if (stateTopic) stateTopic.unsubscribe()
    if (ros.value) ros.value.close()
  }

  return { state: readonly(state), connected: readonly(connected), ros: readonly(ros), connect, disconnect, publish }
}