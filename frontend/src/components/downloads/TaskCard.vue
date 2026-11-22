<script setup lang="ts">
import { computed } from 'vue'
import { AlertTriangle, ChevronRight, Clock, FolderCheck, Layers } from 'lucide-vue-next'
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
const completedItems = computed(
  () => props.task.items.filter((item) => item.state === 'completed').length,
)
const failedItems = computed(
  () => props.task.items.filter((item) => item.state === 'failed').length,
)
const primaryPath = computed(
  () => props.task.final_path || props.task.final_paths[0] || props.task.save_path || null,
)
</script>

<template>
  <article
    class="surface-card-interactive group flex cursor-pointer flex-col justify-between rounded-xl p-4"
    role="button"
    tabindex="0"
    @click="$emit('select', task)"
    @keydown.enter="$emit('select', task)"
  >
    <div>
      <!-- Top Row: Status + ID -->
      <div class="flex items-start justify-between gap-2">
        <TaskStatusBadge :state="task.state" />
        <span
          class="rounded bg-[var(--bg-subtle)] px-1.5 py-0.5 font-mono text-[11px] text-[var(--text-muted)] tabular-nums"
          :title="task.id"
        >
          {{ shortTaskId(task.id) }}
        </span>
      </div>

      <!-- Title & Recognized Anime Name -->
      <div class="mt-3">
        <h3
          class="line-clamp-2 text-sm font-semibold leading-snug text-[var(--text-primary)] group-hover:text-[var(--accent)]"
          :title="task.title"
        >
          {{ task.title }}
        </h3>
        <div class="mt-2 flex flex-wrap items-center gap-1.5 text-xs">
          <span
            v-if="task.anime_name"
            class="rounded-md bg-[var(--bg-subtle)] px-2 py-0.5 font-medium text-[var(--text-primary)]"
          >
            {{ task.anime_name }}
          </span>
          <span
            v-if="seasonEp"
            class="rounded-md border border-[var(--border-default)] px-1.5 py-0.5 font-mono text-[11px] text-[var(--text-secondary)]"
          >
            {{ seasonEp }}
          </span>
          <span
            v-if="task.fansub"
            class="rounded-md border border-[var(--border-default)] px-1.5 py-0.5 text-[11px] text-[var(--text-secondary)]"
          >
            {{ task.fansub }}
          </span>
          <span
            v-if="task.quality"
            class="rounded-md border border-[var(--border-default)] px-1.5 py-0.5 font-mono text-[11px] text-[var(--text-secondary)]"
          >
            {{ task.quality }}
          </span>
        </div>
      </div>

      <!-- Error Banner (real error_message only) -->
      <div
        v-if="task.error_message"
        class="mt-3 flex items-start gap-2 rounded-lg border border-rose-500/25 bg-rose-500/10 px-2.5 py-2 text-xs text-rose-600 dark:text-rose-300"
      >
        <AlertTriangle class="mt-0.5 h-3.5 w-3.5 shrink-0" />
        <p class="line-clamp-2 break-all">{{ task.error_message }}</p>
      </div>

      <!-- Collection item breakdown when present -->
      <div
        v-if="task.items.length > 0"
        class="mt-3 flex items-center gap-2 text-xs text-[var(--text-secondary)]"
      >
        <Layers class="h-3.5 w-3.5 shrink-0 text-[var(--text-muted)]" />
        <span class="tabular-nums">
          共 {{ task.items.length }} 个文件条目 · 完成 {{ completedItems }}
          <template v-if="failedItems > 0">
            · <span class="text-rose-400">失败 {{ failedItems }}</span>
          </template>
        </span>
      </div>

      <!-- Final or Save Path -->
      <div
        v-if="primaryPath"
        class="mt-2.5 flex items-center gap-1.5 text-xs text-[var(--text-muted)]"
        :title="primaryPath"
      >
        <FolderCheck class="h-3.5 w-3.5 shrink-0" />
        <span class="truncate font-mono text-[11px]">{{ primaryPath }}</span>
      </div>
    </div>

    <!-- Footer Timestamps -->
    <div
      class="mt-4 flex items-center justify-between border-t border-[var(--border-default)] pt-3 text-[11px] text-[var(--text-muted)]"
    >
      <div class="flex items-center gap-1.5 tabular-nums">
        <Clock class="h-3 w-3 shrink-0" />
        <span>
          {{
            task.completed_at
              ? `完成于 ${formatDateTime(task.completed_at, settingsStore.language)}`
              : `添加于 ${formatDateTime(task.created_at, settingsStore.language)}`
          }}
        </span>
      </div>
      <span class="inline-flex items-center gap-0.5 text-[var(--text-secondary)] group-hover:text-[var(--accent)]">
        详情
        <ChevronRight class="h-3.5 w-3.5" />
      </span>
    </div>
  </article>
</template>
