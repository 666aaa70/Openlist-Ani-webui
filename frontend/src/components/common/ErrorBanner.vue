<script setup lang="ts">
import { AlertCircle, RefreshCw } from 'lucide-vue-next'

defineProps<{
  title?: string
  message: string
  retryable?: boolean
}>()

defineEmits<{
  retry: []
}>()
</script>

<template>
  <div
    role="alert"
    class="flex flex-col gap-3 rounded-xl border border-rose-500/30 bg-rose-500/10 px-4 py-3.5 text-sm sm:flex-row sm:items-center sm:justify-between"
  >
    <div class="flex items-start gap-3">
      <AlertCircle class="mt-0.5 h-4 w-4 shrink-0 text-rose-400" />
      <div class="min-w-0">
        <p v-if="title" class="font-medium text-rose-300 dark:text-rose-200">{{ title }}</p>
        <p class="text-xs leading-relaxed text-rose-600 dark:text-rose-200/90">{{ message }}</p>
      </div>
    </div>
    <button
      v-if="retryable"
      type="button"
      class="inline-flex shrink-0 items-center justify-center gap-1.5 rounded-lg border border-rose-500/35 bg-rose-500/15 px-3 py-1.5 text-xs font-medium text-rose-700 transition hover:bg-rose-500/25 dark:text-rose-100"
      @click="$emit('retry')"
    >
      <RefreshCw class="h-3.5 w-3.5" />
      重试
    </button>
  </div>
</template>
