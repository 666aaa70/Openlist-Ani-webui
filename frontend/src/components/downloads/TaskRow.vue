<script setup lang="ts">
import { computed } from 'vue'
import { AlertTriangle, ChevronRight } from 'lucide-vue-next'
import type { DownloadTaskResponse } from '@/types/api'
import { formatDateTime, formatSeasonEpisode, shortTaskId } from '@/utils/format'
import { useSettingsStore } from '@/stores/settings'
import TaskStatusBadge from './TaskStatusBadge.vue'

const props = defineProps<{
  task: DownloadTaskResponse
}>()

defineEmits<{
  select: [task: DownloadTaskResponse]
}>()

const settingsStore = useSettingsStore()
const seasonEp = computed(() => formatSeasonEpisode(props.task.season, props.task.episode))
const primaryPath = computed(
  () => props.task.final_path || props.task.final_paths[0] || props.task.save_path || '—',
)
</script>

<template>
  <tr
    class="cursor-pointer border-b border-[var(--border-default)] transition-colors hover:bg-[var(--bg-surface-hover)]"
    @click="$emit('select', task)"
  >
    <td class="py-3 pl-4 pr-3 align-middle">
      <div class="min-w-0 max-w-md">
        <p class="truncate text-sm font-medium text-[var(--text-primary)]" :title="task.title">
          {{ task.title }}
        </p>
        <div class="mt-0.5 flex flex-wrap items-center gap-2 text-xs text-[var(--text-muted)]">
          <span class="font-mono text-[11px]" :title="task.id">{{ shortTaskId(task.id) }}</span>
          <span v-if="task.anime_name" class="text-[var(--text-secondary)]">{{ task.anime_name }}</span>
          <span v-if="seasonEp" class="font-mono">{{ seasonEp }}</span>
          <span v-if="task.fansub">{{ task.fansub }}</span>
          <span v-if="task.quality" class="font-mono">{{ task.quality }}</span>
        </div>
        <p
          v-if="task.error_message"
          class="mt-1 flex items-center gap-1 truncate text-xs text-rose-500 dark:text-rose-400"
          :title="task.error_message"
        >
          <AlertTriangle class="h-3 w-3 shrink-0" />
          <span class="truncate">{{ task.error_message }}</span>
        </p>
      </div>
    </td>
    <td class="px-3 py-3 align-middle">
      <TaskStatusBadge :state="task.state" compact />
      <p v-if="task.items.length > 0" class="mt-1 text-[11px] text-[var(--text-muted)] tabular-nums">
        {{ task.items.length }} 项文件
      </p>
    </td>
    <td class="hidden px-3 py-3 align-middle lg:table-cell">
      <p class="max-w-xs truncate font-mono text-xs text-[var(--text-secondary)]" :title="primaryPath">
        {{ primaryPath }}
      </p>
    </td>
    <td class="hidden px-3 py-3 align-middle text-xs text-[var(--text-secondary)] tabular-nums md:table-cell">
      <div>{{ formatDateTime(task.created_at, settingsStore.language) }}</div>
      <div v-if="task.completed_at" class="mt-0.5 text-[11px] text-emerald-600 dark:text-emerald-400">
        完: {{ formatDateTime(task.completed_at, settingsStore.language) }}
      </div>
    </td>
    <td class="py-3 pl-2 pr-4 text-right align-middle">
      <ChevronRight class="ml-auto h-4 w-4 text-[var(--text-muted)]" />
    </td>
  </tr>
</template>
