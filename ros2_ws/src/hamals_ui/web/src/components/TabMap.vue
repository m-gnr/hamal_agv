<template>
  <div class="tab-map">
    <Card class="map-main-card">
      <template #header>
        <div class="map-card-header">
          <SectionTitle :icon="MapIcon">Harita &amp; Rota</SectionTitle>
          <div class="header-right">
            <span :class="['nav-pill', s.nav?.mode === 'line_follow' ? 'nav-line' : 'nav-nav2']">
              <Zap v-if="s.nav?.mode === 'line_follow'" :size="11" />
              <Compass v-else :size="11" />
              {{ s.nav?.mode === 'line_follow' ? 'Çizgi Takibi' : 'Nav2' }}
            </span>
            <div class="zoom-btns">
              <button class="zoom-btn" title="Yakınlaştır"><ZoomIn :size="14" /></button>
              <button class="zoom-btn" title="Uzaklaştır"><ZoomOut :size="14" /></button>
            </div>
          </div>
        </div>
      </template>
      <div class="map-canvas-wrap">
        <MiniMap :state="s" :fullsize="true" style="width:100%;height:auto;" />
      </div>
      <div class="color-legend">
        <span class="cleg-item"><span class="cleg-dot" style="background:#3b82f6" />Başlangıç/Bağlantı</span>
        <span class="cleg-item"><span class="cleg-dot cleg-diamond" style="background:#ef4444" />Alma İstasyonu</span>
        <span class="cleg-item"><span class="cleg-dot cleg-diamond" style="background:#3b82f6" />Bırakma İstasyonu</span>
        <span class="cleg-item"><span class="cleg-dot cleg-sq" style="background:#22c55e" />QR Kod Noktası</span>
        <span class="cleg-item"><span class="cleg-dot" style="background:#f5a524" />Kapı</span>
        <span class="cleg-item"><span class="cleg-dot cleg-robot" style="background:#f5a524" />Robot</span>
      </div>
    </Card>

    <div class="map-side">
      <!-- Route info -->
      <Card>
        <template #header><SectionTitle :icon="Route">Rota Bilgisi</SectionTitle></template>
        <LabelRow label="Görev ID">{{ s.mission?.id || '—' }}</LabelRow>
        <LabelRow label="Alma">
          <span class="id-pickup">{{ s.mission?.pickup || '—' }}</span>
        </LabelRow>
        <LabelRow label="Bırakma">
          <span class="id-dropoff">{{ s.mission?.dropoff || '—' }}</span>
        </LabelRow>
        <LabelRow label="Hedef">{{ s.nav?.current_goal || '—' }}</LabelRow>
        <LabelRow label="Toplam Mesafe">{{ fmt(s.nav?.total_distance_m) }} m</LabelRow>
        <LabelRow label="Kalan Mesafe">{{ fmt(s.nav?.remaining_m) }} m</LabelRow>
        <div v-if="(s.nav?.total_distance_m || 0) > 0" class="progress-wrap">
          <div class="progress-bar">
            <div class="progress-fill" :style="{ width: navProgress + '%' }" />
          </div>
          <span class="progress-pct">{{ navProgress }}%</span>
        </div>
      </Card>

      <!-- Precise position -->
      <Card>
        <template #header><SectionTitle :icon="Navigation">Hassas Konum</SectionTitle></template>
        <LabelRow label="X">{{ fmt(s.pose?.x, 3) }} m</LabelRow>
        <LabelRow label="Y">{{ fmt(s.pose?.y, 3) }} m</LabelRow>
        <LabelRow label="Yön (θ)">{{ fmt(s.pose?.theta_deg, 2) }}°</LabelRow>
        <LabelRow label="Hız">{{ fmt(s.pose?.speed) }} m/s</LabelRow>
        <LabelRow label="Rota Sapması">
          <span :class="deviationCls">{{ fmt(s.pose?.path_deviation_cm) }} cm</span>
        </LabelRow>
      </Card>

      <!-- Map controls -->
      <Card>
        <template #header><SectionTitle :icon="Layers">Harita Kontrol</SectionTitle></template>
        <div class="ctrl-list">
          <button class="ctrl-btn" @click="send('mapping', { action: 'start' })">
            <PlayCircle :size="14" /> Haritalama Başlat
          </button>
          <button class="ctrl-btn" @click="send('mapping', { action: 'stop' })">
            <StopCircle :size="14" /> Haritalama Durdur
          </button>
          <button class="ctrl-btn" @click="send('define_route', {})">
            <Pin :size="14" /> Rota Tanımla
          </button>
        </div>
      </Card>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import {
  Map as MapIcon, Compass, Zap, ZoomIn, ZoomOut, Navigation,
  Route, Layers, PlayCircle, StopCircle, Pin,
} from 'lucide-vue-next'
import Card from './Card.vue'
import SectionTitle from './SectionTitle.vue'
import LabelRow from './LabelRow.vue'
import MiniMap from './MiniMap.vue'

const props = defineProps({ state: Object })
const emit = defineEmits(['send-cmd'])
const s = computed(() => props.state || {})

const navProgress = computed(() => {
  const total = s.value.nav?.total_distance_m || 0
  const rem = s.value.nav?.remaining_m || 0
  if (!total) return 0
  return Math.round(((total - rem) / total) * 100)
})

const deviationCls = computed(() => {
  const d = s.value.pose?.path_deviation_cm || 0
  return d > 10 ? 'val-red' : d > 7 ? 'val-amber' : ''
})

function fmt(v, d = 2) { return (v ?? 0).toFixed(d) }
function send(type, payload) { emit('send-cmd', { type, payload }) }
</script>

<style scoped>
.tab-map { display: grid; grid-template-columns: 1fr 230px; gap: 10px; height: 100%; overflow: hidden; }
.map-main-card { display: flex; flex-direction: column; overflow: hidden; }
.map-side { display: flex; flex-direction: column; gap: 10px; overflow-y: auto; }

.map-card-header { display: flex; align-items: center; justify-content: space-between; }
.header-right { display: flex; align-items: center; gap: 8px; }
.nav-pill { display: inline-flex; align-items: center; gap: 4px; padding: 2px 9px; border-radius: 12px; font-size: 11px; font-weight: 700; }
.nav-nav2 { background: rgba(59,130,246,.15); color: var(--accent); }
.nav-line  { background: rgba(34,197,94,.15);  color: var(--green); }
.zoom-btns { display: flex; gap: 4px; }
.zoom-btn {
  width: 26px; height: 26px; border: 1px solid var(--border); border-radius: 6px;
  background: var(--panel-2); color: var(--text-dim); cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  transition: color .15s, border-color .15s;
}
.zoom-btn:hover { color: var(--text); border-color: var(--accent); }

.map-canvas-wrap { flex: 1; min-height: 0; overflow: hidden; }

.color-legend { display: flex; flex-wrap: wrap; gap: 10px; padding-top: 8px; border-top: 1px solid var(--border); margin-top: 8px; }
.cleg-item { display: flex; align-items: center; gap: 5px; font-size: 11px; color: var(--text-dim); }
.cleg-dot    { width: 8px; height: 8px; border-radius: 50%; display: inline-block; flex-shrink: 0; }
.cleg-diamond{ border-radius: 2px; transform: rotate(45deg); }
.cleg-sq     { border-radius: 1px; }
.cleg-robot  { border-radius: 2px; }

/* Route progress */
.progress-wrap { display: flex; align-items: center; gap: 8px; margin-top: 10px; }
.progress-bar  { flex: 1; height: 6px; background: var(--panel-2); border-radius: 3px; overflow: hidden; border: 1px solid var(--border); }
.progress-fill { height: 100%; background: var(--accent); border-radius: 3px; transition: width .5s; }
.progress-pct  { font-size: 11px; font-weight: 700; color: var(--accent); min-width: 28px; text-align: right; }

/* ID badges */
.id-pickup  { color: #a78bfa; font-weight: 700; }
.id-dropoff { color: var(--accent); font-weight: 700; }

/* Value colors */
.val-red   { color: var(--red) !important;   font-weight: 700; }
.val-amber { color: var(--amber) !important; font-weight: 700; }

/* Ctrl buttons */
.ctrl-list { display: flex; flex-direction: column; gap: 6px; }
.ctrl-btn {
  display: flex; align-items: center; gap: 8px;
  padding: 7px 12px; border-radius: var(--radius-sm);
  border: 1px solid var(--border); background: var(--panel-2);
  color: var(--text-dim); font-size: 12px; cursor: pointer;
  font-family: inherit; transition: color .15s, border-color .15s, background .15s;
}
.ctrl-btn:hover { color: var(--text); border-color: var(--accent); background: rgba(59,130,246,.08); }
</style>
