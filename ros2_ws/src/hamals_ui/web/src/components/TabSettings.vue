<template>
  <div class="tab-settings">
    <!-- Tolerances -->
    <Card>
      <template #header>
        <div class="tol-header">
          <SectionTitle :icon="Ruler">Toleranslar</SectionTitle>
          <span class="readonly-badge">
            <Lock :size="10" /> Salt-Okunur — Şartname md. 8
          </span>
        </div>
      </template>
      <div class="tol-grid">
        <div v-for="tol in TOLERANCES" :key="tol.key" class="tol-item">
          <div class="tol-icon-wrap">
            <component :is="tol.icon" :size="16" />
          </div>
          <div class="tol-info">
            <span class="tol-name">{{ tol.name }}</span>
            <span class="tol-limit">Limit: {{ tol.limit }}</span>
          </div>
          <div class="tol-val-wrap">
            <span :class="['tol-val', tol.cls(state)]">{{ tol.fmt(state) }}</span>
          </div>
        </div>
      </div>
    </Card>

    <div class="settings-cols">
      <!-- Network -->
      <Card>
        <template #header><SectionTitle :icon="Network">Ağ Bilgisi</SectionTitle></template>
        <LabelRow label="PLC IP">{{ state?.plc?.ip || '—' }}</LabelRow>
        <LabelRow label="PLC Port">{{ state?.plc?.port || '—' }}</LabelRow>
        <LabelRow label="Protokol">{{ state?.plc?.protocol || '—' }}</LabelRow>
        <LabelRow label="rosbridge">
          <StatPill :variant="state?.connection?.rosbridge ? 'success' : 'danger'" :dot="true">
            {{ state?.connection?.rosbridge ? 'Bağlı' : 'Bağlı değil' }}
          </StatPill>
        </LabelRow>
        <LabelRow label="WiFi SSID">—</LabelRow>
        <button class="action-btn" @click="testConn">
          <PlugZap :size="13" /> Bağlantı Testi
        </button>
      </Card>

      <!-- Mode info -->
      <Card>
        <template #header><SectionTitle :icon="Settings2">Çalışma Modu</SectionTitle></template>
        <div class="mode-pill-row">
          <StatPill :variant="state?.meta?.mode === 'mock' ? 'warn' : 'success'" :dot="true">
            {{ state?.meta?.mode === 'mock' ? 'MOCK / DEBUG' : 'CANLI' }}
          </StatPill>
        </div>
        <div class="mode-hint">
          Değiştirmek için: <code>config/params.yaml</code> → <code>mode:</code>
        </div>
        <LabelRow label="Zaman Damgası">
          <span class="mono">{{ fmtTs(state?.meta?.ts) }}</span>
        </LabelRow>
        <LabelRow label="Bridge OK">
          <StatPill :variant="state?.meta?.bridge_ok ? 'success' : 'danger'" :dot="true">
            {{ state?.meta?.bridge_ok ? 'Evet' : 'Hayır' }}
          </StatPill>
        </LabelRow>
      </Card>

      <!-- Sensor status -->
      <Card>
        <template #header><SectionTitle :icon="Cpu">Sensör Durumu</SectionTitle></template>
        <div class="sensor-list">
          <div v-for="[key, label] in SENSORS" :key="key" class="sensor-item">
            <span :class="['s-dot', state?.sensors?.[key] ? 'dot-green' : 'dot-red']" />
            <span :class="['s-label', state?.sensors?.[key] ? '' : 's-off']">{{ label }}</span>
            <span :class="['s-badge', state?.sensors?.[key] ? 'badge-ok' : 'badge-err']">
              {{ state?.sensors?.[key] ? 'Aktif' : 'Pasif' }}
            </span>
          </div>
        </div>
      </Card>
    </div>

    <!-- About -->
    <Card>
      <template #header><SectionTitle :icon="Info">Proje Bilgisi</SectionTitle></template>
      <div class="about-row">
        <span class="about-item">HAMALS AGV</span>
        <span class="about-sep">·</span>
        <span class="about-item">TEKNOFEST 2026 Sanayide Robotik Uygulamalar</span>
        <span class="about-sep">·</span>
        <span class="about-item">ROS 2 Humble</span>
        <span class="about-sep">·</span>
        <span class="about-item">hamals_ui v0.0.1</span>
        <span class="about-sep">·</span>
        <span class="about-item">Raspberry Pi 5 · Ubuntu 22.04</span>
      </div>
    </Card>
  </div>
</template>

<script setup>
import {
  Ruler, Lock, Network, Settings2, Cpu, Info, PlugZap,
  Move, Crosshair, Compass, Weight,
} from 'lucide-vue-next'
import Card from './Card.vue'
import SectionTitle from './SectionTitle.vue'
import StatPill from './StatPill.vue'
import LabelRow from './LabelRow.vue'

const props = defineProps({ state: Object })

const TOLERANCES = [
  {
    key: 'path_dev', name: 'Yol Sapması', limit: '≤ 10 cm', icon: Move,
    fmt: (s) => `${(s?.pose?.path_deviation_cm ?? 0).toFixed(1)} cm`,
    cls: (s) => {
      const v = s?.pose?.path_deviation_cm || 0
      return v > 10 ? 'tol-red' : v > 7 ? 'tol-amber' : 'tol-green'
    },
  },
  {
    key: 'pos', name: 'Konum Hassasiyeti', limit: '± 7.5 cm', icon: Crosshair,
    fmt: () => '—',
    cls: () => '',
  },
  {
    key: 'heading', name: 'Yön Hassasiyeti', limit: '± 5°', icon: Compass,
    fmt: (s) => `${(s?.pose?.theta_deg ?? 0).toFixed(1)}°`,
    cls: (s) => {
      const v = Math.abs(s?.pose?.theta_deg || 0)
      return v > 10 ? 'tol-amber' : 'tol-green'
    },
  },
  {
    key: 'load', name: 'Maks. Yük', limit: '5 kg', icon: Weight,
    fmt: () => '—',
    cls: () => '',
  },
]

const SENSORS = [
  ['lidar', 'LiDAR'],
  ['cam_front', 'Ön Kamera'],
  ['cam_back', 'Arka Kamera'],
  ['imu', 'IMU (BNO085)'],
  ['encoder', 'Enkoder'],
]

function fmtTs(ts) {
  if (!ts) return '—'
  return new Date(ts * 1000).toLocaleTimeString('tr-TR', { hour12: false })
}

function testConn() {
  alert('Bağlantı testi: rosbridge = ' + (props.state?.connection?.rosbridge ? 'Bağlı' : 'Bağlı değil'))
}
</script>

<style scoped>
.tab-settings { display: flex; flex-direction: column; gap: 10px; height: 100%; overflow: hidden; }
.settings-cols { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 10px; }

/* Tolerances */
.tol-header { display: flex; align-items: center; justify-content: space-between; }
.readonly-badge {
  display: flex; align-items: center; gap: 4px;
  font-size: 10px; color: var(--text-dim); padding: 2px 8px;
  background: var(--panel-2); border: 1px solid var(--border); border-radius: 8px;
}
.tol-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; }
.tol-item { display: flex; align-items: center; gap: 10px; padding: 8px 12px; background: var(--panel-2); border-radius: var(--radius-sm); border: 1px solid var(--border); }
.tol-icon-wrap { width: 32px; height: 32px; border-radius: 8px; background: rgba(59,130,246,.1); color: var(--accent); display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.tol-info { flex: 1; display: flex; flex-direction: column; gap: 2px; }
.tol-name  { font-size: 12px; color: var(--text); font-weight: 600; }
.tol-limit { font-size: 10px; color: var(--text-dim); }
.tol-val   { font-size: 16px; font-weight: 700; font-variant-numeric: tabular-nums; }
.tol-green { color: var(--green); }
.tol-amber { color: var(--amber); }
.tol-red   { color: var(--red); }

/* Mode */
.mode-pill-row { margin-bottom: 10px; }
.mode-hint { font-size: 11px; color: var(--text-dim); margin-bottom: 10px; }
code { background: var(--panel-2); padding: 1px 5px; border-radius: 4px; font-size: 11px; color: var(--accent); border: 1px solid var(--border); }
.mono { font-variant-numeric: tabular-nums; font-size: 12px; }

/* Sensors */
.sensor-list { display: flex; flex-direction: column; gap: 6px; }
.sensor-item { display: flex; align-items: center; gap: 8px; font-size: 12px; }
.s-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.dot-green { background: var(--green); box-shadow: 0 0 5px var(--green); }
.dot-red   { background: var(--red); }
.s-label { flex: 1; }
.s-off   { color: var(--red); }
.s-badge { padding: 1px 7px; border-radius: 8px; font-size: 10px; font-weight: 700; }
.badge-ok  { background: rgba(34,197,94,.12); color: var(--green); }
.badge-err { background: rgba(239,68,68,.12); color: var(--red); }

/* Action */
.action-btn {
  display: flex; align-items: center; gap: 6px;
  margin-top: 10px; padding: 6px 14px; border-radius: var(--radius-sm);
  border: 1px solid var(--border); background: var(--panel-2);
  color: var(--text-dim); font-size: 12px; cursor: pointer; font-family: inherit;
  transition: color .15s, border-color .15s;
}
.action-btn:hover { color: var(--text); border-color: var(--accent); }

/* About */
.about-row { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.about-item{ font-size: 12px; color: var(--text-dim); }
.about-sep { color: var(--border); }
</style>
