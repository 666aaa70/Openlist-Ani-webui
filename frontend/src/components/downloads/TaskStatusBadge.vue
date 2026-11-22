<script setup lang="ts">
import { computed } from 'vue'
import {
  AlertTriangle,
  Ban,
  CheckCircle2,
  Clock,
  Download,
  FileSearch,
  FolderSync,
  Send,
} from 'lucide-vue-next'
import type { TaskStateString } from '@/types/api'
import { getTaskStateInfo, getTaskStateLabel } from '@/utils/format'
import { useSettingsStore } from '@/stores/settings'

const props = defineProps<{
  state: TaskStateString
  compact?: boolean
}>()

const settingsStore = useSettingsStore()

const info = computed(() => getTaskStateInfo(props.state))
const label = computed(() => getTaskStateLabel(props.state, settingsStore.language))

const toneClasses = computed(() => {
  switch (info.value.tone) {
    case 'sky':
      return 'border-sky-500/30 bg-sky-500/12 text-sky-700 dark:text-sky-300'
    case 'amber':
      return 'border-amber-500/30 bg-amber-500/12 text-amber-700 dark:text-amber-300'
    case 'emerald':
      return 'border-emerald-500/30 bg-emerald-500/12 text-emerald-700 dark:text-emerald-300'
    case 'rose':
      return 'border-rose-500/30 bg-rose-500/12 text-rose-700 dark:text-rose-300'
    default:
      return 'border-slate-500/30 bg-slate-500/12 text-slate-700 dark:text-slate-300'
  }
})

const iconComponent = computed(() => {
  switch (props.state) {
    case 'downloading':
      return Download
    case 'downloaded':
    case 'resolving':
      return FileSearch
    case 'renaming':
    case 'renamed':
      return FolderSync
    case 'notifying':
      return Send
    case 'completed':
      return CheckCircle2
    case 'failed':
      return AlertTriangle
    case 'cancelled':
    case 'skipped':
      return Ban
    default:
      return Clock
  }
})
</script>

<template>
  <span
    class="inline-flex items-center gap-1.5 rounded-md border font-medium whitespace-nowrap"
    :class="[toneClasses, compact ? 'px-2 py-0.5 text-[11px]' : 'px-2.5 py-1 text-xs']"
  >
    <component :is="iconComponent" :class="compact ? 'h-3 w-3' : 'h-3.5 w-3.5'" />
    <span>{{ label }}</span>
  </span>
</template>
