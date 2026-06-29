<template>
  <div class="tab-camera">
    <!-- Main camera area: two cameras side by side -->
    <Card class="cam-main-card">
      <template #header>
        <div class="cam-card-header">
          <SectionTitle :icon="CameraIcon">Kamera Akışları</SectionTitle>
          <StatPill :variant="s.nav?.mode === 'line_follow' ? 'success' : 'info'">
            {{ s.nav?.mode === 'line_follow' ? 'Çizgi Takibi' : 'Nav2' }}
          </StatPill>
        </div>
      </template>
      <div class="cameras-grid">
        <!-- Front camera -->
        <div :class="['cam-panel', s.cameras?.active === 'front' ? 'cam-panel-active' : 'cam-panel-dim']">
          <div class="cam-panel-header">
            <span class="cam-label">ÖN KAMERA</span>
            <span v-if="s.cameras?.active === 'front'" class="cam-active-badge">AKTİF</span>
            <span :class="['cam-sensor-dot', s.sensors?.cam_front ? 'dot-green' : 'dot-red']" />
          </div>
          <div class="cam-stream-wrap">
            <img
              v-if="s.cameras?.front_url"
              :src="s.cameras.front_url"
              class="cam-stream"
              onerror="this.style.display='none'"
              alt="Ön kamera akışı"
            />
            <div v-else class="no-stream">
              <CameraOff :size="36" />
              <span>Ön kamera mevcut değil</span>
            </div>
          </div>
          <div class="cam-panel-footer">
            <StatPill :variant="s.sensors?.cam_front ? 'success' : 'danger'" :dot="true">
              {{ s.sensors?.cam_front ? 'Aktif' : 'Pasif' }}
            </StatPill>
          </div>
        </div>

        <!-- Back camera -->
        <div :class="['cam-panel', s.cameras?.active === 'back' ? 'cam-panel-active' : 'cam-panel-dim']">
          <div class="cam-panel-header">
            <span class="cam-label">ARKA KAMERA</span>
            <span v-if="s.cameras?.active === 'back'" class="cam-active-badge">AKTİF</span>
            <span :class="['cam-sensor-dot', s.sensors?.cam_back ? 'dot-green' : 'dot-red']" />
          </div>
          <div class="cam-stream-wrap">
            <img
              v-if="s.cameras?.back_url"
              :src="s.cameras.back_url"
              class="cam-stream"
              onerror="this.style.display='none'"
              alt="Arka kamera akışı"
            />
            <div v-else class="no-stream">
              <CameraOff :size="36" />
              <span>Arka kamera mevcut değil</span>
            </div>
          </div>
          <div class="cam-panel-footer">
            <StatPill :variant="s.sensors?.cam_back ? 'success' : 'danger'" :dot="true">
              {{ s.sensors?.cam_back ? 'Aktif' : 'Pasif' }}
            </StatPill>
          </div>
        </div>
      </div>
    </Card>

    <!-- Right column -->
    <div class="right-col">
      <!-- Line follower -->
      <Card>
        <template #header><SectionTitle :icon="ScanLine">Çizgi Takibi</SectionTitle></template>
        <div class="line-status-row">
          <StatPill :variant="s.line?.status === 'tracking' ? 'success' : 'danger'" :dot="true">
            {{ LINE_STATUS[s.line?.status] || s.line?.status || '—' }}
          </StatPill>
        </div>
        <LabelRow label="Algılandı">
          <span :class="s.line?.detected ? 'val-green' : 'val-red'">
            {{ s.line?.detected ? 'Evet' : 'Hayır' }}
          </span>
        </LabelRow>
        <LabelRow label="Merkez">{{ s.line?.center_px ?? '—' }} px</LabelRow>
        <LabelRow label="Sapma">
          <span :class="lineDevCls">{{ fmt(s.line?.deviation_cm) }} cm</span>
        </LabelRow>
        <div class="line-graph">
          <div class="graph-track">
            <div class="graph-center-line" />
            <div class="graph-robot-marker" :style="{ left: robotPos + '%' }" />
          </div>
          <div class="graph-axis">
            <span>-15</span><span>0</span><span>+15</span>
          </div>
        </div>
      </Card>

      <!-- QR -->
      <Card>
        <template #header><SectionTitle :icon="QrCode">QR Kodu</SectionTitle></template>
        <div class="qr-status-row">
          <StatPill :variant="qrVariant" :dot="true">{{ QR_STATUS[s.qr?.status] || s.qr?.status || '—' }}</StatPill>
        </div>
        <template v-if="s.qr?.id">
          <LabelRow label="ID">{{ s.qr.id }}</LabelRow>
          <LabelRow label="Mesafe">{{ fmt(s.qr.distance_m) }} m</LabelRow>
          <LabelRow label="Δx">{{ fmt(s.qr.x) }} m</LabelRow>
          <LabelRow label="Δy">{{ fmt(s.qr.y) }} m</LabelRow>
          <LabelRow label="Açı">{{ fmt(s.qr.angle_deg) }}°</LabelRow>
        </template>
        <div v-else class="empty-state">QR bekleniyor</div>
      </Card>

      <!-- Sensor chips -->
      <Card>
        <template #header><SectionTitle :icon="Cpu">Görüntü İşleme</SectionTitle></template>
        <div class="sensor-chips">
          <div v-for="[k, label] in CAMS" :key="k" :class="['sensor-chip', s.sensors?.[k] ? 'chip-ok' : 'chip-off']">
            <span :class="['chip-dot', s.sensors?.[k] ? 'dot-green' : 'dot-red']" />
            {{ label }}
          </div>
        </div>
        <div class="nav-row">
          <span class="nav-label">Nav Modu</span>
          <span :class="['nav-badge', s.nav?.mode === 'line_follow' ? 'badge-line' : 'badge-nav2']">
            {{ s.nav?.mode || '—' }}
          </span>
        </div>
      </Card>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import {
  Camera as CameraIcon, CameraOff, ScanLine, QrCode, Cpu,
} from 'lucide-vue-next'
import Card from './Card.vue'
import SectionTitle from './SectionTitle.vue'
import StatPill from './StatPill.vue'
import LabelRow from './LabelRow.vue'

const props = defineProps({ state: Object })
const s = computed(() => props.state || {})

const LINE_STATUS = { tracking: 'Takip Ediliyor', lost: 'Çizgi Kayboldu' }
const QR_STATUS   = { read: 'Okundu', searching: 'Aranıyor', none: 'Bekliyor' }
const CAMS = [['cam_front', 'Ön Kamera'], ['cam_back', 'Arka Kamera'], ['lidar', 'LiDAR']]

const qrVariant = computed(() => {
  const st = s.value.qr?.status
  return st === 'read' ? 'success' : st === 'searching' ? 'warn' : 'default'
})

const lineDevCls = computed(() => {
  const d = Math.abs(s.value.line?.deviation_cm || 0)
  return d > 10 ? 'val-red' : d > 6 ? 'val-amber' : ''
})

const robotPos = computed(() => {
  const px = s.value.line?.center_px || 0
  return Math.max(0, Math.min(100, ((px + 30) / 60) * 100))
})

function fmt(v, d = 2) { return (v ?? 0).toFixed(d) }
</script>

<style scoped>
.tab-camera {
  display: grid;
  grid-template-columns: 1fr 240px;
  gap: 10px;
  height: 100%;
  overflow: hidden;
}
.cam-main-card { display: flex; flex-direction: column; overflow: hidden; min-height: 0; }
.right-col { display: flex; flex-direction: column; gap: 10px; overflow-y: auto; min-width: 0; }

/* Camera card header */
.cam-card-header { display: flex; align-items: center; justify-content: space-between; }

/* Two cameras side by side */
.cameras-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

.cam-panel {
  display: flex;
  flex-direction: column;
  border-radius: var(--radius-sm);
  border: 2px solid var(--border);
  overflow: hidden;
  transition: border-color .2s;
  min-height: 0;
}
.cam-panel-active { border-color: var(--green); box-shadow: 0 0 10px rgba(34,197,94,.18); }
.cam-panel-dim    { opacity: .7; }

.cam-panel-header {
  display: flex; align-items: center; gap: 6px;
  padding: 5px 10px;
  background: var(--panel-2);
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}
.cam-label { font-size: 10px; font-weight: 700; color: var(--text-dim); text-transform: uppercase; letter-spacing: .5px; flex: 1; }
.cam-active-badge {
  font-size: 9px; font-weight: 700; padding: 1px 6px; border-radius: 8px;
  background: rgba(34,197,94,.15); color: var(--green); border: 1px solid rgba(34,197,94,.35);
}
.cam-sensor-dot { width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0; }
.dot-green { background: var(--green); box-shadow: 0 0 4px var(--green); }
.dot-red   { background: var(--red); }

.cam-stream-wrap {
  flex: 1; min-height: 0;
  background: var(--panel-2);
  display: flex; align-items: center; justify-content: center;
  overflow: hidden;
}
.cam-stream { max-width: 100%; max-height: 100%; display: block; }
.no-stream  { display: flex; flex-direction: column; align-items: center; gap: 8px; padding: 20px; color: var(--text-dim); font-size: 12px; text-align: center; }

.cam-panel-footer { padding: 5px 10px; background: var(--panel-2); border-top: 1px solid var(--border); flex-shrink: 0; }

/* Line graph */
.line-status-row { margin-bottom: 8px; }
.line-graph { margin-top: 12px; }
.graph-track {
  position: relative; height: 20px; background: var(--panel-2);
  border-radius: 4px; border: 1px solid var(--border);
}
.graph-center-line {
  position: absolute; left: 50%; top: 0; bottom: 0;
  width: 1px; background: var(--text-dim); transform: translateX(-50%);
}
.graph-robot-marker {
  position: absolute; top: 3px; bottom: 3px; width: 10px;
  background: var(--accent); border-radius: 3px; transform: translateX(-50%); transition: left .2s;
}
.graph-axis { display: flex; justify-content: space-between; font-size: 9px; color: var(--text-dim); margin-top: 3px; }

/* QR */
.qr-status-row { margin-bottom: 8px; }
.empty-state { font-size: 12px; color: var(--text-dim); padding: 4px 0; }

/* Value colors */
.val-green { color: var(--green) !important; font-weight: 700; }
.val-red   { color: var(--red)   !important; font-weight: 700; }
.val-amber { color: var(--amber) !important; font-weight: 700; }

/* Sensor chips */
.sensor-chips { display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 10px; }
.sensor-chip {
  display: flex; align-items: center; gap: 5px;
  padding: 3px 10px; border-radius: 10px; font-size: 11px; font-weight: 600; border: 1px solid;
}
.chip-ok  { background: rgba(34,197,94,.1);  color: var(--green); border-color: rgba(34,197,94,.3); }
.chip-off { background: rgba(239,68,68,.1);  color: var(--red);   border-color: rgba(239,68,68,.3); }
.chip-dot { width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0; }

/* Nav mode */
.nav-row  { display: flex; align-items: center; justify-content: space-between; }
.nav-label{ font-size: 12px; color: var(--text-dim); }
.nav-badge{ padding: 2px 8px; border-radius: 10px; font-size: 11px; font-weight: 700; }
.badge-nav2 { background: rgba(59,130,246,.15); color: var(--accent); }
.badge-line { background: rgba(34,197,94,.15);  color: var(--green); }
</style>
