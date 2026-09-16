<template>
  <aside class="sidebar">
    <nav class="sidebar__nav">
      <button
        v-for="tab in mainTabs"
        :key="tab.id"
        :class="['nav-item', { active: active === tab.id }]"
        @click="$emit('change', tab.id)"
      >
        <component :is="tab.icon" class="nav-item__icon" :size="18" />
        <span class="nav-item__label">{{ tab.title }}</span>
        <span v-if="active === tab.id" class="nav-item__indicator" />
      </button>
    </nav>
    <div class="sidebar__bottom">
      <button
        :class="['nav-item', { active: active === 'settings' }]"
        @click="$emit('change', 'settings')"
      >
        <Settings class="nav-item__icon" :size="18" />
        <span class="nav-item__label">Ayarlar</span>
        <span v-if="active === 'settings'" class="nav-item__indicator" />
      </button>
    </div>
  </aside>
</template>

<script setup>
import {
  LayoutDashboard, Map, ClipboardList,
  Gamepad2, Camera, ShieldAlert, Settings,
} from 'lucide-vue-next'

defineProps({ active: String })
defineEmits(['change'])

const mainTabs = [
  { id: 'dashboard', title: 'Genel Durum',    icon: LayoutDashboard },
  { id: 'map',       title: 'Harita & Rota',  icon: Map },
  { id: 'mission',   title: 'Görev & PLC',    icon: ClipboardList },
  { id: 'manual',    title: 'Manuel Kontrol', icon: Gamepad2 },
  { id: 'camera',    title: 'Kamera & Çizgi', icon: Camera },
  { id: 'errors',    title: 'Hata & Güvenlik',icon: ShieldAlert },
]
</script>

<style scoped>
.sidebar {
  width: var(--sidebar-w);
  flex-shrink: 0;
  background: var(--panel);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.sidebar__nav   { flex: 1; padding: 10px 8px; display: flex; flex-direction: column; gap: 2px; }
.sidebar__bottom{ padding: 8px; border-top: 1px solid var(--border); }

.nav-item {
  position: relative;
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 10px 12px;
  border: none;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--text-dim);
  font-size: 13px;
  font-family: inherit;
  cursor: pointer;
  transition: background .15s, color .15s;
  overflow: hidden;
}
.nav-item:hover { background: rgba(255,255,255,.05); color: var(--text); }
.nav-item.active {
  background: rgba(59,130,246,.18);
  color: var(--text);
}
.nav-item__icon  { flex-shrink: 0; }
.nav-item__label { font-weight: 500; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.nav-item__indicator {
  position: absolute;
  left: 0; top: 20%; bottom: 20%;
  width: 3px;
  background: var(--accent);
  border-radius: 0 3px 3px 0;
}
</style>
