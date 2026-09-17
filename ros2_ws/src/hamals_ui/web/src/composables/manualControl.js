import { ref } from 'vue'

const LINEAR_MIN = -0.20
const LINEAR_MAX = 0.25
const ANGULAR_MAX = 0.50
const ANGULAR_STEP = 0.10
const LINEAR_STEP = 0.05
const clamp = (value, min, max) => Math.max(min, Math.min(max, value))
const rounded = value => +value.toFixed(2)

// One controller owns both button and keyboard input; transport stays in the caller.
export function manualControl(allowed, publishMotion, publishFork, timers = globalThis) {
  const targetLinear = ref(0)
  const targetAngular = ref(0)
  const activeButton = ref(null)
  let publishTimer = null
  let feedbackTimer = null

  function publish() {
    if (allowed()) publishMotion({ linear: targetLinear.value, angular: targetAngular.value })
  }
  function feedback(button) {
    activeButton.value = button
    if (feedbackTimer != null) timers.clearTimeout(feedbackTimer)
    feedbackTimer = timers.setTimeout(() => { activeButton.value = null }, 150)
  }
  function linear(direction, button = null) {
    if (!allowed()) return
    targetLinear.value = rounded(clamp(targetLinear.value + direction * LINEAR_STEP, LINEAR_MIN, LINEAR_MAX))
    if (button) feedback(button)
    publish()
  }
  function angular(direction, button = null) {
    if (!allowed()) return
    targetAngular.value = rounded(clamp(targetAngular.value + direction * ANGULAR_STEP, -ANGULAR_MAX, ANGULAR_MAX))
    if (button) feedback(button)
    publish()
  }
  function stop(button = null) {
    targetLinear.value = 0
    targetAngular.value = 0
    if (button) feedback(button)
    // Best effort on a mode change or disconnect; the transport checks the socket.
    publishMotion({ linear: 0, angular: 0 })
  }
  function fork(action, button = null) {
    if (!allowed()) return
    if (button) feedback(button)
    publishFork(action)
  }
  function keydown(event) {
    if (event.repeat || event.altKey || event.ctrlKey || event.metaKey || !allowed()) return
    const target = event.target
    if (target?.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(target?.tagName)) return
    if (event.shiftKey) {
      const action = event.code === 'ArrowUp' ? 'up' : event.code === 'ArrowDown' ? 'down' : event.code === 'Space' ? 'stop' : null
      if (action) { event.preventDefault(); fork(action, `fork-${action}`) }
      return
    }
    const key = event.key.toLowerCase()
    if (key === 'w') linear(1, 'up')
    else if (key === 's') linear(-1, 'down')
    else if (key === 'a') angular(1, 'left')
    else if (key === 'd') angular(-1, 'right')
    else if (event.code === 'Space') stop('stop')
    else return
    event.preventDefault()
  }
  function start() {
    if (publishTimer != null) return
    publishTimer = timers.setInterval(publish, 50)
  }
  function dispose() {
    stop()
    if (publishTimer != null) timers.clearInterval(publishTimer)
    if (feedbackTimer != null) timers.clearTimeout(feedbackTimer)
    publishTimer = feedbackTimer = null
  }
  return { targetLinear, targetAngular, activeButton, linear, angular, stop, fork, keydown, start, dispose }
}
