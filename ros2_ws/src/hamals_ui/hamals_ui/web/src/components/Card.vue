<template>
  <div class="card" :class="[variant && `card--${variant}`, className]">
    <div v-if="title || $slots.header" class="card__header">
      <slot name="header">
        <SectionTitle :icon="icon">{{ title }}</SectionTitle>
      </slot>
    </div>
    <div class="card__body">
      <slot />
    </div>
  </div>
</template>

<script setup>
import SectionTitle from './SectionTitle.vue'
defineProps({
  title:     { type: String, default: '' },
  icon:      { type: Object, default: null },
  variant:   { type: String, default: '' },   // 'danger' | 'warn' | 'success'
  className: { type: String, default: '' },
})
</script>

<style scoped>
.card {
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 16px;
}
.card--danger { border-color: rgba(239,68,68,.45); }
.card--warn   { border-color: rgba(245,165,36,.45); }
.card--success{ border-color: rgba(34,197,94,.35); }
.card__header { margin-bottom: 12px; }
.card__body   { }
</style>
