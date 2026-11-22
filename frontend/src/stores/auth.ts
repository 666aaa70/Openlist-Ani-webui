import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api, ApiClientError } from '@/api/client'

export const useAuthStore = defineStore('auth', () => {
  const authenticated = ref(false)
  const username = ref('')
  const csrfToken = ref<string | null>(null)
  const initialized = ref(false)
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function checkSession(): Promise<boolean> {
    try {
      const res = await api.me()
      authenticated.value = res.authenticated
      username.value = res.username
      csrfToken.value = res.csrf_token
      error.value = null
      return true
    } catch {
      clearSession()
      return false
    } finally {
      initialized.value = true
    }
  }

  async function login(user: string, password: string): Promise<boolean> {
    loading.value = true
    error.value = null
    try {
      const res = await api.login(user, password)
      authenticated.value = res.authenticated
      username.value = res.username
      csrfToken.value = res.csrf_token
      initialized.value = true
      return true
    } catch (err) {
      if (err instanceof ApiClientError) {
        error.value = err.message
      } else {
        error.value = '登录失败，请稍后重试'
      }
      return false
    } finally {
      loading.value = false
    }
  }

  async function logout(): Promise<void> {
    try {
      await api.logout()
    } catch {
      // Ignore network errors on logout and clear client session state
    } finally {
      clearSession()
    }
  }

  function clearSession(): void {
    authenticated.value = false
    username.value = ''
    csrfToken.value = null
  }

  return {
    authenticated,
    username,
    csrfToken,
    initialized,
    loading,
    error,
    checkSession,
    login,
    logout,
    clearSession,
  }
})
