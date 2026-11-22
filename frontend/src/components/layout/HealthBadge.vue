<script setup lang="ts">
import { computed } from 'vue'
import { useHealthStore } from '@/stores/health'
import { useSettingsStore } from '@/stores/settings'

const healthStore = useHealthStore()
const settingsStore = useSettingsStore()

const statusView = computed(() => {
  const h = healthStore.health
  if (!h) {
    return {
      label: settingsStore.t('health.checking'),
      dotClass: 'bg-slate-400',
      pillClass: 'border-[var(--border-default)] bg-[var(--bg-subtle)] text-[var(--text-secondary)]',
      tooltip: '正在检测 Openlist-Ani 服务状态',
    }
  }
  if (!h.upstream_reachable) {
    return {
      label: settingsStore.t('health.unreachable'),
      dotClass: 'bg-rose-500',
      pillClass: 'border-rose-500/30 bg-rose-500/10 text-rose-600 dark:text-rose-300',
      tooltip: h.error_message || '无法连接到 Openlist-Ani',
    }
  }
  if (h.upstream_ready) {
    const workers = h.workers ? ` · ${h.workers.running}/${h.workers.expected} 工作线程` : ''
    const latency = h.latency_ms !== null ? ` · ${h.latency_ms}ms` : ''
    return {
      label: settingsStore.t('health.ready'),
      dotClass: 'bg-emerald-500',
      pillClass: 'border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300',
      tooltip: `Openlist-Ani 就绪${workers}${latency}`,
    }
  }
  return {
    label:
      h.upstream_status === 'starting'
        ? settingsStore.t('health.starting')
        : settingsStore.t('health.degraded'),
    dotClass: 'bg-amber-500',
    pillClass: 'border-amber-500/30 bg-amber-500/10 text-amber-700 dark:text-amber-300',
    tooltip: `Openlist-Ani 状态: ${h.upstream_status}`,
  }
})
</script>

<template>
  <RouterLink
    to="/settings"
    :title="statusView.tooltip"
    class="inline-flex items-center gap-2 rounded-full border px-2.5 py-1 text-xs font-medium transition hover:opacity-90"
    :class="statusView.pillClass"
  >
    <span class="h-2 w-2 rounded-full" :class="statusView.dotClass" />
    <span class="hidden sm:inline">{{ statusView.label }}</span>
    <span
      v-if="healthStore.health?.upstream_reachable && healthStore.health.latency_ms !== null"
      class="hidden font-mono text-[11px] opacity-75 tabular-nums md:inline"
    >
      {{ healthStore.health.latency_ms }}ms
    </span>
  </RouterLink>
</template>
