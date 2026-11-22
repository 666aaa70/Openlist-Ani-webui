<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import {
  AlertTriangle,
  CheckCircle2,
  FileText,
  FileVideo,
  Link2,
  Loader2,
  Magnet,
  ShieldAlert,
  Sparkles,
  X,
} from 'lucide-vue-next'
import { api, ApiClientError } from '@/api/client'
import type {
  DownloadPreflightResponse,
  PolicyConflictResponse,
  ResolveResourceResponse,
} from '@/types/api'
import { formatBytes } from '@/utils/format'
import { allowsManualTitleFallback, detectResourceType } from '@/utils/torrent'

const props = defineProps<{
  open: boolean
}>()

const emit = defineEmits<{
  close: []
  created: [taskId: string]
}>()

const rawLink = ref('')
const metadataTimeout = ref(30)
const title = ref('')
const collectionHint = ref(false)
const userEditedCollectionHint = ref(false)

const resolving = ref(false)
const resolveError = ref<string | null>(null)
const resolved = ref<ResolveResourceResponse | null>(null)

const preflighting = ref(false)
const submitting = ref(false)
const preflightResult = ref<DownloadPreflightResponse | null>(null)
const pendingConflicts = ref<PolicyConflictResponse[]>([])
const pendingWarnings = ref<string[]>([])
const pendingReviewToken = ref<string | null>(null)
const conflictsConfirmed = ref(false)
const submitError = ref<string | null>(null)
const submitBlockedMessage = ref<string | null>(null)

let autoResolveTimer: number | null = null

const detectedType = computed(() => detectResourceType(rawLink.value))

const linkValid = computed(() => detectedType.value !== 'unknown')

const needsConflictConfirmation = computed(
  () => pendingConflicts.value.length > 0 && pendingReviewToken.value !== null,
)

const isHardResolverBlock = computed(() => {
  if (!resolved.value || resolved.value.success) return false
  return !allowsManualTitleFallback(resolved.value.resource_type, resolved.value.error_code)
})

const canRunSubmit = computed(() => {
  if (!linkValid.value) return false
  if (!title.value.trim()) return false
  if (resolving.value || preflighting.value || submitting.value) return false
  if (isHardResolverBlock.value) return false
  if (needsConflictConfirmation.value && !conflictsConfirmed.value) return false
  return true
})

function resetPreflightState(): void {
  preflightResult.value = null
  pendingConflicts.value = []
  pendingWarnings.value = []
  pendingReviewToken.value = null
  conflictsConfirmed.value = false
  submitError.value = null
  submitBlockedMessage.value = null
}

function resetAll(): void {
  if (autoResolveTimer !== null) {
    window.clearTimeout(autoResolveTimer)
    autoResolveTimer = null
  }
  rawLink.value = ''
  metadataTimeout.value = 30
  title.value = ''
  collectionHint.value = false
  userEditedCollectionHint.value = false
  resolving.value = false
  resolveError.value = null
  resolved.value = null
  preflighting.value = false
  submitting.value = false
  resetPreflightState()
}

watch(
  () => props.open,
  (isOpen) => {
    if (!isOpen) {
      resetAll()
    }
  },
)

// Invalidate preflight confirmation whenever user edits URL, title, or collection_hint
// because Openlist-Ani binds policy_review_token via HMAC to these exact fields.
watch([rawLink, title, collectionHint], () => {
  if (preflightResult.value || pendingConflicts.value.length > 0 || submitBlockedMessage.value) {
    resetPreflightState()
  }
})

function handleLinkPaste(): void {
  if (autoResolveTimer !== null) {
    window.clearTimeout(autoResolveTimer)
  }
  autoResolveTimer = window.setTimeout(() => {
    if (detectResourceType(rawLink.value) !== 'unknown') {
      void runResolve()
    }
  }, 150)
}

async function runResolve(): Promise<void> {
  const cleaned = rawLink.value.trim()
  const type = detectResourceType(cleaned)
  if (type === 'unknown') {
    resolveError.value = '请粘贴有效的 magnet:? 磁力链接或 http(s):// .torrent 下载链接'
    return
  }

  resolving.value = true
  resolveError.value = null
  resolved.value = null
  resetPreflightState()

  try {
    const data =
      type === 'magnet'
        ? await api.resolveMagnet(cleaned, metadataTimeout.value)
        : await api.resolveTorrent(cleaned)

    resolved.value = data
    if (data.title && data.title.trim()) {
      title.value = data.title.trim()
    } else if (!title.value.trim()) {
      // Never fabricate a title when upstream couldn't resolve one
      title.value = ''
    }

    if (!userEditedCollectionHint.value) {
      collectionHint.value = data.collection_hint
    }
  } catch (err) {
    resolveError.value = err instanceof ApiClientError ? err.message : '解析资源失败，请检查 Openlist-Ani 连接'
  } finally {
    resolving.value = false
  }
}

async function handleSubmit(): Promise<void> {
  const cleanedUrl = rawLink.value.trim()
  const cleanedTitle = title.value.trim()
  if (!cleanedUrl || !cleanedTitle) return

  submitError.value = null
  submitBlockedMessage.value = null

  // If user already reviewed & confirmed conflicts from preflight, submit directly with override
  if (needsConflictConfirmation.value) {
    if (!conflictsConfirmed.value) return
    await executeCreateDownload({
      downloadUrl: cleanedUrl,
      title: cleanedTitle,
      overridePolicy: true,
      acknowledgedConflicts: pendingConflicts.value.map((c) => c.key),
      reviewToken: pendingReviewToken.value,
    })
    return
  }

  // Step 1: Always run POST /api/downloads/preflight first
  preflighting.value = true
  try {
    const pre = await api.preflightDownload({
      download_url: cleanedUrl,
      title: cleanedTitle,
      collection_hint: collectionHint.value,
    })
    preflightResult.value = pre

    if (!pre.success) {
      // Hard blocker (e.g. already downloaded / already active) — do NOT allow override
      submitBlockedMessage.value = pre.message
      return
    }

    if (pre.confirmation_required && pre.policy_conflicts.length > 0) {
      pendingConflicts.value = pre.policy_conflicts
      pendingWarnings.value = pre.policy_warnings
      pendingReviewToken.value = pre.policy_review_token
      conflictsConfirmed.value = false
      return
    }

    pendingWarnings.value = pre.policy_warnings
  } catch (err) {
    submitError.value = err instanceof ApiClientError ? err.message : '预检请求失败'
    return
  } finally {
    preflighting.value = false
  }

  // Step 2: Preflight clean -> submit POST /api/downloads
  await executeCreateDownload({
    downloadUrl: cleanedUrl,
    title: cleanedTitle,
    overridePolicy: false,
    acknowledgedConflicts: [],
    reviewToken: null,
  })
}

async function executeCreateDownload(params: {
  downloadUrl: string
  title: string
  overridePolicy: boolean
  acknowledgedConflicts: string[]
  reviewToken: string | null
}): Promise<void> {
  submitting.value = true
  submitError.value = null
  try {
    const res = await api.createDownload({
      download_url: params.downloadUrl,
      title: params.title,
      collection_hint: collectionHint.value,
      override_policy: params.overridePolicy,
      acknowledged_conflicts: params.acknowledgedConflicts,
      policy_review_token: params.reviewToken,
    })

    if (res.confirmation_required && res.policy_conflicts.length > 0) {
      pendingConflicts.value = res.policy_conflicts
      pendingWarnings.value = res.policy_warnings
      pendingReviewToken.value = res.policy_review_token
      conflictsConfirmed.value = false
      submitError.value = res.message
      return
    }

    if (!res.success) {
      submitBlockedMessage.value = res.message
      return
    }

    emit('created', res.task?.id || '')
    emit('close')
  } catch (err) {
    submitError.value = err instanceof ApiClientError ? err.message : '提交下载任务失败'
  } finally {
    submitting.value = false
  }
}

function handleKeydown(event: KeyboardEvent): void {
  if (event.key === 'Escape' && props.open) {
    emit('close')
  }
}

onMounted(() => window.addEventListener('keydown', handleKeydown))
onBeforeUnmount(() => {
  window.removeEventListener('keydown', handleKeydown)
  if (autoResolveTimer !== null) window.clearTimeout(autoResolveTimer)
})
</script>

<template>
  <Teleport to="body">
    <div
      v-if="open"
      class="fixed inset-0 z-50 flex items-end justify-center bg-black/65 p-0 backdrop-blur-[2px] sm:items-center sm:p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="new-download-modal-title"
      @click.self="$emit('close')"
    >
      <div
        class="flex max-h-[92dvh] w-full max-w-2xl flex-col overflow-hidden rounded-t-2xl border border-[var(--border-default)] bg-[var(--bg-chrome)] shadow-2xl sm:rounded-2xl"
      >
        <!-- Header -->
        <div class="flex items-center justify-between border-b border-[var(--border-default)] px-5 py-4">
          <div class="flex items-center gap-2.5">
            <div class="flex h-8 w-8 items-center justify-center rounded-lg bg-[var(--accent-soft)] text-[var(--accent)]">
              <Magnet class="h-4 w-4" />
            </div>
            <div>
              <h2 id="new-download-modal-title" class="text-sm font-semibold text-[var(--text-primary)]">
                新建下载任务
              </h2>
              <p class="text-xs text-[var(--text-muted)]">
                粘贴磁力链接或 .torrent 地址，自动解析元数据并进行策略预检
              </p>
            </div>
          </div>
          <button
            id="close-new-download-modal"
            type="button"
            class="btn-secondary inline-flex h-8 w-8 items-center justify-center rounded-lg"
            aria-label="关闭弹窗"
            @click="$emit('close')"
          >
            <X class="h-4 w-4" />
          </button>
        </div>

        <!-- Scrollable Content -->
        <div class="flex-1 space-y-4 overflow-y-auto px-5 py-5">
          <!-- Step 1: Resource URL -->
          <div>
            <div class="mb-1.5 flex items-center justify-between gap-2">
              <label for="download-link-input" class="text-xs font-medium text-[var(--text-primary)]">
                磁力链接 / .torrent 下载链接 <span class="text-rose-400">*</span>
              </label>
              <span
                v-if="detectedType !== 'unknown'"
                class="inline-flex items-center gap-1 rounded bg-[var(--accent-soft)] px-2 py-0.5 text-[11px] font-medium text-[var(--accent)]"
              >
                <Magnet v-if="detectedType === 'magnet'" class="h-3 w-3" />
                <Link2 v-else class="h-3 w-3" />
                {{ detectedType === 'magnet' ? 'Magnet 磁力链接' : 'HTTP(S) 种子链接' }}
              </span>
            </div>

            <textarea
              id="download-link-input"
              v-model="rawLink"
              rows="3"
              placeholder="粘贴 magnet:?xt=urn:btih:... 或 https://.../xxx.torrent"
              class="input-field w-full resize-none rounded-xl px-3.5 py-2.5 font-mono text-xs leading-relaxed"
              @paste="handleLinkPaste"
            />

            <div class="mt-2.5 flex flex-wrap items-center justify-between gap-2">
              <div v-if="detectedType === 'magnet'" class="flex items-center gap-2 text-xs text-[var(--text-muted)]">
                <label for="metadata-timeout-input">元数据超时</label>
                <input
                  id="metadata-timeout-input"
                  v-model.number="metadataTimeout"
                  type="number"
                  min="5"
                  max="120"
                  class="input-field w-16 rounded-md px-2 py-1 text-center font-mono text-xs tabular-nums"
                />
                <span>秒</span>
              </div>
              <div v-else class="text-xs text-[var(--text-muted)]">
                支持自动解析标题与种子内文件列表
              </div>

              <button
                id="resolve-resource-btn"
                type="button"
                class="btn-secondary inline-flex items-center gap-1.5 rounded-lg px-3.5 py-1.5 text-xs font-medium"
                :disabled="!linkValid || resolving"
                @click="runResolve"
              >
                <Loader2 v-if="resolving" class="h-3.5 w-3.5 animate-spin text-[var(--accent)]" />
                <Sparkles v-else class="h-3.5 w-3.5 text-[var(--accent)]" />
                {{ resolving ? '正在解析元数据…' : '解析链接' }}
              </button>
            </div>
          </div>

          <!-- Network / Transport Resolve Error -->
          <div
            v-if="resolveError"
            class="flex items-start gap-2.5 rounded-xl border border-rose-500/30 bg-rose-500/10 p-3 text-xs text-rose-600 dark:text-rose-300"
          >
            <AlertTriangle class="mt-0.5 h-4 w-4 shrink-0" />
            <p class="leading-relaxed">{{ resolveError }}</p>
          </div>

          <!-- Upstream Resolve Result Summary -->
          <div
            v-if="resolved"
            class="rounded-xl border p-3.5 text-xs"
            :class="
              !resolved.success
                ? 'border-rose-500/30 bg-rose-500/10'
                : resolved.inspection_incomplete
                  ? 'border-amber-500/30 bg-amber-500/10'
                  : 'border-emerald-500/25 bg-emerald-500/8'
            "
          >
            <div class="flex flex-wrap items-center justify-between gap-2">
              <div class="flex items-center gap-2 font-medium">
                <CheckCircle2
                  v-if="resolved.success && !resolved.inspection_incomplete"
                  class="h-4 w-4 text-emerald-500"
                />
                <AlertTriangle
                  v-else
                  class="h-4 w-4"
                  :class="resolved.success ? 'text-amber-500' : 'text-rose-500'"
                />
                <span class="text-[var(--text-primary)]">
                  {{
                    !resolved.success
                      ? '资源解析未成功'
                      : resolved.inspection_incomplete
                        ? '已提取标题，但种子文件列表未完整获取'
                        : '资源解析成功'
                  }}
                </span>
              </div>
              <div class="flex items-center gap-2 text-[11px] text-[var(--text-secondary)]">
                <span v-if="resolved.source" class="rounded bg-[var(--bg-chrome)] px-2 py-0.5 font-mono">
                  来源: {{ resolved.source }}
                </span>
                <span v-if="resolved.error_code" class="rounded bg-[var(--bg-chrome)] px-2 py-0.5 font-mono">
                  {{ resolved.error_code }}
                </span>
              </div>
            </div>

            <p v-if="resolved.message" class="mt-1.5 leading-relaxed text-[var(--text-secondary)]">
              {{ resolved.message }}
            </p>

            <p v-if="isHardResolverBlock" class="mt-2 font-medium text-rose-600 dark:text-rose-300">
              该错误属于无效链接或后端解析依赖异常，无法仅通过手动输入标题绕过，请检查链接或 Openlist-Ani 服务日志。
            </p>
            <p
              v-else-if="!resolved.success"
              class="mt-2 text-amber-700 dark:text-amber-300"
            >
              DHT/Peer 元数据获取未完成。您仍可手动填写准确的番剧发布标题继续提交，系统将按保守合集策略进行预检。
            </p>

            <!-- Resolved Files List -->
            <div v-if="resolved.files.length > 0" class="mt-3">
              <div class="mb-1.5 flex items-center justify-between text-[11px] text-[var(--text-secondary)]">
                <span class="tabular-nums">
                  种子文件列表（共 {{ resolved.file_count ?? resolved.files.length }} 个，其中视频文件 {{ resolved.video_file_count }} 个）
                </span>
                <span
                  class="rounded px-2 py-0.5 font-medium"
                  :class="
                    resolved.collection_hint
                      ? 'bg-amber-500/15 text-amber-600 dark:text-amber-300'
                      : 'bg-sky-500/15 text-sky-600 dark:text-sky-300'
                  "
                >
                  {{ resolved.collection_hint ? '识别为合集' : '识别为单集' }}
                </span>
              </div>
              <div
                class="max-h-40 divide-y divide-[var(--border-default)] overflow-y-auto rounded-lg border border-[var(--border-default)] bg-[var(--bg-chrome)]"
              >
                <div
                  v-for="(file, index) in resolved.files"
                  :key="file.name + index"
                  class="flex items-center justify-between gap-3 px-3 py-1.5 text-[11px]"
                >
                  <div class="flex min-w-0 items-center gap-2">
                    <FileVideo v-if="file.is_video" class="h-3.5 w-3.5 shrink-0 text-[var(--accent)]" />
                    <FileText v-else class="h-3.5 w-3.5 shrink-0 text-[var(--text-muted)]" />
                    <span
                      class="truncate font-mono"
                      :class="file.is_video ? 'text-[var(--text-primary)]' : 'text-[var(--text-muted)]'"
                      :title="file.name"
                    >
                      {{ file.name }}
                    </span>
                  </div>
                  <span class="shrink-0 font-mono text-[var(--text-muted)] tabular-nums">
                    {{ formatBytes(file.size) }}
                  </span>
                </div>
              </div>
            </div>
          </div>

          <!-- Step 2: Canonical Title & Collection Mode -->
          <div class="space-y-3">
            <div>
              <label for="download-title-input" class="mb-1.5 block text-xs font-medium text-[var(--text-primary)]">
                番剧发布标题 (title) <span class="text-rose-400">*</span>
              </label>
              <input
                id="download-title-input"
                v-model="title"
                type="text"
                placeholder="自动解析后将自动填入；若无法解析，请手动输入真实发布标题"
                class="input-field w-full rounded-xl px-3.5 py-2.5 text-sm"
              />
              <p class="mt-1 text-[11px] text-[var(--text-muted)]">
                Openlist-Ani 依赖此标题执行番剧识别与重命名，请勿留空或随意填写无关名称。
              </p>
            </div>

            <!-- Single vs Collection Mode -->
            <div class="surface-card flex flex-col justify-between gap-2 rounded-xl px-3.5 py-3 sm:flex-row sm:items-center">
              <div>
                <p class="text-xs font-medium text-[var(--text-primary)]">
                  资源类型：{{ collectionHint ? '合集模式 (collection_hint = true)' : '单集模式 (collection_hint = false)' }}
                </p>
                <p class="mt-0.5 text-[11px] text-[var(--text-muted)]">
                  {{
                    resolved?.inspection_incomplete
                      ? '文件列表未完整检查，已按 Openlist-Ani 官方规则保守开启合集提示。'
                      : '根据种子内视频文件数量自动判断（多视频文件为合集）。'
                  }}
                </p>
              </div>
              <label class="inline-flex shrink-0 cursor-pointer items-center gap-2 text-xs text-[var(--text-secondary)]">
                <input
                  id="collection-hint-toggle"
                  v-model="collectionHint"
                  type="checkbox"
                  class="h-4 w-4 rounded border-[var(--border-strong)] accent-sky-500"
                  @change="userEditedCollectionHint = true"
                />
                <span>按合集处理</span>
              </label>
            </div>
          </div>

          <!-- Hard Preflight / Create Blocker (e.g. duplicate) -->
          <div
            v-if="submitBlockedMessage"
            class="flex items-start gap-2.5 rounded-xl border border-rose-500/35 bg-rose-500/10 p-3.5 text-xs text-rose-600 dark:text-rose-300"
          >
            <AlertTriangle class="mt-0.5 h-4 w-4 shrink-0" />
            <div>
              <p class="font-semibold">任务已被 Openlist-Ani 拦截</p>
              <p class="mt-1 leading-relaxed">{{ submitBlockedMessage }}</p>
            </div>
          </div>

          <!-- Generic Submit Error -->
          <div
            v-if="submitError"
            class="flex items-start gap-2.5 rounded-xl border border-rose-500/35 bg-rose-500/10 p-3.5 text-xs text-rose-600 dark:text-rose-300"
          >
            <AlertTriangle class="mt-0.5 h-4 w-4 shrink-0" />
            <p class="leading-relaxed">{{ submitError }}</p>
          </div>

          <!-- Policy Conflicts Confirmation Box (from POST /api/downloads/preflight) -->
          <div
            v-if="needsConflictConfirmation"
            class="space-y-3 rounded-xl border border-amber-500/40 bg-amber-500/10 p-4 text-xs"
          >
            <div class="flex items-start gap-2.5">
              <ShieldAlert class="mt-0.5 h-4 w-4 shrink-0 text-amber-500" />
              <div>
                <p class="font-semibold text-amber-700 dark:text-amber-200">
                  策略预检发现冲突，需要您明确确认
                </p>
                <p class="mt-1 text-amber-700/90 dark:text-amber-200/80">
                  继续提交将针对本次手动任务绕过以下自动 RSS 过滤、优先级或严格模式规则：
                </p>
              </div>
            </div>

            <ul class="space-y-2">
              <li
                v-for="conflict in pendingConflicts"
                :key="conflict.key"
                class="rounded-lg border border-amber-500/25 bg-[var(--bg-chrome)] p-3"
              >
                <div class="flex flex-wrap items-center justify-between gap-2">
                  <code class="font-mono text-[11px] font-semibold text-amber-600 dark:text-amber-300">
                    {{ conflict.code }}
                  </code>
                  <code class="font-mono text-[10px] text-[var(--text-muted)]">
                    {{ conflict.key }}
                  </code>
                </div>
                <p class="mt-1 leading-relaxed text-[var(--text-primary)]">{{ conflict.reason }}</p>
                <p v-if="conflict.matched" class="mt-1 font-mono text-[11px] text-[var(--text-muted)]">
                  命中项: {{ conflict.matched }}
                </p>
              </li>
            </ul>

            <div
              v-if="pendingWarnings.length > 0"
              class="rounded-lg border border-amber-500/20 bg-[var(--bg-chrome)]/70 p-2.5 text-[11px] text-[var(--text-secondary)]"
            >
              <p class="font-medium text-amber-600 dark:text-amber-300">额外提醒：</p>
              <ul class="mt-1 list-disc space-y-0.5 pl-4">
                <li v-for="(w, idx) in pendingWarnings" :key="idx">{{ w }}</li>
              </ul>
            </div>

            <label class="flex cursor-pointer items-start gap-2.5 pt-1 text-[var(--text-primary)]">
              <input
                id="confirm-policy-conflicts-checkbox"
                v-model="conflictsConfirmed"
                type="checkbox"
                class="mt-0.5 h-4 w-4 rounded border-amber-500 accent-amber-500"
              />
              <span class="leading-relaxed font-medium">
                我已阅读上述全部策略冲突原因，确认覆盖自动策略并提交此下载任务
              </span>
            </label>
          </div>
        </div>

        <!-- Footer Actions -->
        <div class="flex items-center justify-end gap-2.5 border-t border-[var(--border-default)] px-5 py-3.5">
          <button
            type="button"
            class="btn-secondary rounded-lg px-4 py-2 text-xs font-medium"
            @click="$emit('close')"
          >
            取消
          </button>
          <button
            id="submit-download-btn"
            type="button"
            class="btn-primary inline-flex items-center gap-2 rounded-lg px-4 py-2 text-xs font-semibold"
            :disabled="!canRunSubmit"
            @click="handleSubmit"
          >
            <Loader2 v-if="preflighting || submitting" class="h-3.5 w-3.5 animate-spin" />
            <span>
              {{
                preflighting
                  ? '正在执行策略预检…'
                  : submitting
                    ? '正在提交下载…'
                    : needsConflictConfirmation
                      ? '确认忽略冲突并提交下载'
                      : '预检并提交下载'
              }}
            </span>
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>
