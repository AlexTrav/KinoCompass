<script setup lang="ts">
import { ArrowLeft, ExternalLink, Film as FilmIcon } from 'lucide-vue-next'
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { api } from '../api/client'
import FilmCard from '../components/FilmCard.vue'
import HintTip from '../components/HintTip.vue'
import StarRating from '../components/StarRating.vue'
import { useRatings } from '../composables/useRatings'
import type { AppLocale, FilmDetail } from '../types'
import { formatNumber, posterUrl } from '../utils/format'

const props = defineProps<{ id: string }>()
const { t, locale } = useI18n()
const lang = computed(() => locale.value as AppLocale)
const router = useRouter()
const film = ref<FilmDetail | null>(null)
const state = ref<'loading' | 'ok' | 'missing' | 'error'>('loading')
const { byId, rate, remove } = useRatings()

async function load() {
  state.value = 'loading'
  try {
    film.value = await api.film(Number(props.id), lang.value)
    state.value = 'ok'
  } catch (err) {
    state.value = (err as { status?: number }).status === 404 ? 'missing' : 'error'
  }
}
watch([() => props.id, lang], load, { immediate: true })

const rating = computed({
  get: () => (film.value ? (byId.value.get(film.value.id) ?? 0) : 0),
  set: (value: number) => {
    if (!film.value) return
    if (value) rate(film.value, value)
    else remove(film.value.id)
  },
})

// два ряда похожих – по поведению людей (ALS) и по смыслу описания (e5): сколько фильмов нашли оба подхода
const plot = computed(() => film.value?.similar_plot ?? [])
const common = computed(() => {
  const behaviour = new Set(film.value?.similar.map((f) => f.id) ?? [])
  return plot.value.filter((f) => behaviour.has(f.id)).length
})
</script>

<template>
  <div class="space-y-10">
    <button type="button" class="flex items-center gap-1 text-sm text-muted hover:text-ink" @click="router.back()">
      <ArrowLeft class="h-4 w-4" /> {{ t('film.back') }}
    </button>

    <p v-if="state === 'loading'" class="text-muted">{{ t('common.loading') }}</p>
    <p v-else-if="state === 'missing'" class="text-muted">{{ t('film.notFound') }}</p>
    <p v-else-if="state === 'error'" class="text-muted">{{ t('rec.error') }}</p>

    <template v-else-if="film">
      <section class="grid gap-8 md:grid-cols-[280px_1fr]">
        <div class="aspect-[2/3] overflow-hidden rounded-2xl border border-line bg-surface-2 shadow-[0_10px_40px_var(--glow)]">
          <img v-if="film.poster" :src="posterUrl(film.poster, 'w500') ?? ''" :alt="film.title" class="h-full w-full object-cover" />
          <div v-else class="flex h-full items-center justify-center text-muted"><FilmIcon class="h-12 w-12" /></div>
        </div>
        <div class="space-y-5">
          <div>
            <h1 class="text-3xl font-bold tracking-tight sm:text-4xl">{{ film.title }}</h1>
            <p class="mt-1 text-muted">
              <span v-if="film.original_title !== film.title">{{ film.original_title }} · </span>{{ film.year ?? '' }}
            </p>
          </div>
          <ul class="flex flex-wrap gap-2">
            <li v-for="g in film.genres" :key="g" class="rounded-full border border-line px-2.5 py-0.5 text-xs text-muted">{{ g }}</li>
          </ul>
          <p class="tabular text-sm text-muted">
            {{ t('film.ratings', { n: formatNumber(film.n_ratings, lang), avg: formatNumber(film.mean_rating, lang, 2) }) }}
          </p>
          <div class="space-y-1">
            <p class="text-sm font-medium">{{ t('film.yourRating') }}</p>
            <StarRating v-model="rating" :size="28" />
          </div>
          <div class="space-y-2">
            <h2 class="text-lg font-semibold">{{ t('film.overview') }}</h2>
            <p class="max-w-2xl leading-relaxed">{{ film.overview ?? t('film.noOverview') }}</p>
          </div>
          <div class="flex flex-wrap gap-3 text-sm">
            <a v-if="film.imdb_id" :href="`https://www.imdb.com/title/${film.imdb_id}/`" target="_blank" rel="noopener" class="flex items-center gap-1 text-accent hover:underline">IMDb <ExternalLink class="h-3.5 w-3.5" /></a>
            <a v-if="film.tmdb_id" :href="`https://www.themoviedb.org/movie/${film.tmdb_id}`" target="_blank" rel="noopener" class="flex items-center gap-1 text-accent hover:underline">TMDb <ExternalLink class="h-3.5 w-3.5" /></a>
          </div>
          <details class="text-sm text-muted">
            <summary class="cursor-pointer">{{ t('film.titles') }}</summary>
            <ul class="mt-2 space-y-0.5">
              <li v-for="(title, l) in film.titles" :key="l"><span class="uppercase">{{ l }}</span>: {{ title }}</li>
            </ul>
          </details>
        </div>
      </section>

      <section class="space-y-4">
        <div>
          <h2 class="flex items-center gap-2 text-2xl font-semibold">{{ t('film.similar') }} <HintTip v-if="plot.length" :text="t('hint.twoRows')" /></h2>
          <p class="mt-1 text-sm text-muted">{{ t('film.similarBy') }}</p>
        </div>
        <div class="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
          <FilmCard v-for="f in film.similar" :key="f.id" :film="f" />
        </div>
      </section>

      <section v-if="plot.length" class="space-y-4">
        <div>
          <h2 class="text-2xl font-semibold">{{ t('film.plot') }}</h2>
          <p class="mt-1 text-sm text-muted">{{ t('film.plotBy') }}</p>
        </div>
        <div class="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
          <FilmCard v-for="f in plot" :key="f.id" :film="f" />
        </div>
        <p class="tabular text-xs text-muted">
          {{ common ? t('film.common', { n: common, total: plot.length }) : t('film.commonNone') }}
        </p>
      </section>
    </template>
  </div>
</template>
