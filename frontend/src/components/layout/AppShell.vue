<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  Download,
  Film,
  LayoutDashboard,
  LogOut,
  Menu,
  Moon,
  Plus,
  RefreshCw,
  Settings,
  Sun,
  X,
} from 'lucide-vue-next'
import { useAuthStore } from '@/stores/auth'
import { useDownloadsStore } from '@/stores/downloads'
import { useHealthStore } from '@/stores/health'
import { useSettingsStore } from '@/stores/settings'
import HealthBadge from './HealthBadge.vue'
import NewDownloadModal from '@/components/downloads/NewDownloadModal.vue'
import TaskDetailDrawer from '@/components/downloads/TaskDetailDrawer.vue'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const downloadsStore = useDownloadsStore()
const healthStore = useHealthStore()
const settingsStore = useSettingsStore()

const mobileNavOpen = ref(false)

const navItems = computed(() => [
  {
    name: 'dashboard',
    to: '/',
    label: settingsStore.t('nav.dashboard'),
    icon: LayoutDashboard,
    badge: null as number | null,
  },
  {
    name: 'downloads',
    to: '/downloads',
    label: settingsStore.t('nav.downloads'),
    icon: Download,
    badge: downloadsStore.activeCount > 0 ? downloadsStore.activeCount : null,
  },
  {
    name: 'recognition',
    to: '/recognition',
    label: settingsStore.t('nav.recognition'),
    icon: Film,
    badge: null as number | null,
  },
  {
    name: 'settings',
    to: '/settings',
    label: settingsStore.t('nav.settings'),
    icon: Settings,
    badge: null as number | null,
  },
])

const currentPageTitle = computed(() => {
  const found = navItems.value.find((item) => item.name === route.name)
  return found?.label ?? settingsStore.t('app.title')
})

async function handleLogout(): Promise<void> {
  downloadsStore.reset()
  await authStore.logout()
  await router.replace({ name: 'login' })
}

async function handleCreated(taskId: string): Promise<void> {
  await downloadsStore.refreshAll(false)
  if (route.name !== 'downloads') {
    await router.push({ name: 'downloads' })
  }
  if (taskId) {
    void downloadsStore.inspectTask(taskId)
  }
}

watch(
  () => settingsStore.pollIntervalSeconds,
  () => {
    if (authStore.authenticated) {
      downloadsStore.startPolling()
    }
  },
)

onMounted(async () => {
  await settingsStore.loadSettings()
  if (!authStore.authenticated) return
  await Promise.all([downloadsStore.fetchDownloads(), healthStore.fetchHealth()])
  if (authStore.authenticated) {
    downloadsStore.startPolling()
  }
})

onBeforeUnmount(() => {
  downloadsStore.stopPolling()
})
</script>

<template>
  <div class="flex min-h-dvh bg-[var(--bg-canvas)] text-[var(--text-primary)]">
    <!-- Desktop Left Sidebar -->
    <aside
      class="hidden w-60 shrink-0 flex-col border-r border-[var(--border-default)] bg-[var(--bg-chrome)] lg:flex"
    >
      <div class="flex h-15 items-center gap-2.5 border-b border-[var(--border-default)] px-5">
        <div
          class="flex h-8 w-8 items-center justify-center rounded-lg bg-[var(--accent)] text-white font-mono text-xs font-bold"
        >
          OA
        </div>
        <div class="min-w-0">
          <p class="truncate text-sm font-semibold tracking-tight">Openlist-Ani</p>
          <p class="truncate text-[11px] text-[var(--text-muted)]">WebUI Console</p>
        </div>
      </div>

      <nav class="flex-1 space-y-1 p-3" aria-label="主导航">
        <RouterLink
          v-for="item in navItems"
          :key="item.name"
          :to="item.to"
          class="flex items-center justify-between rounded-lg px-3 py-2 text-sm font-medium transition-colors"
          :class="
            route.name === item.name
              ? 'bg-[var(--accent-soft)] text-[var(--accent)]'
              : 'text-[var(--text-secondary)] hover:bg-[var(--bg-subtle)] hover:text-[var(--text-primary)]'
          "
        >
          <span class="flex items-center gap-2.5">
            <component :is="item.icon" class="h-4 w-4 shrink-0" />
            <span>{{ item.label }}</span>
          </span>
          <span
            v-if="item.badge !== null"
            class="rounded-full bg-[var(--accent)] px-1.5 py-0.5 text-[11px] font-semibold leading-none text-white tabular-nums"
          >
            {{ item.badge }}
          </span>
        </RouterLink>
      </nav>

      <!-- Sidebar Footer: Account -->
      <div class="border-t border-[var(--border-default)] p-3">
        <div class="flex items-center justify-between rounded-lg bg-[var(--bg-subtle)] px-3 py-2">
          <div class="min-w-0">
            <p class="truncate text-xs font-medium text-[var(--text-primary)]">
              {{ authStore.username || 'admin' }}
            </p>
            <p class="text-[11px] text-[var(--text-muted)]">已通过安全会话登录</p>
          </div>
          <button
            type="button"
            class="rounded-md p-1.5 text-[var(--text-muted)] transition hover:bg-[var(--bg-surface-hover)] hover:text-rose-400"
            :title="settingsStore.t('action.logout')"
            @click="handleLogout"
          >
            <LogOut class="h-4 w-4" />
          </button>
        </div>
      </div>
    </aside>

    <!-- Mobile Slide-Over Drawer -->
    <Teleport to="body">
      <div
        v-if="mobileNavOpen"
        class="fixed inset-0 z-50 flex bg-black/60 backdrop-blur-[2px] lg:hidden"
        @click.self="mobileNavOpen = false"
      >
        <div class="flex h-full w-64 flex-col border-r border-[var(--border-default)] bg-[var(--bg-chrome)]">
          <div class="flex h-15 items-center justify-between border-b border-[var(--border-default)] px-4">
            <span class="text-sm font-semibold">Openlist-Ani WebUI</span>
            <button
              type="button"
              class="btn-secondary inline-flex h-8 w-8 items-center justify-center rounded-lg"
              @click="mobileNavOpen = false"
            >
              <X class="h-4 w-4" />
            </button>
          </div>
          <nav class="flex-1 space-y-1 p-3">
            <RouterLink
              v-for="item in navItems"
              :key="item.name"
              :to="item.to"
              class="flex items-center justify-between rounded-lg px-3 py-2.5 text-sm font-medium"
              :class="
                route.name === item.name
                  ? 'bg-[var(--accent-soft)] text-[var(--accent)]'
                  : 'text-[var(--text-secondary)] hover:bg-[var(--bg-subtle)]'
              "
              @click="mobileNavOpen = false"
            >
              <span class="flex items-center gap-2.5">
                <component :is="item.icon" class="h-4 w-4" />
                <span>{{ item.label }}</span>
              </span>
              <span
                v-if="item.badge !== null"
                class="rounded-full bg-[var(--accent)] px-1.5 py-0.5 text-[11px] font-semibold text-white tabular-nums"
              >
                {{ item.badge }}
              </span>
            </RouterLink>
          </nav>
          <div class="border-t border-[var(--border-default)] p-3">
            <button
              type="button"
              class="btn-secondary flex w-full items-center justify-center gap-2 rounded-lg py-2 text-xs font-medium text-rose-500"
              @click="handleLogout"
            >
              <LogOut class="h-3.5 w-3.5" />
              <span>{{ settingsStore.t('action.logout') }}</span>
            </button>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- Main Column -->
    <div class="flex min-w-0 flex-1 flex-col">
      <!-- Top Status Bar -->
      <header
        class="sticky top-0 z-30 flex h-15 items-center justify-between gap-3 border-b border-[var(--border-default)] bg-[var(--bg-chrome)]/95 px-4 backdrop-blur sm:px-6"
      >
        <div class="flex min-w-0 items-center gap-3">
          <button
            type="button"
            class="btn-secondary inline-flex h-8 w-8 items-center justify-center rounded-lg lg:hidden"
            aria-label="打开导航菜单"
            @click="mobileNavOpen = true"
          >
            <Menu class="h-4 w-4" />
          </button>
          <h1 class="truncate text-base font-semibold tracking-tight text-[var(--text-primary)]">
            {{ currentPageTitle }}
          </h1>
        </div>

        <div class="flex items-center gap-2">
          <HealthBadge />

          <button
            id="top-refresh-btn"
            type="button"
            class="btn-secondary inline-flex h-8 w-8 items-center justify-center rounded-lg"
            :title="settingsStore.t('action.refresh')"
            :disabled="downloadsStore.refreshing"
            @click="downloadsStore.refreshAll(false)"
          >
            <RefreshCw
              class="h-3.5 w-3.5"
              :class="{ 'animate-spin text-[var(--accent)]': downloadsStore.refreshing }"
            />
          </button>

          <button
            id="theme-toggle-btn"
            type="button"
            class="btn-secondary inline-flex h-8 w-8 items-center justify-center rounded-lg"
            :title="settingsStore.theme === 'dark' ? '切换浅色模式' : '切换深色模式'"
            @click="settingsStore.toggleTheme(true)"
          >
            <Sun v-if="settingsStore.theme === 'dark'" class="h-4 w-4" />
            <Moon v-else class="h-4 w-4" />
          </button>

          <button
            id="new-download-btn"
            type="button"
            class="btn-primary inline-flex h-8 items-center gap-1.5 rounded-lg px-3 text-xs font-semibold shadow-sm"
            @click="downloadsStore.openNewDownloadModal()"
          >
            <Plus class="h-4 w-4" />
            <span>{{ settingsStore.t('action.newDownload') }}</span>
          </button>
        </div>
      </header>

      <!-- Page Content -->
      <main class="mx-auto w-full max-w-7xl flex-1 px-4 py-5 pb-20 sm:px-6 lg:pb-8">
        <slot />
      </main>
    </div>

    <!-- Mobile Bottom Navigation Bar -->
    <nav
      class="fixed inset-x-0 bottom-0 z-30 grid grid-cols-4 border-t border-[var(--border-default)] bg-[var(--bg-chrome)]/95 pb-[env(safe-area-inset-bottom)] backdrop-blur lg:hidden"
      aria-label="移动端底部导航"
    >
      <RouterLink
        v-for="item in navItems"
        :key="item.name"
        :to="item.to"
        class="relative flex flex-col items-center justify-center gap-0.5 py-2 text-[11px] font-medium"
        :class="
          route.name === item.name
            ? 'text-[var(--accent)]'
            : 'text-[var(--text-muted)]'
        "
      >
        <component :is="item.icon" class="h-4 w-4" />
        <span>{{ item.label }}</span>
        <span
          v-if="item.badge !== null"
          class="absolute top-1.5 right-1/4 h-2 w-2 rounded-full bg-[var(--accent)]"
        />
      </RouterLink>
    </nav>

    <!-- Global Modals & Drawers -->
    <NewDownloadModal
      :open="downloadsStore.newDownloadModalOpen"
      @close="downloadsStore.closeNewDownloadModal()"
      @created="handleCreated"
    />
    <TaskDetailDrawer />
  </div>
</template>
