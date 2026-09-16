<template>
  <span :class="['pill', `pill--${variant}`]">
    <span v-if="dot" class="pill__dot" />
    <slot />
  </span>
</template>

<script setup>
defineProps({
  variant: { type: String, default: 'default' }, // success|danger|warn|info|default
  dot:     { type: Boolean, default: false },
})
</script>

<style scoped>
.pill {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 3px 10px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 600;
  white-space: nowrap;
}
.pill__dot { width: 7px; height: 7px; border-radius: 50%; background: currentColor; flex-shrink: 0; }
.pill--success { background: rgba(34,197,94,.14);  color: var(--green); border: 1px solid rgba(34,197,94,.32); }
.pill--danger  { background: rgba(239,68,68,.14);  color: var(--red);   border: 1px solid rgba(239,68,68,.32); }
.pill--warn    { background: rgba(245,165,36,.14); color: var(--amber); border: 1px solid rgba(245,165,36,.32); }
.pill--info    { background: rgba(59,130,246,.14); color: var(--accent);border: 1px solid rgba(59,130,246,.32); }
.pill--default { background: rgba(125,138,160,.1); color: var(--text-dim); border: 1px solid var(--border); }
</style>
