import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api, ApiClientError } from '@/api/client'
import type { ServiceHealthResponse } from '@/types/api'

export const useHealthStore = defineStore('health', () => {
  const health = ref<ServiceHealthResponse | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function fetchHealth(): Promise<ServiceHealthResponse | null> {
    loading.value = true
    error.value = null
    try {
      const data = await api.getHealth()
      health.value = data
      return data
    } catch (err) {
      error.value = err instanceof ApiClientError ? err.message : '健康状态获取失败'
      return null
    } finally {
      loading.value = false
    }
  }

  async function testConnection(): Promise<ServiceHealthResponse | null> {
    loading.value = true
    error.value = null
    try {
      const data = await api.testConnection()
      health.value = data
      return data
    } catch (err) {
      error.value = err instanceof ApiClientError ? err.message : '连接测试失败'
      return null
    } finally {
      loading.value = false
    }
  }

  return {
    health,
    loading,
    error,
    fetchHealth,
    testConnection,
  }
})
