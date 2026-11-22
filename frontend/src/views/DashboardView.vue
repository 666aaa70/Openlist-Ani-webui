<script setup lang="ts">
import { computed } from 'vue'
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  Clock,
  Cpu,
  Download,
  Plus,
  Server,
  ShieldAlert,
  XCircle,
} from 'lucide-vue-next'
import { useDownloadsStore } from '@/stores/downloads'
import { useHealthStore } from '@/stores/health'
import { useSettingsStore } from '@/stores/settings'
import { formatDateTime, formatSeasonEpisode } from '@/utils/format'
import EmptyState from '@/components/common/EmptyState.vue'
import ErrorBanner from '@/components/common/ErrorBanner.vue'
import TaskStatusBadge from '@/components/downloads/TaskStatusBadge.vue'

const downloadsStore = useDownloadsStore()
const healthStore = useHealthStore()
const settingsStore = useSettingsStore()

const recentTasks = computed(() => downloadsStore.tasks.slice(0, 6))

const recentErrorTasks = computed(() =>
  downloadsStore.tasks
    .filter(
      (task) =>
        task.state === 'failed' ||
        Boolean(task.error_message) ||
        task.warning_count > 0 ||
        task.items.some((item) => Boolean(item.error) || item.state === 'failed'),
    )
    .slice(0, 6),
)

const healthSummary = computed(() => {
  const h = healthStore.health
  if (!h) {
    return {
      title: '正在检测',
      subtitle: '等待服务端返回健康探针数据',
      tone: 'slate' as const,
    }
  }
  if (!h.upstream_reachable) {
    return {
      title: '无法连接',
      subtitle: h.error_message || '无法访问 Openlist-Ani 内部服务',
      tone: 'rose' as const,
    }
  }
  if (h.upstream_ready) {
    const workerText = h.workers
      ? `工作线程 ${h.workers.running}/${h.workers.expected}`
      : '服务已就绪'
    const latencyText = h.latency_ms !== null ? ` · 延迟 ${h.latency_ms}ms` : ''
    return {
      title: '运行正常',
      subtitle: `${workerText}${latencyText}`,
      tone: 'emerald' as const,
    }
  }
  return {
    title: h.upstream_status === 'starting' ? '正在启动' : '服务降级',
    subtitle: `状态: ${h.upstream_status}`,
    tone: 'amber' as const,
  }
})

const degradedEntries = computed(() => {
  const map = healthStore.health?.degraded
  if (!map) return []
  return Object.entries(map)
})
</script>

<template>
  <div class="space-y-6">
    <!-- Unreachable / API Error Banner -->
    <ErrorBanner
      v-if="downloadsStore.error"
      title="Openlist-Ani 连接异常"
      :message="downloadsStore.error"
      retryable
      @retry="downloadsStore.refreshAll(false)"
    />

    <!-- KPI Cards (Real API Counts Only) -->
    <section aria-label="核心状态指标" class="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
      <RouterLink
        to="/downloads"
        class="surface-card-interactive flex items-start justify-between rounded-xl p-4"
      >
        <div>
          <p class="text-xs font-medium text-[var(--text-secondary)]">
            {{ settingsStore.t('dashboard.active') }}
          </p>
          <p class="mt-2 font-mono text-2xl font-semibold text-[var(--text-primary)] tabular-nums">
            {{ downloadsStore.activeCount }}
          </p>
          <p class="mt-1 text-[11px] text-[var(--text-muted)]">等待 / 下载 / 解析 / 重命名中</p>
        </div>
        <div class="flex h-9 w-9 items-center justify-center rounded-lg bg-sky-500/12 text-sky-500">
          <Download class="h-4 w-4" />
        </div>
      </RouterLink>

      <RouterLink
        to="/downloads"
        class="surface-card-interactive flex items-start justify-between rounded-xl p-4"
      >
        <div>
          <p class="text-xs font-medium text-[var(--text-secondary)]">
            {{ settingsStore.t('dashboard.completed') }}
          </p>
          <p class="mt-2 font-mono text-2xl font-semibold text-[var(--text-primary)] tabular-nums">
            {{ downloadsStore.completedCount }}
          </p>
          <p class="mt-1 text-[11px] text-[var(--text-muted)]">经官方任务接口核验已完成</p>
        </div>
        <div class="flex h-9 w-9 items-center justify-center rounded-lg bg-emerald-500/12 text-emerald-500">
          <CheckCircle2 class="h-4 w-4" />
        </div>
      </RouterLink>

      <RouterLink
        to="/downloads"
        class="surface-card-interactive flex items-start justify-between rounded-xl p-4"
      >
        <div>
          <p class="text-xs font-medium text-[var(--text-secondary)]">
            {{ settingsStore.t('dashboard.failed') }}
          </p>
          <p class="mt-2 font-mono text-2xl font-semibold text-[var(--text-primary)] tabular-nums">
            {{ downloadsStore.failedCount }}
          </p>
          <p class="mt-1 text-[11px] text-[var(--text-muted)]">需要排查失败原因的任务</p>
        </div>
        <div class="flex h-9 w-9 items-center justify-center rounded-lg bg-rose-500/12 text-rose-500">
          <XCircle class="h-4 w-4" />
        </div>
      </RouterLink>

      <RouterLink
        to="/settings"
        class="surface-card-interactive flex items-start justify-between rounded-xl p-4"
      >
        <div class="min-w-0 pr-2">
          <p class="text-xs font-medium text-[var(--text-secondary)]">
            {{ settingsStore.t('dashboard.serviceHealth') }}
          </p>
          <p
            class="mt-2 text-lg font-semibold"
            :class="{
              'text-emerald-500': healthSummary.tone === 'emerald',
              'text-amber-500': healthSummary.tone === 'amber',
              'text-rose-500': healthSummary.tone === 'rose',
              'text-[var(--text-secondary)]': healthSummary.tone === 'slate',
            }"
          >
            {{ healthSummary.title }}
          </p>
          <p class="mt-1 truncate text-[11px] text-[var(--text-muted)]" :title="healthSummary.subtitle">
            {{ healthSummary.subtitle }}
          </p>
        </div>
        <div
          class="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg"
          :class="{
            'bg-emerald-500/12 text-emerald-500': healthSummary.tone === 'emerald',
            'bg-amber-500/12 text-amber-500': healthSummary.tone === 'amber',
            'bg-rose-500/12 text-rose-500': healthSummary.tone === 'rose',
            'bg-slate-500/12 text-slate-400': healthSummary.tone === 'slate',
          }"
        >
          <Server class="h-4 w-4" />
        </div>
      </RouterLink>
    </section>

    <!-- Degraded Workers Detail (Only when upstream actually reports degraded components) -->
    <section
      v-if="degradedEntries.length > 0"
      class="rounded-xl border border-amber-500/35 bg-amber-500/10 p-4 text-xs"
    >
      <div class="flex items-center gap-2 font-semibold text-amber-700 dark:text-amber-300">
        <ShieldAlert class="h-4 w-4" />
        <span>Openlist-Ani 降级组件告警</span>
      </div>
      <dl class="mt-2.5 space-y-1.5 font-mono text-[11px]">
        <div
          v-for="[key, reason] in degradedEntries"
          :key="key"
          class="flex flex-col gap-0.5 rounded-lg bg-[var(--bg-chrome)] px-3 py-2 sm:flex-row sm:gap-3"
        >
          <dt class="font-semibold text-amber-600 dark:text-amber-300">{{ key }}</dt>
          <dd class="text-[var(--text-secondary)]">{{ reason }}</dd>
        </div>
      </dl>
    </section>

    <!-- Two-Column Main Area: Recent Tasks & Recent Errors -->
    <div class="grid grid-cols-1 gap-6 xl:grid-cols-5">
      <!-- Recent Tasks (3 cols) -->
      <section class="surface-card flex flex-col rounded-xl xl:col-span-3">
        <div class="flex items-center justify-between border-b border-[var(--border-default)] px-4 py-3.5">
          <div class="flex items-center gap-2">
            <Activity class="h-4 w-4 text-[var(--accent)]" />
            <h2 class="text-sm font-semibold text-[var(--text-primary)]">
              {{ settingsStore.t('dashboard.recentTasks') }}
            </h2>
          </div>
          <RouterLink
            to="/downloads"
            class="inline-flex items-center gap-1 text-xs font-medium text-[var(--accent)] hover:underline"
          >
            查看全部
            <ArrowRight class="h-3.5 w-3.5" />
          </RouterLink>
        </div>

        <div v-if="downloadsStore.initialLoading" class="space-y-2 p-4">
          <div v-for="i in 4" :key="i" class="h-14 animate-pulse rounded-lg bg-[var(--bg-subtle)]" />
        </div>

        <div v-else-if="recentTasks.length === 0" class="p-6">
          <EmptyState
            title="暂无下载任务"
            description="点击「新建下载」提交磁力或 .torrent 任务，或等待 Openlist-Ani 自动拉取 RSS 更新。"
          >
            <template #action>
              <button
                type="button"
                class="btn-primary inline-flex items-center gap-1.5 rounded-lg px-3.5 py-2 text-xs font-semibold"
                @click="downloadsStore.openNewDownloadModal()"
              >
                <Plus class="h-3.5 w-3.5" />
                <span>新建下载</span>
              </button>
            </template>
          </EmptyState>
        </div>

        <ul v-else class="divide-y divide-[var(--border-default)]">
          <li
            v-for="task in recentTasks"
            :key="task.id"
            class="flex cursor-pointer items-center justify-between gap-3 px-4 py-3 transition hover:bg-[var(--bg-surface-hover)]"
            @click="downloadsStore.inspectTask(task.id)"
          >
            <div class="min-w-0 flex-1">
              <p class="truncate text-sm font-medium text-[var(--text-primary)]" :title="task.title">
                {{ task.title }}
              </p>
              <div class="mt-1 flex flex-wrap items-center gap-2 text-[11px] text-[var(--text-muted)] tabular-nums">
                <span v-if="task.anime_name" class="text-[var(--text-secondary)]">
                  {{ task.anime_name }}
                </span>
                <span v-if="formatSeasonEpisode(task.season, task.episode)" class="font-mono">
                  {{ formatSeasonEpisode(task.season, task.episode) }}
                </span>
                <span class="inline-flex items-center gap-1">
                  <Clock class="h-3 w-3" />
                  {{ formatDateTime(task.updated_at, settingsStore.language) }}
                </span>
              </div>
            </div>
            <TaskStatusBadge :state="task.state" compact />
          </li>
        </ul>
      </section>

      <!-- Recent Errors & Service Details (2 cols) -->
      <div class="space-y-6 xl:col-span-2">
        <section class="surface-card rounded-xl">
          <div class="flex items-center justify-between border-b border-[var(--border-default)] px-4 py-3.5">
            <div class="flex items-center gap-2">
              <AlertTriangle class="h-4 w-4 text-rose-500" />
              <h2 class="text-sm font-semibold text-[var(--text-primary)]">
                {{ settingsStore.t('dashboard.recentErrors') }}
              </h2>
            </div>
            <span class="font-mono text-xs text-[var(--text-muted)] tabular-nums">
              {{ recentErrorTasks.length }}
            </span>
          </div>

          <div v-if="recentErrorTasks.length === 0" class="px-4 py-8 text-center text-xs text-[var(--text-muted)]">
            当前没有任务失败或文件处理错误记录。
          </div>

          <ul v-else class="divide-y divide-[var(--border-default)]">
            <li
              v-for="task in recentErrorTasks"
              :key="task.id"
              class="cursor-pointer px-4 py-3 transition hover:bg-[var(--bg-surface-hover)]"
              @click="downloadsStore.inspectTask(task.id)"
            >
              <div class="flex items-center justify-between gap-2">
                <p class="truncate text-xs font-medium text-[var(--text-primary)]" :title="task.title">
                  {{ task.title }}
                </p>
                <TaskStatusBadge :state="task.state" compact />
              </div>
              <p
                v-if="task.error_message"
                class="mt-1.5 line-clamp-2 break-all font-mono text-[11px] text-rose-500 dark:text-rose-400"
              >
                {{ task.error_message }}
              </p>
              <p
                v-else-if="task.warning_count > 0"
                class="mt-1 text-[11px] text-amber-600 dark:text-amber-300"
              >
                包含 {{ task.warning_count }} 条单文件告警，点击查看明细
              </p>
            </li>
          </ul>
        </section>

        <!-- Upstream Health Detail Card -->
        <section class="surface-card rounded-xl p-4">
          <div class="flex items-center gap-2 text-xs font-semibold text-[var(--text-primary)]">
            <Cpu class="h-4 w-4 text-[var(--accent)]" />
            <span>Openlist-Ani 实时探针</span>
          </div>
          <dl class="mt-3 space-y-2 text-xs">
            <div class="flex items-center justify-between">
              <dt class="text-[var(--text-muted)]">连通状态</dt>
              <dd class="font-medium text-[var(--text-primary)]">
                {{ healthStore.health?.upstream_reachable ? '已连接' : '未连接' }}
              </dd>
            </div>
            <div class="flex items-center justify-between">
              <dt class="text-[var(--text-muted)]">/health/live</dt>
              <dd class="font-mono text-[var(--text-secondary)]">
                {{ healthStore.health?.upstream_live ? 'live' : 'unavailable' }}
              </dd>
            </div>
            <div class="flex items-center justify-between">
              <dt class="text-[var(--text-muted)]">/health/ready</dt>
              <dd class="font-mono text-[var(--text-secondary)]">
                {{ healthStore.health?.upstream_status || '—' }}
              </dd>
            </div>
            <div class="flex items-center justify-between">
              <dt class="text-[var(--text-muted)]">后台工作线程</dt>
              <dd class="font-mono text-[var(--text-secondary)] tabular-nums">
                {{
                  healthStore.health?.workers
                    ? `${healthStore.health.workers.running} / ${healthStore.health.workers.expected}`
                    : '—'
                }}
              </dd>
            </div>
            <div class="flex items-center justify-between">
              <dt class="text-[var(--text-muted)]">检测时间</dt>
              <dd class="font-mono text-[11px] text-[var(--text-muted)] tabular-nums">
                {{ formatDateTime(healthStore.health?.checked_at, settingsStore.language) }}
              </dd>
            </div>
          </dl>
        </section>
      </div>
    </div>
  </div>
</template>
