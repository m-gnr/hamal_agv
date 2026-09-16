<template>
  <div ref="wrapper" :class="['mini-map-wrap', fullsize ? 'mini-map-fill' : 'mini-map-ratio']">
    <canvas ref="canvas" class="mini-map" />
  </div>
</template>

<script setup>
import { ref, watch, onMounted, onUnmounted } from 'vue'

const props = defineProps({ state: Object, fullsize: Boolean })

const NODES = {
  START: { x: 40,  y: 100, type: 'start'   },
  D1:    { x: 100, y: 100, type: 'junction' },
  D2:    { x: 180, y: 100, type: 'junction' },
  D3:    { x: 260, y: 100, type: 'junction' },
  DOOR:  { x: 295, y: 100, type: 'door'     },
  D4:    { x: 330, y: 100, type: 'junction' },
  D5:    { x: 330, y: 150, type: 'junction' },
  D6:    { x: 330, y: 55,  type: 'junction' },
  A1:    { x: 100, y: 45,  type: 'pickup'   },
  A2:    { x: 180, y: 45,  type: 'pickup'   },
  A3:    { x: 260, y: 45,  type: 'pickup'   },
  B1:    { x: 390, y: 150, type: 'dropoff'  },
  B2:    { x: 390, y: 100, type: 'dropoff'  },
  B3:    { x: 390, y: 55,  type: 'dropoff'  },
}

const EDGES = [
  ['START','D1'],['D1','D2'],['D2','D3'],['D3','DOOR'],['DOOR','D4'],
  ['D1','A1'],['D2','A2'],['D3','A3'],
  ['D4','B2'],['D4','D5'],['D5','B1'],['D4','D6'],['D6','B3'],
]

const canvas = ref(null)
const wrapper = ref(null)
let ro = null

function draw(state) {
  const cvs = canvas.value
  if (!cvs) return
  const W = cvs.width
  const H = cvs.height
  if (!W || !H) return
  const ctx = cvs.getContext('2d')
  ctx.clearRect(0, 0, W, H)

  const sx = W / 440
  const sy = H / 220
  const fs = Math.max(8, Math.round(W / 38))
  const R_base = Math.max(4, Math.round(W / 60))

  function nx(id) { return NODES[id]?.x * sx }
  function ny(id) { return NODES[id]?.y * sy }

  // Background
  ctx.fillStyle = '#0e1521'
  ctx.fillRect(0, 0, W, H)

  // Grid lines
  ctx.strokeStyle = '#1a2436'
  ctx.lineWidth = 0.5
  const gx = W / 20, gy = H / 20
  for (let x = 0; x < W; x += gx) {
    ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, H); ctx.stroke()
  }
  for (let y = 0; y < H; y += gy) {
    ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.stroke()
  }

  // Edges
  const goal = state?.nav?.current_goal
  for (const [a, b] of EDGES) {
    const isDoor = (a === 'DOOR' || b === 'DOOR')
    ctx.beginPath()
    ctx.moveTo(nx(a), ny(a))
    ctx.lineTo(nx(b), ny(b))
    ctx.strokeStyle = isDoor ? '#f5a524' : '#2a3a50'
    ctx.lineWidth = isDoor ? 2 : 1.5
    ctx.setLineDash(isDoor ? [4, 3] : [])
    ctx.stroke()
    ctx.setLineDash([])
  }

  // Active goal highlight
  if (goal && NODES[goal]) {
    ctx.beginPath()
    ctx.arc(nx(goal), ny(goal), R_base * 2.5, 0, Math.PI * 2)
    ctx.strokeStyle = '#3b82f6'
    ctx.lineWidth = 2
    ctx.setLineDash([4, 3])
    ctx.stroke()
    ctx.setLineDash([])
  }

  // Nodes
  for (const [id, n] of Object.entries(NODES)) {
    const x = n.x * sx, y = n.y * sy
    const R = id === 'DOOR' ? R_base + 2 : R_base

    if (n.type === 'pickup' || n.type === 'dropoff') {
      const half = R + 2
      ctx.save()
      ctx.translate(x, y)
      ctx.rotate(Math.PI / 4)
      ctx.beginPath()
      ctx.rect(-half, -half, half * 2, half * 2)
      ctx.fillStyle = n.type === 'pickup' ? '#ef4444' : '#3b82f6'
      ctx.fill()
      ctx.strokeStyle = n.type === 'pickup' ? '#fca5a5' : '#93c5fd'
      ctx.lineWidth = 1
      ctx.stroke()
      ctx.restore()
    } else if (n.type === 'start') {
      ctx.beginPath()
      ctx.arc(x, y, R, 0, Math.PI * 2)
      ctx.fillStyle = '#22c55e'
      ctx.fill()
    } else if (n.type === 'door') {
      ctx.beginPath()
      ctx.arc(x, y, R, 0, Math.PI * 2)
      ctx.fillStyle = '#f5a524'
      ctx.fill()
      ctx.strokeStyle = '#fde68a'
      ctx.lineWidth = 1.5
      ctx.stroke()
    } else {
      ctx.beginPath()
      ctx.arc(x, y, R, 0, Math.PI * 2)
      ctx.fillStyle = '#2a3a50'
      ctx.fill()
    }

    ctx.fillStyle = '#7d8aa0'
    ctx.font = `${fs}px "Inter Variable", Inter, sans-serif`
    ctx.textAlign = 'center'
    ctx.fillText(id, x, y - R - 3)
  }

  // Robot marker
  const SCALE = 40 * sx
  const ORIGIN = { x: 40 * sx, y: 100 * sy }
  const rx = ORIGIN.x + (state?.pose?.x || 0) * SCALE
  const ry = ORIGIN.y - (state?.pose?.y || 0) * SCALE
  const rTheta = ((state?.pose?.theta_deg || 0) * Math.PI) / 180
  const rw = Math.max(8, R_base * 1.8)
  const rh = Math.max(6, R_base * 1.4)

  ctx.save()
  ctx.translate(rx, ry)
  ctx.rotate(rTheta)
  ctx.fillStyle = '#f5a524'
  ctx.beginPath()
  if (ctx.roundRect) {
    ctx.roundRect(-rw / 2, -rh / 2, rw, rh, 2)
  } else {
    ctx.rect(-rw / 2, -rh / 2, rw, rh)
  }
  ctx.fill()
  ctx.fillStyle = '#fff'
  ctx.beginPath()
  const aw = rw * 0.45
  ctx.moveTo(rw / 2 + aw * 0.4, 0)
  ctx.lineTo(rw / 2 - aw * 0.2, -aw * 0.5)
  ctx.lineTo(rw / 2 - aw * 0.2,  aw * 0.5)
  ctx.closePath()
  ctx.fill()
  ctx.restore()
}

function syncSize() {
  const w = wrapper.value
  const cvs = canvas.value
  if (!w || !cvs) return
  const cw = w.clientWidth
  const ch = w.clientHeight
  if (cw > 0 && ch > 0) {
    cvs.width = cw
    cvs.height = ch
    draw(props.state)
  }
}

onMounted(() => {
  ro = new ResizeObserver(syncSize)
  if (wrapper.value) ro.observe(wrapper.value)
  syncSize()
})

onUnmounted(() => ro?.disconnect())

watch(() => props.state, s => draw(s), { deep: true })
</script>

<style scoped>
.mini-map-wrap {
  width: 100%;
  overflow: hidden;
  border-radius: 6px;
  border: 1px solid var(--border);
}
.mini-map-ratio { aspect-ratio: 440 / 220; }
.mini-map-fill  { height: 100%; }
.mini-map {
  display: block;
  width: 100%;
  height: 100%;
}
</style>
