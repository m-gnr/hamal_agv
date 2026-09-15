import test from 'node:test'
import assert from 'node:assert/strict'
import { createServer } from 'vite'
import { createSSRApp, h } from 'vue'
import { renderToString } from 'vue/server-renderer'
import { liveState } from '../src/composables/liveState.js'

let server, Panel, Header
// Compile the actual Vue components; transports remain absent in render tests.
test.before(async () => {
  server = await createServer({ server: { middlewareMode: true, hmr: false }, appType: 'custom' })
  Panel = (await server.ssrLoadModule('/src/components/LivePanel.vue')).default
  Header = (await server.ssrLoadModule('/src/components/TopBar.vue')).default
})
test.after(async () => { await server?.close() })
const render = (component, props) => renderToString(createSSRApp({ render: () => h(component, props) }))
for (const tab of ['dashboard', 'map', 'mission', 'manual', 'camera', 'errors', 'settings']) {
  test(`live ${tab} renders without telemetry and no fake battery`, async () => {
    const html = await render(Panel, { tab, state: liveState(null, false, null) })
    assert.match(html, /Disconnected/)
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
test('actual safety panel renders boolean obstacle as ENGEL', async () => {
  const state = liveState({ meta: { mode: 'live', ts: 100, sources: {
    '/safety/state': { age_s: 0 }, '/scan/obstacle_state': { age_s: 0 },
  } }, safety: { obstacle_active: true }, obstacle: { active: true, regions: [{ region: 'front', has_obstacle: true, min_distance: 0.3 }] } }, true, 1000, 1000)
  const html = await render(Panel, { tab: 'errors', state })
  assert.match(html, /ENGEL/); assert.match(html, /class="danger"/)
  assert.doesNotMatch(html, /Temiz|class="healthy"/)
})
