/**
 * Frontend-level mock data provider.
 * Replays scenario steps locally — no rosbridge needed.
 * Activated when dataSource === 'mock' (set in App.vue).
 */

import { ref } from 'vue'

const DEFAULT_NODES = [
  { name: 'hamals_controller', active: true  },
  { name: 'nav2_planner',      active: true  },
  { name: 'plc_bridge',        active: false }, // starts disconnected
  { name: 'ui_bridge',         active: true  },
  { name: 'mission_mgr',       active: true  },
  { name: 'scan_matcher',      active: true  },
  { name: 'cam_front',         active: true  },
  { name: 'cam_back',          active: true  },
]

// ── Senaryo 1: A2 → B1 (standart yarışma döngüsü) ────────────────────────────
const SCENARIO_1 = [
  {
    dt_s: 3, label: 'Sistem başlatılıyor',
    state: {
      meta: { mode: 'mock', bridge_ok: true, scenario: 'senaryo1', scenarios: ['senaryo1', 'senaryo2'] },
      connection: { robot: true, plc: false, rosbridge: true },
      switch: { mode: 'auto' },
      estop: { active: false, source: 'hw' },
      battery: { percent: 92, voltage: 24.8, current: 1.2, eta_min: 180, status: 'normal' },
      mission: { id: '25', fsm: 'idle', pickup: '', dropoff: '', step: 'Sistem başlatılıyor', elapsed_s: 0, timer: { elapsed_s: 0, target_s: 1800, limit_s: 2700 } },
      pose: { x: 0.1, y: 0.1, theta_deg: 0.0, speed: 0.0, path_deviation_cm: 0.0 },
      nav: { mode: 'nav2', current_goal: '', total_distance_m: 0, remaining_m: 0 },
      qr: { id: '', status: 'none' },
      line: { detected: false, center_px: 0, deviation_cm: 0, status: 'tracking', history: [] },
      plc: { connected: false, signal: 0, door_permission: 'none', last_msg: '' },
      sensors: { lidar: true, cam_front: true, cam_back: true, imu: true, encoder: true },
      safety: { estop: false, obstacle: 'safe', obstacle_distance_m: 3.0, system_health: 'normal', zones: { front: 'safe', left: 'safe', right: 'safe', back: 'safe' } },
      cameras: { active: 'front', front_url: 'http://robot:8081/stream?topic=/camera_front/image_raw', back_url: 'http://robot:8081/stream?topic=/camera_back/image_raw' },
      messages: [],
      errors: [],
      logs: [{ ts: '00:00:00', event: 'Sistem başlatıldı', dir: 'robot2plc' }],
      nodes: JSON.parse(JSON.stringify(DEFAULT_NODES)),
    },
  },
  {
    dt_s: 4, label: 'PLC bekleniyor',
    patch: { 'mission.fsm': 'idle', 'mission.step': 'PLC bağlantısı bekleniyor', 'mission.elapsed_s': 3 },
  },
  {
    dt_s: 3, label: 'PLC bağlandı',
    patch: {
      'mission.fsm': 'waiting_plc', 'mission.step': 'PLC bağlantısı kuruldu', 'mission.elapsed_s': 7,
      'plc.connected': true, 'plc.ip': '192.168.1.50', 'plc.port': 502, 'plc.signal': 4,
      'plc.last_msg': 'Bağlantı kuruldu', 'plc.door_permission': 'none',
      'connection.plc': true,
    },
    push: { messages: { ts: '00:00:07', dir: 'plc2robot', text: 'Bağlantı kuruldu' } },
    nodesPatch: { plc_bridge: true },
  },
  {
    dt_s: 2, label: 'Görev alındı',
    patch: {
      'mission.fsm': 'task_processing', 'mission.pickup': 'A2', 'mission.dropoff': 'B1',
      'mission.step': 'Görev alındı: A2 → B1', 'mission.elapsed_s': 10,
      'nav.mode': 'nav2', 'nav.current_goal': 'A2', 'nav.total_distance_m': 18.5, 'nav.remaining_m': 18.5,
    },
    push: { messages: { ts: '00:00:10', dir: 'plc2robot', text: 'Görev: A2→B1' } },
  },
  {
    dt_s: 5, label: 'Boş hareket D1→D2',
    patch: {
      'mission.fsm': 'moving_empty', 'mission.step': 'D2 düğümüne ilerleniyor', 'mission.elapsed_s': 16,
      'pose.x': 2.8, 'pose.y': 0.1, 'pose.theta_deg': 1.5, 'pose.speed': 0.45, 'pose.path_deviation_cm': 2.1,
      'nav.remaining_m': 9.8, 'battery.percent': 90, 'battery.current': 3.8,
    },
  },
  {
    dt_s: 3, label: 'A2 yaklaşımı — QR aranıyor',
    patch: {
      'mission.step': 'A2 yaklaşımı: QR aranıyor', 'mission.elapsed_s': 21,
      'pose.x': 3.4, 'pose.y': 0.6, 'pose.theta_deg': 88.0, 'pose.speed': 0.15, 'pose.path_deviation_cm': 3.5,
      'nav.remaining_m': 1.2, 'qr.status': 'searching', 'cameras.active': 'front',
    },
  },
  {
    dt_s: 3, label: 'QR3 okundu',
    patch: {
      'mission.step': 'q3 QR kodu okundu', 'mission.elapsed_s': 24,
      'pose.x': 3.45, 'pose.y': 1.1, 'pose.theta_deg': 89.5, 'pose.speed': 0.08, 'pose.path_deviation_cm': 1.2,
      'qr.id': 'q3', 'qr.x': -0.05, 'qr.y': 0.12, 'qr.angle_deg': -1.8, 'qr.distance_m': 0.38, 'qr.status': 'read',
      'nav.mode': 'line_follow', 'nav.remaining_m': 0.4,
    },
    push: { messages: { ts: '00:00:24', dir: 'robot2plc', text: 'q3 okundu — çizgi takibine geçiliyor' } },
  },
  {
    dt_s: 4, label: 'Çizgi takibi — A2 hizalama',
    patch: {
      'mission.step': 'Çizgi takibi ile A2 hizalanıyor', 'mission.elapsed_s': 27,
      'pose.x': 3.5, 'pose.y': 1.5, 'pose.theta_deg': 90.1, 'pose.speed': 0.05, 'pose.path_deviation_cm': 0.8,
      'line.detected': true, 'line.center_px': -8, 'line.deviation_cm': 1.6, 'line.status': 'tracking',
    },
  },
  {
    dt_s: 3, label: 'Yük alındı',
    patch: {
      'mission.fsm': 'task_processing', 'mission.step': 'Yük alındı — B1\'e gidiliyor', 'mission.elapsed_s': 34,
      'pose.speed': 0.0, 'pose.path_deviation_cm': 0.3,
      'line.center_px': 2, 'line.deviation_cm': 0.4,
      'nav.mode': 'nav2', 'nav.current_goal': 'B1', 'nav.remaining_m': 14.0,
      'cameras.active': 'back',
    },
    push: { messages: { ts: '00:00:34', dir: 'robot2plc', text: 'Yük alındı — B1\'e gidiliyor' } },
  },
  {
    dt_s: 5, label: 'Yüklü hareket',
    patch: {
      'mission.fsm': 'moving_loaded', 'mission.step': 'Kapıya yaklaşılıyor (q5)', 'mission.elapsed_s': 40,
      'pose.x': 4.8, 'pose.y': 0.1, 'pose.theta_deg': 0.5, 'pose.speed': 0.4, 'pose.path_deviation_cm': 2.3,
      'nav.remaining_m': 8.5, 'battery.percent': 88, 'battery.current': 4.2,
    },
  },
  {
    dt_s: 3, label: 'Q5 — kapı izni isteniyor',
    patch: {
      'mission.step': 'q5 okundu — kapı izni bekleniyor', 'mission.elapsed_s': 46,
      'pose.speed': 0.0,
      'qr.id': 'q5', 'qr.status': 'read', 'qr.distance_m': 0.50,
      'plc.door_permission': 'waiting', 'plc.last_msg': 'Kapı geçiş izni isteniyor',
    },
    push: { messages: { ts: '00:00:46', dir: 'robot2plc', text: 'Kapı izni isteniyor (q5)' } },
  },
  {
    dt_s: 4, label: 'Kapı izni verildi',
    patch: {
      'mission.step': 'Kapı geçiş izni verildi — geçiliyor', 'mission.elapsed_s': 52,
      'pose.x': 5.6, 'pose.speed': 0.25,
      'plc.door_permission': 'granted', 'plc.last_msg': 'Kapı geçiş izni verildi',
      'nav.remaining_m': 5.5,
    },
    push: { messages: { ts: '00:00:52', dir: 'plc2robot', text: 'Kapı geçiş izni verildi' } },
  },
  {
    dt_s: 5, label: 'B1 yaklaşımı — q9',
    patch: {
      'mission.step': 'B1 yaklaşımı: q9 QR', 'mission.elapsed_s': 62,
      'pose.x': 6.5, 'pose.y': 1.2, 'pose.theta_deg': 90.5, 'pose.speed': 0.1, 'pose.path_deviation_cm': 2.0,
      'qr.id': 'q9', 'qr.status': 'read', 'qr.distance_m': 0.45,
      'nav.mode': 'line_follow', 'nav.remaining_m': 0.3,
      'cameras.active': 'back',
      'line.detected': true, 'line.center_px': 5, 'line.deviation_cm': 1.0, 'line.status': 'tracking',
    },
  },
  {
    dt_s: 3, label: 'Yük bırakıldı B1',
    patch: {
      'mission.fsm': 'task_processing', 'mission.step': 'Yük B1\'e bırakıldı', 'mission.elapsed_s': 69,
      'pose.speed': 0.0, 'cameras.active': 'front',
      'plc.last_msg': 'Görev onaylandı',
    },
    push: { messages: { ts: '00:01:09', dir: 'robot2plc', text: 'Görev tamamlandı: A2→B1' } },
  },
  {
    dt_s: 8, label: 'Dönüş',
    patch: {
      'mission.fsm': 'returning_home', 'mission.step': 'Başlangıç noktasına dönülüyor', 'mission.elapsed_s': 72,
      'nav.mode': 'nav2', 'nav.current_goal': 'START', 'nav.remaining_m': 12.0,
      'pose.x': 5.0, 'pose.y': 0.1, 'pose.theta_deg': 180.0, 'pose.speed': 0.45, 'pose.path_deviation_cm': 2.5,
      'battery.percent': 85, 'battery.current': 3.9,
    },
  },
  {
    dt_s: 5, label: 'Başlangıca döndü',
    patch: {
      'mission.fsm': 'idle', 'mission.step': 'Başlangıç noktasında bekliyor', 'mission.elapsed_s': 85,
      'mission.pickup': '', 'mission.dropoff': '',
      'pose.x': 0.1, 'pose.y': 0.1, 'pose.theta_deg': 0.0, 'pose.speed': 0.0, 'pose.path_deviation_cm': 0.0,
      'nav.current_goal': '', 'nav.remaining_m': 0.0,
      'plc.door_permission': 'none', 'plc.last_msg': 'Bir sonraki görev bekleniyor',
      'battery.percent': 84, 'battery.current': 1.1, 'battery.eta_min': 160,
    },
    push: { messages: { ts: '00:01:25', dir: 'robot2plc', text: 'Döngü tamamlandı — bekleniyor' } },
  },
]

// ── Senaryo 2: A3 → B3 (hata enjeksiyonlu varyant) ───────────────────────────
const SCENARIO_2_NODES = [
  { name: 'hamals_controller', active: true  },
  { name: 'nav2_planner',      active: true  },
  { name: 'plc_bridge',        active: false },
  { name: 'ui_bridge',         active: true  },
  { name: 'mission_mgr',       active: true  },
  { name: 'scan_matcher',      active: false }, // başta pasif
  { name: 'cam_front',         active: true  },
  { name: 'cam_back',          active: true  },
]

const SCENARIO_2 = [
  {
    dt_s: 3, label: '[S2] Sistem başlatılıyor',
    state: {
      meta: { mode: 'mock', bridge_ok: true, scenario: 'senaryo2', scenarios: ['senaryo1', 'senaryo2'] },
      connection: { robot: true, plc: false, rosbridge: true },
      switch: { mode: 'auto' },
      estop: { active: false, source: 'hw' },
      battery: { percent: 78, voltage: 24.1, current: 1.0, eta_min: 130, status: 'normal' },
      mission: { id: '26', fsm: 'idle', pickup: '', dropoff: '', step: '[S2] Sistem başlatılıyor', elapsed_s: 0, timer: { elapsed_s: 0, target_s: 1800, limit_s: 2700 } },
      pose: { x: 0.1, y: 0.1, theta_deg: 0.0, speed: 0.0, path_deviation_cm: 0.0 },
      nav: { mode: 'nav2', current_goal: '', total_distance_m: 0, remaining_m: 0 },
      qr: { id: '', status: 'none' },
      line: { detected: false, center_px: 0, deviation_cm: 0, status: 'tracking', history: [] },
      plc: { connected: false, signal: 0, door_permission: 'none', last_msg: '' },
      sensors: { lidar: true, cam_front: true, cam_back: true, imu: true, encoder: false }, // encoder başta off
      safety: { estop: false, obstacle: 'safe', obstacle_distance_m: 3.0, system_health: 'warn', zones: { front: 'safe', left: 'safe', right: 'safe', back: 'safe' } },
      cameras: { active: 'front', front_url: 'http://robot:8081/stream?topic=/camera_front/image_raw', back_url: 'http://robot:8081/stream?topic=/camera_back/image_raw' },
      messages: [],
      errors: [{ code: 'E01', ts: '00:00:00', text: 'Enkoder başlatılamadı' }],
      logs: [{ ts: '00:00:00', event: '[S2] Sistem başlatıldı (enkoder uyarısı)', dir: 'robot2plc' }],
      nodes: JSON.parse(JSON.stringify(SCENARIO_2_NODES)),
    },
  },
  {
    dt_s: 3, label: '[S2] Enkoder kurtarıldı',
    patch: {
      'mission.step': 'Enkoder kurtarıldı — PLC bekleniyor', 'mission.elapsed_s': 3,
      'sensors.encoder': true, 'safety.system_health': 'normal',
    },
  },
  {
    dt_s: 3, label: '[S2] PLC bağlandı',
    patch: {
      'mission.fsm': 'waiting_plc', 'mission.step': '[S2] PLC bağlantısı kuruldu', 'mission.elapsed_s': 6,
      'plc.connected': true, 'plc.ip': '192.168.1.50', 'plc.port': 502, 'plc.signal': 3,
      'plc.last_msg': 'Bağlantı kuruldu', 'connection.plc': true,
    },
    push: { messages: { ts: '00:00:06', dir: 'plc2robot', text: 'Bağlantı kuruldu' } },
    nodesPatch: { plc_bridge: true, scan_matcher: true },
  },
  {
    dt_s: 2, label: '[S2] Görev: A3→B3',
    patch: {
      'mission.fsm': 'task_processing', 'mission.pickup': 'A3', 'mission.dropoff': 'B3',
      'mission.step': 'Görev alındı: A3 → B3', 'mission.elapsed_s': 9,
      'nav.current_goal': 'A3', 'nav.total_distance_m': 21.2, 'nav.remaining_m': 21.2,
    },
    push: { messages: { ts: '00:00:09', dir: 'plc2robot', text: 'Görev: A3→B3' } },
  },
  {
    dt_s: 5, label: '[S2] Boş hareket → A3',
    patch: {
      'mission.fsm': 'moving_empty', 'mission.step': 'A3\'e ilerleniyor', 'mission.elapsed_s': 14,
      'pose.x': 3.8, 'pose.y': 0.1, 'pose.theta_deg': 0.5, 'pose.speed': 0.45, 'pose.path_deviation_cm': 2.8,
      'nav.remaining_m': 12.0, 'battery.percent': 76, 'battery.current': 3.6,
    },
  },
  {
    dt_s: 3, label: '[S2] Engel algılandı!',
    patch: {
      'mission.step': 'UYARI: Engel algılandı — bekliyor', 'mission.elapsed_s': 19,
      'pose.speed': 0.0,
      'safety.obstacle': 'danger', 'safety.obstacle_distance_m': 0.4,
      'safety.zones.front': 'danger', 'safety.system_health': 'warn',
    },
    push: { messages: { ts: '00:00:19', dir: 'robot2plc', text: 'Engel algılandı — duraklatıldı' } },
  },
  {
    dt_s: 4, label: '[S2] Engel geçildi',
    patch: {
      'mission.step': 'Engel geçildi — A3\'e devam', 'mission.elapsed_s': 23,
      'pose.x': 4.2, 'pose.speed': 0.35, 'pose.path_deviation_cm': 3.1,
      'safety.obstacle': 'safe', 'safety.obstacle_distance_m': 2.5,
      'safety.zones.front': 'safe', 'safety.system_health': 'normal',
    },
    push: { messages: { ts: '00:00:23', dir: 'robot2plc', text: 'Engel geçildi — devam' } },
  },
  {
    dt_s: 3, label: '[S2] QR4 okundu',
    patch: {
      'mission.step': 'q4 QR kodu okundu', 'mission.elapsed_s': 28,
      'pose.x': 4.9, 'pose.y': 0.6, 'pose.theta_deg': 88.5, 'pose.speed': 0.08, 'pose.path_deviation_cm': 0.9,
      'qr.id': 'q4', 'qr.status': 'read', 'qr.distance_m': 0.32,
      'nav.mode': 'line_follow', 'nav.remaining_m': 0.5,
    },
    push: { messages: { ts: '00:00:28', dir: 'robot2plc', text: 'q4 okundu — çizgi takibine geçiliyor' } },
  },
  {
    dt_s: 3, label: '[S2] Yük alındı A3',
    patch: {
      'mission.fsm': 'moving_loaded', 'mission.step': 'Yük alındı — B3\'e gidiliyor', 'mission.elapsed_s': 34,
      'pose.speed': 0.0, 'nav.mode': 'nav2', 'nav.current_goal': 'B3', 'nav.remaining_m': 11.0,
      'cameras.active': 'back',
    },
    push: { messages: { ts: '00:00:34', dir: 'robot2plc', text: 'Yük alındı (A3) — B3\'e gidiliyor' } },
  },
  {
    dt_s: 5, label: '[S2] Yüklü hareket → B3',
    patch: {
      'mission.step': 'B3 istasyonuna gidiliyor', 'mission.elapsed_s': 40,
      'pose.x': 7.2, 'pose.y': 0.1, 'pose.theta_deg': 0.0, 'pose.speed': 0.42, 'pose.path_deviation_cm': 2.0,
      'nav.remaining_m': 5.5, 'battery.percent': 73, 'battery.current': 4.0,
    },
  },
  {
    dt_s: 3, label: '[S2] Yük bırakıldı B3',
    patch: {
      'mission.fsm': 'task_processing', 'mission.step': 'Yük B3\'e bırakıldı', 'mission.elapsed_s': 49,
      'pose.speed': 0.0, 'cameras.active': 'front',
      'plc.last_msg': 'Görev onaylandı (A3→B3)',
    },
    push: { messages: { ts: '00:00:49', dir: 'robot2plc', text: 'Görev tamamlandı: A3→B3' } },
  },
  {
    dt_s: 6, label: '[S2] Eve dönüş',
    patch: {
      'mission.fsm': 'returning_home', 'mission.step': 'Başlangıç noktasına dönülüyor', 'mission.elapsed_s': 52,
      'nav.mode': 'nav2', 'nav.current_goal': 'START', 'nav.remaining_m': 14.0,
      'pose.x': 5.0, 'pose.theta_deg': 180.0, 'pose.speed': 0.45,
    },
  },
  {
    dt_s: 4, label: '[S2] Başlangıca döndü',
    patch: {
      'mission.fsm': 'idle', 'mission.step': '[S2] Döngü tamamlandı — bekleniyor', 'mission.elapsed_s': 62,
      'mission.pickup': '', 'mission.dropoff': '',
      'pose.x': 0.1, 'pose.y': 0.1, 'pose.theta_deg': 0.0, 'pose.speed': 0.0, 'pose.path_deviation_cm': 0.0,
      'nav.current_goal': '', 'nav.remaining_m': 0.0,
      'battery.percent': 70, 'battery.current': 1.0, 'battery.eta_min': 100,
    },
    push: { messages: { ts: '00:01:02', dir: 'robot2plc', text: '[S2] Döngü tamamlandı' } },
  },
]

const SCENARIOS = { senaryo1: SCENARIO_1, senaryo2: SCENARIO_2 }

// ── Helpers ───────────────────────────────────────────────────────────────────
function setNested(obj, dotkey, value) {
  const parts = dotkey.split('.')
  let cur = obj
  for (let i = 0; i < parts.length - 1; i++) {
    if (cur[parts[i]] === undefined) cur[parts[i]] = {}
    cur = cur[parts[i]]
  }
  cur[parts[parts.length - 1]] = value
}

// ── Composable ────────────────────────────────────────────────────────────────
export function useMockData() {
  const state = ref(null)
  let activeScenario = 'senaryo1'
  let stepIdx = 0
  let stepStart = Date.now()
  let timer = null

  function applyStep(step) {
    if (step.state) {
      state.value = JSON.parse(JSON.stringify(step.state))
    } else if (step.patch) {
      if (!state.value) return
      const s = state.value
      for (const [k, v] of Object.entries(step.patch)) {
        setNested(s, k, v)
      }
    }
    // nodes patch (partial node active-state update)
    if (step.nodesPatch && state.value?.nodes) {
      for (const [name, active] of Object.entries(step.nodesPatch)) {
        const node = state.value.nodes.find(n => n.name === name)
        if (node) node.active = active
      }
    }
    if (step.push && state.value) {
      for (const [list, item] of Object.entries(step.push)) {
        if (!Array.isArray(state.value[list])) state.value[list] = []
        state.value[list].unshift(item)
        if (state.value[list].length > 30) state.value[list].pop()
      }
    }
    // sync timer
    if (state.value?.mission) {
      const e = state.value.mission.elapsed_s || 0
      state.value.mission.timer = { elapsed_s: e, target_s: 1800, limit_s: 2700 }
    }
  }

  function tick() {
    if (!state.value) return
    const now = Date.now()
    const steps = SCENARIOS[activeScenario]
    const step = steps[stepIdx]
    if ((now - stepStart) >= step.dt_s * 1000) {
      stepIdx = (stepIdx + 1) % steps.length
      stepStart = now
      applyStep(steps[stepIdx])
    }
  }

  function setScenario(name) {
    if (!SCENARIOS[name]) return
    activeScenario = name
    stepIdx = 0
    stepStart = Date.now()
    applyStep(SCENARIOS[name][0])
  }

  function handleCmd(cmd) {
    if (!state.value) return
    const s = state.value
    switch (cmd.type) {
      case 'teleop':
        s.pose.speed = Math.abs(cmd.payload?.linear || 0)
        break
      case 'estop':
        s.mission.fsm = 'emergency_stop'
        s.estop.active = true
        s.pose.speed = 0
        s.mission.step = 'ACİL DURDURMA — yazılımsal'
        if (timer) { clearInterval(timer); timer = null }
        break
      case 'estop_ack':
        s.estop.active = false
        s.mission.fsm = 'idle'
        s.mission.step = 'Acil durum temizlendi — hazır'
        if (!timer) timer = setInterval(tick, 200)
        break
      case 'switch_mode':
        if (cmd.payload === 'manual' || cmd.payload === 'auto') {
          s.switch.mode = cmd.payload
        }
        break
      case 'scenario':
        setScenario(cmd.name)
        break
    }
  }

  function start() {
    applyStep(SCENARIOS[activeScenario][0])
    timer = setInterval(tick, 200)
  }

  function stop() {
    if (timer) clearInterval(timer)
  }

  return { state, start, stop, handleCmd }
}
