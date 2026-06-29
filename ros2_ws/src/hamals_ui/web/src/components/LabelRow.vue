<template>
  <div class="label-row">
    <span class="label-row__key">{{ label }}</span>
    <span :class="['label-row__val', valueClass]"><slot /></span>
  </div>
</template>

<script setup>
defineProps({
  label:      { type: String, required: true },
  valueClass: { type: String, default: '' },
})
</script>

<style scoped>
.label-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 4px 0;
  gap: 8px;
}
.label-row + .label-row { border-top: 1px solid var(--border); }
.label-row__key {
  font-size: 12px;
  color: var(--text-dim);
  text-transform: uppercase;
  letter-spacing: .4px;
  flex-shrink: 0;
}
.label-row__val {
  font-size: 13px;
  font-weight: 600;
  color: var(--text);
  text-align: right;
  font-variant-numeric: tabular-nums;
}
</style>
