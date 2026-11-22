import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api, ApiClientError } from '@/api/client'
import type { DownloadTaskResponse } from '@/types/api'
import { useHealthStore } from './health'
import { useSettingsStore } from './settings'

export const useDownloadsStore = defineStore('downloads', () => {
  const tasks = ref<DownloadTaskResponse[]>([])
  const total = ref(0)
  const activeCount = ref(0)
  const completedCount = ref(0)
  const failedCount = ref(0)
  const cancelledCount = ref(0)
  const syncedAt = ref<string | null>(null)

  const initialLoading = ref(false)
  const refreshing = ref(false)
  const error = ref<string | null>(null)
  const errorCode = ref<string | null>(null)

  const selectedTask = ref<DownloadTaskResponse | null>(null)
  const selectedTaskLoading = ref(false)
  const selectedTaskError = ref<string | null>(null)

  const newDownloadModalOpen = ref(false)
  const pollingEnabled = ref(true)

  let pollTimer: number | null = null
  let inFlight = false
  let visibilityBound = false
  let inspectSeq = 0

  async function fetchDownloads(options: { silent?: boolean } = {}): Promise<void> {
    if (inFlight) return
    inFlight = true
    if (!options.silent && tasks.value.length === 0 && !syncedAt.value) {
      initialLoading.value = true
    } else if (!options.silent) {
      refreshing.value = true
    }

    try {
      const data = await api.listDownloads()
      tasks.value = data.tasks
      total.value = data.total
      activeCount.value = data.active_count
      completedCount.value = data.completed_count
      failedCount.value = data.failed_count
      cancelledCount.value = data.cancelled_count
      syncedAt.value = data.synced_at
      error.value = null
      errorCode.value = null

      // Keep open detail drawer synchronized with latest task snapshot
      if (selectedTask.value) {
        const updated = data.tasks.find((t) => t.id === selectedTask.value?.id)
        if (updated) {
          selectedTask.value = updated
        }
      }
    } catch (err) {
      if (err instanceof ApiClientError) {
        error.value = err.message
        errorCode.value = err.code
      } else {
        error.value = '获取下载列表失败'
        errorCode.value = 'unknown'
      }
    } finally {
      inFlight = false
      initialLoading.value = false
      refreshing.value = false
    }
  }

  async function inspectTask(taskId: string): Promise<DownloadTaskResponse | null> {
    const cleaned = taskId.trim()
    if (!cleaned) return null
    inspectSeq += 1
    const mySeq = inspectSeq
    selectedTaskLoading.value = true
    selectedTaskError.value = null
    const existing = tasks.value.find((t) => t.id === cleaned)
    if (existing) {
      selectedTask.value = existing
    }
    try {
      const fresh = await api.getDownload(cleaned)
      if (mySeq !== inspectSeq) return null
      selectedTask.value = fresh
      // Merge into local tasks list if newly discovered via historical task ID lookup
      const idx = tasks.value.findIndex((t) => t.id === fresh.id)
      if (idx >= 0) {
        tasks.value[idx] = fresh
      } else {
        tasks.value = [fresh, ...tasks.value]
        recomputeCounts()
      }
      return fresh
    } catch (err) {
      if (mySeq !== inspectSeq) return null
      selectedTaskError.value = err instanceof ApiClientError ? err.message : '无法加载任务详情'
      return null
    } finally {
      if (mySeq === inspectSeq) {
        selectedTaskLoading.value = false
      }
    }
  }

  function recomputeCounts(): void {
    total.value = tasks.value.length
    completedCount.value = tasks.value.filter((t) => t.state === 'completed').length
    failedCount.value = tasks.value.filter((t) => t.state === 'failed').length
    cancelledCount.value = tasks.value.filter((t) => t.state === 'cancelled').length
    activeCount.value =
      total.value - completedCount.value - failedCount.value - cancelledCount.value
  }

  function closeTaskDetail(): void {
    inspectSeq += 1
    selectedTask.value = null
    selectedTaskError.value = null
    selectedTaskLoading.value = false
  }

  function reset(): void {
    stopPolling()
    closeTaskDetail()
    newDownloadModalOpen.value = false
    tasks.value = []
    total.value = 0
    activeCount.value = 0
    completedCount.value = 0
    failedCount.value = 0
    cancelledCount.value = 0
    syncedAt.value = null
    error.value = null
    errorCode.value = null
    initialLoading.value = false
    refreshing.value = false
  }

  function openNewDownloadModal(): void {
    newDownloadModalOpen.value = true
  }

  function closeNewDownloadModal(): void {
    newDownloadModalOpen.value = false
  }

  function handleVisibilityChange(): void {
    if (document.visibilityState === 'visible' && pollingEnabled.value) {
      void refreshAll(true)
    }
  }

  async function refreshAll(silent = false): Promise<void> {
    const healthStore = useHealthStore()
    await Promise.all([fetchDownloads({ silent }), healthStore.fetchHealth()])
  }

  function startPolling(): void {
    stopPolling()
    const settingsStore = useSettingsStore()
    const intervalMs = Math.max(2000, settingsStore.pollIntervalSeconds * 1000)

    if (!visibilityBound && typeof document !== 'undefined') {
      document.addEventListener('visibilitychange', handleVisibilityChange)
      visibilityBound = true
    }

    pollTimer = window.setInterval(() => {
      if (!pollingEnabled.value) return
      if (typeof document !== 'undefined' && document.visibilityState === 'hidden') return
      void refreshAll(true)
    }, intervalMs)
  }

  function stopPolling(): void {
    if (pollTimer !== null) {
      window.clearInterval(pollTimer)
      pollTimer = null
    }
    if (visibilityBound && typeof document !== 'undefined') {
      document.removeEventListener('visibilitychange', handleVisibilityChange)
      visibilityBound = false
    }
  }

  return {
    tasks,
    total,
    activeCount,
    completedCount,
    failedCount,
    cancelledCount,
    syncedAt,
    initialLoading,
    refreshing,
    error,
    errorCode,
    selectedTask,
    selectedTaskLoading,
    selectedTaskError,
    newDownloadModalOpen,
    pollingEnabled,
    fetchDownloads,
    inspectTask,
    closeTaskDetail,
    reset,
    openNewDownloadModal,
    closeNewDownloadModal,
    refreshAll,
    startPolling,
    stopPolling,
  }
})
