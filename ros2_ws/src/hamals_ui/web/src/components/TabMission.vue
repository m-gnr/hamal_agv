<template>
  <div class="tab-mission">
    <!-- FSM step strip -->
    <Card class="fsm-strip-card">
      <template #header><SectionTitle :icon="GitBranch">Görev Durumu — FSM</SectionTitle></template>
      <div class="fsm-strip">
        <div
          v-for="(step, idx) in FSM_STEPS"
          :key="step.id"
          :class="['fsm-step', step.id === s.mission?.fsm ? 'step-active' : '',
                    isCompleted(step.id) ? 'step-done' : '']"
        >
          <div class="step-connector" v-if="idx > 0" />
          <div class="step-icon-wrap">
            <component :is="step.icon" :size="13" />
          </div>
          <div class="step-label">{{ step.label }}</div>
        </div>
      </div>
    </Card>

    <!-- Scenario selector (mock only) -->
    <Card v-if="isMock" class="scenario-card">
      <template #header>
        <div class="scenario-header">
          <SectionTitle :icon="Play">Senaryo Seçimi</SectionTitle>
          <span class="mock-only-badge">MOCK</span>
        </div>
      </template>
      <div class="scenario-row">
        <div class="scenario-btns">
          <button
            v-for="sc in (s.meta?.scenarios || [])"
            :key="sc"
            :class="['scenario-btn', s.meta?.scenario === sc ? 'scenario-active' : '']"
            @click="sendScenario(sc)"
          >
            {{ sc }}
          </button>
        </div>
        <div class="playback-controls" v-if="s.meta?.scenario">
          <button
            v-if="playbackStatus !== 'playing'"
            class="pb-btn pb-start"
            @click="send('start_scenario', {})"
          >
            <Play :size="13" /> Başlat
          </button>
          <button
            v-else
            class="pb-btn pb-stop"
            @click="send('stop_scenario', {})"
          >
            <Square :size="13" /> Durdur
          </button>
        </div>
      </div>
      <div v-if="s.meta?.scenario" class="scenario-info">
        Aktif: <strong>{{ s.meta.scenario }}</strong>
        <span class="playback-status" :class="playbackStatus === 'playing' ? 'pb-playing' : 'pb-paused'">
          {{ playbackStatus === 'playing' ? '▶ Oynatılıyor' : '⏸ Duraklatıldı' }}
        </span>
      </div>
    </Card>

    <div class="mission-cols">
      <!-- Active mission -->
      <Card>
        <template #header><SectionTitle :icon="ClipboardList">Aktif Görev</SectionTitle></template>
        <div class="fsm-current-pill" :class="fsmCls">{{ FSM_TR[s.mission?.fsm] || s.mission?.fsm || 'BOŞTA' }}</div>
        <LabelRow label="Görev ID">{{ s.mission?.id || '—' }}</LabelRow>
        <LabelRow label="Alma">
          <span class="id-pickup">{{ s.mission?.pickup || '—' }}</span>
        </LabelRow>
        <LabelRow label="Bırakma">
          <span class="id-dropoff">{{ s.mission?.dropoff || '—' }}</span>
        </LabelRow>
        <LabelRow label="Adım">{{ s.mission?.step || '—' }}</LabelRow>
        <LabelRow label="Geçen Süre">
          <span class="mono">{{ fmtTime(s.mission?.elapsed_s) }}</span>
        </LabelRow>
        <div class="action-row">
          <button class="action-btn" @click="send('set_ready', {})">
            <Radio :size="13" /> Hazır Bildir
          </button>
          <button class="action-btn" @click="send('connect_plc', {})">
            <PlugZap :size="13" /> PLC Bağlan
          </button>
        </div>
      </Card>

      <!-- PLC detail -->
      <Card>
        <template #header><SectionTitle :icon="ServerIcon">PLC Detayı</SectionTitle></template>
        <div class="plc-header-row">
          <StatPill :variant="s.plc?.connected ? 'success' : 'default'" :dot="true">
            {{ s.plc?.connected ? 'BAĞLI' : 'Bağlantı Yok' }}
          </StatPill>
          <span v-if="s.plc?.signal !== undefined" class="signal-bars">
            <span v-for="i in 5" :key="i"
              :class="['sig-bar', i <= (s.plc?.signal || 0) ? 'sig-on' : '']"
              :style="{ height: (5 + i * 3) + 'px' }" />
          </span>
        </div>
        <LabelRow label="IP">{{ s.plc?.ip || '—' }}</LabelRow>
        <LabelRow label="Port">{{ s.plc?.port || '—' }}</LabelRow>
        <LabelRow label="Protokol">{{ s.plc?.protocol || '—' }}</LabelRow>
        <LabelRow label="Sinyal">{{ s.plc?.signal || 0 }}/5</LabelRow>
        <LabelRow label="Kapı İzni">
          <StatPill :variant="doorVariant">{{ DOOR_TR[s.plc?.door_permission] || '—' }}</StatPill>
        </LabelRow>
        <div v-if="s.plc?.last_msg" class="plc-last-msg">
          <MessageSquare :size="10" /> {{ s.plc.last_msg }}
        </div>
      </Card>

      <!-- Message history -->
      <Card class="msg-card">
        <template #header>
          <div class="msg-header">
            <SectionTitle :icon="MessageSquare">PLC / Robot Mesaj Geçmişi</SectionTitle>
            <span class="msg-count-chip">{{ (s.messages || []).length }}</span>
          </div>
        </template>
        <div class="msg-list">
          <div v-for="(m, i) in (s.messages || []).slice(0, 20)" :key="i" class="msg-row">
            <span :class="['dir-chip', m.dir === 'plc2robot' ? 'chip-green' : 'chip-blue']">
              {{ m.dir === 'plc2robot' ? 'PLC' : 'ROBOT' }}
            </span>
            <span class="msg-ts">{{ m.ts }}</span>
            <span class="msg-text">{{ m.text }}</span>
          </div>
          <div v-if="!s.messages?.length" class="empty-msg">Henüz mesaj yok</div>
        </div>
      </Card>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import {
  GitBranch, ClipboardList, Server as ServerIcon, MessageSquare,
  Radio, PlugZap, Play,
  Circle, CheckCircle2, AlertCircle, XCircle, ArrowRight,
} from 'lucide-vue-next'
import Card from './Card.vue'
import SectionTitle from './SectionTitle.vue'
import StatPill from './StatPill.vue'
import LabelRow from './LabelRow.vue'

const props = defineProps({ state: Object, isMock: Boolean })
const emit = defineEmits(['send-cmd'])
const s = computed(() => props.state || {})

const FSM_STEPS = [
  { id: 'idle',            label: 'Boşta',        icon: Circle },
  { id: 'waiting_plc',     label: 'PLC Bekleniyor', icon: Circle },
  { id: 'task_processing', label: 'Görev İşleniyor', icon: Circle },
  { id: 'moving_empty',    label: 'Boş Hareket',  icon: ArrowRight },
  { id: 'moving_loaded',   label: 'Yüklü Hareket', icon: ArrowRight },
  { id: 'returning_home',  label: 'Eve Dönüyor',  icon: ArrowRight },
  { id: 'error',           label: 'Hata',         icon: AlertCircle },
  { id: 'emergency_stop',  label: 'ACİL STOP',    icon: XCircle },
]
const FSM_ORDER = FSM_STEPS.map(s => s.id)
const FSM_TR = {
  idle: 'BOŞTA', task_processing: 'Görev İşleniyor',
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
const DOOR_TR = { granted: 'VERİLDİ', waiting: 'BEKLİYOR', none: '—' }

const fsmCls = computed(() => FSM_CLS[s.value.mission?.fsm] || 'fsm-dim')
const playbackStatus = computed(() => s.value.meta?.playback_status || 'paused')
const doorVariant = computed(() => {
  const d = s.value.plc?.door_permission
  return d === 'granted' ? 'success' : d === 'waiting' ? 'warn' : 'default'
})

function isCompleted(id) {
  const cur = s.value.mission?.fsm
  const ci = FSM_ORDER.indexOf(cur)
  const ii = FSM_ORDER.indexOf(id)
  return ci > ii && ii >= 0
}

function fmtTime(sec) {
  if (!sec && sec !== 0) return '--:--'
  const m = Math.floor(sec / 60), ss = Math.floor(sec % 60)
  return `${String(m).padStart(2, '0')}:${String(ss).padStart(2, '0')}`
}
function send(type, payload) { emit('send-cmd', { type, payload }) }
function sendScenario(name) { emit('send-cmd', { type: 'scenario', name }) }
</script>

<style scoped>
.tab-mission { display: flex; flex-direction: column; gap: 10px; height: 100%; overflow: hidden; }
.mission-cols { display: grid; grid-template-columns: 1fr 1fr 1.2fr; gap: 10px; flex: 1; min-height: 0; overflow: hidden; }

/* FSM Strip */
.fsm-strip-card { flex-shrink: 0; }
.fsm-strip { display: flex; align-items: center; gap: 0; overflow-x: auto; padding-bottom: 4px; }
.fsm-step  { display: flex; flex-direction: column; align-items: center; gap: 4px; padding: 4px 8px; position: relative; flex-shrink: 0; min-width: 80px; }
.step-connector {
  position: absolute; left: -1px; top: 14px; width: 2px; height: 2px;
  border-top: 1px dashed var(--border); width: 100%; top: 14px; left: -50%;
  pointer-events: none;
}
.step-icon-wrap {
  width: 28px; height: 28px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  background: var(--panel-2); border: 2px solid var(--border);
  color: var(--text-dim); transition: all .2s; flex-shrink: 0;
}
.step-label { font-size: 10px; color: var(--text-dim); text-align: center; line-height: 1.2; }

.step-done .step-icon-wrap  { background: rgba(34,197,94,.15); border-color: var(--green); color: var(--green); }
.step-done .step-label      { color: var(--green); }
.step-active .step-icon-wrap{ background: rgba(59,130,246,.2); border-color: var(--accent); color: var(--accent); box-shadow: 0 0 10px rgba(59,130,246,.4); }
.step-active .step-label    { color: var(--accent); font-weight: 700; }

/* FSM pill */
.fsm-current-pill { display: inline-flex; padding: 4px 14px; border-radius: 14px; font-size: 12px; font-weight: 700; margin-bottom: 10px; }
.fsm-dim     { background: rgba(125,138,160,.1);  color: var(--text-dim); }
.fsm-info    { background: rgba(59,130,246,.15);  color: var(--accent); }
.fsm-success { background: rgba(34,197,94,.14);   color: var(--green); }
.fsm-warn    { background: rgba(245,165,36,.14);  color: var(--amber); }
.fsm-danger  { background: rgba(239,68,68,.14);   color: var(--red); animation: pulse .8s infinite; }

/* IDs */
.id-pickup  { color: #a78bfa; font-weight: 700; }
.id-dropoff { color: var(--accent); font-weight: 700; }
.mono       { font-variant-numeric: tabular-nums; }

/* Actions */
.action-row { display: flex; gap: 6px; margin-top: 10px; flex-wrap: wrap; }
.action-btn {
  display: flex; align-items: center; gap: 6px;
  padding: 5px 12px; border-radius: var(--radius-sm);
  border: 1px solid var(--border); background: var(--panel-2);
  color: var(--text-dim); font-size: 12px; cursor: pointer; font-family: inherit;
  transition: color .15s, border-color .15s;
}
.action-btn:hover { color: var(--text); border-color: var(--accent); }

/* PLC signal */
.plc-header-row { display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px; }
.signal-bars { display: flex; align-items: flex-end; gap: 2px; height: 18px; }
.sig-bar { width: 4px; border-radius: 2px; background: var(--border); }
.sig-on  { background: var(--green); }
.plc-last-msg { display: flex; align-items: center; gap: 5px; margin-top: 8px; font-size: 11px; color: var(--text-dim); font-style: italic; }

/* Messages */
.msg-card  { display: flex; flex-direction: column; overflow: hidden; }
.msg-header{ display: flex; align-items: center; justify-content: space-between; }
.msg-count-chip { background: var(--panel-2); border: 1px solid var(--border); border-radius: 10px; padding: 1px 8px; font-size: 11px; color: var(--text-dim); }
.msg-list  { overflow-y: auto; display: flex; flex-direction: column; gap: 4px; max-height: 100%; }
.msg-row   { display: flex; align-items: flex-start; gap: 6px; font-size: 11px; }
.dir-chip  { padding: 1px 7px; border-radius: 10px; font-size: 10px; font-weight: 700; flex-shrink: 0; }
.chip-green{ background: rgba(34,197,94,.15);  color: var(--green); border: 1px solid rgba(34,197,94,.3); }
.chip-blue { background: rgba(59,130,246,.15); color: var(--accent);border: 1px solid rgba(59,130,246,.3); }
.msg-ts   { color: var(--text-dim); flex-shrink: 0; font-variant-numeric: tabular-nums; }
.msg-text { color: var(--text); }
.empty-msg{ color: var(--text-dim); font-size: 12px; }

/* Scenario card */
.scenario-card { flex-shrink: 0; }
.scenario-header { display: flex; align-items: center; justify-content: space-between; }
.mock-only-badge {
  font-size: 10px; font-weight: 700; padding: 2px 8px; border-radius: 10px;
  background: rgba(245,165,36,.18); color: var(--amber); border: 1px solid rgba(245,165,36,.4);
}
.scenario-row    { display: flex; align-items: center; justify-content: space-between; gap: 10px; margin-bottom: 6px; }
.scenario-btns   { display: flex; gap: 8px; flex-wrap: wrap; }
.scenario-btn {
  padding: 5px 16px; border-radius: 10px; font-size: 12px; font-weight: 700;
  border: 1px solid var(--border); background: var(--panel-2); color: var(--text-dim);
  cursor: pointer; font-family: inherit; transition: all .15s;
}
.scenario-btn:hover { border-color: var(--accent); color: var(--text); }
.scenario-active {
  background: rgba(59,130,246,.18) !important; color: var(--accent) !important;
  border-color: rgba(59,130,246,.5) !important;
}
.playback-controls { display: flex; gap: 6px; flex-shrink: 0; }
.pb-btn {
  display: flex; align-items: center; gap: 5px;
  padding: 5px 14px; border-radius: var(--radius-sm); font-size: 12px; font-weight: 700;
  border: 1px solid; cursor: pointer; font-family: inherit; transition: all .15s;
}
.pb-start { background: rgba(34,197,94,.15); border-color: rgba(34,197,94,.5); color: var(--green); }
.pb-start:hover { background: rgba(34,197,94,.28); }
.pb-stop  { background: rgba(239,68,68,.12); border-color: rgba(239,68,68,.4); color: var(--red); }
.pb-stop:hover  { background: rgba(239,68,68,.22); }
.scenario-info { display: flex; align-items: center; gap: 8px; font-size: 11px; color: var(--text-dim); }
.scenario-info strong { color: var(--accent); }
.playback-status { font-size: 10px; font-weight: 700; padding: 1px 7px; border-radius: 8px; }
.pb-playing { background: rgba(34,197,94,.15); color: var(--green); border: 1px solid rgba(34,197,94,.3); }
.pb-paused  { background: rgba(245,165,36,.12); color: var(--amber); border: 1px solid rgba(245,165,36,.3); }
</style>
