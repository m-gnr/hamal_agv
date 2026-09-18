import test from 'node:test'
import assert from 'node:assert/strict'
import { createServer } from 'vite'
import { createSSRApp, h } from 'vue'
import { renderToString } from 'vue/server-renderer'
import { liveState } from '../src/composables/liveState.js'
import { createMapFeed } from '../src/composables/occupancyGrid.js'

let server, Panel, Header, PlcPanel, MockCamera
// Compile the actual Vue components; transports remain absent in render tests.
test.before(async () => {
  server = await createServer({ server: { middlewareMode: true, hmr: false }, appType: 'custom' })
  Panel = (await server.ssrLoadModule('/src/components/LivePanel.vue')).default
  Header = (await server.ssrLoadModule('/src/components/TopBar.vue')).default
  PlcPanel = (await server.ssrLoadModule('/src/components/PlcStatusPanel.vue')).default
  MockCamera = (await server.ssrLoadModule('/src/components/TabCamera.vue')).default
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
test('camera switch is directly below the stream in the active live and mock camera cards', async () => {
  const live = await render(Panel, { tab: 'camera', state: liveState(null, true, null), rosConnected: true, cameraIsBack: true })
  assert.ok(live.indexOf('camera-stream') < live.indexOf('camera-controls'))
  assert.match(live, /class="camera-controls"[\s\S]*?Kamera Değiştir · Kamera: Arka/)
  assert.doesNotMatch(live, /class="camera-switch"[^>]*disabled/)
  const mock = await render(MockCamera, { state: { sensors: {} }, cameraIsBack: false })
  assert.ok(mock.indexOf('camera-stream') < mock.indexOf('camera-controls'))
  assert.match(mock, /class="camera-controls"[\s\S]*?Kamera Değiştir · Kamera: Ön/)
})
test('header always renders BATARYA 77% independently of telemetry', async () => {
  for (const state of [
    liveState(null, false, null),
    { meta: { mode: 'live' }, battery: { percent: 5 } },
    { meta: { mode: 'mock' }, battery: { percent: 99 } },
  ]) {
    const html = await render(Header, { state })
    assert.match(html, /BATARYA<\/span>[\s\S]*?77%/)
    assert.doesNotMatch(html, /N\/A|5%|99%|100%/)
  }
  const disconnected = await render(Header, { state: liveState(null, false, null) })
  assert.match(disconnected, /Disconnected/)
  assert.doesNotMatch(disconnected, /MANUEL/)
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
test('live header shows fixed battery and session time independent of mission freshness', async () => {
  const state = liveState({ meta: { mode: 'live', ts: 100, sources: {} },
    host: { battery: { percent: 62, status: 'charging' }, session_elapsed_s: 3661 },
    mission: { elapsed_s: 12 } }, true, 1000, 1000)
  const html = await render(Header, { state })
  assert.match(html, /BATARYA/)
  assert.match(html, /77%/)
  assert.match(html, /01:01:01/)
  assert.doesNotMatch(html, /00:00:12|62%/)
})
test('mock header shows fixed battery and host session time', async () => {
  const html = await render(Header, { state: {
    meta: { mode: 'mock' }, battery: { percent: 92 },
    host: { session_elapsed_s: 5 },
  } })
  assert.match(html, /BATARYA/)
  assert.match(html, /77%/)
  assert.match(html, /00:00:05/)
  assert.doesNotMatch(html, /N\/A|92%|100%/)
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

test('PLC panel distinguishes ROS disconnect, PLC error, and connected telemetry', async () => {
  const plc = { connection_state: 2, transport: 'udp', active_task_id: 'plc-0004',
    rx_pickup: 1, rx_dropoff: 2, rx_control: 2, rx_age_sec: .3, tx_age_sec: .4,
    tx_status: 4, door_permission: false, last_rx: 'debug RX', last_tx: 'debug TX' }
  const mission = { state: 2, phase: 'MOVE_LOADED', task_id: 'plc-0004', pickup_id: 'A1', dropoff_id: 'B2' }
  let html = await render(PlcPanel, { plc, mission, rosConnected: true })
  assert.match(html, /Bağlı/)
  assert.match(html, /A1 → B2/)
  assert.match(html, /BAŞLA \/ DEVAM ET/)
  assert.match(html, /0\.3 sn/)
  assert.match(html, /0\.4 sn/)
  assert.match(html, /MOVE_LOADED/)
  assert.match(html, /<details/)
  plc.connection_state = 3
  plc.error_message = 'PLC UDP: bağlantı yok / RX timeout'
  html = await render(PlcPanel, { plc, mission, rosConnected: true })
  assert.match(html, /Bağlantı yok/)
  assert.match(html, /RX timeout/)
  html = await render(PlcPanel, { plc, mission, rosConnected: false })
  assert.match(html, /ROS bağlantısı yok/)
  assert.match(html, /Bilinmiyor \(ROS bağlantısı yok\)/)
})

test('PLC WAIT and door wait use structured fields, not debug strings or stale /ui/state', async () => {
  const plc = { connection_state: 2, transport: 'udp', active_task_id: 'plc-0005',
    rx_pickup: 1, rx_dropoff: 2, rx_control: 1, rx_age_sec: .2,
    last_rx: 'RX pu=3 do=3 ctrl=2', last_tx: 'TX st=7', tx_status: 5 }
  let html = await render(Panel, { tab: 'dashboard', state: liveState(null, true, null),
    rosConnected: true, plcState: plc, missionState: {
      state: 8, phase: 'MOVE_EMPTY', task_id: 'plc-0005', pickup_id: 'A1', dropoff_id: 'B2',
    } })
  assert.match(html, /PLC tarafından duraklatıldı/)
  assert.match(html, /BEKLE/)
  assert.match(html, /A1 → B2/)
  assert.match(html, /Son RX/)
  assert.doesNotMatch(html, /A3 → B3/)
  html = await render(PlcPanel, { plc, mission: { state: 3, phase: 'REQUEST_DOOR' }, rosConnected: true })
  assert.match(html, /PLC \/ kapı izni bekleniyor/)
  assert.match(html, /WAITING_PLC/)
})

test('UDP live mission is monitoring only; mock retains explicit direct mission test', async () => {
  const state = liveState(null, true, null)
  let html = await render(Panel, { tab: 'mission', state, rosConnected: true,
    plcState: { transport: 'udp', connection_state: 2 } })
  assert.match(html, /GUI yalnızca izler/)
  assert.doesNotMatch(html, />Başlat<|>Pause<|>Resume<|>Cancel</)
  html = await render(Panel, { tab: 'mission', state, rosConnected: true,
    plcState: { transport: 'mock', connection_state: 2 } })
  assert.match(html, />Başlat</)
  assert.match(html, /Doğrudan mission testi/)
})

test('PLC card follows connection and mission display priority', async () => {
  const plc = { connection_state: 2, transport: 'udp' }
  for (const [state, label] of [
    [7, 'Acil durdurma aktif'], [6, 'Mission hatası'],
    [5, 'Operatör tarafından duraklatıldı'], [4, 'Engel nedeniyle duraklatıldı'],
    [8, 'PLC tarafından duraklatıldı'], [3, 'PLC / kapı izni bekleniyor'],
  ]) {
    const html = await render(PlcPanel, { plc, mission: { state }, rosConnected: true })
    assert.ok(html.includes(label), `${state} must show ${label}`)
  }
  plc.connection_state = 3
  const error = await render(PlcPanel, { plc, mission: { state: 7 }, rosConnected: true })
  assert.match(error, /role="status"[^>]*>Bağlantı yok/)
  const disconnected = await render(PlcPanel, { plc, mission: { state: 7 }, rosConnected: false })
  assert.match(disconnected, /role="status"[^>]*>ROS bağlantısı yok/)
})
