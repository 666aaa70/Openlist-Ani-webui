import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api, ApiClientError } from '@/api/client'
import { translate } from '@/i18n'
import type { LanguageCode, ThemeMode, UpdateSettingsRequest } from '@/types/api'

const THEME_STORAGE_KEY = 'oani_webui_theme'
const LANG_STORAGE_KEY = 'oani_webui_lang'

export const useSettingsStore = defineStore('settings', () => {
  const upstreamConfigured = ref(false)
  const upstreamMasked = ref('未配置')
  const apiTimeoutSeconds = ref(30)
  const pollIntervalSeconds = ref(5)
  const theme = ref<ThemeMode>(loadInitialTheme())
  const language = ref<LanguageCode>(loadInitialLanguage())

  const loading = ref(false)
  const saving = ref(false)
  const error = ref<string | null>(null)
  const loadedFromServer = ref(false)

  function loadInitialTheme(): ThemeMode {
    try {
      const saved = localStorage.getItem(THEME_STORAGE_KEY)
      if (saved === 'light' || saved === 'dark') return saved
    } catch {
      // Ignore storage failures in private mode
    }
    return 'dark'
  }

  function loadInitialLanguage(): LanguageCode {
    try {
      const saved = localStorage.getItem(LANG_STORAGE_KEY)
      if (saved === 'zh-CN' || saved === 'en-US') return saved
    } catch {
      // Ignore storage failures
    }
    return 'zh-CN'
  }

  function applyTheme(next: ThemeMode): void {
    theme.value = next
    const root = document.documentElement
    root.classList.toggle('dark', next === 'dark')
    const metaTheme = document.querySelector('meta[name="theme-color"]')
    if (metaTheme) {
      metaTheme.setAttribute('content', next === 'dark' ? '#0A0E14' : '#F8FAFC')
    }
    try {
      localStorage.setItem(THEME_STORAGE_KEY, next)
    } catch {
      // Ignore
    }
  }

  function applyLanguage(next: LanguageCode): void {
    language.value = next
    document.documentElement.lang = next
    try {
      localStorage.setItem(LANG_STORAGE_KEY, next)
    } catch {
      // Ignore
    }
  }

  function t(key: string): string {
    return translate(language.value, key)
  }

  async function loadSettings(): Promise<void> {
    loading.value = true
    error.value = null
    try {
      const data = await api.getSettings()
      upstreamConfigured.value = data.upstream_configured
      upstreamMasked.value = data.upstream_masked
      apiTimeoutSeconds.value = data.api_timeout_seconds
      pollIntervalSeconds.value = data.poll_interval_seconds
      applyTheme(data.theme)
      applyLanguage(data.language)
      loadedFromServer.value = true
    } catch (err) {
      error.value = err instanceof ApiClientError ? err.message : '加载系统设置失败'
    } finally {
      loading.value = false
    }
  }

  async function saveSettings(payload: UpdateSettingsRequest): Promise<boolean> {
    saving.value = true
    error.value = null
    try {
      const data = await api.updateSettings(payload)
      upstreamConfigured.value = data.upstream_configured
      upstreamMasked.value = data.upstream_masked
      apiTimeoutSeconds.value = data.api_timeout_seconds
      pollIntervalSeconds.value = data.poll_interval_seconds
      applyTheme(data.theme)
      applyLanguage(data.language)
      loadedFromServer.value = true
      return true
    } catch (err) {
      error.value = err instanceof ApiClientError ? err.message : '保存设置失败'
      return false
    } finally {
      saving.value = false
    }
  }

  async function toggleTheme(persistToServer = true): Promise<void> {
    const next: ThemeMode = theme.value === 'dark' ? 'light' : 'dark'
    applyTheme(next)
    if (persistToServer && loadedFromServer.value) {
      await saveSettings({ theme: next })
    }
  }

  // Apply initial theme & language immediately on store creation
  applyTheme(theme.value)
  applyLanguage(language.value)

  return {
    upstreamConfigured,
    upstreamMasked,
    apiTimeoutSeconds,
    pollIntervalSeconds,
    theme,
    language,
    loading,
    saving,
    error,
    loadedFromServer,
    t,
    applyTheme,
    applyLanguage,
    loadSettings,
    saveSettings,
    toggleTheme,
  }
})
