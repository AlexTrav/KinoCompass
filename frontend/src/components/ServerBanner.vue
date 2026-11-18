<script setup lang="ts">
import { CloudOff, Loader } from 'lucide-vue-next'
import { useI18n } from 'vue-i18n'
import { useServerStatus } from '../composables/useServerStatus'

const { t } = useI18n()
const { state } = useServerStatus()
</script>

<template>
  <div v-if="state !== 'ok'" role="status" aria-live="polite" class="border-b border-line bg-accent-soft text-sm">
    <p class="mx-auto flex max-w-6xl items-center gap-2 px-4 py-2 sm:px-6">
      <Loader v-if="state === 'slow'" class="h-4 w-4 shrink-0 animate-spin" />
      <CloudOff v-else class="h-4 w-4 shrink-0" />
      {{ state === 'slow' ? t('server.waking') : t('server.down') }}
    </p>
  </div>
</template>
