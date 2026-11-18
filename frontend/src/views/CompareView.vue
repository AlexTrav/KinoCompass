<script setup lang="ts">
import { Award, Timer } from 'lucide-vue-next'
import { computed, ref, watch } from 'vue'
import VChart from 'vue-echarts'
import { useI18n } from 'vue-i18n'
import { api } from '../api/client'
import { baseOptions, useChartColors } from '../charts'
import HintTip from '../components/HintTip.vue'
import { useRatings } from '../composables/useRatings'
import site from '../data/site.json'
import type { AppLocale, Compare, ModelKey } from '../types'
import { formatNumber, posterUrl } from '../utils/format'

const METRIC = 'NDCG@10'
const SCENARIOS = ['cold5', 'cold10', 'warm'] as const
const LIVE: ModelKey[] = ['popular', 'als', 'content', 'hybrid']

const { t, locale } = useI18n()
const lang = computed(() => locale.value as AppLocale)
const { payload } = useRatings()
const colors = useChartColors()
const fmt = (x: number | null, d = 3) => (x === null ? '–' : formatNumber(x, lang.value, d))

// ---------- вживую ----------
const live = ref<Compare | null>(null)
const liveState = ref<'idle' | 'loading' | 'error'>('idle')
async function loadLive() {
  if (!payload.value.length) return
  liveState.value = 'loading'
  try {
    live.value = await api.compare(payload.value, lang.value)
    liveState.value = 'idle'
  } catch {
    liveState.value = 'error'
  }
}
watch([() => JSON.stringify(payload.value), lang], loadLive, { immediate: true })
const siteIds = computed(() => new Set(live.value?.models.hybrid.items.map((f) => f.id) ?? []))

// ---------- итоговый тест: валидация и тест рядом, лучшие сверху ----------
const models = computed(() => [...site.models].sort((a, b) => (a.test ?? 0) - (b.test ?? 0)))
const chart = computed(() => {
  const c = colors.value
  const base = baseOptions(c)
  const names = models.value.map((m) => t(`models.${m.key}`))
  // цвет серии – на уровне серии (его берёт легенда); у модели сайта столбец теста – янтарный
  const bar = (key: 'validation' | 'test') =>
    models.value.map((m) => ({
      value: m[key],
      itemStyle: m.key === site.site_model && key === 'test' ? { color: c.accent } : undefined,
    }))
  return {
    textStyle: base.textStyle,
    tooltip: { ...base.tooltip, trigger: 'axis', axisPointer: { type: 'shadow' }, valueFormatter: (v: number) => fmt(v, 4) },
    legend: { top: 0, textStyle: { color: c.muted }, itemWidth: 12, itemHeight: 12 },
    grid: { left: 8, right: 48, top: 32, bottom: 8, containLabel: true },
    xAxis: { type: 'value', ...base.axis, min: 0, splitNumber: 4, axisLabel: { color: c.muted, hideOverlap: true, formatter: (v: number) => fmt(v, 2) } },
    yAxis: { type: 'category', data: names, ...base.axis, axisLabel: { color: c.text } },
    series: [
      {
        name: t('compare.validation'),
        type: 'bar',
        data: bar('validation'),
        barGap: '15%',
        barMaxWidth: 12,
        itemStyle: { color: c.other, borderRadius: [0, 4, 4, 0] },
      },
      {
        name: t('compare.testLabel'),
        type: 'bar',
        data: bar('test'),
        barMaxWidth: 12,
        itemStyle: { color: c.series[0], borderRadius: [0, 4, 4, 0] },
        label: { show: true, position: 'right', color: c.muted, fontSize: 11, formatter: (p: { value: number }) => fmt(p.value, 3) },
      },
    ],
  }
})

const best = computed(() => {
  const out: Record<string, number> = {}
  for (const s of SCENARIOS) out[s] = Math.max(...site.models.map((m) => m.scenarios[s].ndcg ?? 0))
  return out
})
</script>

<template>
  <div class="space-y-12">
    <header class="space-y-3">
      <h1 class="text-3xl font-bold tracking-tight sm:text-4xl">{{ t('compare.title') }}</h1>
      <p class="max-w-3xl text-muted">{{ t('compare.lead') }}</p>
    </header>

    <!-- вживую -->
    <section class="space-y-4">
      <h2 class="flex items-center gap-2 text-2xl font-semibold">{{ t('compare.live') }} <HintTip :text="t('hint.live')" /></h2>
      <div v-if="!payload.length" class="rounded-xl border border-dashed border-line p-6 text-center text-muted">
        {{ t('compare.noRatings') }}
        <RouterLink to="/" class="ml-2 text-accent underline">{{ t('compare.goPick') }}</RouterLink>
      </div>
      <p v-else-if="liveState === 'error'" class="text-muted">{{ t('rec.error') }}</p>
      <div v-else-if="live" class="grid gap-4 sm:grid-cols-2 lg:grid-cols-4" :class="{ 'opacity-60': liveState === 'loading' }">
        <div
          v-for="key in LIVE"
          :key="key"
          class="min-w-0 rounded-2xl border bg-surface p-4"
          :class="key === 'hybrid' ? 'border-accent shadow-[0_0_30px_var(--glow)]' : 'border-line'"
        >
          <!-- min-w-0: карточке в сетке разрешено сжиматься, длинные названия обрезаются многоточием -->
          <div class="mb-3 flex flex-wrap items-start justify-between gap-x-2 gap-y-1">
            <h3 class="font-semibold leading-tight">
              {{ t(`models.${key}`) }}
              <span v-if="key === 'hybrid'" class="ml-1 rounded bg-accent px-1.5 py-0.5 text-[11px] font-medium text-accent-ink">{{ t('compare.siteModel') }}</span>
            </h3>
            <span class="tabular flex shrink-0 items-center gap-1 text-xs text-muted"><Timer class="h-3.5 w-3.5" />{{ t('compare.ms', { n: fmt(live.models[key].ms, 1) }) }}</span>
          </div>
          <ol class="space-y-2">
            <li v-for="(f, i) in live.models[key].items" :key="f.id" class="flex items-center gap-2 text-sm">
              <span class="tabular w-5 shrink-0 text-right text-xs text-muted">{{ i + 1 }}</span>
              <img v-if="f.poster" :src="posterUrl(f.poster, 'w185') ?? ''" alt="" loading="lazy" class="h-9 w-6 shrink-0 rounded object-cover" />
              <div v-else class="h-9 w-6 shrink-0 rounded bg-surface-2" />
              <RouterLink :to="{ name: 'film', params: { id: f.id } }" class="min-w-0 flex-1 truncate hover:text-accent" :title="f.title">{{ f.title }}</RouterLink>
              <Award v-if="key !== 'hybrid' && siteIds.has(f.id)" class="h-3.5 w-3.5 shrink-0 text-accent" :aria-label="t('compare.inHybrid')" />
            </li>
          </ol>
        </div>
      </div>
      <p v-if="live" class="flex items-center gap-1 text-xs text-muted"><Award class="h-3.5 w-3.5 text-accent" /> {{ t('compare.inHybrid') }}</p>
    </section>

    <!-- итоговый тест -->
    <section class="space-y-4">
      <h2 class="flex items-center gap-2 text-2xl font-semibold">
        {{ t('compare.test') }} <HintTip :text="`${t('hint.valtest')} ${t('hint.metric')}`" />
      </h2>
      <p class="max-w-3xl text-sm text-muted">{{ t('compare.testHint', { metric: METRIC }) }}</p>
      <!-- высоту задаёт обёртка: свой стиль vue-echarts (height: 100%) сильнее классов Tailwind в слое utilities -->
      <div class="h-[440px] rounded-2xl border border-line bg-surface p-4">
        <VChart :option="chart" autoresize />
      </div>
      <p class="text-xs text-muted">{{ t('compare.metric', { metric: METRIC }) }}</p>
    </section>

    <section class="space-y-3">
      <h2 class="flex items-center gap-2 text-xl font-semibold">
        {{ t('compare.scenarios', { metric: METRIC }) }} <HintTip :text="`${t('hint.scenarios')} ${t('hint.ci')}`" />
      </h2>
      <div class="overflow-x-auto rounded-2xl border border-line">
        <table class="tabular w-full min-w-[640px] text-sm">
          <thead class="bg-surface-2 text-left text-muted">
            <tr>
              <th class="px-4 py-2 font-medium">{{ t('compare.model') }}</th>
              <th v-for="s in SCENARIOS" :key="s" class="px-4 py-2 font-medium">
                {{ t(`compare.${s}`) }}
                <span class="block text-xs font-normal">{{ t('compare.people', { n: formatNumber(site.protocol.people[s], lang) }) }}</span>
              </th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="m in [...models].reverse()" :key="m.key" class="border-t border-line" :class="{ 'bg-accent-soft/40': m.key === site.site_model }">
              <td class="px-4 py-2">
                {{ t(`models.${m.key}`) }}
                <span v-if="m.key === site.site_model" class="ml-1 text-xs text-accent">{{ t('compare.siteModel') }}</span>
              </td>
              <td v-for="s in SCENARIOS" :key="s" class="px-4 py-2">
                <span :class="{ 'font-semibold text-accent': m.scenarios[s].ndcg === best[s] }">{{ fmt(m.scenarios[s].ndcg) }}</span>
                <span v-if="m.scenarios[s].ci.length" class="ml-1 text-xs text-muted">{{ fmt(m.scenarios[s].ci[0]) }}–{{ fmt(m.scenarios[s].ci[1]) }}</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <section class="space-y-2 rounded-2xl border border-line bg-surface p-5">
      <h2 class="text-xl font-semibold">{{ t('compare.newTitle') }}</h2>
      <p class="max-w-3xl text-sm leading-relaxed text-muted">
        {{ t('compare.newText', { val: fmt(site.new_items.validation.hybrid_new, 4), test: fmt(site.new_items.test.content_text, 4) }) }}
      </p>
    </section>
  </div>
</template>
