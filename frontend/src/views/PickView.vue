<script setup lang="ts">
import { refDebounced } from '@vueuse/core'
import { Search, Sparkles, Trash2, X } from 'lucide-vue-next'
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { api } from '../api/client'
import CompassRose from '../components/CompassRose.vue'
import FilmCard from '../components/FilmCard.vue'
import HintTip from '../components/HintTip.vue'
import { ENOUGH, useRatings } from '../composables/useRatings'
import type { AppLocale, Film } from '../types'
import { posterUrl } from '../utils/format'

const { t, locale } = useI18n()
const lang = computed(() => locale.value as AppLocale)
const { ratings, payload, remove, clear } = useRatings()

// ---------- фильмы для оценки: популярное, поиск по названию или по описанию ----------
const mode = ref<'title' | 'meaning'>('title')
const query = ref('')
const debounced = refDebounced(query, 350)
const pool = ref<Film[]>([])
const poolLoading = ref(false)
let poolAbort: AbortController | null = null

async function loadPool() {
  poolAbort?.abort()
  poolAbort = new AbortController()
  poolLoading.value = true
  const q = debounced.value.trim()
  try {
    const res =
      mode.value === 'meaning' && q
        ? await api.search(q, lang.value, 24, poolAbort.signal)
        : await api.films(q, lang.value, 24, poolAbort.signal)
    pool.value = res.items
  } catch {
    // aborted или сеть – плашка сервера покажет причину
  } finally {
    poolLoading.value = false
  }
}
watch([debounced, mode, lang], loadPool, { immediate: true })

// ---------- советы и новинки: пересчёт при каждой оценке и движении ползунка ----------
const weight = ref(0.4) // вес популярности: 0,4 – как на тесте
const novelty = computed({ get: () => Math.round((0.8 - weight.value) * 10) / 10, set: (v) => (weight.value = Math.round((0.8 - v) * 10) / 10) })
const recs = ref<Film[]>([])
const fresh = ref<Film[]>([])
const recState = ref<'idle' | 'loading' | 'error'>('idle')
const trigger = refDebounced(computed(() => JSON.stringify([payload.value, weight.value, lang.value])), 300)
let recAbort: AbortController | null = null

async function loadRecs() {
  recAbort?.abort()
  if (!payload.value.length) {
    recs.value = []
    fresh.value = []
    return
  }
  recAbort = new AbortController()
  recState.value = 'loading'
  try {
    const [r, n] = await Promise.all([
      api.recommend(payload.value, lang.value, weight.value, recAbort.signal),
      api.newItems(payload.value, lang.value, recAbort.signal),
    ])
    recs.value = r.items
    fresh.value = n.items
    recState.value = 'idle'
  } catch (err) {
    if ((err as Error).message !== 'aborted') recState.value = 'error'
  }
}
watch(trigger, loadRecs, { immediate: true })

const left = computed(() => Math.max(0, ENOUGH - ratings.value.length))
const progress = computed(() => Math.min(1, ratings.value.length / ENOUGH))
</script>

<template>
  <div class="space-y-12">
    <!-- первый экран: зачем сайт и компас вкуса -->
    <section class="grid items-center gap-8 md:grid-cols-2">
      <div class="space-y-5">
        <h1 class="text-4xl font-bold tracking-tight sm:text-5xl">
          {{ t('hero.title') }}
        </h1>
        <p class="max-w-xl text-lg text-muted">{{ t('hero.lead') }}</p>
        <div class="max-w-md space-y-2">
          <div class="flex justify-between text-sm">
            <span class="tabular">{{ t('hero.progress', { n: Math.min(ratings.length, ENOUGH), need: ENOUGH }) }}</span>
            <span v-if="!left" class="text-accent">{{ t('hero.ready') }}</span>
          </div>
          <div class="h-2 overflow-hidden rounded-full bg-surface-2">
            <div class="h-full rounded-full bg-accent transition-all duration-500" :style="{ width: `${progress * 100}%` }" />
          </div>
        </div>
      </div>
      <CompassRose :ratings="ratings" />
    </section>

    <!-- ваши оценки -->
    <section v-if="ratings.length" class="space-y-3">
      <div class="flex items-center justify-between">
        <h2 class="text-lg font-semibold">{{ t('rate.yours') }}</h2>
        <button type="button" class="flex items-center gap-1 text-sm text-muted hover:text-ink" @click="clear">
          <Trash2 class="h-4 w-4" /> {{ t('rate.clear') }}
        </button>
      </div>
      <ul class="flex flex-wrap gap-2">
        <li v-for="r in ratings" :key="r.id" class="flex items-center gap-2 rounded-full border border-line bg-surface py-1 pl-1 pr-2 text-sm">
          <img v-if="r.poster" :src="posterUrl(r.poster, 'w185') ?? ''" alt="" class="h-7 w-7 rounded-full object-cover" />
          <RouterLink :to="{ name: 'film', params: { id: r.id } }" class="max-w-[12rem] truncate hover:text-accent">{{ r.title }}</RouterLink>
          <span class="tabular text-accent">★ {{ r.rating.toLocaleString(lang) }}</span>
          <button type="button" class="text-muted hover:text-ink" :aria-label="t('rate.remove')" @click="remove(r.id)">
            <X class="h-4 w-4" />
          </button>
        </li>
      </ul>
    </section>

    <!-- советы -->
    <section class="space-y-5">
      <div class="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h2 class="flex items-center gap-2 text-2xl font-semibold">
            <Sparkles class="h-6 w-6 text-accent" /> {{ t('rec.title') }} <HintTip :text="t('hint.because')" />
          </h2>
          <p v-if="ratings.length && left" class="mt-1 text-sm text-muted">{{ t('rec.more', { n: left }) }}</p>
        </div>
        <div v-if="ratings.length" class="w-full max-w-sm space-y-1">
          <label for="novelty" class="flex justify-between text-sm">
            <span class="flex items-center gap-1">{{ t('rec.novelty') }} <HintTip :text="t('hint.novelty')" /></span>
            <span v-if="weight === 0.4" class="text-accent">{{ t('rec.tested') }}</span>
          </label>
          <div class="relative">
            <input id="novelty" v-model.number="novelty" type="range" min="0" max="0.8" step="0.1" class="w-full accent-[var(--accent)]" :title="t('rec.noveltyHint')" />
            <span class="pointer-events-none absolute left-1/2 top-full h-2 w-px -translate-x-1/2 bg-accent" aria-hidden="true" />
          </div>
          <div class="flex justify-between text-xs text-muted">
            <span>{{ t('rec.hits') }}</span>
            <span>{{ t('rec.taste') }}</span>
          </div>
        </div>
      </div>
      <p v-if="!ratings.length" class="rounded-xl border border-dashed border-line p-6 text-center text-muted">{{ t('rec.empty') }}</p>
      <p v-else-if="recState === 'error'" class="flex items-center gap-3 text-muted">
        {{ t('rec.error') }}
        <button type="button" class="rounded-lg bg-accent px-3 py-1 text-sm text-accent-ink" @click="loadRecs">{{ t('rec.retry') }}</button>
      </p>
      <div v-else class="grid grid-cols-2 gap-4 transition-opacity sm:grid-cols-3 lg:grid-cols-6" :class="{ 'opacity-60': recState === 'loading' }">
        <FilmCard v-for="f in recs" :key="f.id" :film="f" show-because />
      </div>
    </section>

    <!-- новинки -->
    <section v-if="fresh.length" class="space-y-4">
      <div>
        <h2 class="flex items-center gap-2 text-2xl font-semibold">{{ t('rec.newTitle') }} <HintTip :text="t('hint.fresh')" /></h2>
      </div>
      <div class="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
        <FilmCard v-for="f in fresh" :key="f.id" :film="f" />
      </div>
    </section>

    <!-- оценить фильмы -->
    <section class="space-y-5">
      <div>
        <h2 class="flex items-center gap-2 text-2xl font-semibold">{{ t('rate.title') }} <HintTip :text="t('hint.stars')" /></h2>
        <p class="mt-1 text-sm text-muted">{{ t('rate.hint') }}</p>
      </div>
      <div class="flex flex-col gap-3 sm:flex-row">
        <div class="flex shrink-0 rounded-xl border border-line p-1 text-sm" role="tablist">
          <button
            v-for="m in (['title', 'meaning'] as const)"
            :key="m"
            type="button"
            role="tab"
            :aria-selected="mode === m"
            class="rounded-lg px-3 py-1.5 transition"
            :class="mode === m ? 'bg-accent text-accent-ink' : 'text-muted hover:text-ink'"
            @click="mode = m"
          >
            {{ m === 'title' ? t('rate.searchTitle') : t('rate.searchMeaning') }}
          </button>
          <span class="flex items-center px-1"><HintTip :text="t('hint.search')" /></span>
        </div>
        <label class="relative flex-1">
          <Search class="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
          <input
            v-model="query"
            type="search"
            maxlength="200"
            class="w-full rounded-xl border border-line bg-surface py-2.5 pl-9 pr-3 outline-none transition focus:border-accent"
            :placeholder="mode === 'title' ? t('rate.placeholderTitle') : t('rate.placeholderMeaning')"
          />
        </label>
      </div>
      <p class="text-sm text-muted">{{ debounced.trim() ? t('rate.found') : t('rate.popular') }}</p>
      <p v-if="!poolLoading && !pool.length" class="text-muted">{{ t('rate.nothing') }}</p>
      <div class="grid grid-cols-2 gap-4 transition-opacity sm:grid-cols-3 lg:grid-cols-6" :class="{ 'opacity-60': poolLoading }">
        <FilmCard v-for="f in pool" :key="f.id" :film="f" />
      </div>
    </section>
  </div>
</template>
