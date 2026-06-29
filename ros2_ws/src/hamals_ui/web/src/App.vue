<template>
  <div class="app">
    <!-- ── TOPBAR ─────────────────────────────────────── -->
    <header class="topbar">
      <!-- Logo -->
      <div class="topbar__logo">
        <div class="logo-icon"><Forklift :size="26" /></div>
        <div class="logo-text">
          <span class="logo-name">HAMAL</span>
          <span class="logo-sub">OTONOM MOBİL ROBOT</span>
        </div>
      </div>

      <!-- Stat cells (TopBar handles these) -->
      <TopBar :state="state" @send-cmd="sendCmd" />

      <!-- Right: E-STOP + clock + mock badge -->
      <div class="topbar__right">
        <!-- E-STOP area -->
        <div class="estop-area">
          <button
            :class="['estop-btn', state?.estop?.active ? 'estop-on' : '']"
            @click="sendCmd({ type: 'estop' })"
            title="Yazılımsal acil durdurma"
          >
            <StopCircle :size="16" />
            <span>E-STOP</span>
          </button>
          <button
            v-if="state?.estop?.active"
            class="estop-ack-btn"
            @click="sendCmd({ type: 'estop_ack' })"
          >
            Sıfırla
          </button>
        </div>

        <div v-if="isMock" class="mock-badge">
          <AlertTriangle :size="12" /> DEBUG / MOCK
        </div>
        <div class="topbar-clock">
          <span class="clock-time">{{ clock }}</span>
          <span class="clock-date">{{ date }}</span>
        </div>
      </div>
    </header>

    <!-- ── BODY ──────────────────────────────────────── -->
    <div class="body">
      <SidebarNav :active="activeTab" @change="activeTab = $event" />

      <main class="main-content">
        <TabDashboard v-if="activeTab === 'dashboard'" :state="state" @send-cmd="sendCmd" />
        <TabMap       v-if="activeTab === 'map'"       :state="state" @send-cmd="sendCmd" />
        <TabMission   v-if="activeTab === 'mission'"   :state="state" :is-mock="isMock" @send-cmd="sendCmd" />
        <TabManual    v-if="activeTab === 'manual'"    :state="state" :is-mock="isMock" @send-cmd="sendCmd" />
        <TabCamera    v-if="activeTab === 'camera'"    :state="state" />
        <TabErrors    v-if="activeTab === 'errors'"    :state="state" />
        <TabSettings  v-if="activeTab === 'settings'"  :state="state" />
      </main>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useMockData } from './composables/useMockData.js'
import { useRosbridge } from './composables/useRosbridge.js'
import { Forklift, AlertTriangle, StopCircle } from 'lucide-vue-next'
import TopBar       from './components/TopBar.vue'
import SidebarNav   from './components/SidebarNav.vue'
import TabDashboard from './components/TabDashboard.vue'
import TabMap       from './components/TabMap.vue'
import TabMission   from './components/TabMission.vue'
import TabManual    from './components/TabManual.vue'
import TabCamera    from './components/TabCamera.vue'
import TabErrors    from './components/TabErrors.vue'
import TabSettings  from './components/TabSettings.vue'

// ── Config ──────────────────────────────────────────────────
// Change to 'rosbridge' for live robot; 'mock' for offline dev
const DATA_SOURCE = import.meta.env.VITE_DATA_SOURCE || 'mock'
const ROSBRIDGE_URL = import.meta.env.VITE_ROSBRIDGE_URL || 'ws://robot:9090'

const TABS = [
  { id: 'dashboard', title: 'Genel Durum', icon: 'LayoutDashboard' },
  { id: 'map',       title: 'Harita & Rota', icon: 'Map' },
  { id: 'mission',   title: 'Görev & PLC',  icon: 'ClipboardList' },
  { id: 'manual',    title: 'Manuel Kontrol', icon: 'Gamepad2' },
  { id: 'camera',    title: 'Kamera & Çizgi', icon: 'Camera' },
  { id: 'errors',    title: 'Hata & Güvenlik', icon: 'ShieldAlert' },
  { id: 'settings',  title: 'Ayarlar', icon: 'Settings' },
]

const activeTab = ref('dashboard')

// Clock
const clock = ref('')
const date = ref('')
let clockTimer = null
function updateClock() {
  const now = new Date()
  clock.value = now.toLocaleTimeString('tr-TR', { hour12: false })
  date.value = now.toLocaleDateString('tr-TR', { day:'2-digit', month:'2-digit', year:'numeric' })
}
onMounted(() => { updateClock(); clockTimer = setInterval(updateClock, 1000) })
onUnmounted(() => clearInterval(clockTimer))

// ── Data source ─────────────────────────────────────────────
const mock = useMockData()
const bridge = useRosbridge(ROSBRIDGE_URL)

const state = computed(() =>
  DATA_SOURCE === 'mock' ? mock.state.value : bridge.state.value
)

const isMock = computed(() =>
  DATA_SOURCE === 'mock' || state.value?.meta?.mode === 'mock'
)

// ── Command dispatcher ───────────────────────────────────────
function sendCmd(cmd) {
  if (DATA_SOURCE === 'mock') {
    mock.handleCmd(cmd)
    return
  }
  bridge.publish('/ui/cmd', 'std_msgs/String', { data: JSON.stringify(cmd) })
}

onMounted(() => {
  if (DATA_SOURCE === 'mock') mock.start()
  else bridge.connect()
})
</script>

<style>
/* ── Design tokens ─────────────────────────────────────── */
:root {
  --bg:        #0a0e16;
  --panel:     #121a28;
  --panel-2:   #0e1521;
  --topcell:   #0f1722;
  --border:    #1e2a3c;
  --text:      #eef2f8;
  --text-dim:  #7d8aa0;
  --accent:    #3b82f6;
  --accent-2:  #4f9cff;
  --green:     #22c55e;
  --amber:     #f5a524;
  --red:       #ef4444;
  --blue-drop: #3b82f6;
  --radius:    12px;
  --radius-sm: 8px;
  --sidebar-w: 212px;
  --topbar-h:  64px;
}

/* ── Reset ─────────────────────────────────────────────── */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
html {
  font-size: clamp(11px, 0.55vw + 6px, 17px);
  height: 100vh; width: 100vw; overflow: hidden;
}
body, #app {
  height: 100%; width: 100%; overflow: hidden;
  background: var(--bg);
  color: var(--text);
  font-family: 'Inter Variable', 'Inter', system-ui, sans-serif;
  font-size: 0.875rem; /* 14px at 16px root */
}

/* ── App shell ─────────────────────────────────────────── */
.app {
  display: flex; flex-direction: column;
  height: 100vh; width: 100vw;
  background: var(--bg); overflow: hidden;
}

/* ── Topbar ────────────────────────────────────────────── */
.topbar {
  display: flex;
  align-items: center;
  gap: 10px;
  height: var(--topbar-h);
  padding: 0 14px;
  background: var(--panel);
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
  overflow: hidden;
}
.topbar__logo {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-shrink: 0;
  padding-right: 14px;
  border-right: 1px solid var(--border);
  margin-right: 4px;
}
.logo-icon {
  width: 38px; height: 38px;
  background: rgba(59,130,246,.15);
  border: 1px solid rgba(59,130,246,.3);
  border-radius: 10px;
  display: flex; align-items: center; justify-content: center;
  color: var(--accent);
  flex-shrink: 0;
}
.logo-text { display: flex; flex-direction: column; }
.logo-name { font-size: 0.9rem; font-weight: 700; color: var(--text); letter-spacing: .5px; }
.logo-sub  { font-size: 0.625rem; color: var(--text-dim); letter-spacing: .5px; text-transform: uppercase; }

.topbar__right {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-shrink: 0;
  margin-left: auto;
}
.topbar-clock {
  display: flex; flex-direction: column; align-items: flex-end;
  padding: 5px 10px;
  background: var(--topcell);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
}
.clock-time { font-size: 1rem; font-weight: 700; font-variant-numeric: tabular-nums; color: var(--text); }
.clock-date { font-size: 0.625rem; color: var(--text-dim); letter-spacing: .3px; }

/* Mock badge */
.mock-badge {
  display: flex; align-items: center; gap: 5px;
  background: rgba(245,165,36,.18);
  color: var(--amber);
  border: 1px solid rgba(245,165,36,.4);
  font-size: 0.688rem; font-weight: 700;
  padding: 4px 10px;
  border-radius: 20px;
  letter-spacing: .4px;
  animation: pulse-amber 2s infinite;
}
@keyframes pulse-amber { 0%,100%{opacity:1} 50%{opacity:.65} }

/* E-STOP area */
.estop-area {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}
.estop-btn {
  display: flex; align-items: center; gap: 6px;
  padding: 6px 14px;
  background: rgba(239,68,68,.18);
  border: 1.5px solid rgba(239,68,68,.6);
  border-radius: var(--radius-sm);
  color: var(--red);
  font-size: 0.8rem; font-weight: 800; font-family: inherit;
  letter-spacing: .5px;
  cursor: pointer;
  transition: background .15s, box-shadow .15s;
}
.estop-btn:hover {
  background: rgba(239,68,68,.28);
  box-shadow: 0 0 12px rgba(239,68,68,.35);
}
.estop-btn.estop-on {
  background: rgba(239,68,68,.9);
  color: #fff;
  animation: glow-red 0.6s infinite;
}
.estop-ack-btn {
  padding: 5px 12px;
  background: rgba(245,165,36,.15);
  border: 1px solid rgba(245,165,36,.5);
  border-radius: var(--radius-sm);
  color: var(--amber);
  font-size: 0.75rem; font-weight: 700; font-family: inherit;
  cursor: pointer;
  transition: background .15s;
}
.estop-ack-btn:hover { background: rgba(245,165,36,.28); }

/* ── Body ──────────────────────────────────────────────── */
.body {
  display: flex;
  flex: 1;
  min-height: 0;
  overflow: hidden;
}
.main-content {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  padding: 12px;
  background: var(--bg);
}

/* ── Global animation ──────────────────────────────────── */
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.55} }
@keyframes glow-red { 0%,100%{box-shadow:0 0 0 0 rgba(239,68,68,0)} 50%{box-shadow:0 0 12px 3px rgba(239,68,68,.55)} }
</style>
