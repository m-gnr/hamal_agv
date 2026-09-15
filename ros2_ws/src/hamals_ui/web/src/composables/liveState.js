// Canonical live contract: null/absent = unknown, age is never inferred from values.
export const STATE_TIMEOUT_MS = 2000
export const MODE_TIMEOUT_S = 1
export function liveState(raw, connected, receivedAt, now = Date.now()) {
  const ageMs = receivedAt == null ? Infinity : Math.max(0, now - receivedAt)
  const accepted = raw?.meta?.mode === 'live'
  return {
    ...(accepted ? raw : {}),
    meta: { ...(accepted ? raw.meta : {}), mode: 'live', ageMs,
      stale: !connected || !accepted || ageMs >= STATE_TIMEOUT_MS,
      mismatch: raw != null && !accepted },
    connection: { ...(accepted ? raw.connection : {}), rosbridge: connected },
  }
}
export function freshness(state, topic, timeout = 3) {
  if (!state?.connection?.rosbridge) return 'disconnected'
  if (state?.meta?.stale) return 'stale'
  const age = state?.meta?.sources?.[topic]?.age_s
  if (age == null || !Number.isFinite(age)) return 'unknown'
  return age + state.meta.ageMs / 1000 < timeout ? 'live' : 'stale'
}
export function manualAllowed(state) {
  return state?.switch?.mode === 'manual' && freshness(state, '/switch/mode', MODE_TIMEOUT_S) === 'live'
}
export function safetySummary(state) {
  const health = freshness(state, '/safety/state')
  if (health !== 'live') return { label: health, tone: health === 'stale' ? 'warn' : 'unknown' }
  const s = state.safety || {}
  if (s.estop_active === true) return { label: 'E-STOP aktif', tone: 'danger' }
  if (s.obstacle_active === true) return { label: 'Engel', tone: 'danger' }
  // A fresh obstacle detector may contradict safety: never render clear then.
  const obstacleFresh = freshness(state, '/scan/obstacle_state')
  if (obstacleFresh === 'live' && state.obstacle?.active === true) return { label: 'Engel', tone: 'danger' }
  if (s.state === 0 && s.motion_allowed === true && s.obstacle_active === false && s.estop_active === false && obstacleFresh === 'live' && state.obstacle?.active === false) {
    return { label: 'Hareket izni var', tone: 'healthy' }
  }
  return { label: s.reason || 'unknown', tone: s.state === 4 ? 'warn' : 'unknown' }
}
export function qrActive(state) {
  return freshness(state, '/qr/detection') === 'live' && state.qr?.detected === true
}
