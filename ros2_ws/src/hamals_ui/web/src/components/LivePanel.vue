<template>
  <div class="live-panel">
    <div v-if="state.meta.stale && tab !== 'manual' && tab !== 'map'" class="notice warn">
      {{ state.connection.rosbridge ? 'Diğer kartlar: /ui/state bayat (PLC doğrudan izlenir)' : 'Disconnected: ROS bağlantısı yok' }}
      · Son /ui/state yaşı: {{ Number.isFinite(state.meta.ageMs) ? (state.meta.ageMs / 1000).toFixed(1) + ' s' : 'unknown' }}
    </div>
    <div v-if="state.meta.mismatch && tab !== 'manual'" class="notice danger">Mock backend reddedildi. Köprüyü mode:=live ile başlatın.</div>
    <TabManual v-if="tab === 'manual'" :state="state" :physical-mode="physicalMode" :is-mock="false" @send-cmd="emit('send-cmd', $event)" />
    <div v-else class="live-grid">
      <Card v-if="show('dashboard', 'errors')">
        <template #header><SectionTitle>Güvenlik</SectionTitle></template>
        <h3 :class="summary.tone">{{ summary.label }}</h3>
        <p>Safety: {{ health('/safety/state') }} · Obstacle: {{ health('/scan/obstacle_state') }}</p>
        <dl>
          <dt>Fiziksel E-STOP status</dt><dd>{{ value('/estop', state.estop?.active) }}</dd>
          <dt>Safety E-STOP</dt><dd>{{ value('/safety/state', state.safety?.estop_active) }}</dd>
          <dt>Hareket izni</dt><dd>{{ value('/safety/state', state.safety?.motion_allowed) }}</dd>
          <dt>Engel (safety)</dt><dd :class="state.safety?.obstacle_active === true && health('/safety/state') === 'live' ? 'danger' : ''">{{ value('/safety/state', state.safety?.obstacle_active) }}</dd>
          <dt>Sebep</dt><dd>{{ value('/safety/state', state.safety?.reason) }}</dd>
        </dl>
        <div v-if="health('/scan/obstacle_state') === 'live'">
          <p v-if="!state.obstacle?.regions?.length">Engel bölgeleri: unknown</p>
          <p v-for="region in state.obstacle?.regions" :key="region.region" :class="region.has_obstacle ? 'danger' : ''">
            {{ region.region }}: {{ region.has_obstacle ? 'ENGEL' : 'Algılanmadı' }} · {{ region.min_distance ?? 'unknown' }} m
          </p>
        </div>
        <p class="warn">Physical E-STOP only. Mevcut firmware E-STOP feedback değerini sabit false gönderiyor; bu değer fiziksel güvenlik teyidi değildir.</p>
      </Card>

      <Card v-if="show('dashboard', 'mission')">
        <template #header><SectionTitle>Görev · {{ health('/mission/state') }}</SectionTitle></template>
        <dl>
          <template v-for="key in ['fsm', 'phase', 'task_id', 'pickup_id', 'dropoff_id', 'active_target', 'carrying_load', 'message', 'elapsed_s', 'pause_reason', 'error_code']" :key="key">
            <dt>{{ key }}</dt><dd>{{ value('/mission/state', state.mission?.[key]) }}</dd>
          </template>
        </dl>
        <form v-if="tab === 'mission' && plcState?.transport === 'mock'" @submit.prevent="command('start_mission', task)">
          <label>Task ID<input v-model.trim="task.task_id" required></label>
          <label>Pickup ID<input v-model.trim="task.pickup_id" required placeholder="World model istasyon ID"></label>
          <label>Dropoff ID<input v-model.trim="task.dropoff_id" required placeholder="World model istasyon ID"></label>
          <button :disabled="!canStart">Başlat</button>
          <p>Doğrudan mission testi; PLC WAIT/START protokol testi değildir. İstasyonlar mission server tarafından doğrulanır.</p>
        </form>
        <div v-if="tab === 'mission' && plcState?.transport === 'mock'" class="buttons">
          <button :disabled="!available('pause_mission')" @click="command('pause_mission', { reason: 'operator pause' })">Pause</button>
          <button :disabled="!available('resume_mission')" @click="command('resume_mission', { operator_id: 'ui' })">Resume</button>
          <button :disabled="!available('cancel_mission')" @click="command('cancel_mission')">Cancel</button>
        </div>
        <p v-if="tab === 'mission' && plcState?.transport === 'mock'">Cancel yalnız bu köprüden başlatılmış action goal için kullanılabilir.</p>
        <p v-if="tab === 'mission' && plcState?.transport === 'udp'">UDP modunda görev komutları PLC yetkisindedir; GUI yalnızca izler.</p>
        <p v-if="state.command_result" :class="state.meta.stale ? 'warn' : ''">Son komut yanıtı: {{ state.command_result.command }} · {{ state.command_result.status }} · {{ state.command_result.message }}</p>
      </Card>

      <PlcStatusPanel v-if="show('dashboard', 'mission', 'settings')" :plc="plcState" :mission="missionState" :ros-connected="rosConnected" />

      <Card v-if="show('dashboard', 'map')" :class="['map-card', { 'map-card-full': tab === 'map' }]">
        <div v-if="tab === 'map'" class="map-toolbar">
          <strong>Harita &amp; Rota</strong>
          <button :disabled="!mapConnected || !mapReady || savePending"
                  :title="!mapConnected ? 'ROS bağlantısı yok' : !mapReady ? 'Kaydedilecek harita yok' : ''"
                  @click="emit('save-map')">{{ savePending ? 'Kaydediliyor...' : 'Haritayı Kaydet' }}</button>
        </div>
        <p v-if="tab === 'map' && saveResult" role="status" :class="saveResult.success ? 'healthy' : 'danger'">
          {{ saveResult.success ? 'Harita kaydedildi' : `Harita kaydedilemedi: ${saveResult.message}` }}
        </p>
        <MapViewer :feed="mapFeed" :connected="mapConnected" />
        <dl>
          <dt>Pose frame</dt><dd>{{ value('/odom', state.pose?.frame_id) }} → {{ value('/odom', state.pose?.child_frame_id) }}</dd>
          <dt>Konum (m)</dt><dd>{{ value('/odom', state.pose?.x) }}, {{ value('/odom', state.pose?.y) }}</dd>
          <dt>Yaw (°)</dt><dd>{{ value('/odom', state.pose?.theta_deg) }}</dd>
          <dt>Hız (m/s)</dt><dd>{{ value('/odom', state.pose?.speed) }}</dd>
          <dt>Navigation (mission phase)</dt><dd>{{ value('/mission/state', state.nav?.status) }}</dd>
          <dt>Hedef</dt><dd>{{ value('/mission/state', state.nav?.current_goal) }}</dd>
        </dl>
      </Card>

      <Card v-if="show('dashboard', 'camera')">
        <template #header><SectionTitle>Kamera · {{ cameraTopic }}</SectionTitle></template>
        <CameraStream :url="state.cameras?.stream_url" :fresh="health(cameraTopic) === 'live'" />
        <div class="camera-controls">
          <p>{{ health(cameraTopic) }}</p>
          <button v-if="tab === 'camera'" class="camera-switch" type="button" :disabled="!rosConnected" @click="emit('switch-camera')">
            Kamera Değiştir · Kamera: {{ cameraIsBack ? 'Arka' : 'Ön' }}
          </button>
        </div>
      </Card>
      <Card v-if="show('dashboard', 'camera')">
        <template #header><SectionTitle>QR / Çizgi</SectionTitle></template>
        <dl>
          <dt>QR detected</dt><dd>{{ value('/qr/detected', state.qr?.detected) }}</dd>
          <dt>Aktif QR</dt><dd>{{ qrActive(state) ? value('/qr/text', state.qr?.id) : '—' }}</dd>
          <dt>QR x / y / z (m)</dt><dd>unknown · bu kaynak yayınlamıyor</dd>
          <dt>Çizgi detected</dt><dd>{{ value('/line/detected', state.line?.detected) }}</dd>
          <dt>Çizgi hatası (px)</dt><dd>{{ health('/line/detected') === 'live' && state.line?.detected === true ? value('/line/error', state.line?.error_px) : '—' }}</dd>
        </dl>
      </Card>
      <Card v-if="show('dashboard', 'settings', 'errors')">
        <template #header><SectionTitle>Kaynaklar / bağlantı</SectionTitle></template>
        <dl>
          <template v-for="(source, topic) in state.meta.sources" :key="topic">
            <dt>{{ topic }}</dt><dd :class="health(topic) === 'stale' ? 'warn' : ''">{{ health(topic, topic === '/switch/mode' ? 1 : 3) }} · {{ source.age_s == null ? 'unknown' : (source.age_s + state.meta.ageMs / 1000).toFixed(1) + ' s' }}</dd>
          </template>
        </dl>
        <p>Batarya: N/A — repo içinde gerçek yayıncı yok.</p>
        <p v-for="n in state.nodes" :key="n.name">{{ n.name }}: {{ state.meta.stale ? 'stale' : n.active == null ? 'unknown' : n.active ? 'ROS graph üzerinde' : 'ROS graph üzerinde yok' }}</p>
      </Card>
    </div>
  </div>
</template>
<script setup>
import { computed, reactive } from 'vue'
import Card from './Card.vue'
import SectionTitle from './SectionTitle.vue'
import TabManual from './TabManual.vue'
import CameraStream from './CameraStream.vue'
import MapViewer from './MapViewer.vue'
import PlcStatusPanel from './PlcStatusPanel.vue'
import { freshness, qrActive, safetySummary } from '../composables/liveState.js'
const props = defineProps({ state: { type: Object, required: true }, plcState: Object, missionState: Object, rosConnected: Boolean, cameraIsBack: Boolean, tab: String, physicalMode: { type: String, default: 'unknown' }, mapFeed: { type: Object, required: true }, mapConnected: Boolean, mapReady: Boolean, savePending: Boolean, saveResult: Object })
const emit = defineEmits(['send-cmd', 'save-map', 'switch-camera'])
const cameraTopic = computed(() => props.state.cameras?.topic || '/camera/image_raw/compressed')
const task = reactive({ task_id: '', pickup_id: '', dropoff_id: '' })
const show = (...tabs) => tabs.includes(props.tab)
const health = (topic, timeout) => freshness(props.state, topic, timeout)
function value(topic, val) {
  const status = health(topic)
  if (status !== 'live') return status
  if (val == null) return 'unknown'
  if (typeof val === 'number') return Number.isInteger(val) ? val : val.toFixed(3)
  if (val === true) return 'true'
  if (val === false) return 'false'
  return val === '' ? '—' : val
}
const summary = computed(() => safetySummary(props.state))
const available = type => !props.state.meta.stale && props.state.controls?.[type] === true
const canStart = computed(() => available('start_mission') && health('/switch/mode', 1) === 'live' && props.state.switch?.mode === 'auto' && Object.values(task).every(Boolean))
function command(type, payload = {}) { emit('send-cmd', { type, payload: { ...payload } }) }
</script>
<style scoped>
.live-panel { height: 100%; overflow: auto; color: var(--text-dim); }
.live-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(340px, 1fr)); gap: 12px; padding-bottom: 16px; }
.notice { padding: 12px; border: 1px solid currentColor; margin-bottom: 12px; border-radius: 8px; }
p { font-size: 12px; line-height: 1.6; overflow-wrap: anywhere; margin: 10px 0; }
h3 { margin: 12px 0; }
dl { display: grid; grid-template-columns: minmax(110px, 1fr) minmax(100px, 1fr); gap: 8px; font-size: 12px; }
dt, dd { margin: 0; overflow-wrap: anywhere; }
dd { color: var(--text); }
.healthy { color: var(--green); }.warn { color: var(--amber); }.danger { color: var(--red); }.unknown { color: var(--text-dim); }
.map-card-full { grid-column: 1 / -1; }
.map-toolbar { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 8px; }
.map-toolbar strong { color: var(--text); font-size: 14px; }
.map-card-full :deep(.map-viewer) { height: min(68vh, 720px); }
form { margin-top: 18px; display: grid; gap: 8px; }
label { display: grid; gap: 5px; font-size: 12px; }
input, button { border: 1px solid var(--border); border-radius: 6px; padding: 9px; background: var(--panel-2); color: var(--text); font: inherit; }
button { cursor: pointer; }button:disabled { opacity: .4; cursor: not-allowed; }.buttons { display: flex; gap: 8px; margin-top: 12px; }
.camera-controls { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-top: 10px; }
.camera-controls p { margin: 0; }
.camera-switch { border-color: var(--accent); background: rgba(59,130,246,.15); white-space: nowrap; }
.camera-switch:hover:not(:disabled) { background: rgba(59,130,246,.25); }
</style>
