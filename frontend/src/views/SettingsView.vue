<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import {
  CheckCircle2,
  Globe,
  Loader2,
  Moon,
  RefreshCw,
  Save,
  Server,
  ShieldCheck,
  Sun,
  XCircle,
} from 'lucide-vue-next'
import { useDownloadsStore } from '@/stores/downloads'
import { useHealthStore } from '@/stores/health'
import { useSettingsStore } from '@/stores/settings'
import type { LanguageCode, ServiceHealthResponse, ThemeMode } from '@/types/api'

const settingsStore = useSettingsStore()
const healthStore = useHealthStore()
const downloadsStore = useDownloadsStore()

const upstreamUrlInput = ref('')
const apiTimeoutSeconds = ref(30)
const pollIntervalSeconds = ref(5)
const theme = ref<ThemeMode>('dark')
const language = ref<LanguageCode>('zh-CN')

const saveSuccess = ref(false)
const testResult = ref<ServiceHealthResponse | null>(null)
const testing = ref(false)

function syncFromStore(): void {
  apiTimeoutSeconds.value = settingsStore.apiTimeoutSeconds
  pollIntervalSeconds.value = settingsStore.pollIntervalSeconds
  theme.value = settingsStore.theme
  language.value = settingsStore.language
}

watch(
  () => settingsStore.theme,
  (next) => {
    theme.value = next
  },
)

watch(
  () => settingsStore.language,
  (next) => {
    language.value = next
  },
)

onMounted(async () => {
  await settingsStore.loadSettings()
  syncFromStore()
})

async function handleSave(): Promise<void> {
  saveSuccess.value = false
  const ok = await settingsStore.saveSettings({
    upstream_url: upstreamUrlInput.value.trim() ? upstreamUrlInput.value.trim() : undefined,
    api_timeout_seconds: apiTimeoutSeconds.value,
    poll_interval_seconds: pollIntervalSeconds.value,
    theme: theme.value,
    language: language.value,
  })
  if (ok) {
    upstreamUrlInput.value = ''
    saveSuccess.value = true
    downloadsStore.startPolling()
    void healthStore.fetchHealth()
    window.setTimeout(() => {
      saveSuccess.value = false
    }, 3000)
  }
}

async function handleTestConnection(): Promise<void> {
  testing.value = true
  testResult.value = await healthStore.testConnection()
  testing.value = false
}
</script>

<template>
  <div class="mx-auto max-w-3xl space-y-6">
    <div>
      <h2 class="text-base font-semibold text-[var(--text-primary)]">
        {{ settingsStore.t('settings.title') }}
      </h2>
      <p class="mt-1 text-xs text-[var(--text-secondary)]">
        {{ settingsStore.t('settings.desc') }}
      </p>
    </div>

    <form class="space-y-5" @submit.prevent="handleSave">
      <!-- Upstream Service Configuration -->
      <section class="surface-card space-y-4 rounded-xl p-5">
        <div class="flex items-center justify-between gap-2">
          <div class="flex items-center gap-2">
            <Server class="h-4 w-4 text-[var(--accent)]" />
            <h3 class="text-sm font-semibold text-[var(--text-primary)]">Openlist-Ani 内部连接</h3>
          </div>
          <span
            class="rounded-md bg-[var(--bg-subtle)] px-2.5 py-1 font-mono text-[11px] text-[var(--text-secondary)]"
          >
            已保存: {{ settingsStore.upstreamMasked }}
          </span>
        </div>

        <div>
          <label for="upstream-url-input" class="mb-1.5 block text-xs font-medium text-[var(--text-primary)]">
            更新 Openlist-Ani 服务地址（留空则保持当前服务端配置）
          </label>
          <input
            id="upstream-url-input"
            v-model="upstreamUrlInput"
            type="text"
            placeholder="例如：http://127.0.0.1:26666 或 http://openlist-ani:26666"
            class="input-field w-full rounded-xl px-3.5 py-2.5 font-mono text-xs"
          />
          <p class="mt-1.5 text-[11px] leading-relaxed text-[var(--text-muted)]">
            该地址仅保存在 WebUI 服务端数据库中用于反向代理转发，接口响应中始终脱敏，不向浏览器明文下发。
          </p>
        </div>

        <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div>
            <label for="api-timeout-input" class="mb-1.5 block text-xs font-medium text-[var(--text-primary)]">
              API 连接超时（秒）
            </label>
            <input
              id="api-timeout-input"
              v-model.number="apiTimeoutSeconds"
              type="number"
              min="3"
              max="300"
              step="1"
              class="input-field w-full rounded-xl px-3.5 py-2 font-mono text-sm tabular-nums"
            />
            <p class="mt-1 text-[11px] text-[var(--text-muted)]">推荐 15 ~ 60 秒；磁力解析会自动延长读取窗口。</p>
          </div>

          <div>
            <label for="poll-interval-input" class="mb-1.5 block text-xs font-medium text-[var(--text-primary)]">
              自动刷新间隔（秒）
            </label>
            <input
              id="poll-interval-input"
              v-model.number="pollIntervalSeconds"
              type="number"
              min="2"
              max="120"
              step="1"
              class="input-field w-full rounded-xl px-3.5 py-2 font-mono text-sm tabular-nums"
            />
            <p class="mt-1 text-[11px] text-[var(--text-muted)]">默认每 5 秒轮询一次下载列表，切后台自动暂停。</p>
          </div>
        </div>

        <!-- Connection Test Result -->
        <div class="flex flex-wrap items-center justify-between gap-3 border-t border-[var(--border-default)] pt-4">
          <button
            id="test-connection-btn"
            type="button"
            class="btn-secondary inline-flex items-center gap-1.5 rounded-lg px-3.5 py-2 text-xs font-medium"
            :disabled="testing"
            @click="handleTestConnection"
          >
            <RefreshCw class="h-3.5 w-3.5" :class="{ 'animate-spin': testing }" />
            <span>{{ settingsStore.t('action.testConnection') }}</span>
          </button>

          <div v-if="testResult" class="flex items-center gap-2 text-xs">
            <CheckCircle2 v-if="testResult.upstream_reachable && testResult.upstream_ready" class="h-4 w-4 text-emerald-500" />
            <XCircle v-else class="h-4 w-4 text-rose-500" />
            <span
              :class="
                testResult.upstream_reachable && testResult.upstream_ready
                  ? 'text-emerald-600 dark:text-emerald-300'
                  : 'text-rose-600 dark:text-rose-300'
              "
            >
              <template v-if="testResult.upstream_reachable && !testResult.error_code">
                已连通（状态: {{ testResult.upstream_status }}
                <template v-if="testResult.workers">
                  · 线程 {{ testResult.workers.running }}/{{ testResult.workers.expected }}
                </template>
                <template v-if="testResult.latency_ms !== null">
                  · {{ testResult.latency_ms }}ms
                </template>
                ）
              </template>
              <template v-else>
                {{ testResult.error_message || '连接失败' }}
              </template>
            </span>
          </div>
        </div>
      </section>

      <!-- Appearance & Locale -->
      <section class="surface-card space-y-4 rounded-xl p-5">
        <div class="flex items-center gap-2">
          <Globe class="h-4 w-4 text-[var(--accent)]" />
          <h3 class="text-sm font-semibold text-[var(--text-primary)]">外观与语言</h3>
        </div>

        <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div>
            <p class="mb-2 text-xs font-medium text-[var(--text-primary)]">界面主题</p>
            <div class="grid grid-cols-2 gap-2">
              <button
                type="button"
                class="flex items-center justify-center gap-2 rounded-xl border px-3 py-2.5 text-xs font-medium transition"
                :class="
                  theme === 'dark'
                    ? 'border-[var(--accent)] bg-[var(--accent-soft)] text-[var(--accent)]'
                    : 'border-[var(--border-default)] bg-[var(--bg-subtle)] text-[var(--text-secondary)]'
                "
                @click="theme = 'dark'; settingsStore.applyTheme('dark')"
              >
                <Moon class="h-3.5 w-3.5" />
                <span>深色模式（默认）</span>
              </button>
              <button
                type="button"
                class="flex items-center justify-center gap-2 rounded-xl border px-3 py-2.5 text-xs font-medium transition"
                :class="
                  theme === 'light'
                    ? 'border-[var(--accent)] bg-[var(--accent-soft)] text-[var(--accent)]'
                    : 'border-[var(--border-default)] bg-[var(--bg-subtle)] text-[var(--text-secondary)]'
                "
                @click="theme = 'light'; settingsStore.applyTheme('light')"
              >
                <Sun class="h-3.5 w-3.5" />
                <span>浅色模式</span>
              </button>
            </div>
          </div>

          <div>
            <label for="language-select" class="mb-2 block text-xs font-medium text-[var(--text-primary)]">
              界面语言
            </label>
            <select
              id="language-select"
              v-model="language"
              class="input-field w-full rounded-xl px-3.5 py-2.5 text-xs"
              @change="settingsStore.applyLanguage(language)"
            >
              <option value="zh-CN">简体中文（默认）</option>
              <option value="en-US">English</option>
            </select>
          </div>
        </div>
      </section>

      <!-- Error / Save Feedback -->
      <div
        v-if="settingsStore.error"
        class="rounded-xl border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-xs text-rose-600 dark:text-rose-300"
      >
        {{ settingsStore.error }}
      </div>

      <div
        v-if="saveSuccess"
        class="flex items-center gap-2 rounded-xl border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-xs text-emerald-700 dark:text-emerald-300"
      >
        <CheckCircle2 class="h-4 w-4" />
        <span>设置已保存并立即生效。</span>
      </div>

      <div class="flex justify-end">
        <button
          id="save-settings-btn"
          type="submit"
          class="btn-primary inline-flex items-center gap-2 rounded-xl px-5 py-2.5 text-xs font-semibold"
          :disabled="settingsStore.saving"
        >
          <Loader2 v-if="settingsStore.saving" class="h-3.5 w-3.5 animate-spin" />
          <Save v-else class="h-3.5 w-3.5" />
          <span>{{ settingsStore.t('action.save') }}</span>
        </button>
      </div>
    </form>

    <!-- Security Summary -->
    <section class="surface-card rounded-xl p-5">
      <div class="flex items-center gap-2 text-xs font-semibold text-[var(--text-primary)]">
        <ShieldCheck class="h-4 w-4 text-emerald-500" />
        <span>安全边界与代理白名单</span>
      </div>
      <ul class="mt-3 list-disc space-y-1.5 pl-4 text-xs leading-relaxed text-[var(--text-secondary)]">
        <li>仅代理白名单接口：<code>/health/live</code>、<code>/health/ready</code>、<code>/api/resolve_magnet</code>、<code>/api/resolve_torrent</code>、<code>/api/downloads/preflight</code>、<code>/api/downloads</code>、<code>/api/downloads/{task_id}</code>。</li>
        <li>不提供任意 URL 代理，并明确禁止代理 <code>/api/restart</code> 等管理控制接口。</li>
        <li>全站启用 HttpOnly 服务端会话、CSRF 令牌校验、Origin 来源校验及登录失败限流。</li>
      </ul>
    </section>
  </div>
</template>
