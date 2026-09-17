<template>
  <div v-if="s.meta?.mode === 'live'" class="stat-cells">
    <div v-for="cell in liveCells" :key="cell.name" class="stat-cell">
      <span class="stat-cell__label">{{ cell.name }}</span>
      <span :class="'live-' + (cell.tone || 'unknown')">{{ cell.value }}</span>
    </div>
  </div>
  <div v-else class="stat-cells">
    <!-- Robot bağlantısı -->
    <div class="stat-cell">
      <span class="stat-cell__label">ROBOT</span>
      <div class="stat-cell__val">
        <span :class="['status-dot', s.connection?.robot ? 'dot-green' : 'dot-red']" />
        <span :class="s.connection?.robot ? 'val-green' : 'val-red'">
          {{ s.connection?.robot ? 'BAĞLI' : 'YOK' }}
        </span>
      </div>
    </div>

    <!-- PLC bağlantısı -->
    <div class="stat-cell">
      <span class="stat-cell__label">PLC</span>
      <div class="stat-cell__val">
        <span :class="['status-dot', s.connection?.plc ? 'dot-green' : 'dot-red']" />
        <span :class="s.connection?.plc ? 'val-green' : 'val-red'">
          {{ s.connection?.plc ? 'BAĞLI' : 'YOK' }}
        </span>
      </div>
    </div>

    <!-- Anahtar modu — Mod + Anahtar Durumu birleşik -->
    <div class="stat-cell">
      <span class="stat-cell__label">ANAHTAR</span>
      <div class="stat-cell__val">
        <ToggleLeft v-if="s.switch?.mode !== 'auto'" :size="13" class="icon-amber" />
        <ToggleRight v-else :size="13" class="icon-accent" />
        <span :class="s.switch?.mode === 'auto' ? 'val-accent' : 'val-amber'">
          {{ s.switch?.mode === 'auto' ? 'OTOMATİK' : 'MANUEL' }}
        </span>
      </div>
    </div>

    <!-- UI host battery; robot power is shown separately on the dashboard. -->
    <div class="stat-cell stat-cell--batt">
      <span class="stat-cell__label">PC BATARYA</span>
      <div class="stat-cell__val">
        <div class="batt-bar-wrap">
          <div class="batt-bar" :class="battCls" :style="{ width: battPct + '%' }" />
        </div>
        <span :class="['batt-pct', battPct === null ? 'val-dim' : battCls === 'batt-red' ? 'val-red' : battCls === 'batt-amber' ? 'val-amber' : 'val-green']">
          {{ hostBatteryText }}
        </span>
      </div>
    </div>

    <!-- Acil Stop -->
    <div class="stat-cell">
      <span class="stat-cell__label">E-STOP</span>
      <div class="stat-cell__val">
        <Power :size="13" :class="s.estop?.active ? 'icon-red' : 'icon-dim'" />
        <span :class="s.estop?.active ? 'val-red estop-active' : 'val-dim'">
          {{ s.estop?.active ? 'AKTİF' : 'PASİF' }}
        </span>
      </div>
    </div>

    <!-- UI oturum süresi -->
    <div class="stat-cell stat-cell--timer">
      <span class="stat-cell__label">SÜRE</span>
      <div class="stat-cell__val timer-val">
        <span class="timer-elapsed">{{ fmtTime(s.host?.session_elapsed_s) }}</span>
      </div>
    </div>

    <!-- Robot durumu / FSM -->
    <div class="stat-cell">
      <span class="stat-cell__label">DURUM</span>
      <div class="stat-cell__val">
        <span :class="['fsm-pill', fsmCls]">{{ FSM_TR[s.mission?.fsm] || s.mission?.fsm || '—' }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { freshness, safetySummary } from '../composables/liveState.js'
import { ToggleLeft, ToggleRight, Power } from 'lucide-vue-next'

const props = defineProps({ state: Object, physicalMode: { type: String, default: 'unknown' } })
defineEmits(['send-cmd'])
const s = computed(() => props.state || {})

const liveCells = computed(() => {
  const state = s.value
  const missionFresh = freshness(state, '/mission/state')
  const safety = safetySummary(state)
  return [
    { name: 'ROS', value: !state.connection?.rosbridge ? 'Disconnected' : state.meta?.mismatch ? 'MOCK backend rejected' : state.meta?.stale ? 'Stale' : 'Connected', tone: state.meta?.stale ? 'warn' : 'healthy' },
    { name: 'MOD · FİZİKSEL', value: props.physicalMode },
    { name: 'GÖREV', value: missionFresh === 'live' ? state.mission?.fsm : missionFresh },
    { name: 'GÜVENLİK', value: safety.label, tone: safety.tone },
    { name: 'SÜRE', value: state.meta?.stale ? '--:--:--' : fmtTime(state.host?.session_elapsed_s) },
    { name: 'PC BATARYA', value: state.meta?.stale ? 'N/A' : batteryText(state.host?.battery) },
  ]
})

const FSM_TR = {
  idle: 'Boşta', task_processing: 'İşleniyor',
  moving_empty: 'Boş Hareket', moving_loaded: 'Yüklü Hareket',
  waiting_plc: 'PLC Bekliyor', returning_home: 'Dönüyor',
  error: 'HATA', emergency_stop: 'ACİL STOP',
}
const FSM_CLS = {
  idle: 'fsm-dim', task_processing: 'fsm-info',
  moving_empty: 'fsm-success', moving_loaded: 'fsm-info',
  waiting_plc: 'fsm-warn', returning_home: 'fsm-info',
  error: 'fsm-danger', emergency_stop: 'fsm-danger',
}
const fsmCls = computed(() => FSM_CLS[s.value.mission?.fsm] || 'fsm-dim')

const battPct = computed(() => validPercent(s.value.host?.battery?.percent) ? Math.round(s.value.host.battery.percent) : null)
const battCls = computed(() => battPct.value === null ? '' : battPct.value < 10 ? 'batt-red' : battPct.value < 20 ? 'batt-amber' : 'batt-green')
const hostBatteryText = computed(() => batteryText(s.value.host?.battery))

function validPercent(value) { return typeof value === 'number' && Number.isFinite(value) && value >= 0 && value <= 100 }
function batteryText(battery) {
  if (!validPercent(battery?.percent)) return 'N/A'
  const status = { charging: ' · Şarj', discharging: ' · Pilde', full: ' · Dolu' }[battery.status] || ''
  return `${Math.round(battery.percent)}%${status}`
}

function fmtTime(sec) {
  if (typeof sec !== 'number' || !Number.isFinite(sec) || sec < 0) return '--:--:--'
  const h = Math.floor(sec / 3600), m = Math.floor(sec % 3600 / 60), ss = Math.floor(sec % 60)
  return `${String(h).padStart(2,'0')}:${String(m).padStart(2,'0')}:${String(ss).padStart(2,'0')}`
}
</script>

<style scoped>
.live-unknown { color: var(--text-dim); }
.live-warn { color: var(--amber); }
.live-danger { color: var(--red); }
.live-healthy { color: var(--green); }
.stat-cells {
  display: flex;
  align-items: stretch;
  gap: 5px;
  flex: 1;
  min-width: 0;
}

.stat-cell {
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 3px;
  padding: 5px 10px;
  background: var(--topcell);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  flex: 1 1 0;
  min-width: 0;
}
.stat-cell--batt  { flex: 1.5 1 0; }
.stat-cell--timer { flex: 1.5 1 0; }

.stat-cell__label {
  font-size: 9px;
  color: var(--text-dim);
  letter-spacing: .7px;
  font-weight: 700;
  white-space: nowrap;
}
.stat-cell__val { display: flex; align-items: center; gap: 5px; }

/* Dots */
.status-dot { width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0; }
.dot-green  { background: var(--green); box-shadow: 0 0 5px var(--green); }
.dot-red    { background: var(--red);   box-shadow: 0 0 5px var(--red); }

/* Value text */
.val-green  { color: var(--green);  font-size: 12px; font-weight: 700; }
.val-red    { color: var(--red);    font-size: 12px; font-weight: 700; }
.val-amber  { color: var(--amber);  font-size: 12px; font-weight: 700; }
.val-accent { color: var(--accent); font-size: 12px; font-weight: 700; }
.val-dim    { color: var(--text-dim); font-size: 12px; font-weight: 600; }

/* Inline icons */
.icon-accent { color: var(--accent); flex-shrink: 0; }
.icon-amber  { color: var(--amber);  flex-shrink: 0; }
.icon-red    { color: var(--red);    flex-shrink: 0; }
.icon-dim    { color: var(--text-dim); flex-shrink: 0; }

.estop-active { animation: pulse 0.6s infinite; }

/* Battery bar */
.batt-bar-wrap { width: 44px; height: 7px; background: var(--panel-2); border-radius: 3px; overflow: hidden; border: 1px solid var(--border); flex-shrink: 0; }
.batt-bar { height: 100%; transition: width .5s; border-radius: 3px; }
.batt-green { background: var(--green); }
.batt-amber { background: var(--amber); }
.batt-red   { background: var(--red); }
.batt-pct   { font-size: 12px; font-weight: 700; }

/* Timer */
.timer-val     { gap: 3px; font-variant-numeric: tabular-nums; }
.timer-elapsed { font-size: 14px; font-weight: 700; color: var(--text); }

/* FSM pill */
.fsm-pill { padding: 2px 8px; border-radius: 10px; font-size: 11px; font-weight: 700; white-space: nowrap; }
.fsm-dim     { background: rgba(125,138,160,.1);  color: var(--text-dim); }
.fsm-info    { background: rgba(59,130,246,.15);  color: var(--accent); }
.fsm-success { background: rgba(34,197,94,.14);   color: var(--green); }
.fsm-warn    { background: rgba(245,165,36,.14);  color: var(--amber); }
.fsm-danger  { background: rgba(239,68,68,.14);   color: var(--red); animation: pulse .8s infinite; }
</style>
