<template>
  <div class="tab-manual">
    <!-- Lock overlay -->
    <div v-if="isLocked" class="lock-overlay">
      <div class="lock-box">
        <div class="lock-icon-wrap"><Lock :size="36" /></div>
        <div class="lock-title">Manuel Kontrol Kilitli</div>
        <div class="lock-msg">
          Fiziksel anahtar <strong>MANUEL</strong> konumuna alınmalıdır.<br>
          Mevcut: <span class="lock-mode">{{ (s.switch?.mode || 'OTOMATİK').toUpperCase() }}</span>
        </div>
        <button v-if="isMock" class="debug-unlock-btn" @click="toggleSwitch">
          DEBUG: Anahtarı MANUEL'e Al
        </button>
      </div>
    </div>

    <!-- Debug bar (mock + unlocked) -->
    <div v-if="isMock && !isLocked" class="debug-mode-bar">
      <span class="debug-mode-label">DEBUG: Manuel Mod Aktif</span>
      <button class="debug-auto-btn" @click="toggleSwitch">OTOMATİK'e Dön</button>
    </div>

    <div :class="['manual-content', isLocked ? 'content-locked' : '']">

      <!-- ── Hareket Kontrolü ── -->
      <Card class="motion-card">
        <template #header>
          <div class="card-header-row">
            <SectionTitle :icon="Gamepad2">Hareket Kontrolü</SectionTitle>
            <!-- 3B: Hassasiyet stepper -->
            <div class="sens-stepper">
              <span class="sens-stepper__label">Hassasiyet</span>
              <button class="sens-step-btn" @click="decSens" :disabled="isLocked">−</button>
              <span class="sens-step-val">{{ stepLin.toFixed(2) }}</span>
              <button class="sens-step-btn" @click="incSens" :disabled="isLocked">+</button>
            </div>
          </div>
        </template>

        <div class="dpad-container">
          <div class="dpad">
            <button class="dpad-btn dpad-up"    @click="cmdLinear(1)"   :disabled="isLocked"><ArrowUp    :size="22" /></button>
            <button class="dpad-btn dpad-left"  @click="cmdAngular(1)"  :disabled="isLocked"><ArrowLeft  :size="22" /></button>
            <button class="dpad-btn dpad-stop"  @click="stopCmd"        :disabled="isLocked">
              <Square :size="16" /><span class="stop-label">DUR</span>
            </button>
            <button class="dpad-btn dpad-right" @click="cmdAngular(-1)" :disabled="isLocked"><ArrowRight :size="22" /></button>
            <button class="dpad-btn dpad-down"  @click="cmdLinear(-1)"  :disabled="isLocked"><ArrowDown  :size="22" /></button>
          </div>
        </div>

        <div class="vel-display">
          <span>v: <strong>{{ curLinear.toFixed(2) }}</strong> m/s</span>
          <span>ω: <strong>{{ curAngular.toFixed(2) }}</strong> rad/s</span>
        </div>
      </Card>

      <!-- ── Çatal Kontrolü ── -->
      <Card class="lift-card">
        <template #header><SectionTitle :icon="ArrowUpDown">Çatal Kontrolü</SectionTitle></template>

        <div class="lift-layout">
          <!-- Butonlar -->
          <div class="lift-buttons">
            <button class="lift-btn lift-up" @click="sendLift('up')" :disabled="isLocked">
              <MoveUp :size="18" /> KALDIR
            </button>
            <button class="lift-btn lift-down" @click="sendLift('down')" :disabled="isLocked">
              <MoveDown :size="18" /> İNDİR
            </button>
          </div>

          <!-- 3A: Yükseklik barı -->
          <div class="height-gauge">
            <div class="height-bar-track">
              <div
                class="height-bar-fill"
                :class="liftMoving ? 'bar-moving' : ''"
                :style="{ height: liftPct + '%' }"
              />
            </div>
            <div class="height-labels">
              <span class="height-label-top">MAX</span>
              <span class="height-pct-val">{{ liftPct }}%</span>
              <span class="height-label-bot">0</span>
            </div>
          </div>
        </div>

        <div class="lift-status-row">
          <span class="lift-status-label">Yükseklik</span>
          <div class="lift-status-bar-wrap">
            <div class="lift-status-bar" :style="{ width: liftPct + '%' }" :class="liftMoving ? 'bar-moving' : ''" />
          </div>
          <span class="lift-status-pct">{{ liftPct }}%</span>
        </div>
      </Card>

      <!-- ── Aktif Kamera ── -->
      <Card class="cam-card">
        <template #header>
          <div class="cam-header">
            <SectionTitle :icon="CameraIcon">Aktif Kamera</SectionTitle>
            <div class="cam-toggle">
              <button :class="['cam-btn', s.cameras?.active !== 'back' ? 'cam-active' : '']">ÖN</button>
              <button :class="['cam-btn', s.cameras?.active === 'back'  ? 'cam-active' : '']">ARKA</button>
            </div>
          </div>
        </template>
        <div class="stream-area">
          <img
            v-if="activeCamUrl" :src="activeCamUrl" class="cam-img"
            onerror="this.style.display='none'" alt="Kamera akışı"
          />
          <div v-else class="no-stream">
            <CameraOff :size="28" />
            <span>Kamera akışı yok</span>
          </div>
        </div>
        <div class="speed-big-section">
          <span class="speed-big-label">Anlık Hız</span>
          <span class="speed-big-val">{{ (s.pose?.speed || 0).toFixed(2) }} m/s</span>
        </div>
      </Card>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import {
  Lock, Gamepad2, ArrowUp, ArrowDown, ArrowLeft, ArrowRight,
  Square, ArrowUpDown, MoveUp, MoveDown,
  Camera as CameraIcon, CameraOff,
} from 'lucide-vue-next'
import Card from './Card.vue'
import SectionTitle from './SectionTitle.vue'

const props = defineProps({ state: Object, isMock: Boolean })
const emit  = defineEmits(['send-cmd'])
const s     = computed(() => props.state || {})

const isLocked = computed(() => s.value.switch?.mode !== 'manual')

function toggleSwitch() {
  emit('send-cmd', { type: 'switch_mode', payload: isLocked.value ? 'manual' : 'auto' })
}

// ── Hassasiyet stepper (3B) ──────────────────────────────────
const SENS_MIN  = 0.01
const SENS_MAX  = 0.50
const SENS_STEP = 0.01
const stepLin = ref(0.10)
const stepAng = ref(0.20)

function incSens() {
  stepLin.value = +Math.min(SENS_MAX, stepLin.value + SENS_STEP).toFixed(2)
  stepAng.value = +Math.min(SENS_MAX * 2, stepLin.value * 2).toFixed(2)
}
function decSens() {
  stepLin.value = +Math.max(SENS_MIN, stepLin.value - SENS_STEP).toFixed(2)
  stepAng.value = +Math.max(SENS_MIN * 2, stepLin.value * 2).toFixed(2)
}

// ── Latched teleop ───────────────────────────────────────────
const curLinear  = ref(0)
const curAngular = ref(0)

function clamp(v, lo, hi) { return Math.min(Math.max(v, lo), hi) }

function sendTeleop() {
  emit('send-cmd', { type: 'teleop', payload: { linear: curLinear.value, angular: curAngular.value } })
}
function cmdLinear(dir) {
  if (isLocked.value) return
  curLinear.value = +clamp(curLinear.value + dir * stepLin.value, -1, 1).toFixed(3)
  sendTeleop()
}
function cmdAngular(dir) {
  if (isLocked.value) return
  curAngular.value = +clamp(curAngular.value + dir * stepAng.value, -2, 2).toFixed(3)
  sendTeleop()
}
function stopCmd() {
  curLinear.value = curAngular.value = 0
  sendTeleop()
}

// ── Lift ─────────────────────────────────────────────────────
const liftPct    = computed(() => s.value.lift?.height_pct ?? 0)
const liftMoving = computed(() => s.value.lift?.moving ?? false)

function sendLift(action) {
  emit('send-cmd', { type: 'lift', payload: { action } })
}

// ── Camera ───────────────────────────────────────────────────
const activeCamUrl = computed(() => {
  const active = s.value.cameras?.active
  return active === 'back' ? s.value.cameras?.back_url : s.value.cameras?.front_url
})
</script>

<style scoped>
.tab-manual { position: relative; height: 100%; display: flex; flex-direction: column; overflow: hidden; }
.manual-content {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 10px;
  flex: 1;
  min-height: 0;
}
.content-locked { opacity: .25; pointer-events: none; user-select: none; }

/* Lock overlay */
.lock-overlay {
  position: absolute; inset: 0; z-index: 20;
  background: rgba(10,14,22,.82);
  display: flex; align-items: center; justify-content: center;
  backdrop-filter: blur(4px);
}
.lock-box {
  text-align: center; padding: 36px 44px;
  background: var(--panel); border: 1px solid rgba(245,165,36,.5);
  border-radius: var(--radius); box-shadow: 0 0 40px rgba(245,165,36,.12);
}
.lock-icon-wrap {
  width: 68px; height: 68px; border-radius: 50%; margin: 0 auto 18px;
  background: rgba(245,165,36,.15); border: 2px solid rgba(245,165,36,.5);
  display: flex; align-items: center; justify-content: center; color: var(--amber);
}
.lock-title { font-size: 20px; font-weight: 700; color: var(--amber); margin-bottom: 10px; }
.lock-msg   { font-size: 13px; color: var(--text-dim); line-height: 1.7; }
.lock-mode  { color: var(--amber); font-weight: 700; }
.debug-unlock-btn {
  margin-top: 16px; padding: 7px 18px;
  background: rgba(59,130,246,.18); border: 1px solid rgba(59,130,246,.5);
  border-radius: var(--radius-sm); color: var(--accent);
  font-size: 13px; font-weight: 700; font-family: inherit; cursor: pointer;
  transition: background .15s;
}
.debug-unlock-btn:hover { background: rgba(59,130,246,.3); }

/* Debug bar */
.debug-mode-bar {
  display: flex; align-items: center; justify-content: space-between;
  padding: 5px 10px; margin-bottom: 8px;
  background: rgba(59,130,246,.08); border: 1px solid rgba(59,130,246,.25);
  border-radius: var(--radius-sm); flex-shrink: 0;
}
.debug-mode-label { font-size: 11px; font-weight: 700; color: var(--accent); }
.debug-auto-btn {
  padding: 2px 10px; border-radius: 10px; font-size: 11px; font-weight: 700;
  background: rgba(245,165,36,.15); border: 1px solid rgba(245,165,36,.4);
  color: var(--amber); cursor: pointer; font-family: inherit; transition: background .15s;
}
.debug-auto-btn:hover { background: rgba(245,165,36,.28); }

/* Card header row */
.card-header-row { display: flex; align-items: center; justify-content: space-between; width: 100%; gap: 8px; }

/* ── Hassasiyet stepper (3B) ── */
.sens-stepper {
  display: flex; align-items: center; gap: 5px; flex-shrink: 0;
}
.sens-stepper__label { font-size: 10px; color: var(--text-dim); white-space: nowrap; }
.sens-step-btn {
  width: 22px; height: 22px; border-radius: 6px; font-size: 15px; font-weight: 700;
  border: 1px solid var(--border); background: var(--panel-2); color: var(--text-dim);
  cursor: pointer; font-family: inherit; display: flex; align-items: center; justify-content: center;
  transition: all .12s; line-height: 1;
}
.sens-step-btn:hover:not(:disabled) { border-color: var(--accent); color: var(--accent); }
.sens-step-btn:disabled { opacity: .35; cursor: default; }
.sens-step-val {
  min-width: 36px; text-align: center; font-size: 12px; font-weight: 700;
  color: var(--accent); font-variant-numeric: tabular-nums;
}

/* ── D-pad ── */
.dpad-container { display: flex; justify-content: center; margin: 12px 0; }
.dpad {
  display: grid;
  grid-template-columns: repeat(3, 64px);
  grid-template-rows:    repeat(3, 64px);
  gap: 6px;
}
.dpad-btn {
  border: 1px solid var(--border); border-radius: 10px;
  background: var(--panel-2); color: var(--text-dim);
  cursor: pointer; transition: background .1s, color .1s, border-color .1s;
  display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 2px;
}
.dpad-btn:hover:not(:disabled) { background: rgba(59,130,246,.15); color: var(--accent); border-color: var(--accent); }
.dpad-btn:disabled { opacity: .35; cursor: default; }
.dpad-up    { grid-column: 2; grid-row: 1; }
.dpad-left  { grid-column: 1; grid-row: 2; }
.dpad-stop  {
  grid-column: 2; grid-row: 2;
  background: rgba(239,68,68,.1); border-color: rgba(239,68,68,.35); color: var(--red);
}
.dpad-stop:hover:not(:disabled) { background: rgba(239,68,68,.2); border-color: var(--red); }
.stop-label  { font-size: 9px; font-weight: 700; letter-spacing: .5px; }
.dpad-right  { grid-column: 3; grid-row: 2; }
.dpad-down   { grid-column: 2; grid-row: 3; }
.vel-display {
  display: flex; justify-content: center; gap: 24px;
  font-size: 12px; color: var(--text-dim); font-variant-numeric: tabular-nums;
}
.vel-display strong { color: var(--text); }

/* ── Çatal Kontrolü (3A) ── */
.lift-layout { display: flex; gap: 14px; align-items: stretch; margin-bottom: 12px; }
.lift-buttons { display: flex; flex-direction: column; gap: 10px; flex: 1; }
.lift-btn {
  display: flex; align-items: center; justify-content: center; gap: 8px;
  padding: 0; height: 56px; border-radius: var(--radius-sm); border: 1px solid var(--border);
  background: var(--panel-2); color: var(--text-dim); font-size: 14px; font-weight: 700;
  cursor: pointer; font-family: inherit; transition: all .15s; flex: 1;
}
.lift-up:hover:not(:disabled)   { background: rgba(34,197,94,.1);  color: var(--green); border-color: var(--green); }
.lift-down:hover:not(:disabled) { background: rgba(239,68,68,.1);  color: var(--red);   border-color: var(--red); }
.lift-btn:disabled { opacity: .35; cursor: default; }

/* Dikey yükseklik barı */
.height-gauge { display: flex; gap: 6px; align-items: stretch; flex-shrink: 0; }
.height-bar-track {
  width: 18px; border-radius: 6px; overflow: hidden;
  background: var(--panel-2); border: 1px solid var(--border);
  display: flex; flex-direction: column; justify-content: flex-end; height: 122px;
}
.height-bar-fill {
  width: 100%; border-radius: 4px; transition: height .35s ease;
  background: linear-gradient(180deg, #22c55e 0%, #16a34a 100%);
}
.height-bar-fill.bar-moving { background: linear-gradient(180deg, #f5a524 0%, #d97706 100%); }
.height-labels {
  display: flex; flex-direction: column; justify-content: space-between;
  font-size: 9px; color: var(--text-dim); height: 122px; padding: 0 0 0 2px;
}
.height-label-top { font-weight: 700; letter-spacing: .3px; }
.height-pct-val   { font-size: 11px; font-weight: 700; color: var(--accent); text-align: center; font-variant-numeric: tabular-nums; }
.height-label-bot { font-weight: 600; }

/* Lift status (yatay bar) */
.lift-status-row {
  display: flex; align-items: center; gap: 8px;
  padding-top: 10px; border-top: 1px solid var(--border);
}
.lift-status-label { font-size: 11px; color: var(--text-dim); flex-shrink: 0; }
.lift-status-bar-wrap { flex: 1; height: 6px; background: var(--panel-2); border-radius: 3px; overflow: hidden; border: 1px solid var(--border); }
.lift-status-bar { height: 100%; border-radius: 3px; background: var(--green); transition: width .35s; }
.lift-status-bar.bar-moving { background: var(--amber); }
.lift-status-pct { font-size: 12px; font-weight: 700; color: var(--accent); font-variant-numeric: tabular-nums; min-width: 32px; text-align: right; }

/* ── Kamera ── */
.cam-card { display: flex; flex-direction: column; overflow: hidden; }
.cam-header { display: flex; align-items: center; justify-content: space-between; }
.cam-toggle { display: flex; gap: 4px; }
.cam-btn {
  padding: 2px 9px; border-radius: 9px; font-size: 11px; font-weight: 700;
  border: 1px solid var(--border); background: var(--panel-2); color: var(--text-dim);
  cursor: pointer; transition: all .15s;
}
.cam-btn.cam-active { background: rgba(59,130,246,.15); color: var(--accent); border-color: var(--accent); }
.stream-area {
  flex: 1; min-height: 0; border-radius: var(--radius-sm); overflow: hidden;
  background: var(--panel-2); border: 1px solid var(--border);
  display: flex; align-items: center; justify-content: center; margin-bottom: 10px;
}
.cam-img   { width: 100%; height: 100%; object-fit: cover; display: block; }
.no-stream { display: flex; flex-direction: column; align-items: center; gap: 8px; padding: 28px; color: var(--text-dim); font-size: 12px; }
.speed-big-section { display: flex; align-items: center; justify-content: space-between; padding-top: 8px; border-top: 1px solid var(--border); flex-shrink: 0; }
.speed-big-label { font-size: 10px; color: var(--text-dim); text-transform: uppercase; letter-spacing: .4px; }
.speed-big-val   { font-size: 22px; font-weight: 700; color: var(--accent); font-variant-numeric: tabular-nums; }

/* Card layout hints */
.motion-card { display: flex; flex-direction: column; }
.lift-card   { display: flex; flex-direction: column; }
</style>
