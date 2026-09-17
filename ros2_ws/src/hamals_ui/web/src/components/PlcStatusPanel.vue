<template>
  <Card :variant="tone">
    <template #header><SectionTitle>PLC</SectionTitle></template>
    <div class="plc-head">
      <span :class="['indicator', tone]" aria-hidden="true" />
      <strong :class="tone" role="status">{{ headline }}</strong>
    </div>
    <dl>
      <dt>Bağlantı</dt><dd>{{ connectionLabel }}</dd>
      <dt>Transport</dt><dd>{{ transportLabel }}</dd>
      <dt>Görev</dt><dd>{{ taskRoute }}</dd>
      <dt>Task</dt><dd>{{ plc?.active_task_id || '—' }}</dd>
      <dt>Son RX görevi</dt><dd>{{ rxRoute }}</dd>
      <dt>PLC Komutu</dt><dd>{{ controlLabel }}</dd>
      <dt>Mission</dt><dd>{{ missionLabel }}</dd>
      <dt>Phase</dt><dd>{{ mission?.phase || '—' }}</dd>
      <dt>Kapı izni</dt><dd>{{ plc ? (plc.door_permission ? 'Aktif' : 'Pasif') : '—' }}</dd>
      <dt>Son RX</dt><dd>{{ ageLabel(plc?.rx_age_sec) }}</dd>
      <dt>Son TX</dt><dd>{{ ageLabel(plc?.tx_age_sec) }}</dd>
      <dt>TX status</dt><dd>{{ plc?.tx_status ?? '—' }}</dd>
    </dl>
    <p v-if="rosConnected && plc?.error_message" class="error-message">{{ plc.error_message }}</p>
    <details v-if="plc?.last_rx || plc?.last_tx" class="debug-details">
      <summary>Detaylar</summary>
      <p>RX: {{ plc.last_rx || '—' }}</p>
      <p>TX: {{ plc.last_tx || '—' }}</p>
    </details>
  </Card>
</template>

<script setup>
import { computed } from 'vue'
import Card from './Card.vue'
import SectionTitle from './SectionTitle.vue'

const props = defineProps({ plc: Object, mission: Object, rosConnected: Boolean })
const missionNames = {
  0: 'BOOTING', 1: 'IDLE', 2: 'EXECUTING', 3: 'WAITING_PLC',
  4: 'PAUSED_OBSTACLE', 5: 'PAUSED_MANUAL', 6: 'ERROR',
  7: 'EMERGENCY_STOP', 8: 'PAUSED_PLC',
}
const missionDescriptions = {
  7: 'Acil durdurma aktif', 6: 'Mission hatası',
  5: 'Operatör tarafından duraklatıldı', 4: 'Engel nedeniyle duraklatıldı',
  8: 'PLC tarafından duraklatıldı', 3: 'PLC / kapı izni bekleniyor',
}
const missionLabel = computed(() => missionNames[props.mission?.state] || '—')
const transportLabel = computed(() => props.plc?.transport?.toUpperCase() || '—')
const connectionLabel = computed(() => {
  if (!props.rosConnected) return 'Bilinmiyor (ROS bağlantısı yok)'
  if (!props.plc) return 'Veri bekleniyor'
  return ({ 0: 'Bağlantı yok', 1: 'Bağlanıyor', 2: 'Bağlı', 3: 'Bağlantı yok' })[props.plc.connection_state] || 'Bilinmiyor'
})
const controlLabel = computed(() => {
  if (!props.rosConnected || !props.plc) return '—'
  return ({ 1: 'BEKLE', 2: 'BAŞLA / DEVAM ET' })[props.plc.rx_control] || 'Bilinmiyor'
})
const taskRoute = computed(() => {
  if (!props.plc?.active_task_id || props.mission?.task_id !== props.plc.active_task_id) return '—'
  if (!props.mission.pickup_id || !props.mission.dropoff_id) return '—'
  return `${props.mission.pickup_id} → ${props.mission.dropoff_id}`
})
const rxRoute = computed(() => {
  if (!props.rosConnected || !props.plc?.rx_pickup || !props.plc?.rx_dropoff) return '—'
  return `A${props.plc.rx_pickup} → B${props.plc.rx_dropoff}`
})
const headline = computed(() => {
  if (!props.rosConnected) return 'ROS bağlantısı yok'
  if (!props.plc) return 'PLC verisi bekleniyor'
  if (props.plc.connection_state === 3 || props.plc.connection_state === 0) return 'Bağlantı yok'
  if (props.plc.connection_state !== 2) return 'PLC bağlanıyor'
  return missionDescriptions[props.mission?.state] || 'Bağlı'
})
const tone = computed(() => {
  if (!props.rosConnected) return 'danger'
  if (!props.plc || props.plc.connection_state === 1) return 'warn'
  if (props.plc.connection_state !== 2) return 'danger'
  if ([6, 7].includes(props.mission?.state)) return 'danger'
  if ([3, 4, 5, 8].includes(props.mission?.state)) return 'warn'
  return 'success'
})
function ageLabel(age) {
  return Number.isFinite(age) && age >= 0 ? `${age.toFixed(1)} sn` : '—'
}
</script>

<style scoped>
.plc-head { display: flex; align-items: center; gap: 9px; margin-bottom: 12px; }
.plc-head strong { font-size: 15px; }
.indicator { width: 9px; height: 9px; border-radius: 50%; flex: none; background: currentColor; }
.success { color: var(--green); }.warn { color: var(--amber); }.danger { color: var(--red); }
dl { display: grid; grid-template-columns: minmax(100px, 1fr) minmax(120px, 1fr); gap: 8px; font-size: 12px; }
dt, dd { margin: 0; overflow-wrap: anywhere; }
dt { color: var(--text-dim); } dd { color: var(--text); }
.error-message { margin-top: 12px; color: var(--red); font-size: 12px; overflow-wrap: anywhere; }
.debug-details { margin-top: 14px; border-top: 1px solid var(--border); padding-top: 8px; color: var(--text-dim); font-size: 11px; }
.debug-details summary { cursor: pointer; }
.debug-details p { overflow-wrap: anywhere; margin-top: 5px; }
@media (max-width: 600px) { dl { grid-template-columns: minmax(84px, .8fr) minmax(0, 1.2fr); } }
</style>
