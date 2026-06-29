<template>
  <div class="tab-dashboard">
    <!-- ── Sol kolon ── -->
    <div class="col-left">
      <!-- Robot Durumu -->
      <Card>
        <template #header><SectionTitle :icon="Bot">Robot Durumu</SectionTitle></template>
        <div :class="['fsm-card', fsmBg]">
          <div class="fsm-icon-wrap">
            <Forklift :size="28" />
          </div>
          <div class="fsm-info">
            <div class="fsm-big">{{ FSM_TR[s.mission?.fsm] || s.mission?.fsm }}</div>
            <div class="fsm-step">{{ s.mission?.step }}</div>
          </div>
        </div>
        <div class="fsm-ids" v-if="s.mission?.pickup">
          <span class="id-badge id-pickup"><MoveDown :size="11" /> {{ s.mission.pickup }}</span>
          <ArrowRight :size="12" class="arrow-icon" />
          <span class="id-badge id-dropoff"><MoveUp :size="11" /> {{ s.mission.dropoff }}</span>
        </div>
        <div class="row-divider" />
        <LabelRow label="Görev ID">{{ s.mission?.id || '—' }}</LabelRow>
        <LabelRow label="Görev Süresi">{{ fmtTime(s.mission?.elapsed_s) }}</LabelRow>
        <LabelRow label="Tahmini Bitiş">{{ estimatedFinish }}</LabelRow>
      </Card>

      <!-- Robot Bilgileri -->
      <Card>
        <template #header><SectionTitle :icon="Navigation">Robot Bilgileri</SectionTitle></template>
        <LabelRow label="Konum (X, Y)">
          <span>{{ fmt(s.pose?.x) }} m, {{ fmt(s.pose?.y) }} m</span>
        </LabelRow>
        <LabelRow label="Yön Açısı (θ)">{{ fmt(s.pose?.theta_deg) }}°</LabelRow>
        <LabelRow label="Hız">{{ fmt(s.pose?.speed) }} m/s</LabelRow>
        <LabelRow label="Yük Durumu">
          <StatPill :variant="s.mission?.pickup ? 'warn' : 'default'">
            {{ s.mission?.pickup ? 'YÜKLÜ' : 'YÜKSÜZ' }}
          </StatPill>
        </LabelRow>
        <LabelRow label="Rota Sapması">
          <span :class="deviationCls">{{ fmt(s.pose?.path_deviation_cm) }} cm</span>
        </LabelRow>
      </Card>

      <!-- Batarya & Güç (2B: sol kolona taşındı) -->
      <Card>
        <template #header><SectionTitle :icon="BatteryMedium">Batarya & Güç</SectionTitle></template>
        <div class="batt-display">
          <div class="batt-big-wrap">
            <div class="batt-big-bar" :class="battCls" :style="{ width: battPct + '%' }" />
            <span class="batt-big-pct">{{ battPct }} %</span>
          </div>
        </div>
        <LabelRow label="Gerilim">{{ fmt(s.battery?.voltage) }} V</LabelRow>
        <LabelRow label="Akım">{{ fmt(s.battery?.current) }} A</LabelRow>
        <LabelRow label="Tahmini Süre">{{ s.battery?.eta_min || '—' }} dk</LabelRow>
        <LabelRow label="Güç Durumu">
          <StatPill :variant="s.battery?.status === 'normal' ? 'success' : 'warn'">
            {{ s.battery?.status === 'normal' ? 'NORMAL' : (s.battery?.status || '—').toUpperCase() }}
          </StatPill>
        </LabelRow>
      </Card>
    </div>

    <!-- ── Orta kolon ── -->
    <div class="col-center">
      <!-- Harita (büyük) -->
      <Card class="map-card">
        <template #header>
          <div class="map-header">
            <SectionTitle :icon="MapIcon">Anlık Harita ve Konum</SectionTitle>
            <span :class="['nav-pill', s.nav?.mode === 'line_follow' ? 'nav-line' : 'nav-nav2']">
              <ZapIcon v-if="s.nav?.mode === 'line_follow'" :size="11" />
              <Compass v-else :size="11" />
              {{ s.nav?.mode === 'line_follow' ? 'Çizgi Takibi' : 'Nav2' }}
            </span>
          </div>
        </template>
        <MiniMap :state="s" />
        <div class="map-legend">
          <span class="leg-item"><span class="leg-dot" style="background:#3b82f6" />Başlangıç</span>
          <span class="leg-item"><span class="leg-dot" style="background:#3b82f6" />Rota</span>
          <span class="leg-item"><span class="leg-dot" style="background:#f5a524" />Robot</span>
          <span class="leg-item"><span class="leg-dot leg-diamond" style="background:#ef4444" />QR</span>
          <span class="leg-item"><span class="leg-dot" style="background:#f5a524" />Kapı</span>
        </div>
      </Card>

      <!-- 2C: Alt satır — Güvenlik | Son Mesajlar yan yana -->
      <div class="bottom-row">
        <!-- Güvenlik (2A+2C: kompakt, sadece Engel + Sistem Sağlığı) -->
        <Card class="safety-card">
          <template #header><SectionTitle :icon="ShieldCheck">Güvenlik</SectionTitle></template>
          <div class="safety-col">
            <div class="safety-item">
              <div class="safety-icon-wrap" :class="s.safety?.obstacle === 'danger' ? 'si-red' : 'si-dim'">
                <ScanLine :size="15" />
              </div>
              <div class="safety-item__text">
                <span class="safety-item__label">Engel</span>
                <StatPill :variant="s.safety?.obstacle === 'danger' ? 'danger' : 'success'" :dot="true">
                  {{ s.safety?.obstacle === 'danger' ? 'YAKINDA' : 'Serbest' }}
                </StatPill>
              </div>
            </div>
            <div class="safety-item">
              <div class="safety-icon-wrap" :class="healthCls">
                <ActivitySquare :size="15" />
              </div>
              <div class="safety-item__text">
                <span class="safety-item__label">Sistem</span>
                <StatPill :variant="s.safety?.system_health === 'normal' ? 'success' : s.safety?.system_health === 'warn' ? 'warn' : 'danger'">
                  {{ HEALTH[s.safety?.system_health] || s.safety?.system_health }}
                </StatPill>
              </div>
            </div>
          </div>
        </Card>

        <!-- Son Mesajlar (2C: orta alta taşındı) -->
        <Card class="msg-card">
          <template #header>
            <div class="msg-header">
              <SectionTitle :icon="MessageSquare">Son Mesajlar</SectionTitle>
              <span class="msg-count-chip">{{ (s.messages || []).length }}</span>
            </div>
          </template>
          <div class="msg-list">
            <div v-for="(m, i) in (s.messages || []).slice(0, 12)" :key="i" class="msg-row">
              <span :class="['dir-chip', m.dir === 'plc2robot' ? 'chip-green' : 'chip-blue']">
                {{ m.dir === 'plc2robot' ? 'PLC' : 'ROBOT' }}
              </span>
              <span class="msg-ts">{{ m.ts }}</span>
              <span class="msg-text">{{ m.text }}</span>
            </div>
            <div v-if="!s.messages?.length" class="empty-state">Mesaj yok</div>
          </div>
        </Card>
      </div>
    </div>

    <!-- ── Sağ kolon ── -->
    <div class="col-right">
      <!-- QR -->
      <Card>
        <template #header><SectionTitle :icon="QrCode">QR Bilgisi</SectionTitle></template>
        <div class="qr-status-row">
          <StatPill :variant="qrVariant" :dot="true">{{ QR_TR[s.qr?.status] || s.qr?.status }}</StatPill>
        </div>
        <template v-if="s.qr?.id">
          <LabelRow label="Okunan QR">{{ s.qr.id }}</LabelRow>
          <LabelRow label="X (m)">{{ fmt(s.qr.x) }}</LabelRow>
          <LabelRow label="Y (m)">{{ fmt(s.qr.y) }}</LabelRow>
          <LabelRow label="Açı (°)">{{ fmt(s.qr.angle_deg) }}</LabelRow>
          <LabelRow label="Mesafe">{{ fmt(s.qr.distance_m) }} m</LabelRow>
        </template>
        <div v-else class="empty-state">QR bekleniyor</div>
      </Card>

      <!-- PLC -->
      <Card>
        <template #header><SectionTitle :icon="ServerIcon">PLC Durumu</SectionTitle></template>
        <div class="plc-conn-row">
          <StatPill :variant="s.plc?.connected ? 'success' : 'default'" :dot="true">
            {{ s.plc?.connected ? 'BAĞLI' : 'Bağlantı Yok' }}
          </StatPill>
          <span v-if="s.plc?.signal" class="signal-bars">
            <span v-for="i in 5" :key="i" :class="['sig-bar', i <= (s.plc?.signal || 0) ? 'sig-active' : '']" :style="{ height: (5 + i*3) + 'px' }" />
          </span>
        </div>
        <template v-if="s.plc?.connected">
          <LabelRow label="Son Mesaj">{{ plcLastTs }}</LabelRow>
          <LabelRow label="Kapı İzni">
            <StatPill :variant="doorVariant">{{ DOOR_TR[s.plc?.door_permission] }}</StatPill>
          </LabelRow>
          <LabelRow label="Beklenen Komut">{{ s.plc?.expected_cmd || 'YOK' }}</LabelRow>
        </template>
      </Card>

      <!-- 2D: Aktif Durum (eski 8-madde lejant yerine) -->
      <Card>
        <template #header><SectionTitle :icon="Activity">Aktif Durum</SectionTitle></template>
        <div class="active-state-card" :class="fsmBg">
          <div :class="['active-state-led', FSM_LED[s.mission?.fsm] || 'led-dim']" />
          <div class="active-state-body">
            <div class="active-state-name">{{ FSM_TR[s.mission?.fsm] || '—' }}</div>
            <div class="active-state-desc">{{ FSM_DESC[s.mission?.fsm] || '' }}</div>
          </div>
        </div>
      </Card>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import {
  Bot, Forklift, Navigation, Map as MapIcon, ShieldCheck,
  QrCode, Server as ServerIcon, MessageSquare, BatteryMedium,
  MoveDown, MoveUp, ArrowRight, ScanLine,
  ActivitySquare, Zap as ZapIcon, Compass,
  Activity,
} from 'lucide-vue-next'
import Card from './Card.vue'
import SectionTitle from './SectionTitle.vue'
import StatPill from './StatPill.vue'
import LabelRow from './LabelRow.vue'
import MiniMap from './MiniMap.vue'

const props = defineProps({ state: Object })
const s = computed(() => props.state || {})

const FSM_TR = {
  idle: 'Boşta', task_processing: 'Görev İşleniyor',
  moving_empty: 'Boş Hareket', moving_loaded: 'Yüklü Hareket',
  waiting_plc: 'PLC Bekliyor', returning_home: 'Eve Dönüyor',
  error: 'HATA', emergency_stop: 'ACİL STOP',
}
const FSM_DESC = {
  idle:            'Göreve hazır, yeni komut bekleniyor',
  task_processing: 'Görev alındı, rota planlanıyor',
  moving_empty:    'Yüksüz olarak alma noktasına gidiyor',
  moving_loaded:   'Yüklü olarak bırakma noktasına gidiyor',
  waiting_plc:     'PLC\'den kapı / izin komutu bekleniyor',
  returning_home:  'Görev tamamlandı, başlangıca dönüyor',
  error:           'Hata durumu — müdahale gerekebilir',
  emergency_stop:  'Acil durdurma aktif',
}
const FSM_BG = {
  idle: 'fsm-idle', task_processing: 'fsm-task',
  moving_empty: 'fsm-move', moving_loaded: 'fsm-loaded',
  waiting_plc: 'fsm-wait', returning_home: 'fsm-return',
  error: 'fsm-error', emergency_stop: 'fsm-error',
}
const FSM_LED = {
  idle: 'led-dim', task_processing: 'led-info',
  moving_empty: 'led-green', moving_loaded: 'led-info',
  waiting_plc: 'led-amber', returning_home: 'led-info',
  error: 'led-red', emergency_stop: 'led-red',
}
const fsmBg = computed(() => FSM_BG[s.value.mission?.fsm] || 'fsm-idle')

const QR_TR   = { read: 'Okundu', searching: 'Aranıyor', none: 'Bekliyor' }
const DOOR_TR = { granted: 'VERİLDİ', waiting: 'BEKLİYOR', none: '—' }
const HEALTH  = { normal: 'Normal', warn: 'Uyarı', error: 'Hata' }

const battPct = computed(() => Math.round(s.value.battery?.percent ?? 100))
const battCls = computed(() => battPct.value < 10 ? 'batt-red' : battPct.value < 20 ? 'batt-amber' : 'batt-green')

const deviationCls = computed(() => {
  const d = s.value.pose?.path_deviation_cm || 0
  return d > 10 ? 'val-red' : d > 7 ? 'val-amber' : ''
})
const qrVariant = computed(() => {
  const st = s.value.qr?.status
  return st === 'read' ? 'success' : st === 'searching' ? 'warn' : 'default'
})
const doorVariant = computed(() => {
  const d = s.value.plc?.door_permission
  return d === 'granted' ? 'success' : d === 'waiting' ? 'warn' : 'default'
})
const healthCls = computed(() => {
  const h = s.value.safety?.system_health
  return h === 'error' ? 'si-red' : h === 'warn' ? 'si-amber' : 'si-dim'
})
const plcLastTs = computed(() => {
  const m = (s.value.messages || [])[0]
  return m ? m.ts : '—'
})
const estimatedFinish = computed(() => {
  const elapsed = s.value.mission?.timer?.elapsed_s || 0
  const target  = s.value.mission?.timer?.target_s  || 1800
  if (!elapsed) return '—'
  const remaining = Math.max(0, target - elapsed)
  const now = new Date()
  now.setSeconds(now.getSeconds() + remaining)
  return now.toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit' })
})

function fmt(v, d = 2) { return (v ?? 0).toFixed(d) }
function fmtTime(sec) {
  if (!sec && sec !== 0) return '--:--'
  const m = Math.floor(sec / 60), ss = Math.floor(sec % 60)
  return `${String(m).padStart(2,'0')}:${String(ss).padStart(2,'0')}`
}
</script>

<style scoped>
.tab-dashboard {
  display: grid;
  grid-template-columns: 190px 1fr 200px;
  gap: 10px;
  height: 100%;
  overflow: hidden;
}
.col-left  { display: flex; flex-direction: column; gap: 10px; overflow-y: auto; }
.col-right { display: flex; flex-direction: column; gap: 10px; overflow-y: auto; }
.col-center {
  display: flex;
  flex-direction: column;
  gap: 10px;
  overflow: hidden;
  min-height: 0;
}
.map-card { flex: 1 1 0; min-height: 0; overflow: hidden; }

/* 2C: Alt satır — Güvenlik | Son Mesajlar */
.bottom-row {
  display: grid;
  grid-template-columns: 170px 1fr;
  gap: 10px;
  flex-shrink: 0;
}
.safety-card { overflow: hidden; }
.msg-card    { overflow: hidden; min-width: 0; }

/* FSM card */
.fsm-card {
  display: flex; align-items: center; gap: 10px;
  padding: 8px 10px; border-radius: var(--radius-sm); margin-bottom: 8px;
}
.fsm-idle   { background: rgba(125,138,160,.08); }
.fsm-task   { background: rgba(59,130,246,.1);   }
.fsm-move   { background: rgba(34,197,94,.1);    }
.fsm-loaded { background: rgba(99,102,241,.1);   }
.fsm-wait   { background: rgba(245,165,36,.1);   }
.fsm-return { background: rgba(168,85,247,.1);   }
.fsm-error  { background: rgba(239,68,68,.1);    }
.fsm-icon-wrap {
  width: 44px; height: 44px; border-radius: 50%; flex-shrink: 0;
  display: flex; align-items: center; justify-content: center;
  background: rgba(245,165,36,.15); color: var(--amber);
}
.fsm-info { flex: 1; min-width: 0; }
.fsm-big  { font-size: 16px; font-weight: 700; color: var(--text); }
.fsm-step {
  font-size: 10px; color: var(--text-dim); margin-top: 2px;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.fsm-ids    { display: flex; align-items: center; gap: 5px; margin-bottom: 8px; }
.id-badge   { display: flex; align-items: center; gap: 3px; padding: 2px 8px; border-radius: 10px; font-size: 11px; font-weight: 700; }
.id-pickup  { background: rgba(239,68,68,.15); color: var(--red); }
.id-dropoff { background: rgba(59,130,246,.15); color: var(--accent); }
.arrow-icon { color: var(--text-dim); flex-shrink: 0; }
.row-divider { height: 1px; background: var(--border); margin: 6px 0; }

/* Map */
.map-header { display: flex; align-items: center; justify-content: space-between; }
.nav-pill { display: inline-flex; align-items: center; gap: 4px; padding: 2px 8px; border-radius: 10px; font-size: 10px; font-weight: 700; }
.nav-nav2 { background: rgba(59,130,246,.15); color: var(--accent); }
.nav-line { background: rgba(34,197,94,.15);  color: var(--green); }
.map-legend { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 6px; padding-top: 6px; border-top: 1px solid var(--border); }
.leg-item { display: flex; align-items: center; gap: 4px; font-size: 10px; color: var(--text-dim); }
.leg-dot  { width: 7px; height: 7px; border-radius: 50%; display: inline-block; }
.leg-diamond { border-radius: 1px; transform: rotate(45deg); }

/* Güvenlik (kompakt — 2 öğe dikey) */
.safety-col   { display: flex; flex-direction: column; gap: 8px; }
.safety-item  { display: flex; align-items: center; gap: 7px; }
.safety-icon-wrap {
  width: 28px; height: 28px; border-radius: 7px; flex-shrink: 0;
  display: flex; align-items: center; justify-content: center;
}
.si-dim   { background: rgba(125,138,160,.1); color: var(--text-dim); }
.si-red   { background: rgba(239,68,68,.15);  color: var(--red); }
.si-amber { background: rgba(245,165,36,.15); color: var(--amber); }
.safety-item__text  { display: flex; flex-direction: column; gap: 2px; }
.safety-item__label { font-size: 10px; color: var(--text-dim); text-transform: uppercase; letter-spacing: .4px; }

/* Son Mesajlar */
.msg-header     { display: flex; align-items: center; justify-content: space-between; }
.msg-count-chip { background: var(--panel-2); border: 1px solid var(--border); border-radius: 10px; padding: 1px 7px; font-size: 10px; color: var(--text-dim); }
.msg-list       { display: flex; flex-direction: column; gap: 4px; overflow-y: auto; max-height: 110px; }
.msg-row        { display: flex; align-items: flex-start; gap: 5px; font-size: 11px; }
.dir-chip       { padding: 1px 6px; border-radius: 8px; font-size: 9px; font-weight: 700; flex-shrink: 0; white-space: nowrap; }
.chip-green { background: rgba(34,197,94,.15);  color: var(--green); border: 1px solid rgba(34,197,94,.3); }
.chip-blue  { background: rgba(59,130,246,.15); color: var(--accent);border: 1px solid rgba(59,130,246,.3); }
.msg-ts   { color: var(--text-dim); flex-shrink: 0; font-variant-numeric: tabular-nums; }
.msg-text { color: var(--text); flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.empty-state { font-size: 12px; color: var(--text-dim); padding: 6px 0; }

/* QR */
.qr-status-row { margin-bottom: 6px; }

/* PLC */
.plc-conn-row { display: flex; align-items: center; justify-content: space-between; margin-bottom: 7px; }
.signal-bars  { display: flex; align-items: flex-end; gap: 2px; height: 14px; }
.sig-bar      { width: 3px; border-radius: 2px; background: var(--border); }
.sig-active   { background: var(--green); }

/* 2D: Aktif Durum card */
.active-state-card {
  display: flex; align-items: flex-start; gap: 10px;
  padding: 10px; border-radius: var(--radius-sm);
}
.active-state-led {
  width: 12px; height: 12px; border-radius: 50%; flex-shrink: 0; margin-top: 3px;
}
.led-dim   { background: var(--text-dim); }
.led-info  { background: var(--accent);   box-shadow: 0 0 6px var(--accent); }
.led-green { background: var(--green);    box-shadow: 0 0 6px var(--green); }
.led-amber { background: var(--amber);    box-shadow: 0 0 6px var(--amber); }
.led-red   { background: var(--red);      box-shadow: 0 0 6px var(--red); animation: pulse .8s infinite; }
.active-state-body { flex: 1; min-width: 0; }
.active-state-name { font-size: 15px; font-weight: 700; color: var(--text); margin-bottom: 4px; }
.active-state-desc { font-size: 11px; color: var(--text-dim); line-height: 1.4; }

/* Battery */
.batt-display   { margin-bottom: 8px; }
.batt-big-wrap  { position: relative; height: 24px; background: var(--panel-2); border-radius: 5px; overflow: hidden; border: 1px solid var(--border); }
.batt-big-bar   { height: 100%; border-radius: 5px; transition: width .5s; }
.batt-green { background: linear-gradient(90deg, #16a34a, var(--green)); }
.batt-amber { background: linear-gradient(90deg, #d97706, var(--amber)); }
.batt-red   { background: linear-gradient(90deg, #b91c1c, var(--red)); }
.batt-big-pct { position: absolute; right: 7px; top: 50%; transform: translateY(-50%); font-size: 12px; font-weight: 700; color: #fff; }

/* Value colors */
.val-green { color: var(--green) !important; font-weight: 700; }
.val-red   { color: var(--red)   !important; font-weight: 700; }
.val-amber { color: var(--amber) !important; font-weight: 700; }
</style>
