<template>
  <div class="section-title">
    <component :is="icon" v-if="icon" class="section-title__icon" :size="13" />
    <span class="section-title__text"><slot /></span>
  </div>
</template>

<script setup>
defineProps({ icon: { type: Object, default: null } })
</script>

<style scoped>
.section-title {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--text-dim);
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: .6px;
}
.section-title__icon { flex-shrink: 0; color: var(--text-dim); }
</style>
