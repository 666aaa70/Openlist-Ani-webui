<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import {
  AlertTriangle,
  Check,
  Copy,
  FileVideo,
  FolderOpen,
  RefreshCw,
  X,
} from 'lucide-vue-next'
import { useDownloadsStore } from '@/stores/downloads'
import { useSettingsStore } from '@/stores/settings'
import { formatDateTime, formatSeasonEpisode, getTaskStateInfo } from '@/utils/format'
import TaskStatusBadge from './TaskStatusBadge.vue'

const downloadsStore = useDownloadsStore()
const settingsStore = useSettingsStore()

const copiedKey = ref<string | null>(null)
const task = computed(() => downloadsStore.selectedTask)

const pipelineSteps = [
  { index: 1, label: '队列等待' },
  { index: 2, label: '离线下载' },
  { index: 3, label: '文件解析' },
  { index: 4, label: '番剧重命名' },
  { index: 5, label: '入库完成' },
]

const currentStageIndex = computed(() => {
  if (!task.value) return 0
  return getTaskStateInfo(task.value.state).stageIndex
})

const isTerminalError = computed(() => {
  const s = task.value?.state
  return s === 'failed' || s === 'cancelled'
})

async function copyText(key: string, value: string): Promise<void> {
  try {
    await navigator.clipboard.writeText(value)
    copiedKey.value = key
    window.setTimeout(() => {
      if (copiedKey.value === key) copiedKey.value = null
    }, 1800)
  } catch {
    // Clipboard unavailable
  }
}

async function refreshTask(): Promise<void> {
  if (!task.value) return
  await downloadsStore.inspectTask(task.value.id)
}

function handleKeydown(event: KeyboardEvent): void {
  if (event.key === 'Escape' && task.value) {
    downloadsStore.closeTaskDetail()
  }
}

onMounted(() => window.addEventListener('keydown', handleKeydown))
onBeforeUnmount(() => window.removeEventListener('keydown', handleKeydown))
</script>

<template>
  <Teleport to="body">
    <div
      v-if="task"
      class="fixed inset-0 z-50 flex justify-end bg-black/60 backdrop-blur-[2px]"
      role="dialog"
      aria-modal="true"
      aria-label="任务详情"
      @click.self="downloadsStore.closeTaskDetail()"
    >
      <div
        class="flex h-full w-full max-w-2xl flex-col border-l border-[var(--border-default)] bg-[var(--bg-chrome)] shadow-2xl"
      >
        <!-- Header -->
        <div class="flex items-start justify-between gap-3 border-b border-[var(--border-default)] px-5 py-4">
          <div class="min-w-0">
            <div class="flex flex-wrap items-center gap-2">
              <TaskStatusBadge :state="task.state" />
              <span
                v-if="task.retry_count > 0"
                class="rounded border border-amber-500/30 bg-amber-500/10 px-2 py-0.5 text-[11px] font-medium text-amber-600 dark:text-amber-300 tabular-nums"
              >
                重试 {{ task.retry_count }} 次
              </span>
              <span
                v-if="task.warning_count > 0"
                class="rounded border border-amber-500/30 bg-amber-500/10 px-2 py-0.5 text-[11px] font-medium text-amber-600 dark:text-amber-300 tabular-nums"
              >
                {{ task.warning_count }} 条文件告警
              </span>
            </div>
            <h2 class="mt-2 break-words text-base font-semibold leading-snug text-[var(--text-primary)]">
              {{ task.title }}
            </h2>
          </div>

          <div class="flex shrink-0 items-center gap-1.5">
            <button
              type="button"
              class="btn-secondary inline-flex h-8 w-8 items-center justify-center rounded-lg"
              title="刷新此任务"
              :disabled="downloadsStore.selectedTaskLoading"
              @click="refreshTask"
            >
              <RefreshCw
                class="h-4 w-4"
                :class="{ 'animate-spin': downloadsStore.selectedTaskLoading }"
              />
            </button>
            <button
              type="button"
              class="btn-secondary inline-flex h-8 w-8 items-center justify-center rounded-lg"
              title="关闭"
              @click="downloadsStore.closeTaskDetail()"
            >
              <X class="h-4 w-4" />
            </button>
          </div>
        </div>

        <!-- Body -->
        <div class="flex-1 space-y-5 overflow-y-auto px-5 py-5">
          <!-- Fetch Error -->
          <div
            v-if="downloadsStore.selectedTaskError"
            class="rounded-lg border border-rose-500/30 bg-rose-500/10 px-3.5 py-2.5 text-xs text-rose-500 dark:text-rose-300"
          >
            {{ downloadsStore.selectedTaskError }}
          </div>

          <!-- Real Stage Stepper (No Fake Percentages) -->
          <section class="surface-card rounded-xl p-4">
            <div class="mb-3 flex items-center justify-between text-xs">
              <span class="font-medium text-[var(--text-secondary)]">任务执行阶段（Openlist-Ani 真实状态）</span>
              <code class="rounded bg-[var(--bg-subtle)] px-1.5 py-0.5 font-mono text-[11px] text-[var(--text-muted)]">
                state: {{ task.state }}
              </code>
            </div>
            <div class="grid grid-cols-5 gap-1.5">
              <div
                v-for="step in pipelineSteps"
                :key="step.index"
                class="flex flex-col gap-1.5"
              >
                <div
                  class="h-1.5 rounded-full transition-colors"
                  :class="
                    isTerminalError
                      ? 'bg-rose-500/35'
                      : currentStageIndex >= step.index
                        ? 'bg-[var(--accent)]'
                        : 'bg-[var(--border-default)]'
                  "
                />
                <span
                  class="text-[11px]"
                  :class="
                    !isTerminalError && currentStageIndex === step.index
                      ? 'font-semibold text-[var(--text-primary)]'
                      : 'text-[var(--text-muted)]'
                  "
                >
                  {{ step.label }}
                </span>
              </div>
            </div>
          </section>

          <!-- Error Message -->
          <section
            v-if="task.error_message"
            class="rounded-xl border border-rose-500/30 bg-rose-500/10 p-4"
          >
            <div class="flex items-center gap-2 text-xs font-semibold text-rose-600 dark:text-rose-300">
              <AlertTriangle class="h-4 w-4" />
              <span>失败原因</span>
            </div>
            <p class="mt-2 break-all font-mono text-xs leading-relaxed text-rose-700 dark:text-rose-200">
              {{ task.error_message }}
            </p>
          </section>

          <!-- Anime Metadata returned by Openlist-Ani -->
          <section class="surface-card rounded-xl p-4">
            <h3 class="text-xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">
              番剧识别信息（Openlist-Ani 返回）
            </h3>
            <dl class="mt-3 grid grid-cols-2 gap-3 text-xs sm:grid-cols-3">
              <div>
                <dt class="text-[var(--text-muted)]">番剧名称</dt>
                <dd class="mt-0.5 font-medium text-[var(--text-primary)]">
                  {{ task.anime_name || '尚未识别' }}
                </dd>
              </div>
              <div>
                <dt class="text-[var(--text-muted)]">季 / 集</dt>
                <dd class="mt-0.5 font-mono font-medium text-[var(--text-primary)]">
                  {{ formatSeasonEpisode(task.season, task.episode) || '—' }}
                </dd>
              </div>
              <div>
                <dt class="text-[var(--text-muted)]">字幕组</dt>
                <dd class="mt-0.5 font-medium text-[var(--text-primary)]">
                  {{ task.fansub || '—' }}
                </dd>
              </div>
              <div>
                <dt class="text-[var(--text-muted)]">清晰度</dt>
                <dd class="mt-0.5 font-mono font-medium text-[var(--text-primary)]">
                  {{ task.quality || '—' }}
                </dd>
              </div>
              <div class="col-span-2">
                <dt class="text-[var(--text-muted)]">任务 ID</dt>
                <dd class="mt-0.5 flex items-center gap-1.5">
                  <code class="truncate font-mono text-[11px] text-[var(--text-primary)]">{{ task.id }}</code>
                  <button
                    type="button"
                    class="rounded p-1 text-[var(--text-muted)] hover:bg-[var(--bg-subtle)] hover:text-[var(--text-primary)]"
                    title="复制任务 ID"
                    @click="copyText('id', task.id)"
                  >
                    <Check v-if="copiedKey === 'id'" class="h-3.5 w-3.5 text-emerald-400" />
                    <Copy v-else class="h-3.5 w-3.5" />
                  </button>
                </dd>
              </div>
            </dl>
          </section>

          <!-- Timestamps -->
          <section class="surface-card rounded-xl p-4">
            <h3 class="text-xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">
              时间线
            </h3>
            <dl class="mt-3 grid grid-cols-1 gap-2.5 text-xs sm:grid-cols-2 tabular-nums">
              <div class="flex justify-between gap-2 sm:block">
                <dt class="text-[var(--text-muted)]">添加时间</dt>
                <dd class="mt-0.5 text-[var(--text-primary)]">
                  {{ formatDateTime(task.created_at, settingsStore.language) }}
                </dd>
              </div>
              <div class="flex justify-between gap-2 sm:block">
                <dt class="text-[var(--text-muted)]">开始时间</dt>
                <dd class="mt-0.5 text-[var(--text-primary)]">
                  {{ formatDateTime(task.started_at, settingsStore.language) }}
                </dd>
              </div>
              <div class="flex justify-between gap-2 sm:block">
                <dt class="text-[var(--text-muted)]">最近更新</dt>
                <dd class="mt-0.5 text-[var(--text-primary)]">
                  {{ formatDateTime(task.updated_at, settingsStore.language) }}
                </dd>
              </div>
              <div class="flex justify-between gap-2 sm:block">
                <dt class="text-[var(--text-muted)]">完成时间</dt>
                <dd class="mt-0.5 text-[var(--text-primary)]">
                  {{ formatDateTime(task.completed_at, settingsStore.language) }}
                </dd>
              </div>
            </dl>
          </section>

          <!-- Paths & Source URL -->
          <section class="surface-card rounded-xl p-4 space-y-3">
            <h3 class="text-xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">
              路径与来源
            </h3>

            <div>
              <p class="text-[11px] text-[var(--text-muted)]">目标保存目录 (save_path)</p>
              <p class="mt-1 break-all rounded-lg bg-[var(--bg-subtle)] px-3 py-2 font-mono text-xs text-[var(--text-primary)]">
                {{ task.save_path || '—' }}
              </p>
            </div>

            <div v-if="task.final_path || task.final_paths.length > 0">
              <p class="text-[11px] text-[var(--text-muted)]">最终文件路径</p>
              <div class="mt-1 space-y-1.5">
                <div
                  v-for="(fp, idx) in task.final_paths.length > 0 ? task.final_paths : [task.final_path!]"
                  :key="fp + idx"
                  class="flex items-center justify-between gap-2 rounded-lg bg-[var(--bg-subtle)] px-3 py-2"
                >
                  <div class="flex min-w-0 items-center gap-2">
                    <FolderOpen class="h-3.5 w-3.5 shrink-0 text-emerald-500" />
                    <code class="break-all font-mono text-xs text-[var(--text-primary)]">{{ fp }}</code>
                  </div>
                  <button
                    type="button"
                    class="shrink-0 rounded p-1 text-[var(--text-muted)] hover:text-[var(--text-primary)]"
                    title="复制路径"
                    @click="copyText(`fp-${idx}`, fp)"
                  >
                    <Check v-if="copiedKey === `fp-${idx}`" class="h-3.5 w-3.5 text-emerald-400" />
                    <Copy v-else class="h-3.5 w-3.5" />
                  </button>
                </div>
              </div>
            </div>

            <div>
              <div class="flex items-center justify-between">
                <p class="text-[11px] text-[var(--text-muted)]">下载链接</p>
                <button
                  type="button"
                  class="inline-flex items-center gap-1 text-[11px] text-[var(--accent)] hover:underline"
                  @click="copyText('url', task.download_url)"
                >
                  <Check v-if="copiedKey === 'url'" class="h-3 w-3" />
                  <Copy v-else class="h-3 w-3" />
                  {{ copiedKey === 'url' ? '已复制' : '复制链接' }}
                </button>
              </div>
              <p class="mt-1 max-h-24 overflow-y-auto break-all rounded-lg bg-[var(--bg-subtle)] px-3 py-2 font-mono text-[11px] text-[var(--text-secondary)]">
                {{ task.download_url }}
              </p>
            </div>
          </section>

          <!-- Per-file Execution Items -->
          <section class="surface-card rounded-xl p-4">
            <div class="flex items-center justify-between">
              <h3 class="text-xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">
                单文件执行结果 ({{ task.items.length }})
              </h3>
            </div>

            <div v-if="task.items.length === 0" class="mt-3 text-xs text-[var(--text-muted)]">
              当前暂无单文件明细条目（通常在下载完成进入解析与重命名阶段后由 Openlist-Ani 生成）。
            </div>

            <div v-else class="mt-3 space-y-2.5">
              <div
                v-for="item in task.items"
                :key="item.item_key"
                class="rounded-lg border border-[var(--border-default)] bg-[var(--bg-subtle)] p-3 text-xs"
              >
                <div class="flex flex-wrap items-center justify-between gap-2">
                  <div class="flex items-center gap-2 min-w-0">
                    <FileVideo class="h-3.5 w-3.5 shrink-0 text-[var(--accent)]" />
                    <span class="font-medium text-[var(--text-primary)]">
                      {{ item.anime_name || item.item_key }}
                    </span>
                    <span
                      v-if="formatSeasonEpisode(item.season, item.episode)"
                      class="rounded border border-[var(--border-default)] px-1.5 py-0.5 font-mono text-[11px] text-[var(--text-secondary)]"
                    >
                      {{ formatSeasonEpisode(item.season, item.episode) }}
                    </span>
                  </div>
                  <TaskStatusBadge :state="item.state" compact />
                </div>

                <div v-if="item.source_path" class="mt-2 break-all font-mono text-[11px] text-[var(--text-muted)]">
                  源文件: {{ item.source_path }}
                </div>
                <div
                  v-if="item.final_path"
                  class="mt-1 break-all font-mono text-[11px] text-emerald-600 dark:text-emerald-400"
                >
                  目标路径: {{ item.final_path }}
                </div>
                <div
                  v-if="item.error"
                  class="mt-1.5 rounded bg-rose-500/10 px-2 py-1 font-mono text-[11px] text-rose-600 dark:text-rose-300"
                >
                  错误: {{ item.error }}
                </div>
              </div>
            </div>
          </section>

          <p class="text-[11px] text-[var(--text-muted)]">
            提示：Openlist-Ani 官方 API 当前仅提供任务查询接口，未提供取消或删除任务接口，因此界面不虚构删除操作。
          </p>
        </div>
      </div>
    </div>
  </Teleport>
</template>
