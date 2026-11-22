<script setup lang="ts">
import { Inbox } from 'lucide-vue-next'

defineProps<{
  title: string
  description?: string
}>()
</script>

<template>
  <div class="surface-card flex flex-col items-center justify-center rounded-xl px-6 py-14 text-center">
    <div
      class="mb-4 flex h-12 w-12 items-center justify-center rounded-xl border border-[var(--border-default)] bg-[var(--bg-subtle)] text-[var(--text-muted)]"
    >
      <slot name="icon">
        <Inbox class="h-5 w-5" />
      </slot>
    </div>
    <h3 class="text-sm font-semibold text-[var(--text-primary)]">{{ title }}</h3>
    <p v-if="description" class="mt-1.5 max-w-md text-xs leading-relaxed text-[var(--text-secondary)]">
      {{ description }}
    </p>
    <div v-if="$slots.action" class="mt-5">
      <slot name="action" />
    </div>
  </div>
</template>
