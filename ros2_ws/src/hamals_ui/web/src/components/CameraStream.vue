<template>
  <div class="camera-stream">
    <img v-if="fresh && url" :key="attempt" v-show="!failed && loaded" :src="streamUrl" alt="Canlı kamera" @error="failed = true" @load="loaded = true; failed = false">
    <div v-if="!fresh || !url || failed || !loaded" class="unavailable">Camera unavailable / stale</div>
    <button v-if="fresh && failed" @click="retry">Yeniden bağlan</button>
  </div>
</template>
<script setup>
import { ref, computed, watch } from 'vue'
const props = defineProps({ url: String, fresh: Boolean })
const failed = ref(false)
const loaded = ref(false)
const attempt = ref(0)
// Optional deployment override; stream topic remains the configured ROS camera topic.
const streamUrl = computed(() => {
  if (!props.url) return ''
  try {
    const url = new URL(props.url)
    if (import.meta.env.VITE_VIDEO_BASE_URL) {
      const base = new URL(import.meta.env.VITE_VIDEO_BASE_URL)
      url.protocol = base.protocol; url.host = base.host
    } else if (url.hostname === 'robot') url.hostname = window.location.hostname
    return url.toString()
  } catch { return '' }
})
function retry() { attempt.value++; failed.value = false; loaded.value = false }
watch(() => [props.fresh, props.url], retry)
</script>
<style scoped>
.camera-stream { min-height: 160px; width: 100%; position: relative; display: grid; place-items: center; background: var(--panel-2); }
img { width: 100%; max-height: 440px; object-fit: contain; }
.unavailable { padding: 28px; color: var(--text-dim); }
button { color: var(--text); background: var(--panel); border: 1px solid var(--border); padding: 8px; }
</style>
