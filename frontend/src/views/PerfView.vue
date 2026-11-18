<script setup lang="ts">
import { Clock, Cpu, Gauge, RefreshCw, Snowflake, Wifi } from 'lucide-vue-next'
import { computed, onMounted, ref } from 'vue'
import VChart from 'vue-echarts'
import { useI18n } from 'vue-i18n'
import { api } from '../api/client'
import { baseOptions, useChartColors } from '../charts'
import HintTip from '../components/HintTip.vue'
import type { AppLocale, Perf } from '../types'
import { formatNumber } from '../utils/format'

const { t, locale } = useI18n()
const lang = computed(() => locale.value as AppLocale)
const colors = useChartColors()
const perf = ref<Perf | null>(null)
const rtt = ref<number[]>([])
const loading = ref(false)

// путь API -> подпись на сайте
const NAMES: Record<string, string> = {
  '/api/recommend': 'recommend', '/api/new': 'new', '/api/film/{movie_id}': 'film', '/api/search': 'search',
  '/api/films': 'films', '/api/compare': 'compare', '/api/map': 'map', '/api/map/me': 'mapMe',
  '/api/health': 'health', '/api/perf': 'perf',
}

async function refresh() {
  loading.value = true
  try {
    // время ответа до браузера: три лёгких запроса подряд (с сетью и TLS), берём каждое
    const times: number[] = []
    for (let i = 0; i < 3; i++) {
      const began = performance.now()
      await api.health()
      times.push(performance.now() - began)
    }
    rtt.value = times
    perf.value = await api.perf()
  } catch {
    // плашка сервера покажет причину
  } finally {
    loading.value = false
  }
}
onMounted(refresh)

const rows = computed(() =>
  Object.entries(perf.value?.endpoints ?? {})
    .filter(([path]) => path !== '/api/perf' && path !== '/api/health')
    .map(([path, s]) => ({ key: NAMES[path] ?? path, ...s }))
    .sort((a, b) => b.p50_ms - a.p50_ms),
)
const ms = (x: number) => t('perf.ms', { n: formatNumber(x, lang.value, x < 10 ? 1 : 0) })
const uptime = computed(() => {
  const s = perf.value?.uptime_seconds ?? 0
  return s < 120 ? t('perf.s', { n: s }) : t('perf.min', { n: Math.round(s / 60) })
})
const memoryShare = computed(() => (perf.value ? (perf.value.memory_mb.peak ?? 0) / perf.value.limit_mb : 0))

const chart = computed(() => {
  const c = colors.value
  const base = baseOptions(c)
  const data = [...rows.value].reverse()
  return {
    textStyle: base.textStyle,
    tooltip: { ...base.tooltip, trigger: 'axis', axisPointer: { type: 'shadow' }, valueFormatter: (v: number) => ms(v) },
    legend: { top: 0, textStyle: { color: c.muted }, itemWidth: 12, itemHeight: 12 },
    grid: { left: 8, right: 56, top: 32, bottom: 8, containLabel: true },
    xAxis: { type: 'value', ...base.axis, axisLabel: { color: c.muted, formatter: (v: number) => ms(v) } },
    yAxis: { type: 'category', data: data.map((r) => t(`perf.ep.${r.key}`)), ...base.axis, axisLabel: { color: c.text } },
    series: [
      { name: t('perf.p50'), type: 'bar', data: data.map((r) => r.p50_ms), barMaxWidth: 12, barGap: '15%', itemStyle: { color: c.series[0], borderRadius: [0, 4, 4, 0] },
        label: { show: true, position: 'right', color: c.muted, fontSize: 11, formatter: (p: { value: number }) => ms(p.value) } },
      { name: t('perf.p95'), type: 'bar', data: data.map((r) => r.p95_ms), barMaxWidth: 12, itemStyle: { color: c.other, borderRadius: [0, 4, 4, 0] } },
    ],
  }
})
</script>

<template>
  <div class="space-y-8">
    <header class="flex flex-wrap items-end justify-between gap-4">
      <div class="space-y-3">
        <h1 class="text-3xl font-bold tracking-tight sm:text-4xl">{{ t('perf.title') }}</h1>
        <p class="max-w-3xl text-muted">{{ t('perf.lead') }}</p>
      </div>
      <button type="button" class="flex items-center gap-2 rounded-xl border border-line px-3 py-2 text-sm hover:border-accent" :disabled="loading" @click="refresh">
        <RefreshCw class="h-4 w-4" :class="{ 'animate-spin': loading }" /> {{ t('perf.refresh') }}
      </button>
    </header>

    <section v-if="perf" class="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      <div class="rounded-2xl border border-line bg-surface p-4">
        <p class="flex items-center gap-2 text-sm text-muted"><Cpu class="h-4 w-4" /> {{ t('perf.memory') }} <HintTip :text="t('hint.memory')" /></p>
        <p class="tabular mt-1 text-2xl font-semibold">{{ formatNumber(memoryShare * 100, lang) }} %</p>
        <div class="mt-2 h-2 overflow-hidden rounded-full bg-surface-2" role="meter" :aria-valuenow="perf.memory_mb.peak" aria-valuemin="0" :aria-valuemax="perf.limit_mb">
          <div class="h-full rounded-full bg-accent" :style="{ width: `${memoryShare * 100}%` }" />
        </div>
        <p class="tabular mt-1 text-xs text-muted">{{ t('perf.memoryText', { now: perf.memory_mb.now ?? '–', peak: perf.memory_mb.peak ?? '–', limit: perf.limit_mb }) }}</p>
      </div>
      <div class="rounded-2xl border border-line bg-surface p-4">
        <p class="flex items-center gap-2 text-sm text-muted"><Wifi class="h-4 w-4" /> {{ t('perf.rtt') }} <HintTip :text="t('hint.rtt')" /></p>
        <p class="tabular mt-1 text-2xl font-semibold">{{ rtt.length ? ms(Math.min(...rtt)) : '–' }}</p>
        <p class="tabular mt-1 text-xs text-muted">{{ t('perf.rttText') }}: {{ rtt.map((x) => formatNumber(x, lang)).join(' / ') }}</p>
      </div>
      <div class="rounded-2xl border border-line bg-surface p-4">
        <p class="flex items-center gap-2 text-sm text-muted"><Gauge class="h-4 w-4" /> {{ t('perf.load') }}</p>
        <p class="tabular mt-1 text-2xl font-semibold">{{ t('perf.s', { n: formatNumber(perf.load_seconds, lang, 1) }) }}</p>
      </div>
      <div class="rounded-2xl border border-line bg-surface p-4">
        <p class="flex items-center gap-2 text-sm text-muted"><Clock class="h-4 w-4" /> {{ t('perf.uptime') }}</p>
        <p class="tabular mt-1 text-2xl font-semibold">{{ uptime }}</p>
      </div>
    </section>

    <section v-if="perf" class="space-y-3">
      <p v-if="!rows.length" class="rounded-xl border border-dashed border-line p-6 text-center text-muted">{{ t('perf.empty') }}</p>
      <template v-else>
        <div class="rounded-2xl border border-line bg-surface p-4">
          <VChart :option="chart" autoresize :style="{ height: `${80 + rows.length * 44}px` }" class="w-full" />
        </div>
        <div class="overflow-x-auto rounded-2xl border border-line">
          <table class="tabular w-full text-sm">
            <thead class="bg-surface-2 text-left text-muted">
              <tr>
                <th class="px-4 py-2 font-medium">{{ t('perf.endpoint') }}</th>
                <th class="px-4 py-2 font-medium">{{ t('perf.count') }}</th>
                <th class="px-4 py-2 font-medium">{{ t('perf.p50') }}</th>
                <th class="px-4 py-2 font-medium">{{ t('perf.p95') }} <HintTip :text="t('hint.p95')" /></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="r in rows" :key="r.key" class="border-t border-line">
                <td class="px-4 py-2">{{ t(`perf.ep.${r.key}`) }}</td>
                <td class="px-4 py-2">{{ r.count }}</td>
                <td class="px-4 py-2">{{ ms(r.p50_ms) }}</td>
                <td class="px-4 py-2">{{ ms(r.p95_ms) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </template>
    </section>

    <section class="flex gap-3 rounded-2xl border border-line bg-surface p-5">
      <Snowflake class="mt-0.5 h-5 w-5 shrink-0 text-accent" />
      <div>
        <h2 class="font-semibold">{{ t('perf.cold') }}</h2>
        <p class="mt-1 text-sm text-muted">{{ t('perf.coldText') }}</p>
      </div>
    </section>
  </div>
</template>
