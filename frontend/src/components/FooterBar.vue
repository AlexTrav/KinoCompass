<script setup lang="ts">
import { useI18n } from 'vue-i18n'

const { t } = useI18n()
</script>

<template>
  <footer class="border-t border-line text-xs text-muted">
    <div class="mx-auto max-w-6xl space-y-1 px-4 py-6 sm:px-6">
      <p>{{ t('footer.data') }}</p>
      <p>{{ t('footer.tmdb') }}</p>
      <p>{{ t('footer.supervisor') }}</p>
      <p>
        {{ t('footer.author') }} ·
        <a class="underline hover:text-ink" href="https://github.com/AlexTrav/KinoCompass" target="_blank" rel="noopener">GitHub</a>
      </p>
    </div>
  </footer>
</template>
