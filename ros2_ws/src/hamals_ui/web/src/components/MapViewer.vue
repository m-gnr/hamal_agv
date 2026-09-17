<template>
  <div class="map-viewer">
    <div class="map-toolbar">
      <strong>HARİTA · CANLI</strong>
      <div class="actions">
        <span :class="['status', status.toLowerCase()]">{{ status }}</span>
        <button type="button" @click="zoomAt(1.25)">＋</button>
        <button type="button" @click="zoomAt(0.8)">－</button>
        <button type="button" @click="fit">Haritaya Sığdır</button>
      </div>
    </div>
    <div ref="viewport" class="viewport" @wheel.prevent="onWheel" @pointerdown="onDown" @pointermove="onMove" @pointerup="onUp" @pointercancel="onUp">
      <canvas ref="canvas" aria-label="Canlı ROS OccupancyGrid haritası" />
      <span v-if="!info" class="waiting">/map verisi bekleniyor...</span>
    </div>
    <div class="meta">
      <span>Frame: {{ info?.frame || '—' }}</span>
      <span>Resolution: {{ info ? info.resolution.toFixed(3) + ' m/cell' : '—' }}</span>
      <span>Boyut: {{ info ? `${info.width} × ${info.height}` : '—' }}</span>
      <span>Origin: {{ info ? `${info.x.toFixed(2)}, ${info.y.toFixed(2)}, ${info.z.toFixed(2)}` : '—' }}</span>
      <span>Son /map: {{ receivedAt ? new Date(receivedAt).toLocaleTimeString('tr-TR') : '—' }}</span>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { mapStatus, occupancyPixels, mapCellToWorld, worldToCanvas } from '../composables/occupancyGrid.js'

const props = defineProps({ feed: { type: Object, required: true }, connected: Boolean })
const canvas = ref(null), viewport = ref(null), info = ref(null), receivedAt = ref(null), now = ref(Date.now())
const status = computed(() => mapStatus(receivedAt.value, props.connected, now.value))
let bitmap = null, currentMap = null, width = 0, height = 0, scale = 1, offsetX = 0, offsetY = 0
let userMoved = false, pointer = null, frame = 0, resizeObserver, unlisten, statusTimer

function draw() {
  frame = 0
  const surface = canvas.value, host = viewport.value
  if (!surface || !host) return
  const box = host.getBoundingClientRect()
  const dpr = window.devicePixelRatio || 1
  const backingWidth = Math.max(1, Math.round(box.width * dpr))
  const backingHeight = Math.max(1, Math.round(box.height * dpr))
  if (surface.width !== backingWidth || surface.height !== backingHeight) {
    surface.width = backingWidth
    surface.height = backingHeight
  }
  const ctx = surface.getContext('2d')
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
  ctx.clearRect(0, 0, box.width, box.height)
  if (!bitmap) return
  ctx.imageSmoothingEnabled = false
  ctx.drawImage(bitmap, offsetX, offsetY, width * scale, height * scale)
}
function scheduleDraw() { if (!frame) frame = requestAnimationFrame(draw) }
function fit() {
  if (!bitmap || !viewport.value) return
  const { width: viewWidth, height: viewHeight } = viewport.value.getBoundingClientRect()
  scale = Math.max(0.1, Math.min(viewWidth * 0.94 / width, viewHeight * 0.94 / height, 100))
  offsetX = (viewWidth - width * scale) / 2
  offsetY = (viewHeight - height * scale) / 2
  userMoved = false
  scheduleDraw()
}
function zoomAt(factor, x, y) {
  if (!bitmap || !viewport.value) return
  const rect = viewport.value.getBoundingClientRect()
  x ??= rect.width / 2
  y ??= rect.height / 2
  const next = Math.min(100, Math.max(0.1, scale * factor))
  offsetX = x - (x - offsetX) * next / scale
  offsetY = y - (y - offsetY) * next / scale
  scale = next
  userMoved = true
  scheduleDraw()
}
function onWheel(event) {
  const rect = viewport.value.getBoundingClientRect()
  zoomAt(Math.exp(-event.deltaY * 0.001), event.clientX - rect.left, event.clientY - rect.top)
}
function onDown(event) {
  if (!bitmap) return
  pointer = { id: event.pointerId, x: event.clientX, y: event.clientY }
  viewport.value.setPointerCapture(event.pointerId)
}
function onMove(event) {
  if (!pointer || pointer.id !== event.pointerId) return
  offsetX += event.clientX - pointer.x
  offsetY += event.clientY - pointer.y
  pointer.x = event.clientX; pointer.y = event.clientY
  userMoved = true
  scheduleDraw()
}
function onUp(event) { if (pointer?.id === event.pointerId) pointer = null }

function receive(message, time) {
  const { width: nextWidth, height: nextHeight, resolution, origin } = message.info
  let centerWorld = null
  if (currentMap && userMoved && viewport.value) {
    const rect = viewport.value.getBoundingClientRect()
    centerWorld = mapCellToWorld(currentMap, {
      x: (rect.width / 2 - offsetX) / scale,
      y: height - (rect.height / 2 - offsetY) / scale,
    })
    scale = Math.min(100, Math.max(0.1, scale * resolution / currentMap.info.resolution))
  }
  const imageCanvas = document.createElement('canvas')
  imageCanvas.width = nextWidth; imageCanvas.height = nextHeight
  const ctx = imageCanvas.getContext('2d')
  ctx.putImageData(occupancyPixels(message, ctx.createImageData(nextWidth, nextHeight)), 0, 0)
  const first = !bitmap
  bitmap = imageCanvas
  currentMap = message
  width = nextWidth; height = nextHeight
  info.value = { width, height, resolution, frame: message.header?.frame_id || '—',
    x: origin?.position?.x ?? 0, y: origin?.position?.y ?? 0, z: origin?.position?.z ?? 0 }
  receivedAt.value = time
  now.value = Date.now()
  if (first || !userMoved) fit()
  else {
    if (centerWorld) {
      const rect = viewport.value.getBoundingClientRect()
      const centerCell = worldToCanvas(message, centerWorld.x, centerWorld.y)
      offsetX = rect.width / 2 - centerCell.x * scale
      offsetY = rect.height / 2 - centerCell.y * scale
    }
    scheduleDraw()
  }
}
onMounted(() => {
  resizeObserver = new ResizeObserver(() => { if (bitmap && !userMoved) fit(); else scheduleDraw() })
  resizeObserver.observe(viewport.value)
  unlisten = props.feed.listen(receive)
  statusTimer = setInterval(() => { now.value = Date.now() }, 5000)
  scheduleDraw()
})
onUnmounted(() => {
  unlisten?.(); resizeObserver?.disconnect(); clearInterval(statusTimer)
  if (frame) cancelAnimationFrame(frame)
})
</script>

<style scoped>
.map-viewer { display:flex; flex-direction:column; min-height:340px; height:100%; gap:9px; }
.map-toolbar { display:flex; align-items:center; justify-content:space-between; gap:8px; flex-wrap:wrap; color:var(--text); font-size:12px; }
.actions { display:flex; align-items:center; gap:5px; }
button { border:1px solid var(--border); border-radius:6px; padding:5px 8px; background:var(--panel-2); color:var(--text); cursor:pointer; font:inherit; }
button:hover { border-color:var(--accent); }
.status { padding:4px 7px; border-radius:6px; font-weight:700; background:#263447; color:var(--text-dim); font-size:11px; }
.status.live { background:#123b2b; color:var(--green); }
.status.stale, .status.disconnected { background:#463515; color:var(--amber); }
.viewport { position:relative; flex:1; min-height:260px; overflow:hidden; background:#222d3b; border:1px solid var(--border); border-radius:8px; cursor:grab; touch-action:none; }
.viewport:active { cursor:grabbing; }
canvas { width:100%; height:100%; display:block; }
.waiting { position:absolute; inset:0; display:grid; place-items:center; color:var(--text-dim); pointer-events:none; }
.meta { display:flex; flex-wrap:wrap; gap:5px 18px; font-size:11px; color:var(--text-dim); }
</style>
