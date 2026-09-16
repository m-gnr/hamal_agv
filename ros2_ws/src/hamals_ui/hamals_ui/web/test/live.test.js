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
test('hold publishes, release sends zero and ends stream', () => {
  const sent = []; let tick; let cleared = false
  const control = manualControl(() => true, msg => sent.push(msg), {
    setInterval(fn) { tick = fn; return 1 }, clearInterval() { cleared = true },
  })
  control.start(0.1, 0); tick(); control.stop()
  assert.deepEqual(sent.at(-1), { linear: 0, angular: 0 }); assert.equal(cleared, true)
})
test('mode loss stops hold without publishing even zero into AUTO', () => {
  let allowed = true; let tick; const sent = []; let cleared = false
  const control = manualControl(() => allowed, msg => sent.push(msg), {
    setInterval(fn) { tick = fn; return 1 }, clearInterval() { cleared = true },
  })
  control.start(0.1, 0); const count = sent.length; allowed = false; tick(); control.stop(); control.start(0.1, 0)
  assert.equal(sent.length, count); assert.equal(cleared, true)
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
  } finally { mock.stop() }
})
