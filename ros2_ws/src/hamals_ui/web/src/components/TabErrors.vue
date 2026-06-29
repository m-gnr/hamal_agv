<template>
  <div class="tab-errors">
    <div class="top-row">
      <!-- LiDAR radar -->
      <Card class="radar-card">
        <template #header><SectionTitle :icon="Radar">LiDAR Bölge Radarı</SectionTitle></template>
        <div class="radar-wrap">
          <canvas ref="radarCanvas" :width="200" :height="200" class="radar-canvas" />
          <div class="radar-zones">
            <div :class="['zone-lbl', 'zone-front', zoneCls('front')]">ÖN</div>
            <div :class="['zone-lbl', 'zone-back',  zoneCls('back')]">ARKA</div>
            <div :class="['zone-lbl', 'zone-left',  zoneCls('left')]">SOL</div>
            <div :class="['zone-lbl', 'zone-right', zoneCls('right')]">SAĞ</div>
          </div>
        </div>
        <div class="obstacle-row">
          <StatPill :variant="s.safety?.obstacle === 'danger' ? 'danger' : 'success'" :dot="true">
            {{ s.safety?.obstacle === 'danger' ? 'ENGEL!' : 'Temiz' }}
          </StatPill>
          <span class="obs-dist">{{ fmt(s.safety?.obstacle_distance_m) }} m</span>
        </div>
      </Card>

      <!-- System health -->
      <Card>
        <template #header><SectionTitle :icon="ShieldCheck">Sistem Sağlığı</SectionTitle></template>
        <div :class="['health-big', healthCls]">{{ HEALTH[s.safety?.system_health] || s.safety?.system_health }}</div>
        <LabelRow label="Acil Stop">
          <StatPill :variant="s.estop?.active ? 'danger' : 'success'" :dot="true">
            {{ s.estop?.active ? 'AKTİF' : 'Normal' }}
          </StatPill>
        </LabelRow>
        <LabelRow label="Engel Algılama">
          <StatPill :variant="s.safety?.obstacle === 'danger' ? 'danger' : 'success'">
            {{ s.safety?.obstacle === 'danger' ? 'Yakında' : 'Serbest' }}
          </StatPill>
        </LabelRow>
        <LabelRow label="Sistem Modu">
          <StatPill :variant="s.switch?.mode === 'auto' ? 'info' : 'warn'">
            {{ s.switch?.mode === 'auto' ? 'Otomatik' : 'Manuel' }}
          </StatPill>
        </LabelRow>
        <div v-if="s.estop?.active" class="estop-notice">
          <AlertTriangle :size="13" />
          Bağlantı kesildi — son bilinen durum gösteriliyor
        </div>
      </Card>

      <!-- Sensor health -->
      <Card>
        <template #header><SectionTitle :icon="Cpu">Sensör Durumu</SectionTitle></template>
        <div class="sensor-grid">
          <div v-for="[k, label] in SENSORS" :key="k" class="sensor-row">
            <span :class="['s-dot', s.sensors?.[k] ? 'dot-green' : 'dot-red']" />
            <span :class="['s-label', s.sensors?.[k] ? '' : 's-off']">{{ label }}</span>
            <span :class="['s-state', s.sensors?.[k] ? 'ok' : 'err']">{{ s.sensors?.[k] ? 'Aktif' : 'Pasif' }}</span>
          </div>
        </div>
      </Card>
    </div>

    <!-- ROS2 Node Status -->
    <Card class="nodes-card">
      <template #header>
        <div class="nodes-header">
          <SectionTitle :icon="Network">ROS2 Node Durumu</SectionTitle>
          <span :class="['nodes-summary', allNodesOk ? 'summary-ok' : 'summary-warn']">
            {{ activeNodeCount }}/{{ (s.nodes || []).length }} aktif
          </span>
        </div>
      </template>
      <div class="nodes-grid">
        <div v-for="node in (s.nodes || [])" :key="node.name" :class="['node-item', node.active ? 'node-ok' : 'node-off']">
          <span :class="['node-dot', node.active ? 'dot-green' : 'dot-off']" />
          <span class="node-name">{{ node.name }}</span>
          <span :class="['node-badge', node.active ? 'badge-ok' : 'badge-off']">
            {{ node.active ? 'Aktif' : 'Pasif' }}
          </span>
        </div>
        <div v-if="!s.nodes?.length" class="nodes-empty">Node verisi bekleniyor…</div>
      </div>
    </Card>

    <!-- Error list -->
    <Card>
      <template #header>
        <div class="err-header">
          <SectionTitle :icon="AlertTriangle">Hatalar</SectionTitle>
          <span :class="['err-count', (s.errors || []).length > 0 ? 'err-count-red' : 'err-count-ok']">
            {{ (s.errors || []).length }} hata
          </span>
        </div>
      </template>
      <div class="error-list">
        <div v-for="(e, i) in (s.errors || [])" :key="i" class="error-row">
          <span class="error-code">{{ e.code }}</span>
          <span class="error-ts">{{ e.ts }}</span>
          <span class="error-text">{{ e.text }}</span>
        </div>
        <div v-if="!s.errors?.length" class="no-errors">
          <CheckCircle2 :size="14" /> Hata yok
        </div>
      </div>
    </Card>

    <!-- Logs -->
    <Card class="log-card">
      <template #header>
        <div class="log-header">
          <SectionTitle :icon="ScrollText">Kayıtlar</SectionTitle>
          <button class="export-btn" @click="exportLogs">
            <Download :size="12" /> Dışa Aktar
          </button>
        </div>
      </template>
      <div class="log-list">
        <div v-for="(l, i) in (s.logs || []).slice(0, 30)" :key="i" class="log-row">
          <span class="log-ts">{{ l.ts }}</span>
          <span :class="['log-dir', l.dir === 'plc2robot' ? 'dir-plc' : 'dir-robot']">
            {{ l.dir === 'plc2robot' ? 'PLC' : 'ROBOT' }}
          </span>
          <span class="log-event">{{ l.event }}</span>
        </div>
        <div v-if="!s.logs?.length" class="empty-logs">Kayıt yok</div>
      </div>
    </Card>
  </div>
</template>

<script setup>
import { ref, watch, onMounted, computed } from 'vue'
import {
  Radar, ShieldCheck, Cpu, AlertTriangle, CheckCircle2, ScrollText, Download, Network,
} from 'lucide-vue-next'
import Card from './Card.vue'
import SectionTitle from './SectionTitle.vue'
import StatPill from './StatPill.vue'
import LabelRow from './LabelRow.vue'

const props = defineProps({ state: Object })
const s = computed(() => props.state || {})

const HEALTH = { normal: 'Normal', warn: 'Uyarı', error: 'Hata' }

const activeNodeCount = computed(() => (s.value.nodes || []).filter(n => n.active).length)
const allNodesOk = computed(() => (s.value.nodes || []).every(n => n.active))

const SENSORS = [
  ['lidar', 'LiDAR'], ['cam_front', 'Ön Kamera'],
  ['cam_back', 'Arka Kamera'], ['imu', 'IMU'], ['encoder', 'Enkoder'],
]

const healthCls = computed(() => {
  const h = s.value.safety?.system_health
  return h === 'error' ? 'health-red' : h === 'warn' ? 'health-amber' : 'health-green'
})

function zoneCls(zone) {
  return s.value.safety?.zones?.[zone] === 'danger' ? 'zone-danger' : 'zone-safe'
}

function fmt(v, d = 1) { return (v ?? 0).toFixed(d) }

function exportLogs() {
  const rows = (s.value.logs || [])
    .map(l => `${l.ts}\t${l.dir}\t${l.event}`)
    .join('\n')
  const blob = new Blob([rows], { type: 'text/plain' })
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = `hamals_logs_${Date.now()}.txt`
  a.click()
}

const radarCanvas = ref(null)

function drawRadar(state) {
  const cvs = radarCanvas.value
  if (!cvs) return
  const ctx = cvs.getContext('2d')
  const cx = 100, cy = 100, r = 80
  ctx.clearRect(0, 0, 200, 200)

  ctx.fillStyle = '#0e1521'
  ctx.beginPath()
  ctx.arc(cx, cy, r, 0, Math.PI * 2)
  ctx.fill()
  ctx.strokeStyle = '#1e2a3c'
  ctx.lineWidth = 1
  ctx.stroke()

  for (const fr of [0.33, 0.66, 1.0]) {
    ctx.beginPath()
    ctx.arc(cx, cy, r * fr, 0, Math.PI * 2)
    ctx.strokeStyle = '#1e2a3c'
    ctx.lineWidth = 1
    ctx.stroke()
  }
  // cross-lines
  ctx.beginPath()
  ctx.moveTo(cx - r, cy); ctx.lineTo(cx + r, cy)
  ctx.moveTo(cx, cy - r); ctx.lineTo(cx, cy + r)
  ctx.strokeStyle = '#1e2a3c'
  ctx.lineWidth = 0.5
  ctx.stroke()

  const zones = [
    { zone: 'front', startAngle: -Math.PI * 0.75, endAngle: -Math.PI * 0.25 },
    { zone: 'right', startAngle: -Math.PI * 0.25, endAngle:  Math.PI * 0.25 },
    { zone: 'back',  startAngle:  Math.PI * 0.25, endAngle:  Math.PI * 0.75 },
    { zone: 'left',  startAngle:  Math.PI * 0.75, endAngle:  Math.PI * 1.25 },
  ]

  for (const { zone, startAngle, endAngle } of zones) {
    const isDanger = state?.safety?.zones?.[zone] === 'danger'
    ctx.beginPath()
    ctx.moveTo(cx, cy)
    ctx.arc(cx, cy, r - 5, startAngle, endAngle)
    ctx.closePath()
    ctx.fillStyle = isDanger ? 'rgba(239,68,68,.22)' : 'rgba(34,197,94,.08)'
    ctx.fill()
    ctx.strokeStyle = isDanger ? '#ef4444' : '#22c55e'
    ctx.lineWidth = isDanger ? 2 : 1
    ctx.stroke()
  }

  // Robot dot (amber)
  ctx.fillStyle = '#f5a524'
  ctx.beginPath()
  ctx.arc(cx, cy, 9, 0, Math.PI * 2)
  ctx.fill()

  // Direction arrow
  const theta = ((state?.pose?.theta_deg || 0) * Math.PI) / 180
  ctx.beginPath()
  ctx.moveTo(cx + Math.cos(theta - Math.PI / 2) * 9, cy + Math.sin(theta - Math.PI / 2) * 9)
  ctx.lineTo(cx + Math.cos(theta - Math.PI / 2) * 22, cy + Math.sin(theta - Math.PI / 2) * 22)
  ctx.strokeStyle = '#fff'
  ctx.lineWidth = 2.5
  ctx.stroke()
}

onMounted(() => drawRadar(props.state))
watch(() => props.state, v => drawRadar(v), { deep: true })
</script>

<style scoped>
.tab-errors { display: flex; flex-direction: column; gap: 10px; height: 100%; overflow: hidden; }
.top-row { display: grid; grid-template-columns: 220px 1fr 1fr; gap: 10px; flex-shrink: 0; }

/* Radar */
.radar-card { display: flex; flex-direction: column; align-items: center; }
.radar-wrap { position: relative; }
.radar-canvas { display: block; }
.radar-zones { position: absolute; inset: 0; pointer-events: none; }
.zone-lbl { position: absolute; font-size: 10px; font-weight: 700; }
.zone-front { top: 4px;    left: 50%;  transform: translateX(-50%); }
.zone-back  { bottom: 4px; left: 50%;  transform: translateX(-50%); }
.zone-left  { left: 4px;   top: 50%;   transform: translateY(-50%); }
.zone-right { right: 4px;  top: 50%;   transform: translateY(-50%); }
.zone-safe   { color: var(--green); }
.zone-danger { color: var(--red); animation: pulse 1s infinite; }
.obstacle-row { display: flex; align-items: center; gap: 8px; margin-top: 8px; }
.obs-dist { font-size: 13px; font-weight: 700; color: var(--text-dim); font-variant-numeric: tabular-nums; }

/* Health */
.health-big { font-size: 24px; font-weight: 700; margin: 6px 0 12px; }
.health-green { color: var(--green); }
.health-amber { color: var(--amber); }
.health-red   { color: var(--red); animation: pulse .8s infinite; }
.estop-notice {
  display: flex; align-items: center; gap: 6px;
  margin-top: 10px; padding: 8px 12px;
  background: rgba(239,68,68,.1); border: 1px solid rgba(239,68,68,.35);
  border-radius: var(--radius-sm); font-size: 12px; color: var(--red);
}

/* Sensors */
.sensor-grid { display: flex; flex-direction: column; gap: 6px; }
.sensor-row  { display: flex; align-items: center; gap: 8px; font-size: 12px; }
.s-dot  { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.dot-green { background: var(--green); box-shadow: 0 0 5px var(--green); }
.dot-red   { background: var(--red); }
.s-label { flex: 1; }
.s-off   { color: var(--red); }
.s-state { font-size: 11px; font-weight: 700; }
.ok { color: var(--green); }
.err{ color: var(--red); }

/* Error list */
.err-header   { display: flex; align-items: center; justify-content: space-between; }
.err-count    { font-size: 12px; padding: 1px 10px; border-radius: 10px; font-weight: 700; }
.err-count-red{ background: rgba(239,68,68,.15); color: var(--red); }
.err-count-ok { background: rgba(34,197,94,.1);  color: var(--green); }
.error-list   { max-height: 100px; overflow-y: auto; display: flex; flex-direction: column; gap: 3px; }
.error-row    { display: flex; align-items: center; gap: 8px; font-size: 12px; padding: 3px 0; border-bottom: 1px solid var(--border); }
.error-code   { background: rgba(239,68,68,.15); color: var(--red); padding: 1px 6px; border-radius: 4px; font-size: 10px; font-weight: 700; flex-shrink: 0; }
.error-ts     { color: var(--text-dim); flex-shrink: 0; font-variant-numeric: tabular-nums; }
.error-text   { color: var(--text); }
.no-errors    { display: flex; align-items: center; gap: 6px; color: var(--green); font-size: 13px; padding: 6px 0; }

/* Nodes */
.nodes-card { flex-shrink: 0; }
.nodes-header { display: flex; align-items: center; justify-content: space-between; }
.nodes-summary { font-size: 12px; font-weight: 700; padding: 1px 10px; border-radius: 10px; }
.summary-ok   { background: rgba(34,197,94,.12);  color: var(--green); }
.summary-warn { background: rgba(245,165,36,.12); color: var(--amber); }
.nodes-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 6px; }
.node-item {
  display: flex; align-items: center; gap: 7px;
  padding: 5px 10px; border-radius: var(--radius-sm);
  background: var(--panel-2); border: 1px solid var(--border);
}
.node-ok  { border-color: rgba(34,197,94,.2); }
.node-off { border-color: rgba(239,68,68,.2); }
.node-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.dot-green{ background: var(--green); box-shadow: 0 0 5px var(--green); }
.dot-off  { background: rgba(125,138,160,.4); }
.node-name { flex: 1; font-size: 11px; color: var(--text); font-variant-numeric: tabular-nums; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.node-badge { font-size: 10px; font-weight: 700; padding: 1px 6px; border-radius: 6px; flex-shrink: 0; }
.badge-ok  { background: rgba(34,197,94,.1);  color: var(--green); }
.badge-off { background: rgba(125,138,160,.1); color: var(--text-dim); }
.nodes-empty { color: var(--text-dim); font-size: 12px; grid-column: 1/-1; padding: 4px 0; }

/* Logs */
.log-card   { flex: 1; min-height: 0; display: flex; flex-direction: column; overflow: hidden; }
.log-header { display: flex; align-items: center; justify-content: space-between; }
.export-btn {
  display: flex; align-items: center; gap: 5px;
  padding: 3px 10px; border-radius: 6px; border: 1px solid var(--border);
  background: var(--panel-2); color: var(--text-dim); font-size: 11px; cursor: pointer; font-family: inherit;
  transition: color .15s, border-color .15s;
}
.export-btn:hover { color: var(--text); border-color: var(--accent); }
.log-list  { flex: 1; overflow-y: auto; display: flex; flex-direction: column; gap: 2px; }
.log-row   { display: flex; align-items: center; gap: 6px; font-size: 11px; padding: 1px 0; }
.log-ts    { color: var(--text-dim); flex-shrink: 0; font-variant-numeric: tabular-nums; }
.log-dir   { flex-shrink: 0; padding: 0px 5px; border-radius: 8px; font-size: 9px; font-weight: 700; }
.dir-plc   { background: rgba(59,130,246,.12); color: var(--accent); }
.dir-robot { background: rgba(34,197,94,.12);  color: var(--green); }
.log-event { color: var(--text); }
.empty-logs{ color: var(--text-dim); font-size: 12px; padding: 4px 0; }
</style>
