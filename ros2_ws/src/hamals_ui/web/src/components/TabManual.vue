<template>
  <div class="tab-manual">
    <!-- Lock overlay -->
    <div v-if="isLocked" class="lock-overlay">
      <div class="lock-box">
        <div class="lock-icon-wrap">
          <Lock :size="36" />
        </div>
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

    <!-- Debug mode bar (only in mock, when unlocked) -->
    <div v-if="isMock && !isLocked" class="debug-mode-bar">
      <span class="debug-mode-label">DEBUG: Manuel Mod Aktif</span>
      <button class="debug-auto-btn" @click="toggleSwitch">OTOMATİK'e Dön</button>
    </div>

    <div :class="['manual-content', isLocked ? 'content-locked' : '']">
      <!-- D-pad -->
      <Card>
        <template #header><SectionTitle :icon="Gamepad2">Hareket Kontrolü</SectionTitle></template>
        <div class="speed-row">
          <span class="speed-label">Hız</span>
          <input class="speed-range" type="range" min="10" max="100" step="5"
            v-model="speedPct" :disabled="isLocked" />
          <span class="speed-val">{{ speedPct }}%</span>
        </div>
        <div class="dpad-container">
          <div class="dpad">
            <button class="dpad-btn dpad-up"
              @mousedown="startCmd(speed, 0)" @mouseup="stop" @mouseleave="stop"
              :disabled="isLocked">
              <ArrowUp :size="22" />
            </button>
            <button class="dpad-btn dpad-left"
              @mousedown="startCmd(0, turnRate)" @mouseup="stop" @mouseleave="stop"
              :disabled="isLocked">
              <ArrowLeft :size="22" />
            </button>
            <button class="dpad-btn dpad-stop" @click="stop" :disabled="isLocked">
              <Square :size="18" />
              <span class="stop-label">DUR</span>
            </button>
            <button class="dpad-btn dpad-right"
              @mousedown="startCmd(0, -turnRate)" @mouseup="stop" @mouseleave="stop"
              :disabled="isLocked">
              <ArrowRight :size="22" />
            </button>
            <button class="dpad-btn dpad-down"
              @mousedown="startCmd(-speed, 0)" @mouseup="stop" @mouseleave="stop"
              :disabled="isLocked">
              <ArrowDown :size="22" />
            </button>
          </div>
        </div>
        <div class="vel-display">
          <span>v: <strong>{{ curLinear.toFixed(2) }}</strong> m/s</span>
          <span>ω: <strong>{{ curAngular.toFixed(2) }}</strong> rad/s</span>
        </div>
      </Card>

      <!-- Lift -->
      <Card>
        <template #header><SectionTitle :icon="ArrowUpDown">Çatal Kontrolü</SectionTitle></template>
        <div class="lift-buttons">
          <button class="lift-btn lift-up" @click="sendLift('up')" :disabled="isLocked">
            <MoveUp :size="18" /> KALDIR
          </button>
          <button class="lift-btn lift-down" @click="sendLift('down')" :disabled="isLocked">
            <MoveDown :size="18" /> İNDİR
          </button>
        </div>
        <div class="tower-section">
          <SectionTitle>Kule Yüksekliği</SectionTitle>
          <div class="tower-display">
            <div class="tower-bar-outer">
              <div class="tower-bar-inner" :style="{ height: towerHeight + '%' }" />
            </div>
            <span class="tower-val">{{ towerHeight }} cm</span>
          </div>
          <input class="tower-range" type="range" min="0" max="100" step="1"
            v-model="towerHeight" :disabled="isLocked" orient="vertical" />
        </div>
      </Card>

      <!-- Camera & speed -->
      <Card>
        <template #header>
          <div class="cam-header">
            <SectionTitle :icon="CameraIcon">Aktif Kamera</SectionTitle>
            <div class="cam-toggle">
              <button :class="['cam-btn', s.cameras?.active !== 'back' ? 'cam-active' : '']">ÖN</button>
              <button :class="['cam-btn', s.cameras?.active === 'back' ? 'cam-active' : '']">ARKA</button>
            </div>
          </div>
        </template>
        <div class="stream-area">
          <img
            v-if="activeCamUrl"
            :src="activeCamUrl"
            class="cam-img"
            onerror="this.style.display='none'"
            alt="Kamera akışı"
          />
          <div v-else class="no-stream">
            <CameraOff :size="32" />
            <span>Kamera akışı mevcut değil</span>
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
import { computed, ref, onUnmounted } from 'vue'
import {
  Lock, Gamepad2, ArrowUp, ArrowDown, ArrowLeft, ArrowRight,
  Square, ArrowUpDown, MoveUp, MoveDown,
  Camera as CameraIcon, CameraOff,
} from 'lucide-vue-next'
import Card from './Card.vue'
import SectionTitle from './SectionTitle.vue'

const props = defineProps({ state: Object, isMock: Boolean })
const emit = defineEmits(['send-cmd'])
const s = computed(() => props.state || {})

const isLocked = computed(() => s.value.switch?.mode !== 'manual')

function toggleSwitch() {
  const target = isLocked.value ? 'manual' : 'auto'
  emit('send-cmd', { type: 'switch_mode', payload: target })
}

const speedPct = ref(40)
const towerHeight = ref(0)
const curLinear = ref(0)
const curAngular = ref(0)

const speed = computed(() => speedPct.value / 100 * 0.5)
const turnRate = computed(() => 0.5)

let cmdInterval = null

function startCmd(linear, angular) {
  if (isLocked.value) return
  curLinear.value = linear
  curAngular.value = angular
  emit('send-cmd', { type: 'teleop', payload: { linear, angular } })
  cmdInterval = setInterval(() => {
    emit('send-cmd', { type: 'teleop', payload: { linear, angular } })
  }, 100)
}

function stop() {
  clearInterval(cmdInterval)
  cmdInterval = null
  curLinear.value = 0
  curAngular.value = 0
  emit('send-cmd', { type: 'teleop', payload: { linear: 0, angular: 0 } })
}

function sendLift(action) {
  emit('send-cmd', { type: 'lift', payload: { action } })
}

const activeCamUrl = computed(() => {
  const active = s.value.cameras?.active
  return active === 'back' ? s.value.cameras?.back_url : s.value.cameras?.front_url
})

onUnmounted(() => clearInterval(cmdInterval))
</script>

<style scoped>
.tab-manual { position: relative; height: 100%; overflow: hidden; }
.manual-content { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 10px; height: 100%; }
.content-locked { opacity: .25; pointer-events: none; user-select: none; }

/* Lock overlay */
.lock-overlay {
  position: absolute; inset: 0; z-index: 20;
  background: rgba(10,14,22,.8);
  display: flex; align-items: center; justify-content: center;
  backdrop-filter: blur(4px);
}
.lock-box {
  text-align: center; padding: 40px 48px;
  background: var(--panel); border: 1px solid rgba(245,165,36,.5);
  border-radius: var(--radius);
  box-shadow: 0 0 40px rgba(245,165,36,.15);
}
.lock-icon-wrap {
  width: 72px; height: 72px; border-radius: 50%; margin: 0 auto 20px;
  background: rgba(245,165,36,.15); border: 2px solid rgba(245,165,36,.5);
  display: flex; align-items: center; justify-content: center;
  color: var(--amber);
}
.lock-title { font-size: 22px; font-weight: 700; color: var(--amber); margin-bottom: 10px; }
.lock-msg   { font-size: 14px; color: var(--text-dim); line-height: 1.7; }
.lock-mode  { color: var(--amber); font-weight: 700; }
.debug-unlock-btn {
  margin-top: 18px;
  padding: 8px 20px;
  background: rgba(59,130,246,.18); border: 1px solid rgba(59,130,246,.5);
  border-radius: var(--radius-sm); color: var(--accent);
  font-size: 13px; font-weight: 700; font-family: inherit; cursor: pointer;
  transition: background .15s;
}
.debug-unlock-btn:hover { background: rgba(59,130,246,.3); }

/* Debug mode bar */
.debug-mode-bar {
  display: flex; align-items: center; justify-content: space-between;
  padding: 6px 12px; margin-bottom: 8px;
  background: rgba(59,130,246,.08); border: 1px solid rgba(59,130,246,.25);
  border-radius: var(--radius-sm); flex-shrink: 0;
}
.debug-mode-label { font-size: 11px; font-weight: 700; color: var(--accent); }
.debug-auto-btn {
  padding: 3px 12px; border-radius: 10px; font-size: 11px; font-weight: 700;
  background: rgba(245,165,36,.15); border: 1px solid rgba(245,165,36,.4);
  color: var(--amber); cursor: pointer; font-family: inherit; transition: background .15s;
}
.debug-auto-btn:hover { background: rgba(245,165,36,.28); }

/* Speed row */
.speed-row   { display: flex; align-items: center; gap: 10px; margin-bottom: 16px; }
.speed-label { font-size: 12px; color: var(--text-dim); flex-shrink: 0; }
.speed-range { flex: 1; accent-color: var(--accent); cursor: pointer; }
.speed-val   { font-size: 13px; font-weight: 700; color: var(--accent); min-width: 36px; text-align: right; }

/* D-pad */
.dpad-container { display: flex; justify-content: center; margin-bottom: 12px; }
.dpad {
  display: grid;
  grid-template-columns: repeat(3, 60px);
  grid-template-rows: repeat(3, 60px);
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
  background: rgba(239,68,68,.1); border-color: rgba(239,68,68,.4); color: var(--red);
}
.dpad-stop:hover:not(:disabled) { background: rgba(239,68,68,.2); border-color: var(--red); color: var(--red); }
.stop-label { font-size: 9px; font-weight: 700; letter-spacing: .5px; }
.dpad-right { grid-column: 3; grid-row: 2; }
.dpad-down  { grid-column: 2; grid-row: 3; }
.vel-display { display: flex; justify-content: center; gap: 20px; font-size: 12px; color: var(--text-dim); font-variant-numeric: tabular-nums; }
.vel-display strong { color: var(--text); }

/* Lift */
.lift-buttons { display: flex; flex-direction: column; gap: 10px; margin-bottom: 16px; }
.lift-btn {
  display: flex; align-items: center; justify-content: center; gap: 8px;
  padding: 16px; border-radius: var(--radius-sm); border: 1px solid var(--border);
  background: var(--panel-2); color: var(--text-dim); font-size: 15px; font-weight: 700;
  cursor: pointer; font-family: inherit; transition: all .15s;
}
.lift-up:hover:not(:disabled)   { background: rgba(34,197,94,.1); color: var(--green); border-color: var(--green); }
.lift-down:hover:not(:disabled) { background: rgba(239,68,68,.1); color: var(--red);   border-color: var(--red); }
.lift-btn:disabled { opacity: .35; cursor: default; }

/* Tower */
.tower-section { margin-top: 8px; }
.tower-display { display: flex; align-items: center; gap: 12px; margin: 8px 0; }
.tower-bar-outer {
  width: 16px; height: 80px; background: var(--panel-2);
  border-radius: 4px; overflow: hidden; border: 1px solid var(--border);
  display: flex; flex-direction: column; justify-content: flex-end;
}
.tower-bar-inner { width: 100%; background: var(--accent); transition: height .3s; border-radius: 4px; }
.tower-val { font-size: 20px; font-weight: 700; color: var(--accent); font-variant-numeric: tabular-nums; }
.tower-range { width: 100%; accent-color: var(--accent); cursor: pointer; }

/* Camera */
.cam-header { display: flex; align-items: center; justify-content: space-between; }
.cam-toggle { display: flex; gap: 4px; }
.cam-btn {
  padding: 3px 10px; border-radius: 10px; font-size: 11px; font-weight: 700;
  border: 1px solid var(--border); background: var(--panel-2); color: var(--text-dim);
  cursor: pointer; transition: all .15s;
}
.cam-btn.cam-active { background: rgba(59,130,246,.15); color: var(--accent); border-color: var(--accent); }
.stream-area {
  min-height: 160px; border-radius: var(--radius-sm); overflow: hidden;
  background: var(--panel-2); border: 1px solid var(--border);
  display: flex; align-items: center; justify-content: center; margin-bottom: 12px;
}
.cam-img  { width: 100%; height: auto; display: block; }
.no-stream { display: flex; flex-direction: column; align-items: center; gap: 10px; padding: 32px; color: var(--text-dim); font-size: 13px; }
.speed-big-section { display: flex; align-items: center; justify-content: space-between; padding-top: 10px; border-top: 1px solid var(--border); }
.speed-big-label { font-size: 11px; color: var(--text-dim); text-transform: uppercase; letter-spacing: .4px; }
.speed-big-val   { font-size: 24px; font-weight: 700; color: var(--accent); font-variant-numeric: tabular-nums; }
</style>
