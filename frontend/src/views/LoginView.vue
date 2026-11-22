<script setup lang="ts">
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { AlertCircle, Loader2, Lock, Moon, ShieldCheck, Sun, User } from 'lucide-vue-next'
import { useAuthStore } from '@/stores/auth'
import { useSettingsStore } from '@/stores/settings'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const settingsStore = useSettingsStore()

const username = ref('admin')
const password = ref('')

async function handleSubmit(): Promise<void> {
  if (!username.value.trim() || !password.value) return
  const ok = await authStore.login(username.value.trim(), password.value)
  if (ok) {
    const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : '/downloads'
    const safeRedirect = redirect.startsWith('/') && !redirect.startsWith('//') ? redirect : '/downloads'
    await router.replace(safeRedirect)
  }
}
</script>

<template>
  <div class="relative flex min-h-dvh flex-col items-center justify-center bg-[var(--bg-canvas)] px-4 py-10">
    <!-- Theme Toggle Corner -->
    <div class="fixed top-4 right-4">
      <button
        type="button"
        class="btn-secondary inline-flex h-9 w-9 items-center justify-center rounded-lg"
        :title="settingsStore.theme === 'dark' ? '切换浅色模式' : '切换深色模式'"
        @click="settingsStore.toggleTheme(false)"
      >
        <Sun v-if="settingsStore.theme === 'dark'" class="h-4 w-4" />
        <Moon v-else class="h-4 w-4" />
      </button>
    </div>

    <div class="w-full max-w-sm">
      <!-- Brand Header -->
      <div class="mb-6 flex flex-col items-center text-center">
        <div
          class="mb-3 flex h-12 w-12 items-center justify-center rounded-xl bg-[var(--accent)] font-mono text-base font-bold text-white shadow-sm"
        >
          OA
        </div>
        <h1 class="text-xl font-semibold tracking-tight text-[var(--text-primary)]">
          {{ settingsStore.t('login.heading') }}
        </h1>
        <p class="mt-1.5 text-xs leading-relaxed text-[var(--text-secondary)]">
          {{ settingsStore.t('login.desc') }}
        </p>
      </div>

      <!-- Login Card -->
      <form
        class="surface-card space-y-4 rounded-2xl p-6 shadow-lg"
        @submit.prevent="handleSubmit"
      >
        <div
          v-if="authStore.error"
          role="alert"
          class="flex items-start gap-2.5 rounded-xl border border-rose-500/30 bg-rose-500/10 px-3.5 py-2.5 text-xs text-rose-600 dark:text-rose-300"
        >
          <AlertCircle class="mt-0.5 h-4 w-4 shrink-0" />
          <span class="leading-relaxed">{{ authStore.error }}</span>
        </div>

        <div>
          <label for="login-username" class="mb-1.5 block text-xs font-medium text-[var(--text-secondary)]">
            {{ settingsStore.t('login.username') }}
          </label>
          <div class="relative">
            <User class="pointer-events-none absolute top-1/2 left-3 h-4 w-4 -translate-y-1/2 text-[var(--text-muted)]" />
            <input
              id="login-username"
              v-model="username"
              type="text"
              autocomplete="username"
              required
              class="input-field w-full rounded-xl py-2.5 pr-3.5 pl-9 text-sm"
              placeholder="admin"
            />
          </div>
        </div>

        <div>
          <label for="login-password" class="mb-1.5 block text-xs font-medium text-[var(--text-secondary)]">
            {{ settingsStore.t('login.password') }}
          </label>
          <div class="relative">
            <Lock class="pointer-events-none absolute top-1/2 left-3 h-4 w-4 -translate-y-1/2 text-[var(--text-muted)]" />
            <input
              id="login-password"
              v-model="password"
              type="password"
              autocomplete="current-password"
              required
              class="input-field w-full rounded-xl py-2.5 pr-3.5 pl-9 text-sm"
              placeholder="请输入管理员密码"
            />
          </div>
        </div>

        <button
          id="login-submit-btn"
          type="submit"
          class="btn-primary flex w-full items-center justify-center gap-2 rounded-xl py-2.5 text-sm font-semibold"
          :disabled="authStore.loading || !username.trim() || !password"
        >
          <Loader2 v-if="authStore.loading" class="h-4 w-4 animate-spin" />
          <span>
            {{ authStore.loading ? settingsStore.t('login.submitting') : settingsStore.t('login.submit') }}
          </span>
        </button>
      </form>

      <!-- Security Footer -->
      <div class="mt-4 flex items-center justify-center gap-1.5 text-[11px] text-[var(--text-muted)]">
        <ShieldCheck class="h-3.5 w-3.5 text-emerald-500" />
        <span>HttpOnly 会话 · CSRF 防护 · 登录限流</span>
      </div>
    </div>
  </div>
</template>
