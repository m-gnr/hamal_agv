<template>
  <div class="stat-cells">
    <!-- Robot connection -->
    <div class="stat-cell">
      <span class="stat-cell__label">Robot Bağlantısı</span>
      <div class="stat-cell__val">
        <span :class="['status-dot', s.connection?.robot ? 'dot-green' : 'dot-red']" />
        <span :class="s.connection?.robot ? 'val-green' : 'val-red'">
          {{ s.connection?.robot ? 'BAĞLI' : 'YOK' }}
        </span>
      </div>
    </div>

    <!-- PLC connection -->
    <div class="stat-cell">
      <span class="stat-cell__label">PLC Bağlantısı</span>
      <div class="stat-cell__val">
        <span :class="['status-dot', s.connection?.plc ? 'dot-green' : 'dot-red']" />
        <span :class="s.connection?.plc ? 'val-green' : 'val-red'">
          {{ s.connection?.plc ? 'BAĞLI' : 'YOK' }}
        </span>
      </div>
    </div>

    <!-- Mode (auto/manual) -->
    <div class="stat-cell">
      <span class="stat-cell__label">Mod</span>
      <div class="stat-cell__val">
        <span :class="s.switch?.mode === 'auto' ? 'val-accent' : 'val-amber'">
          {{ s.switch?.mode === 'auto' ? 'OTOMATİK' : 'MANUEL' }}
        </span>
      </div>
    </div>

    <!-- Switch state -->
    <div class="stat-cell">
      <span class="stat-cell__label">Anahtar Durumu</span>
      <div class="stat-cell__val">
        <span :class="s.switch?.mode === 'auto' ? 'val-accent' : 'val-amber'">
          {{ s.switch?.mode === 'auto' ? 'OTOMATİK' : 'MANUEL' }}
        </span>
      </div>
    </div>

    <!-- Battery -->
    <div class="stat-cell stat-cell--wide">
      <span class="stat-cell__label">Batarya</span>
      <div class="stat-cell__val">
        <div class="batt-bar-wrap">
          <div class="batt-bar" :class="battCls" :style="{ width: battPct + '%' }" />
        </div>
        <span :class="['batt-pct', battCls === 'batt-red' ? 'val-red' : battCls === 'batt-amber' ? 'val-amber' : 'val-green']">
          {{ battPct }}%
        </span>
      </div>
    </div>

    <!-- E-stop -->
    <div class="stat-cell">
      <span class="stat-cell__label">Acil Stop</span>
      <div class="stat-cell__val">
        <span :class="['status-dot', s.estop?.active ? 'dot-red' : 'dot-green']" />
        <span :class="s.estop?.active ? 'val-red estop-active' : 'val-dim'">
          {{ s.estop?.active ? 'AKTİF' : 'PASİF' }}
        </span>
      </div>
    </div>

    <!-- Mission timer -->
    <div class="stat-cell stat-cell--timer">
      <span class="stat-cell__label">Görev Süresi</span>
      <div class="stat-cell__val timer-val" :class="timerCls">
        <span class="timer-elapsed">{{ fmtTime(s.mission?.timer?.elapsed_s) }}</span>
        <span class="timer-sep">/</span>
        <span class="timer-target">{{ fmtTime(s.mission?.timer?.target_s) }}</span>
      </div>
    </div>

    <!-- FSM pill -->
    <div class="stat-cell">
      <span class="stat-cell__label">Robot Durumu</span>
      <div class="stat-cell__val">
        <span :class="['fsm-pill', fsmCls]">{{ FSM_TR[s.mission?.fsm] || s.mission?.fsm || '—' }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({ state: Object })
defineEmits(['send-cmd'])
const s = computed(() => props.state || {})

const FSM_TR = {
  idle: 'Boşta', task_processing: 'İşleniyor',
  moving_empty: 'Boş Hareket', moving_loaded: 'Yüklü Hareket',
  waiting_plc: 'PLC Bekliyor', returning_home: 'Eve Dönüyor',
  error: 'HATA', emergency_stop: 'ACİL STOP',
}
const FSM_CLS = {
  idle: 'fsm-dim', task_processing: 'fsm-info',
  moving_empty: 'fsm-success', moving_loaded: 'fsm-info',
  waiting_plc: 'fsm-warn', returning_home: 'fsm-info',
  error: 'fsm-danger', emergency_stop: 'fsm-danger',
}
const fsmCls = computed(() => FSM_CLS[s.value.mission?.fsm] || 'fsm-dim')

const battPct = computed(() => Math.round(s.value.battery?.percent ?? 100))
const battCls = computed(() => battPct.value < 10 ? 'batt-red' : battPct.value < 20 ? 'batt-amber' : 'batt-green')

const elapsed = computed(() => s.value.mission?.timer?.elapsed_s || 0)
const target  = computed(() => s.value.mission?.timer?.target_s || 1800)
const timerCls = computed(() => {
  const lim = s.value.mission?.timer?.limit_s || 2700
  if (elapsed.value > lim)    return 'timer-danger'
  if (elapsed.value > target.value) return 'timer-warn'
  return ''
})

function fmtTime(sec) {
  if (sec === undefined || sec === null) return '--:--'
  const m = Math.floor(sec / 60), ss = Math.floor(sec % 60)
  return `${String(m).padStart(2,'0')}:${String(ss).padStart(2,'0')}`
}
</script>

<style scoped>
.stat-cells {
  display: flex;
  align-items: center;
  gap: 6px;
  flex: 1;
  min-width: 0;
  overflow: hidden;
}
.stat-cell {
  display: flex;
  flex-direction: column;
  gap: 3px;
  padding: 8px 12px;
  background: var(--topcell);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  flex-shrink: 1;
  min-width: 72px;
  overflow: hidden;
}
.stat-cell--wide  { min-width: 110px; }
.stat-cell--timer { min-width: 110px; }
.stat-cell__label { font-size: 10px; color: var(--text-dim); text-transform: uppercase; letter-spacing: .5px; font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.stat-cell__val   { display: flex; align-items: center; gap: 5px; }

.status-dot { width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0; }
.dot-green  { background: var(--green); box-shadow: 0 0 6px var(--green); }
.dot-red    { background: var(--red);   box-shadow: 0 0 6px var(--red); }

.val-green  { color: var(--green); font-size: 13px; font-weight: 700; }
.val-red    { color: var(--red);   font-size: 13px; font-weight: 700; }
.val-amber  { color: var(--amber); font-size: 13px; font-weight: 700; }
.val-accent { color: var(--accent);font-size: 13px; font-weight: 700; }
.val-dim    { color: var(--text-dim); font-size: 13px; font-weight: 600; }

.estop-active { animation: pulse 0.6s infinite; }

/* Battery bar */
.batt-bar-wrap { width: 50px; height: 8px; background: var(--panel-2); border-radius: 4px; overflow: hidden; border: 1px solid var(--border); }
.batt-bar { height: 100%; transition: width .5s; border-radius: 4px; }
.batt-green { background: var(--green); }
.batt-amber { background: var(--amber); }
.batt-red   { background: var(--red); }
.batt-pct   { font-size: 13px; font-weight: 700; }

/* Timer */
.timer-val { gap: 3px; font-variant-numeric: tabular-nums; }
.timer-elapsed { font-size: 15px; font-weight: 700; color: var(--text); }
.timer-sep     { font-size: 12px; color: var(--text-dim); }
.timer-target  { font-size: 12px; color: var(--text-dim); }
.timer-warn    .timer-elapsed { color: var(--amber); }
.timer-danger  .timer-elapsed { color: var(--red); animation: pulse .7s infinite; }

/* FSM pill */
.fsm-pill { padding: 2px 10px; border-radius: 12px; font-size: 11px; font-weight: 700; white-space: nowrap; }
.fsm-dim     { background: rgba(125,138,160,.1);  color: var(--text-dim); }
.fsm-info    { background: rgba(59,130,246,.15);  color: var(--accent); }
.fsm-success { background: rgba(34,197,94,.14);   color: var(--green); }
.fsm-warn    { background: rgba(245,165,36,.14);  color: var(--amber); }
.fsm-danger  { background: rgba(239,68,68,.14);   color: var(--red); animation: pulse .8s infinite; }
</style>
