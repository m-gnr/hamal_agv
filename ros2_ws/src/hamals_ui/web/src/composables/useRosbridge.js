/**
 * Connects to rosbridge WebSocket and subscribes to /ui/state.
 * Falls back gracefully — state stays null until first message arrives.
 */

import { ref, readonly } from 'vue'
import ROSLIB from 'roslib'

export function useRosbridge(url) {
  const state = ref(null)
  const connected = ref(false)
  let ros = null
  let stateTopic = null

  function connect() {
    ros = new ROSLIB.Ros({ url })

    ros.on('connection', () => {
      connected.value = true
      stateTopic = new ROSLIB.Topic({
        ros,
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

    ros.on('error', () => { connected.value = false })
    ros.on('close', () => {
      connected.value = false
      // Attempt reconnect after 3s
      setTimeout(connect, 3000)
    })
  }

  function publish(topic, type, data) {
    if (!ros || !connected.value) return
    const t = new ROSLIB.Topic({ ros, name: topic, messageType: type })
    t.publish(new ROSLIB.Message(data))
  }

  function disconnect() {
    if (stateTopic) stateTopic.unsubscribe()
    if (ros) ros.close()
  }

  return { state: readonly(state), connected: readonly(connected), connect, disconnect, publish }
}
