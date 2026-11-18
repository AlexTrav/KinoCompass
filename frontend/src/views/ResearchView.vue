<script setup lang="ts">
import { ExternalLink, LogOut } from 'lucide-vue-next'
import { computed } from 'vue'
import VChart from 'vue-echarts'
import { useI18n } from 'vue-i18n'
import { baseOptions, useChartColors } from '../charts'
import HintTip from '../components/HintTip.vue'
import site from '../data/site.json'
import type { AppLocale } from '../types'
import { formatNumber, formatPercent } from '../utils/format'

const { t, locale } = useI18n()
const lang = computed(() => locale.value as AppLocale)
const colors = useChartColors()
const r = site.research
const pct = (x: number) => formatPercent(x, lang.value)
const num = (x: number, d = 0) => formatNumber(x, lang.value, d)
const compact = (x: number) => new Intl.NumberFormat(lang.value, { notation: 'compact', maximumFractionDigits: 1 }).format(x)

const tiles = computed(() => [
  { value: compact(r.ratings), label: t('research.ratings') },
  { value: num(r.users), label: t('research.users') },
  { value: num(r.movies_rated), label: t('research.films') },
  // годы включительно: 1995–2023 – это 29 лет (как в подзаголовке)
  { value: String(Number(r.period[1].slice(0, 4)) - Number(r.period[0].slice(0, 4)) + 1), label: t('research.years') },
])

function axes(c: ReturnType<typeof useChartColors>['value']) {
  return baseOptions(c)
}

// кривая концентрации: доля оценок у первых x % фильмов и людей (самые активные первыми)
const lorenz = computed(() => {
  const c = colors.value
  const b = axes(c)
  return {
    textStyle: b.textStyle,
    tooltip: { ...b.tooltip, trigger: 'axis', valueFormatter: (v: number) => pct(v) },
    legend: { top: 0, textStyle: { color: c.muted }, itemWidth: 14, itemHeight: 3 },
    grid: { left: 8, right: 16, top: 32, bottom: 28, containLabel: true },
    xAxis: { type: 'value', min: 0, max: 1, name: t('research.tailX'), nameLocation: 'middle', nameGap: 28, nameTextStyle: { color: c.muted }, ...b.axis, axisLabel: { color: c.muted, formatter: (v: number) => pct(v) } },
    yAxis: { type: 'value', min: 0, max: 1, name: t('research.tailY'), nameTextStyle: { color: c.muted }, ...b.axis, axisLabel: { color: c.muted, formatter: (v: number) => pct(v) } },
    series: [
      { name: t('research.tailFilms'), type: 'line', showSymbol: false, data: r.lorenz.map((p) => [p[0], p[1]]), lineStyle: { width: 2, color: c.accent }, itemStyle: { color: c.accent } },
      { name: t('research.tailUsers'), type: 'line', showSymbol: false, data: r.lorenz.map((p) => [p[0], p[2]]), lineStyle: { width: 2, color: c.series[0] }, itemStyle: { color: c.series[0] } },
    ],
  }
})

const hist = computed(() => {
  const c = colors.value
  const b = axes(c)
  return {
    textStyle: b.textStyle,
    tooltip: { ...b.tooltip, trigger: 'axis', axisPointer: { type: 'shadow' }, valueFormatter: (v: number) => num(v) },
    grid: { left: 8, right: 8, top: 12, bottom: 8, containLabel: true },
    xAxis: { type: 'category', data: r.ratings_hist.map((p) => num(p[0], 1)), ...b.axis, splitLine: { show: false } },
    yAxis: { type: 'value', ...b.axis, axisLabel: { color: c.muted, formatter: (v: number) => compact(v) } },
    series: [{ type: 'bar', data: r.ratings_hist.map((p) => p[1]), barMaxWidth: 26, itemStyle: { color: c.accent, borderRadius: [4, 4, 0, 0] } }],
  }
})

const years = computed(() => {
  const c = colors.value
  const b = axes(c)
  return {
    textStyle: b.textStyle,
    tooltip: { ...b.tooltip, trigger: 'axis', axisPointer: { type: 'shadow' }, valueFormatter: (v: number) => num(v) },
    grid: { left: 8, right: 8, top: 12, bottom: 8, containLabel: true },
    xAxis: { type: 'category', data: r.years.map((y) => String(y.year)), ...b.axis, splitLine: { show: false } },
    yAxis: { type: 'value', ...b.axis, axisLabel: { color: c.muted, formatter: (v: number) => compact(v) } },
    series: [{
      type: 'bar', barMaxWidth: 14,
      data: r.years.map((y) => ({ value: y.ratings, itemStyle: { color: y.year >= 2021 ? c.accent : c.series[0], borderRadius: [3, 3, 0, 0] } })),
    }],
  }
})

const popularity = computed(() => {
  const c = colors.value
  const b = axes(c)
  const x = r.popularity.map((p) => compact(p[0]))
  return {
    textStyle: b.textStyle,
    tooltip: { ...b.tooltip, trigger: 'axis', valueFormatter: (v: number) => num(v, 2) },
    grid: { left: 8, right: 16, top: 16, bottom: 28, containLabel: true },
    xAxis: { type: 'category', data: x, name: t('research.popX'), nameLocation: 'middle', nameGap: 28, nameTextStyle: { color: c.muted }, ...b.axis, splitLine: { show: false } },
    yAxis: { type: 'value', min: 2.5, max: 4.2, ...b.axis, axisLabel: { color: c.muted, formatter: (v: number) => num(v, 1) } },
    series: [
      { name: 'q25', type: 'line', data: r.popularity.map((p) => p[2]), lineStyle: { opacity: 0 }, showSymbol: false, stack: 'band', silent: true },
      { name: 'q25–q75', type: 'line', data: r.popularity.map((p) => p[3] - p[2]), lineStyle: { opacity: 0 }, showSymbol: false, stack: 'band', areaStyle: { color: c.series[0], opacity: 0.18 }, silent: true, tooltip: { show: false } },
      { name: t('research.popY'), type: 'line', data: r.popularity.map((p) => p[1]), symbolSize: 6, lineStyle: { width: 2, color: c.series[0] }, itemStyle: { color: c.series[0] } },
    ],
  }
})

const searchRows = computed(() => (['ru', 'kk', 'en'] as const).map((l) => ({ lang: l, ...site.search['0.1'][l] })))
</script>

<template>
  <div class="space-y-12">
    <header class="space-y-3">
      <h1 class="text-3xl font-bold tracking-tight sm:text-4xl">{{ t('research.title') }}</h1>
      <p class="max-w-3xl text-muted">{{ t('research.lead') }}</p>
    </header>

    <section class="grid grid-cols-2 gap-4 lg:grid-cols-4">
      <div v-for="tile in tiles" :key="tile.label" class="rounded-2xl border border-line bg-surface p-5">
        <p class="tabular text-3xl font-bold text-accent">{{ tile.value }}</p>
        <p class="mt-1 text-sm text-muted">{{ tile.label }}</p>
      </div>
    </section>

    <section class="grid gap-6 lg:grid-cols-[1.4fr_1fr]">
      <div class="space-y-2">
        <h2 class="flex items-center gap-2 text-xl font-semibold">{{ t('research.tailTitle') }} <HintTip :text="t('hint.tail')" /></h2>
        <p class="text-sm text-muted">{{ t('research.tailText', { top1: pct(r.top1_share), top10: pct(r.top10_share) }) }}</p>
        <div class="h-80 rounded-2xl border border-line bg-surface p-3"><VChart :option="lorenz" autoresize /></div>
      </div>
      <div class="flex flex-col justify-center gap-3 rounded-2xl border border-accent bg-surface p-6 shadow-[0_0_30px_var(--glow)]">
        <LogOut class="h-8 w-8 text-accent" />
        <h2 class="text-xl font-semibold">{{ t('research.firstTitle') }}</h2>
        <p class="tabular text-5xl font-bold text-accent">{{ pct(r.only_first_day) }}</p>
        <p class="text-sm text-muted">{{ t('research.firstText', { share: pct(r.only_first_day) }) }}</p>
      </div>
    </section>

    <section class="grid gap-6 lg:grid-cols-2">
      <div class="space-y-2">
        <h2 class="text-xl font-semibold">{{ t('research.histTitle') }}</h2>
        <p class="text-sm text-muted">{{ t('research.histText', { mean: num(r.mean_rating, 2) }) }}</p>
        <div class="h-64 rounded-2xl border border-line bg-surface p-3"><VChart :option="hist" autoresize /></div>
      </div>
      <div class="space-y-2">
        <h2 class="text-xl font-semibold">{{ t('research.yearsTitle') }}</h2>
        <p class="text-sm text-muted">{{ t('research.yearsText') }}</p>
        <div class="h-64 rounded-2xl border border-line bg-surface p-3"><VChart :option="years" autoresize /></div>
      </div>
    </section>

    <section class="space-y-2">
      <h2 class="text-xl font-semibold">{{ t('research.popTitle') }}</h2>
      <p class="max-w-3xl text-sm text-muted">{{ t('research.popText') }}</p>
      <div class="h-72 rounded-2xl border border-line bg-surface p-3"><VChart :option="popularity" autoresize /></div>
    </section>

    <section class="space-y-3">
      <h2 class="text-xl font-semibold">{{ t('research.searchTitle') }}</h2>
      <p class="max-w-3xl text-sm text-muted">{{ t('research.searchText') }}</p>
      <div class="overflow-x-auto rounded-2xl border border-line">
        <table class="tabular w-full text-sm">
          <thead class="bg-surface-2 text-left text-muted">
            <tr><th class="px-4 py-2 font-medium" /><th class="px-4 py-2 font-medium">{{ t('research.plot') }}</th><th class="px-4 py-2 font-medium">{{ t('research.genre') }}</th></tr>
          </thead>
          <tbody>
            <tr v-for="row in searchRows" :key="row.lang" class="border-t border-line">
              <td class="px-4 py-2 uppercase">{{ row.lang }}</td>
              <td class="px-4 py-2">{{ Math.round(row.plot_hit * 5) }} / 5</td>
              <td class="px-4 py-2">{{ pct(row.genre_precision) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <a href="https://github.com/AlexTrav/KinoCompass/blob/main/research/README.md" target="_blank" rel="noopener" class="inline-flex items-center gap-1 text-accent hover:underline">
      {{ t('research.full') }} <ExternalLink class="h-4 w-4" />
    </a>
  </div>
</template>
