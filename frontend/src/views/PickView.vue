<script setup lang="ts">
import { refDebounced } from '@vueuse/core'
import { Drama, Ghost, Rocket, Search, Share2, Smile, Sparkles, Trash2, Undo2, X } from 'lucide-vue-next'
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { api, ratedCards } from '../api/client'
import CompassRose from '../components/CompassRose.vue'
import FilmCard from '../components/FilmCard.vue'
import HintTip from '../components/HintTip.vue'
import RecsInsight from '../components/RecsInsight.vue'
import ShareDialog from '../components/ShareDialog.vue'
import WhyDialog from '../components/WhyDialog.vue'
import { ENOUGH, useRatings } from '../composables/useRatings'
import type { AppLocale, Because, Film } from '../types'
import { posterUrl } from '../utils/format'
import { type Persona, type PersonaKey, PERSONAS, personaRatings } from '../utils/personas'
import { decodeRatings, SHARE_PARAM } from '../utils/share'

const { t, locale } = useI18n()
const lang = computed(() => locale.value as AppLocale)
const { ratings, payload, backup, remove, clear, replace, restore } = useRatings()

// ---------- готовые вкусы и оценки из ссылки «Поделиться»: заменяют оценки, свои можно вернуть ----------
const PERSONA_ICON = { scifi: Rocket, animation: Smile, classic: Drama, horror: Ghost } as const
const applied = ref<PersonaKey | 'link' | null>(null)
const linkState = ref<'idle' | 'loading' | 'failed'>('idle')
const shareOpen = ref(false)
const appliedText = computed(() =>
  applied.value === 'link'
    ? t('persona.appliedLink')
    : applied.value
      ? t('persona.applied', { name: t(`persona.${applied.value}`) })
      : '',
)

// после выбора – к советам: их пересчёт виден сразу
async function showRecs() {
  await nextTick()
  document.getElementById('recs')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

function applyPersona(persona: Persona) {
  replace(personaRatings(persona, lang.value))
  applied.value = persona.key
  showRecs()
}

function restoreOwn() {
  restore()
  applied.value = null
}

// ссылка вида /?r=2571-10.318-9: оценки грузятся один раз, параметр убирается из адреса – перезагрузка страницы
// не заменит оценки повторно
const route = useRoute()
const router = useRouter()
onMounted(async () => {
  const raw = route.query[SHARE_PARAM]
  if (typeof raw !== 'string' || !raw) return
  const scores = decodeRatings(raw)
  router.replace({ query: {} })
  if (!scores.length) return
  linkState.value = 'loading'
  const cards = await ratedCards(scores, lang.value)
  if (!cards.length) {
    linkState.value = 'failed'
    return
  }
  replace(cards)
  applied.value = 'link'
  linkState.value = 'idle'
  showRecs()
})

// ---------- «Показать ещё»: страница за страницей (offset), пока фильмы в списке не кончатся ----------
// популярное – весь каталог, поиск по названию – все совпадения, новинки – все 443, советы – весь каталог
const STEP = { recs: 12, fresh: 12, pool: 24 }
const PAGE_MAX = 50 // больше за один запрос сервер не отдаёт: после новой оценки открытые советы – до 50

/** К списку – следующая страница без повторов; кнопка остаётся, пока страница пришла полной. */
function append(list: Film[], page: Film[]): Film[] {
  const seen = new Set(list.map((f) => f.id))
  return [...list, ...page.filter((f) => !seen.has(f.id))]
}

// ---------- фильмы для оценки: популярное, поиск по названию или по описанию ----------
const mode = ref<'title' | 'meaning'>('title')
const query = ref('')
const debounced = refDebounced(query, 350)
const pool = ref<Film[]>([])
const poolLoading = ref(false)
const poolMore = ref(false)
let poolAbort: AbortController | null = null
const byMeaning = computed(() => mode.value === 'meaning' && !!debounced.value.trim())

async function loadPool(more = false) {
  poolAbort?.abort()
  poolAbort = new AbortController()
  poolLoading.value = true
  const q = debounced.value.trim()
  const offset = more ? pool.value.length : 0
  try {
    const res = byMeaning.value
      ? await api.search(q, lang.value, STEP.pool, poolAbort.signal, offset)
      : await api.films(q, lang.value, STEP.pool, poolAbort.signal, offset)
    pool.value = more ? append(pool.value, res.items) : res.items
    poolMore.value = res.items.length === STEP.pool
  } catch {
    // aborted или сеть – плашка сервера покажет причину
  } finally {
    poolLoading.value = false
  }
}
// новый запрос – снова с первой страницы
watch([debounced, mode, lang], () => loadPool(), { immediate: true })

// ---------- советы и новинки: пересчёт при каждой оценке и движении ползунка ----------
const weight = ref(0.4) // вес популярности: 0,4 – как на тесте
const novelty = computed({ get: () => Math.round((0.8 - weight.value) * 10) / 10, set: (v) => (weight.value = Math.round((0.8 - v) * 10) / 10) })
const recs = ref<Film[]>([])
const fresh = ref<Film[]>([])
const recState = ref<'idle' | 'loading' | 'error'>('idle')
const recsMore = ref(false)
const freshMore = ref(false)
const moreLoading = ref<'recs' | 'fresh' | null>(null)
const trigger = refDebounced(computed(() => JSON.stringify([payload.value, weight.value, lang.value])), 300)
let recAbort: AbortController | null = null

// объяснения: вклад ваших фильмов в первую страницу советов (столько советов – influenceBasis) и вес
// популярности, с которым они посчитаны (ползунок мог сдвинуться, пока ответ в пути); окно «Почему этот фильм» –
// для совета (taste) или новинки (plot)
const influence = ref<Because[]>([])
const influenceBasis = ref(0)
const recWeight = ref(weight.value)
const why = ref<{ film: Film; kind: 'taste' | 'plot' } | null>(null)

async function loadRecs() {
  recAbort?.abort()
  if (!payload.value.length) {
    recs.value = []
    fresh.value = []
    influence.value = []
    return
  }
  recAbort = new AbortController()
  recState.value = 'loading'
  // после новой оценки список пересчитывается заново, уже открытое число карточек сохраняется (до 50)
  const recK = Math.min(Math.max(STEP.recs, recs.value.length), PAGE_MAX)
  const freshK = Math.min(Math.max(STEP.fresh, fresh.value.length), PAGE_MAX)
  try {
    const [r, n] = await Promise.all([
      api.recommend(payload.value, lang.value, weight.value, recAbort.signal, recK),
      api.newItems(payload.value, lang.value, recAbort.signal, freshK),
    ])
    recs.value = r.items
    recsMore.value = r.items.length === recK
    influence.value = r.influence ?? []
    influenceBasis.value = r.items.length
    recWeight.value = r.popularity_weight
    fresh.value = n.items
    freshMore.value = n.items.length === freshK
    recState.value = 'idle'
  } catch (err) {
    if ((err as Error).message !== 'aborted') recState.value = 'error'
  }
}
watch(trigger, loadRecs, { immediate: true })

// следующая страница советов или новинок – с тем же весом популярности, что у открытого списка; новая оценка
// во время загрузки отменяет её (recAbort), чтобы не смешать списки по старым и новым оценкам
async function more(kind: 'recs' | 'fresh') {
  const signal = recAbort?.signal
  moreLoading.value = kind
  try {
    if (kind === 'recs') {
      const r = await api.recommend(payload.value, lang.value, recWeight.value, signal, STEP.recs, recs.value.length)
      recs.value = append(recs.value, r.items)
      recsMore.value = r.items.length === STEP.recs
    } else {
      const n = await api.newItems(payload.value, lang.value, signal, STEP.fresh, fresh.value.length)
      fresh.value = append(fresh.value, n.items)
      freshMore.value = n.items.length === STEP.fresh
    }
  } catch {
    // отменено новой оценкой или сеть – плашка сервера покажет причину
  } finally {
    moreLoading.value = null
  }
}

const moreClass =
  'mx-auto block rounded-xl border border-line px-5 py-2 text-sm transition hover:border-accent hover:text-accent disabled:opacity-50'

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
        <!-- готовые вкусы: советы в один клик -->
        <div class="max-w-xl space-y-2">
          <p class="text-sm text-muted">{{ t('persona.lead') }}</p>
          <div class="flex flex-wrap gap-2">
            <button
              v-for="p in PERSONAS"
              :key="p.key"
              type="button"
              class="flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-sm transition"
              :class="applied === p.key ? 'border-accent bg-accent-soft' : 'border-line bg-surface hover:border-accent hover:text-accent'"
              :aria-pressed="applied === p.key"
              @click="applyPersona(p)"
            >
              <component :is="PERSONA_ICON[p.key]" class="h-4 w-4 text-accent" /> {{ t(`persona.${p.key}`) }}
            </button>
          </div>
          <p v-if="linkState === 'loading'" class="text-sm text-muted">{{ t('persona.loadingLink') }}</p>
          <p v-else-if="linkState === 'failed'" class="text-sm text-muted">{{ t('persona.linkFailed') }}</p>
          <p v-if="applied" class="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm">
            <span class="text-muted">{{ appliedText }}</span>
            <button v-if="backup" type="button" class="flex items-center gap-1 text-accent hover:underline" @click="restoreOwn">
              <Undo2 class="h-4 w-4" /> {{ t('persona.restore') }}
            </button>
          </p>
        </div>
      </div>
      <CompassRose :ratings="ratings" />
    </section>

    <!-- ваши оценки -->
    <section v-if="ratings.length" class="space-y-3">
      <div class="flex items-center justify-between">
        <h2 class="text-lg font-semibold">{{ t('rate.yours') }}</h2>
        <div class="flex items-center gap-4">
          <button type="button" class="flex items-center gap-1 text-sm text-accent hover:underline" @click="shareOpen = true">
            <Share2 class="h-4 w-4" /> {{ t('share.button') }}
          </button>
          <button type="button" class="flex items-center gap-1 text-sm text-muted hover:text-ink" @click="clear">
            <Trash2 class="h-4 w-4" /> {{ t('rate.clear') }}
          </button>
        </div>
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
    <section id="recs" class="scroll-mt-24 space-y-5">
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
      <RecsInsight
        v-if="ratings.length && recState !== 'error' && recs.length && influence.length"
        :influence="influence"
        :recs="recs"
        :weight="recWeight"
        :basis="influenceBasis"
      />
      <p v-if="!ratings.length" class="rounded-xl border border-dashed border-line p-6 text-center text-muted">{{ t('rec.empty') }}</p>
      <p v-else-if="recState === 'error'" class="flex items-center gap-3 text-muted">
        {{ t('rec.error') }}
        <button type="button" class="rounded-lg bg-accent px-3 py-1 text-sm text-accent-ink" @click="loadRecs">{{ t('rec.retry') }}</button>
      </p>
      <div v-else class="grid grid-cols-2 gap-4 transition-opacity sm:grid-cols-3 lg:grid-cols-6" :class="{ 'opacity-60': recState === 'loading' }">
        <FilmCard v-for="f in recs" :key="f.id" :film="f" show-because @why="why = { film: $event, kind: 'taste' }" />
      </div>
      <button v-if="ratings.length && recState !== 'error' && recsMore" type="button" :class="moreClass" :disabled="recState === 'loading' || moreLoading === 'recs'" @click="more('recs')">
        {{ t('common.more') }}
      </button>
    </section>

    <!-- новинки -->
    <section v-if="fresh.length" class="space-y-4">
      <div>
        <h2 class="flex items-center gap-2 text-2xl font-semibold">{{ t('rec.newTitle') }} <HintTip :text="t('hint.fresh')" /></h2>
      </div>
      <div class="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
        <FilmCard v-for="f in fresh" :key="f.id" :film="f" show-because because-kind="plot" @why="why = { film: $event, kind: 'plot' }" />
      </div>
      <button v-if="freshMore" type="button" :class="moreClass" :disabled="recState === 'loading' || moreLoading === 'fresh'" @click="more('fresh')">
        {{ t('common.more') }}
      </button>
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
      <button v-if="poolMore" type="button" :class="moreClass" :disabled="poolLoading" @click="loadPool(true)">
        {{ t('common.more') }}
      </button>
    </section>

    <WhyDialog :film="why?.film ?? null" :kind="why?.kind ?? 'taste'" :weight="recWeight" @close="why = null" />
    <ShareDialog :open="shareOpen" @close="shareOpen = false" />
  </div>
</template>
