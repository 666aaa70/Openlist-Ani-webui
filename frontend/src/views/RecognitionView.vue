<script setup lang="ts">
import { computed, ref } from 'vue'
import { ChevronRight, Film, FolderCheck, Search } from 'lucide-vue-next'
import { useDownloadsStore } from '@/stores/downloads'
import { useSettingsStore } from '@/stores/settings'
import type { DownloadTaskResponse } from '@/types/api'
import { formatSeasonEpisode } from '@/utils/format'
import EmptyState from '@/components/common/EmptyState.vue'
import ErrorBanner from '@/components/common/ErrorBanner.vue'
import TaskStatusBadge from '@/components/downloads/TaskStatusBadge.vue'

interface RecognitionRow {
  rowKey: string
  taskId: string
  isSubItem: boolean
  rawTitle: string
  animeName: string | null
  season: number | null
  episode: number | null
  fansub: string | null
  quality: string | null
  state: string
  finalPath: string | null
  error: string | null
  task: DownloadTaskResponse
}

type RecognitionFilter = 'all' | 'recognized' | 'unrecognized' | 'errors'

const downloadsStore = useDownloadsStore()
const settingsStore = useSettingsStore()

const searchQuery = ref('')
const filterMode = ref<RecognitionFilter>('all')

/**
 * Flatten authentic Openlist-Ani task & per-file item recognition results.
 * Does NOT perform any client-side parsing or re-implementation of Openlist-Ani's metadata engine.
 */
const rows = computed<RecognitionRow[]>(() => {
  const output: RecognitionRow[] = []
  for (const task of downloadsStore.tasks) {
    if (task.items.length > 0) {
      for (const item of task.items) {
        output.push({
          rowKey: `${task.id}::${item.item_key}`,
          taskId: task.id,
          isSubItem: task.items.length > 1,
          rawTitle: item.source_path || task.title,
          animeName: item.anime_name ?? task.anime_name,
          season: item.season ?? task.season,
          episode: item.episode ?? task.episode,
          fansub: task.fansub,
          quality: task.quality,
          state: item.state,
          finalPath: item.final_path,
          error: item.error,
          task,
        })
      }
    } else {
      output.push({
        rowKey: task.id,
        taskId: task.id,
        isSubItem: false,
        rawTitle: task.title,
        animeName: task.anime_name,
        season: task.season,
        episode: task.episode,
        fansub: task.fansub,
        quality: task.quality,
        state: task.state,
        finalPath: task.final_path || task.final_paths[0] || null,
        error: task.error_message,
        task,
      })
    }
  }
  return output
})

const filteredRows = computed(() => {
  const q = searchQuery.value.trim().toLowerCase()
  return rows.value.filter((row) => {
    if (filterMode.value === 'recognized' && !row.animeName) return false
    if (filterMode.value === 'unrecognized' && Boolean(row.animeName)) return false
    if (filterMode.value === 'errors' && !row.error && row.state !== 'failed') return false

    if (!q) return true
    const haystack = [
      row.animeName,
      row.rawTitle,
      row.fansub,
      row.quality,
      row.finalPath,
      row.state,
      formatSeasonEpisode(row.season, row.episode),
    ]
      .filter(Boolean)
      .join(' ')
      .toLowerCase()
    return haystack.includes(q)
  })
})

const recognizedCount = computed(() => rows.value.filter((r) => Boolean(r.animeName)).length)
const renamedCount = computed(() => rows.value.filter((r) => Boolean(r.finalPath)).length)
</script>

<template>
  <div class="space-y-4">
    <ErrorBanner
      v-if="downloadsStore.error"
      title="无法获取 Openlist-Ani 识别数据"
      :message="downloadsStore.error"
      retryable
      @retry="downloadsStore.refreshAll(false)"
    />

    <!-- Info Bar -->
    <div class="surface-card flex flex-col justify-between gap-3 rounded-xl p-4 sm:flex-row sm:items-center">
      <div>
        <h2 class="text-sm font-semibold text-[var(--text-primary)]">
          {{ settingsStore.t('recognition.title') }}
        </h2>
        <p class="mt-0.5 text-xs text-[var(--text-secondary)]">
          {{ settingsStore.t('recognition.desc') }}
        </p>
      </div>
      <div class="flex shrink-0 items-center gap-4 text-xs tabular-nums">
        <div>
          <span class="text-[var(--text-muted)]">总条目：</span>
          <span class="font-mono font-semibold text-[var(--text-primary)]">{{ rows.length }}</span>
        </div>
        <div>
          <span class="text-[var(--text-muted)]">已识别番名：</span>
          <span class="font-mono font-semibold text-sky-500">{{ recognizedCount }}</span>
        </div>
        <div>
          <span class="text-[var(--text-muted)]">已输出最终路径：</span>
          <span class="font-mono font-semibold text-emerald-500">{{ renamedCount }}</span>
        </div>
      </div>
    </div>

    <!-- Search & Filter Controls -->
    <div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
      <div class="flex flex-wrap items-center gap-1.5">
        <button
          v-for="tab in [
            { key: 'all', label: '全部条目' },
            { key: 'recognized', label: '已识别' },
            { key: 'unrecognized', label: '待识别' },
            { key: 'errors', label: '处理异常' },
          ]"
          :key="tab.key"
          type="button"
          class="rounded-lg px-3 py-1.5 text-xs font-medium transition"
          :class="
            filterMode === tab.key
              ? 'bg-[var(--accent)] text-white'
              : 'surface-card text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
          "
          @click="filterMode = tab.key as RecognitionFilter"
        >
          {{ tab.label }}
        </button>
      </div>

      <div class="relative w-full sm:w-72">
        <Search class="pointer-events-none absolute top-1/2 left-3 h-4 w-4 -translate-y-1/2 text-[var(--text-muted)]" />
        <input
          v-model="searchQuery"
          type="search"
          placeholder="搜索番剧名、字幕组、清晰度或路径…"
          class="input-field w-full rounded-lg py-2 pr-3 pl-9 text-xs"
        />
      </div>
    </div>

    <!-- Empty -->
    <EmptyState
      v-if="filteredRows.length === 0"
      title="暂无番剧识别记录"
      description="当 Openlist-Ani 接收任务并执行元数据识别或合集整理后，此处将实时展示番剧名、季/集、字幕组、清晰度与最终路径。"
    >
      <template #icon>
        <Film class="h-5 w-5" />
      </template>
    </EmptyState>

    <!-- Desktop Table + Mobile Card List -->
    <div v-else class="surface-card overflow-hidden rounded-xl">
      <div class="hidden overflow-x-auto md:block">
        <table class="w-full border-collapse text-left">
          <thead>
            <tr
              class="border-b border-[var(--border-default)] bg-[var(--bg-subtle)] text-[11px] font-semibold uppercase tracking-wide text-[var(--text-muted)]"
            >
              <th class="py-2.5 pl-4 pr-3">番剧名称 / 原始标题</th>
              <th class="px-3 py-2.5">季 / 集</th>
              <th class="px-3 py-2.5">字幕组</th>
              <th class="px-3 py-2.5">清晰度</th>
              <th class="px-3 py-2.5">处理结果</th>
              <th class="px-3 py-2.5">最终路径</th>
              <th class="py-2.5 pl-2 pr-4 text-right">详情</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-[var(--border-default)] text-xs">
            <tr
              v-for="row in filteredRows"
              :key="row.rowKey"
              class="cursor-pointer transition hover:bg-[var(--bg-surface-hover)]"
              @click="downloadsStore.inspectTask(row.taskId)"
            >
              <td class="max-w-xs py-3 pl-4 pr-3 align-middle">
                <p class="truncate font-semibold text-[var(--text-primary)]">
                  {{ row.animeName || '尚未识别' }}
                </p>
                <p
                  class="mt-0.5 truncate font-mono text-[11px] text-[var(--text-muted)]"
                  :title="row.rawTitle"
                >
                  {{ row.rawTitle }}
                </p>
              </td>
              <td class="px-3 py-3 align-middle font-mono text-[var(--text-primary)] tabular-nums">
                {{ formatSeasonEpisode(row.season, row.episode) || '—' }}
              </td>
              <td class="px-3 py-3 align-middle text-[var(--text-secondary)]">
                {{ row.fansub || '—' }}
              </td>
              <td class="px-3 py-3 align-middle font-mono text-[var(--text-secondary)]">
                {{ row.quality || '—' }}
              </td>
              <td class="px-3 py-3 align-middle">
                <TaskStatusBadge :state="row.state" compact />
                <p
                  v-if="row.error"
                  class="mt-1 max-w-[180px] truncate font-mono text-[11px] text-rose-500 dark:text-rose-400"
                  :title="row.error"
                >
                  {{ row.error }}
                </p>
              </td>
              <td class="max-w-sm px-3 py-3 align-middle">
                <div
                  v-if="row.finalPath"
                  class="flex items-center gap-1.5 text-emerald-600 dark:text-emerald-400"
                  :title="row.finalPath"
                >
                  <FolderCheck class="h-3.5 w-3.5 shrink-0" />
                  <span class="truncate font-mono text-[11px]">{{ row.finalPath }}</span>
                </div>
                <span v-else class="text-[var(--text-muted)]">—</span>
              </td>
              <td class="py-3 pl-2 pr-4 text-right align-middle">
                <ChevronRight class="ml-auto h-4 w-4 text-[var(--text-muted)]" />
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Mobile Compact Cards -->
      <ul class="divide-y divide-[var(--border-default)] md:hidden">
        <li
          v-for="row in filteredRows"
          :key="row.rowKey"
          class="cursor-pointer space-y-2 p-4 transition hover:bg-[var(--bg-surface-hover)]"
          @click="downloadsStore.inspectTask(row.taskId)"
        >
          <div class="flex items-start justify-between gap-2">
            <div class="min-w-0">
              <p class="truncate text-sm font-semibold text-[var(--text-primary)]">
                {{ row.animeName || '尚未识别' }}
              </p>
              <p class="mt-0.5 truncate font-mono text-[11px] text-[var(--text-muted)]">
                {{ row.rawTitle }}
              </p>
            </div>
            <TaskStatusBadge :state="row.state" compact />
          </div>

          <div class="flex flex-wrap gap-1.5 text-[11px] text-[var(--text-secondary)]">
            <span
              v-if="formatSeasonEpisode(row.season, row.episode)"
              class="rounded border border-[var(--border-default)] px-1.5 py-0.5 font-mono"
            >
              {{ formatSeasonEpisode(row.season, row.episode) }}
            </span>
            <span v-if="row.fansub" class="rounded border border-[var(--border-default)] px-1.5 py-0.5">
              {{ row.fansub }}
            </span>
            <span v-if="row.quality" class="rounded border border-[var(--border-default)] px-1.5 py-0.5 font-mono">
              {{ row.quality }}
            </span>
          </div>

          <p
            v-if="row.finalPath"
            class="break-all font-mono text-[11px] text-emerald-600 dark:text-emerald-400"
          >
            {{ row.finalPath }}
          </p>
          <p v-if="row.error" class="break-all font-mono text-[11px] text-rose-500 dark:text-rose-400">
            {{ row.error }}
          </p>
        </li>
      </ul>
    </div>
  </div>
</template>
