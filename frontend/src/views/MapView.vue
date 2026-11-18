<script setup lang="ts">
import { useMediaQuery } from '@vueuse/core'
import { computed, ref, watch } from 'vue'
import VChart from 'vue-echarts'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { api } from '../api/client'
import { baseOptions, DIRECTION_ORDER, useChartColors } from '../charts'
import HintTip from '../components/HintTip.vue'
import { useRatings } from '../composables/useRatings'
import type { AppLocale, MapFilm, MapMe } from '../types'
import { mainDirection } from '../utils/compass'

const { t, locale } = useI18n()
const lang = computed(() => locale.value as AppLocale)
const router = useRouter()
const colors = useChartColors()
const narrow = useMediaQuery('(max-width: 640px)')
const { payload, byId } = useRatings()

const films = ref<MapFilm[]>([])
const me = ref<MapMe | null>(null)
const state = ref<'loading' | 'ok' | 'error'>('loading')

async function load() {
  state.value = 'loading'
  try {
    films.value = (await api.map(lang.value)).films
    state.value = 'ok'
  } catch {
    state.value = 'error'
  }
}
async function loadMe() {
  me.value = payload.value.length ? await api.mapMe(payload.value).catch(() => null) : null
}
watch(lang, load, { immediate: true })
watch(() => JSON.stringify(payload.value), loadMe, { immediate: true })

// группа точки – самая характерная (редкая) сторона компаса среди жанров фильма; без стороны – «Другое»
const groups = computed(() => {
  const out: Record<string, [number, number, number, string][]> = {}
  for (const f of films.value) {
    const d = mainDirection(f.genres) ?? 'other'
    ;(out[d] ??= []).push([f.x, f.y, f.id, f.title])
  }
  return out
})

const option = computed(() => {
  const c = colors.value
  const base = baseOptions(c)
  const order = [...DIRECTION_ORDER, 'other'] as const
  const series: object[] = order.map((d, i) => ({
    name: d === 'other' ? t('map.other') : t(`dir.${d}`).replace('\n', ' '),
    type: 'scatter',
    data: groups.value[d] ?? [],
    symbolSize: 5,
    large: true,
    largeThreshold: 3000,
    itemStyle: { color: d === 'other' ? c.other : c.series[i], opacity: c.dark ? 0.75 : 0.65 },
    emphasis: { scale: 2.2 },
  }))
  const mine = films.value.filter((f) => byId.value.has(f.id)).map((f) => [f.x, f.y, f.id, f.title])
  series.push({
    name: t('map.yours'),
    type: 'scatter',
    data: mine,
    // светлая заливка и янтарная обводка – не путаются ни с одним цветом групп
    symbolSize: 13,
    z: 5,
    itemStyle: { color: c.text, borderColor: c.accent, borderWidth: 3 },
  })
  if (me.value?.x !== null && me.value?.x !== undefined) {
    series.push({
      name: t('map.you'),
      type: 'scatter',
      data: [[me.value.x, me.value.y, 0, t('map.you')]],
      symbol: 'path://M12 2l2.9 6.1 6.6.8-4.9 4.6 1.3 6.6L12 17.3l-5.9 3.3 1.3-6.6L2.5 9.4l6.6-.8z',
      symbolSize: 26,
      z: 6,
      itemStyle: { color: c.accent, borderColor: c.surface, borderWidth: 2, shadowBlur: 16, shadowColor: c.accent },
      label: {
        show: true, position: 'top', formatter: t('map.you'), color: c.accent, fontWeight: 700,
        backgroundColor: c.surface, borderColor: c.accent, borderWidth: 1, borderRadius: 6, padding: [3, 6],
      },
    })
  }
  const hidden = { show: false }
  return {
    backgroundColor: 'transparent',
    textStyle: base.textStyle,
    tooltip: { ...base.tooltip, trigger: 'item', formatter: (p: { data: [number, number, number, string]; seriesName: string }) => `${p.data[3]}<br/><span style="opacity:.7">${p.seriesName}</span>` },
    // легенда переносится на несколько строк (а не листается стрелками); под неё – место внизу
    legend: { type: 'plain', bottom: 0, left: 'center', textStyle: { color: c.muted }, itemWidth: 10, itemHeight: 10, itemGap: 12 },
    grid: { left: 0, right: 0, top: 8, bottom: narrow.value ? 120 : 64 },
    xAxis: { type: 'value', min: -1.05, max: 1.05, show: false, splitLine: hidden },
    yAxis: { type: 'value', min: -1.05, max: 1.05, show: false, splitLine: hidden },
    dataZoom: [
      { type: 'inside', xAxisIndex: 0, filterMode: 'none' },
      { type: 'inside', yAxisIndex: 0, filterMode: 'none' },
    ],
    series,
  }
})

function open(params: { data?: unknown }) {
  const id = Array.isArray(params.data) ? Number(params.data[2]) : 0
  if (id) router.push({ name: 'film', params: { id } })
}
</script>

<template>
  <div class="space-y-6">
    <header class="space-y-3">
      <h1 class="flex items-center gap-2 text-3xl font-bold tracking-tight sm:text-4xl">{{ t('map.title') }} <HintTip :text="t('hint.map')" /></h1>
      <p class="max-w-3xl text-muted">{{ t('map.lead') }}</p>
    </header>
    <p v-if="!payload.length" class="text-sm text-muted">
      {{ t('map.rateFirst') }} <RouterLink to="/" class="text-accent underline">{{ t('compare.goPick') }}</RouterLink>
    </p>
    <!-- высоту задаёт обёртка: свой стиль vue-echarts (height: 100%) сильнее классов Tailwind в слое utilities -->
    <div class="relative h-[70vh] min-h-[420px] overflow-hidden rounded-2xl border border-line bg-surface p-2" style="background-image: radial-gradient(ellipse at center, var(--glow), transparent 70%)">
      <p v-if="state === 'loading'" class="absolute inset-0 flex items-center justify-center text-muted">{{ t('common.loading') }}</p>
      <p v-else-if="state === 'error'" class="absolute inset-0 flex items-center justify-center text-muted">{{ t('rec.error') }}</p>
      <VChart v-if="state === 'ok'" :option="option" autoresize @click="open" />
    </div>
    <p class="text-xs text-muted">{{ t('map.hint') }} {{ t('map.method') }}</p>
  </div>
</template>
