import { ref, watch } from 'vue'
import ROSLIB from 'roslib'

export function useLiveTopics(rosRef) {
  const mapData = ref(null)     // { info: {...}, data: Int8Array-like }
  const scanData = ref(null)    // { angle_min, angle_increment, ranges, range_max }
  const robotPose = ref(null)   // { x, y, theta_deg } in the MAP frame (from TF, not /odom)

  let mapTopic = null
  let scanTopic = null
  let tfClient = null

  function quatToYawDeg(q) {
    const siny_cosp = 2 * (q.w * q.z + q.x * q.y)
    const cosy_cosp = 1 - 2 * (q.y * q.y + q.z * q.z)
    return Math.atan2(siny_cosp, cosy_cosp) * 180 / Math.PI
  }

  function subscribe(ros) {
    if (!ros) return

    mapTopic = new ROSLIB.Topic({
      ros,
      name: '/map',
      messageType: 'nav_msgs/OccupancyGrid',
    })
    mapTopic.subscribe((msg) => { mapData.value = msg })

    scanTopic = new ROSLIB.Topic({
      ros,
      name: '/scan',
      messageType: 'sensor_msgs/LaserScan',
    })
    scanTopic.subscribe((msg) => { scanData.value = msg })

    // Robot pose in the MAP frame, via TF (map -> base_footprint).
    // Using /odom directly would be wrong here: /odom is in the odom
    // frame, which can be offset from map (loop closure, AMCL correction).
    tfClient = new ROSLIB.TFClient({
      ros,
      fixedFrame: 'map',
      angularThres: 0.01,
      transThres: 0.01,
      rate: 10.0,
    })
    tfClient.subscribe('base_footprint', (tf) => {
      robotPose.value = {
        x: tf.translation.x,
        y: tf.translation.y,
        theta_deg: quatToYawDeg(tf.rotation),
      }
    })
  }

  function unsubscribe() {
    if (mapTopic) mapTopic.unsubscribe()
    if (scanTopic) scanTopic.unsubscribe()
    if (tfClient) tfClient.dispose()
  }

  // rosRef becomes available asynchronously (after rosbridge connects)
  watch(rosRef, (ros) => {
    unsubscribe()
    if (ros) subscribe(ros)
  }, { immediate: true })

  return { mapData, scanData, robotPose, unsubscribe }
}