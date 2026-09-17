import test from 'node:test'
import assert from 'node:assert/strict'
import { liveState, freshness, manualAllowed, qrActive, safetySummary } from '../src/composables/liveState.js'
import { manualControl } from '../src/composables/manualControl.js'
function fixture(mode = 'manual') {
  return liveState({ meta: { mode: 'live', ts: 10, sources: {
    '/switch/mode': { age_s: 0.1 }, '/safety/state': { age_s: 0.1 },
    '/scan/obstacle_state': { age_s: 0.1 }, '/qr/detected': { age_s: 0.1 },
  } }, switch: { mode } }, true, 1000, 1000)
}
for (const mode of ['manual', 'auto', 'unknown', '', 'MANUAL', ' manual']) {
  test(`manual gate: ${JSON.stringify(mode)}`, () => assert.equal(manualAllowed(fixture(mode)), mode === 'manual'))
}
test('disconnect blocks manual and marks all sources disconnected', () => {
  const s = liveState(fixture(), false, 1000, 1100)
  assert.equal(s.meta.stale, true)
  assert.equal(manualAllowed(s), false)
  assert.equal(freshness(s, '/safety/state'), 'disconnected')
})
test('stale mode cannot be renewed by live aggregate snapshots', () => {
  const s = fixture(); s.meta.sources['/switch/mode'].age_s = 1.1
  assert.equal(manualAllowed(s), false)
})
test('browser receipt age advances per-source age', () => {
  const s = liveState(fixture(), true, 1000, 1950)
  assert.equal(manualAllowed(s), false)
})
test('global stale blocks controls', () => assert.equal(manualAllowed(liveState(fixture(), true, 1000, 4000)), false))
test('startup contains no fake telemetry', () => {
  const s = liveState(null, true, null)
  for (const key of ['battery', 'pose', 'fork', 'mission', 'safety', 'plc', 'qr', 'line']) assert.equal(s[key], undefined)
  assert.equal(safetySummary(s).tone, 'warn')
})
test('backend mock data is rejected by live provider', () => {
  const s = liveState({ meta: { mode: 'mock' }, battery: { percent: 100 }, switch: { mode: 'manual' } }, true, 1000, 1000)
  assert.equal(s.meta.mismatch, true); assert.equal(s.battery, undefined); assert.equal(manualAllowed(s), false)
})
test('unknown safety never healthy', () => assert.equal(safetySummary(fixture()).tone, 'unknown'))
test('boolean obstacle true renders danger', () => {
  const s = fixture(); s.safety = { obstacle_active: true }
  assert.equal(safetySummary(s).tone, 'danger')
})
test('raw obstacle overrides inconsistent clear safety', () => {
  const s = fixture(); s.safety = { state: 0, motion_allowed: true, obstacle_active: false, estop_active: false }; s.obstacle = { active: true }
  assert.equal(safetySummary(s).tone, 'danger')
})
test('stale safety never healthy', () => {
  const s = fixture(); s.meta.sources['/safety/state'].age_s = 4
  assert.equal(safetySummary(s).tone, 'warn')
})
test('QR false never exposes an old active payload', () => {
  const s = fixture(); s.qr = { detected: false, id: 'OLD' }
  assert.equal(qrActive(s), false)
  s.qr.detected = true; assert.equal(qrActive(s), true)
  s.meta.sources['/qr/detected'].age_s = 4; assert.equal(qrActive(s), false)
})
test('step commands clamp, repeat is ignored, and 20 Hz loop sends current targets', () => {
  const sent = []; let tick; let period
  const control = manualControl(() => true, msg => sent.push(msg), () => {}, {
    setInterval(fn, ms) { tick = fn; period = ms; return 1 }, clearInterval() {},
    setTimeout() { return 2 }, clearTimeout() {},
  })
  const press = (key, repeat = false) => control.keydown({ key, code: `Key${key.toUpperCase()}`, repeat, shiftKey: false, preventDefault() {} })
  control.start()
  press('w'); press('w', true); press('w'); press('w')
  assert.equal(control.targetLinear.value, 0.15)
  for (let i = 0; i < 10; i++) press('w')
  assert.equal(control.targetLinear.value, 0.25)
  press('s')
  assert.equal(control.targetLinear.value, 0.20)
  press('a'); press('a'); press('d')
  assert.equal(control.targetAngular.value, 0.1)
  tick()
  assert.equal(period, 50)
  assert.deepEqual(sent.at(-1), { linear: 0.20, angular: 0.1 })
  control.keydown({ key: ' ', code: 'Space', repeat: false, shiftKey: false, preventDefault() {} })
  assert.deepEqual(sent.at(-1), { linear: 0, angular: 0 })
  control.dispose()
})
test('fork shortcuts publish once and Shift+Space preserves movement', () => {
  let allowed = true; const sent = [], forks = []
  const control = manualControl(() => allowed, msg => sent.push(msg), action => forks.push(action), {
    setInterval() { return 1 }, clearInterval() {}, setTimeout() { return 2 }, clearTimeout() {},
  })
  const press = (code, repeat = false) => control.keydown({ key: code, code, repeat, shiftKey: true, preventDefault() {} })
  control.linear(1)
  press('ArrowUp'); press('ArrowUp', true); press('ArrowDown'); press('Space')
  assert.deepEqual(forks, ['up', 'down', 'stop'])
  assert.equal(control.targetLinear.value, 0.05)
  allowed = false; control.stop(); press('ArrowUp')
  assert.deepEqual(sent.at(-1), { linear: 0, angular: 0 })
  assert.deepEqual(forks, ['up', 'down', 'stop'])
  control.dispose()
})

test('mock demo remains explicit and can simulate mode/fork without transport', async () => {
  const { useMockData } = await import('../src/composables/useMockData.js')
  const mock = useMockData()
  try {
    mock.start()
    assert.equal(mock.state.value.meta.mode, 'mock')
    mock.handleCmd({ type: 'switch_mode', payload: 'manual' })
    assert.equal(mock.state.value.switch.mode, 'manual')
    const previous = mock.state.value.lift.height_pct
    mock.handleCmd({ type: 'lift', payload: { action: 'up' } })
    assert.equal(mock.state.value.lift.height_pct, previous + 10)
    mock.handleCmd({ type: 'lift', payload: { action: 'stop' } })
    assert.equal(mock.state.value.lift.moving, false)
  } finally { mock.stop() }
})
