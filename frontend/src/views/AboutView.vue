<script setup lang="ts">
import { AlertTriangle, Database, ExternalLink, FlaskConical, Layers, Sparkles } from 'lucide-vue-next'
import { useI18n } from 'vue-i18n'
import { API_BASE } from '../api/client'

const { t } = useI18n()
const BLOCKS = [
  { key: 'what', icon: Sparkles },
  { key: 'data', icon: Database },
  { key: 'protocol', icon: FlaskConical },
  { key: 'models', icon: Layers },
] as const
const LIMITS = ['limit1', 'limit2', 'limit3', 'limit4', 'limit5'] as const
</script>

<template>
  <div class="space-y-10">
    <header class="space-y-3">
      <h1 class="text-3xl font-bold tracking-tight sm:text-4xl">{{ t('about.title') }}</h1>
      <p class="max-w-3xl text-muted">{{ t('about.lead') }}</p>
      <p class="text-sm">{{ t('footer.author') }}</p>
      <p class="text-sm text-accent">{{ t('footer.supervisor') }}</p>
    </header>

    <section class="grid gap-4 md:grid-cols-2">
      <article v-for="b in BLOCKS" :key="b.key" class="space-y-2 rounded-2xl border border-line bg-surface p-5">
        <h2 class="flex items-center gap-2 text-lg font-semibold"><component :is="b.icon" class="h-5 w-5 text-accent" /> {{ t(`about.${b.key}Title`) }}</h2>
        <p class="text-sm leading-relaxed text-muted">{{ t(`about.${b.key}Text`) }}</p>
      </article>
    </section>

    <section class="space-y-3 rounded-2xl border border-accent bg-surface p-5">
      <h2 class="flex items-center gap-2 text-lg font-semibold"><AlertTriangle class="h-5 w-5 text-accent" /> {{ t('about.limitsTitle') }}</h2>
      <ul class="list-disc space-y-1.5 pl-5 text-sm leading-relaxed text-muted">
        <li v-for="l in LIMITS" :key="l">{{ t(`about.${l}`) }}</li>
      </ul>
    </section>

    <section class="space-y-2">
      <h2 class="text-lg font-semibold">{{ t('about.linksTitle') }}</h2>
      <ul class="space-y-1 text-sm">
        <li><a href="https://github.com/AlexTrav/KinoCompass" target="_blank" rel="noopener" class="inline-flex items-center gap-1 text-accent hover:underline">{{ t('about.github') }} <ExternalLink class="h-3.5 w-3.5" /></a></li>
        <li><a :href="`${API_BASE}/docs`" target="_blank" rel="noopener" class="inline-flex items-center gap-1 text-accent hover:underline">{{ t('about.api') }} <ExternalLink class="h-3.5 w-3.5" /></a></li>
      </ul>
      <p class="pt-2 text-xs text-muted">{{ t('footer.tmdb') }}</p>
    </section>
  </div>
</template>
