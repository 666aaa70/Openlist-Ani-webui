<script setup lang="ts">
import { computed, ref } from 'vue'
import {
  ArrowDownUp,
  Download,
  Hash,
  LayoutGrid,
  List,
  Loader2,
  Plus,
  RefreshCw,
  Search,
} from 'lucide-vue-next'
import { useDownloadsStore } from '@/stores/downloads'
import { useSettingsStore } from '@/stores/settings'
import { formatDateTime, getTaskStateInfo } from '@/utils/format'
import EmptyState from '@/components/common/EmptyState.vue'
import ErrorBanner from '@/components/common/ErrorBanner.vue'
import TaskCard from '@/components/downloads/TaskCard.vue'
import TaskRow from '@/components/downloads/TaskRow.vue'

type FilterTab = 'all' | 'active' | 'completed' | 'failed'
type ViewMode = 'card' | 'list'
type SortOption = 'created_desc' | 'created_asc' | 'updated_desc' | 'title_asc'

const downloadsStore = useDownloadsStore()
const settingsStore = useSettingsStore()

const activeTab = ref<FilterTab>('all')
const viewMode = ref<ViewMode>('card')
const sortBy = ref<SortOption>('created_desc')
const searchQuery = ref('')
const lookupTaskId = ref('')
const lookupError = ref<string | null>(null)
const lookupLoading = ref(false)

const tabs = computed(() => [
  { key: 'all' as FilterTab, label: settingsStore.t('downloads.tabAll'), count: downloadsStore.total },
  {
    key: 'active' as FilterTab,
    label: settingsStore.t('downloads.tabActive'),
    count: downloadsStore.activeCount,
  },
  {
    key: 'completed' as FilterTab,
    label: settingsStore.t('downloads.tabCompleted'),
    count: downloadsStore.completedCount,
  },
  {
    key: 'failed' as FilterTab,
    label: settingsStore.t('downloads.tabFailed'),
    count: downloadsStore.failedCount,
  },
])

const filteredTasks = computed(() => {
  const q = searchQuery.value.trim().toLowerCase()
  const list = downloadsStore.tasks.filter((task) => {
    const category = getTaskStateInfo(task.state).category
    if (activeTab.value === 'active' && category !== 'active') return false
    if (activeTab.value === 'completed' && category !== 'completed') return false
    if (activeTab.value === 'failed' && category !== 'failed') return false

    if (!q) return true
    const haystack = [
      task.title,
      task.id,
      task.anime_name,
      task.fansub,
      task.quality,
      task.state,
      task.final_path,
      task.save_path,
      task.error_message,
      ...task.final_paths,
    ]
      .filter(Boolean)
      .join(' ')
      .toLowerCase()
    return haystack.includes(q)
  })

  return [...list].sort((a, b) => {
    switch (sortBy.value) {
      case 'created_asc':
        return a.created_at.localeCompare(b.created_at)
      case 'updated_desc':
        return b.updated_at.localeCompare(a.updated_at)
      case 'title_asc':
        return a.title.localeCompare(b.title, 'zh-CN')
      case 'created_desc':
      default:
        return b.created_at.localeCompare(a.created_at)
    }
  })
})

async function handleLookupTask(): Promise<void> {
  const id = lookupTaskId.value.trim()
  if (!id) return
  lookupLoading.value = true
  lookupError.value = null
  const found = await downloadsStore.inspectTask(id)
  lookupLoading.value = false
  if (!found) {
    lookupError.value = downloadsStore.selectedTaskError || `未找到任务 ID: ${id}`
  } else {
    lookupTaskId.value = ''
  }
}
</script>

<template>
  <div class="space-y-4">
    <!-- Connection / API Error Banner -->
    <ErrorBanner
      v-if="downloadsStore.error"
      title="Openlist-Ani 数据同步失败"
      :message="downloadsStore.error"
      retryable
      @retry="downloadsStore.refreshAll(false)"
    />

    <!-- Filter Tabs & Sync Meta -->
    <div class="flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
      <div class="flex flex-wrap items-center gap-1.5" role="tablist" aria-label="任务状态筛选">
        <button
          v-for="tab in tabs"
          :key="tab.key"
          type="button"
          role="tab"
          :aria-selected="activeTab === tab.key"
          class="inline-flex items-center gap-2 rounded-lg px-3 py-1.5 text-xs font-medium transition"
          :class="
            activeTab === tab.key
              ? 'bg-[var(--accent)] text-white shadow-sm'
              : 'surface-card text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
          "
          @click="activeTab = tab.key"
        >
          <span>{{ tab.label }}</span>
          <span
            class="rounded-full px-1.5 py-0.5 text-[11px] leading-none tabular-nums"
            :class="
              activeTab === tab.key
                ? 'bg-white/20 text-white'
                : 'bg-[var(--bg-subtle)] text-[var(--text-muted)]'
            "
          >
            {{ tab.count }}
          </span>
        </button>
      </div>

      <div class="flex items-center gap-2 text-xs text-[var(--text-muted)] tabular-nums">
        <span>每 {{ settingsStore.pollIntervalSeconds }} 秒自动刷新</span>
        <span v-if="downloadsStore.syncedAt">
          · 更新于 {{ formatDateTime(downloadsStore.syncedAt, settingsStore.language) }}
        </span>
      </div>
    </div>

    <!-- Search, Sort, View Toggle & Historical ID Lookup -->
    <div class="surface-card flex flex-col gap-3 rounded-xl p-3 sm:flex-row sm:items-center sm:justify-between">
      <div class="relative flex-1">
        <Search class="pointer-events-none absolute top-1/2 left-3 h-4 w-4 -translate-y-1/2 text-[var(--text-muted)]" />
        <input
          id="downloads-search-input"
          v-model="searchQuery"
          type="search"
          :placeholder="settingsStore.t('downloads.searchPlaceholder')"
          class="input-field w-full rounded-lg py-2 pr-3 pl-9 text-xs"
        />
      </div>

      <div class="flex flex-wrap items-center gap-2">
        <!-- Sort Selector -->
        <div class="relative inline-flex items-center">
          <ArrowDownUp class="pointer-events-none absolute left-2.5 h-3.5 w-3.5 text-[var(--text-muted)]" />
          <select
            id="downloads-sort-select"
            v-model="sortBy"
            aria-label="排序方式"
            class="input-field rounded-lg py-2 pr-7 pl-8 text-xs"
          >
            <option value="created_desc">按添加时间（最新）</option>
            <option value="created_asc">按添加时间（最早）</option>
            <option value="updated_desc">按最近更新</option>
            <option value="title_asc">按番剧标题 A-Z</option>
          </select>
        </div>

        <!-- View Mode Toggle -->
        <div class="inline-flex rounded-lg border border-[var(--border-default)] bg-[var(--bg-subtle)] p-0.5">
          <button
            id="view-mode-card"
            type="button"
            class="inline-flex items-center gap-1 rounded-md px-2.5 py-1.5 text-xs font-medium transition"
            :class="
              viewMode === 'card'
                ? 'bg-[var(--bg-surface)] text-[var(--text-primary)] shadow-xs'
                : 'text-[var(--text-muted)] hover:text-[var(--text-primary)]'
            "
            title="卡片视图"
            @click="viewMode = 'card'"
          >
            <LayoutGrid class="h-3.5 w-3.5" />
            <span class="hidden sm:inline">卡片</span>
          </button>
          <button
            id="view-mode-list"
            type="button"
            class="inline-flex items-center gap-1 rounded-md px-2.5 py-1.5 text-xs font-medium transition"
            :class="
              viewMode === 'list'
                ? 'bg-[var(--bg-surface)] text-[var(--text-primary)] shadow-xs'
                : 'text-[var(--text-muted)] hover:text-[var(--text-primary)]'
            "
            title="列表视图"
            @click="viewMode = 'list'"
          >
            <List class="h-3.5 w-3.5" />
            <span class="hidden sm:inline">列表</span>
          </button>
        </div>

        <!-- Manual Refresh -->
        <button
          type="button"
          class="btn-secondary inline-flex items-center gap-1.5 rounded-lg px-3 py-2 text-xs font-medium"
          :disabled="downloadsStore.refreshing"
          @click="downloadsStore.refreshAll(false)"
        >
          <RefreshCw class="h-3.5 w-3.5" :class="{ 'animate-spin': downloadsStore.refreshing }" />
          <span>刷新</span>
        </button>
      </div>
    </div>

    <!-- Direct Lookup via GET /api/downloads/{task_id} -->
    <form
      class="flex flex-col gap-2 sm:flex-row sm:items-center"
      @submit.prevent="handleLookupTask"
    >
      <div class="relative flex-1 sm:max-w-sm">
        <Hash class="pointer-events-none absolute top-1/2 left-3 h-3.5 w-3.5 -translate-y-1/2 text-[var(--text-muted)]" />
        <input
          id="lookup-task-id-input"
          v-model="lookupTaskId"
          type="text"
          :placeholder="settingsStore.t('downloads.lookupPlaceholder')"
          class="input-field w-full rounded-lg py-1.5 pr-3 pl-8 font-mono text-xs"
        />
      </div>
      <button
        type="submit"
        class="btn-secondary inline-flex items-center justify-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium"
        :disabled="!lookupTaskId.trim() || lookupLoading"
      >
        <Loader2 v-if="lookupLoading" class="h-3.5 w-3.5 animate-spin" />
        <span>{{ settingsStore.t('downloads.lookupBtn') }}</span>
      </button>
      <span v-if="lookupError" class="text-xs text-rose-500 dark:text-rose-400">
        {{ lookupError }}
      </span>
      <span v-else class="text-[11px] text-[var(--text-muted)]">
        已完成任务由 WebUI 跟踪并通过官方 GET /api/downloads/{task_id} 实时校验
      </span>
    </form>

    <!-- Initial Loading Skeleton -->
    <div
      v-if="downloadsStore.initialLoading"
      class="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3"
    >
      <div
        v-for="i in 6"
        :key="i"
        class="surface-card h-44 animate-pulse rounded-xl p-4"
      >
        <div class="h-5 w-24 rounded bg-[var(--bg-subtle)]" />
        <div class="mt-4 h-4 w-3/4 rounded bg-[var(--bg-subtle)]" />
        <div class="mt-2 h-4 w-1/2 rounded bg-[var(--bg-subtle)]" />
        <div class="mt-8 h-3 w-2/3 rounded bg-[var(--bg-subtle)]" />
      </div>
    </div>

    <!-- Empty State -->
    <EmptyState
      v-else-if="filteredTasks.length === 0"
      :title="settingsStore.t('downloads.emptyTitle')"
      :description="settingsStore.t('downloads.emptyDesc')"
    >
      <template #icon>
        <Download class="h-5 w-5" />
      </template>
      <template #action>
        <button
          type="button"
          class="btn-primary inline-flex items-center gap-1.5 rounded-lg px-4 py-2 text-xs font-semibold"
          @click="downloadsStore.openNewDownloadModal()"
        >
          <Plus class="h-4 w-4" />
          <span>{{ settingsStore.t('action.newDownload') }}</span>
        </button>
      </template>
    </EmptyState>

    <!-- Card View -->
    <div
      v-else-if="viewMode === 'card'"
      class="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3"
    >
      <TaskCard
        v-for="task in filteredTasks"
        :key="task.id"
        :task="task"
        @select="downloadsStore.inspectTask($event.id)"
      />
    </div>

    <!-- List / Table View -->
    <div v-else class="surface-card overflow-hidden rounded-xl">
      <div class="overflow-x-auto">
        <table class="w-full border-collapse text-left">
          <thead>
            <tr
              class="border-b border-[var(--border-default)] bg-[var(--bg-subtle)] text-[11px] font-semibold uppercase tracking-wide text-[var(--text-muted)]"
            >
              <th class="py-2.5 pl-4 pr-3">任务 / 番剧信息</th>
              <th class="px-3 py-2.5">真实状态</th>
              <th class="hidden px-3 py-2.5 lg:table-cell">最终 / 保存路径</th>
              <th class="hidden px-3 py-2.5 md:table-cell">添加 / 完成时间</th>
              <th class="py-2.5 pl-2 pr-4 text-right">详情</th>
            </tr>
          </thead>
          <tbody>
            <TaskRow
              v-for="task in filteredTasks"
              :key="task.id"
              :task="task"
              @select="downloadsStore.inspectTask($event.id)"
            />
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>
