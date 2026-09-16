// Hold-to-run controller. A lost lease clears the hold; it never restarts itself.
export function manualControl(allowed, publish, timers = globalThis) {
  let timer = null
  function stop() {
    if (timer != null) timers.clearInterval(timer)
    timer = null
    if (allowed()) publish({ linear: 0, angular: 0 })
  }
  function start(linear, angular) {
    if (!allowed()) return
    stop()
    const tick = () => {
      if (!allowed()) { stop(); return }
      publish({ linear, angular })
    }
    tick()
    timer = timers.setInterval(tick, 100)
  }
  return { start, stop }
}
