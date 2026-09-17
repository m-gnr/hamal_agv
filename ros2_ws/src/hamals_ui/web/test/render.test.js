import test from 'node:test'
import assert from 'node:assert/strict'
import { createServer } from 'vite'
import { createSSRApp, h } from 'vue'
import { renderToString } from 'vue/server-renderer'
import { liveState } from '../src/composables/liveState.js'
import { createMapFeed } from '../src/composables/occupancyGrid.js'

let server, Panel, Header
// Compile the actual Vue components; transports remain absent in render tests.
test.before(async () => {
  server = await createServer({ server: { middlewareMode: true, hmr: false }, appType: 'custom' })
  Panel = (await server.ssrLoadModule('/src/components/LivePanel.vue')).default
  Header = (await server.ssrLoadModule('/src/components/TopBar.vue')).default
})
test.after(async () => { await server?.close() })
const render = (component, props) => renderToString(createSSRApp({ render: () => h(component, component === Panel ? { mapFeed: createMapFeed(), ...props } : props) }))
for (const tab of ['dashboard', 'map', 'mission', 'manual', 'camera', 'errors', 'settings']) {
  test(`live ${tab} renders without telemetry and no fake battery`, async () => {
    const html = await render(Panel, { tab, state: liveState(null, false, null) })
    if (tab !== 'manual') assert.match(html, /Disconnected|DISCONNECTED/)
    assert.doesNotMatch(html, /100%|24V|Temiz|class="healthy"/)
    if (tab === 'manual') assert.match(html, /Manuel Kontrol Kilitli/)
    if (tab === 'camera') assert.match(html, /Camera unavailable/)
  })
}
test('live header renders N/A and unknown mode without MANUEL fallback', async () => {
  const html = await render(Header, { state: liveState(null, false, null) })
  assert.match(html, /N\/A/); assert.match(html, /Disconnected/)
  assert.doesNotMatch(html, /MANUEL|100%/)
})
test('map save button follows connection and /map, independent of stale state', async () => {
  const state = liveState(null, true, null)
  let html = await render(Panel, { tab: 'map', state, mapConnected: true, mapReady: false })
  assert.match(html, /Kaydedilecek harita yok/)
  assert.match(html, /disabled[^>]*>Haritayı Kaydet/)
  html = await render(Panel, { tab: 'map', state, mapConnected: true, mapReady: true })
  assert.match(html, /Haritayı Kaydet/)
  assert.doesNotMatch(html, /disabled[^>]*>Haritayı Kaydet/)
  html = await render(Panel, { tab: 'map', state, mapConnected: true, mapReady: true, savePending: true })
  assert.match(html, /Kaydediliyor\.\.\./)
  assert.match(html, /disabled[^>]*>Kaydediliyor/)
  html = await render(Panel, { tab: 'map', state, mapConnected: false, mapReady: true,
    saveResult: { success: false, message: 'disk full' } })
  assert.match(html, /Harita kaydedilemedi: disk full/)
  assert.match(html, /ROS bağlantısı yok/)
})
test('manual screen and physical mode label stay available without /ui/state', async () => {
  const state = liveState(null, true, null)
  const panel = await render(Panel, { tab: 'manual', state, physicalMode: 'manual' })
  const header = await render(Header, { state, physicalMode: 'manual' })
  assert.doesNotMatch(panel, /Manuel Kontrol Kilitli|Stale: yeni canlı veri bekleniyor/)
  assert.match(panel, /Klavye Kısayolları/)
  assert.match(panel, /class="dpad-btn dpad-up"[^>]*>/)
  assert.doesNotMatch(panel, /class="dpad-btn dpad-up" disabled/)
  assert.match(header, /MOD · FİZİKSEL/)
  assert.match(header, /manual/)
  const locked = await render(Panel, { tab: 'manual', state, physicalMode: 'auto' })
  assert.match(locked, /Manuel Kontrol Kilitli/)
  assert.match(locked, /AUTO/)
  assert.match(locked, /class="dpad-btn dpad-up" disabled/)
})
test('actual safety panel renders boolean obstacle as ENGEL', async () => {
  const state = liveState({ meta: { mode: 'live', ts: 100, sources: {
    '/safety/state': { age_s: 0 }, '/scan/obstacle_state': { age_s: 0 },
  } }, safety: { obstacle_active: true }, obstacle: { active: true, regions: [{ region: 'front', has_obstacle: true, min_distance: 0.3 }] } }, true, 1000, 1000)
  const html = await render(Panel, { tab: 'errors', state })
  assert.match(html, /ENGEL/); assert.match(html, /class="danger"/)
  assert.doesNotMatch(html, /Temiz|class="healthy"/)
})

test('single compressed camera and split QR topics render live without raw camera or QrDetection', async () => {
  const state = liveState({ meta: { mode: 'live', sources: {
    '/camera/image_raw/compressed': { age_s: 0 },
    '/qr/detected': { age_s: 0 }, '/qr/text': { age_s: 0 },
    '/line/detected': { age_s: 0 }, '/line/error': { age_s: 0 },
  } }, cameras: { topic: '/camera/image_raw/compressed',
    stream_url: 'http://localhost:8081/stream?topic=/camera/image_raw&default_transport=compressed&qos_profile=sensor_data' },
    qr: { detected: true, id: 'PALLET-42' }, line: { detected: true, error_px: -12 },
  }, true, 1000, 1000)
  const html = await render(Panel, { tab: 'camera', state })
  assert.match(html, /PALLET-42/)
  assert.match(html, /-12/)
  assert.match(html, /default_transport=compressed/)
  assert.match(html, /Kamera · \/camera\/image_raw\/compressed/)
  assert.equal((html.match(/<img /g) || []).length, 1)
  assert.doesNotMatch(html, /ÖN KAMERA|ARKA KAMERA/)
  state.meta.sources['/qr/text'].age_s = 5
  const stale = await render(Panel, { tab: 'camera', state })
  assert.doesNotMatch(stale, /PALLET-42/)
})
