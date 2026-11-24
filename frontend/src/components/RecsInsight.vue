<script setup lang="ts">
import { ChevronDown, Film as FilmIcon, Info, Lightbulb } from 'lucide-vue-next'
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRatings } from '../composables/useRatings'
import type { AppLocale, Because, Film } from '../types'
import { needle } from '../utils/compass'
import { directionCounts, splitInfluence } from '../utils/explain'
import { formatPercent, posterUrl } from '../utils/format'

// панель «Почему такие советы» – разбор всей подборки: вклад ваших фильмов (influence – точное разложение балла
// ALS по всем показанным советам, считает сервер), доля популярности (ползунок), стороны компаса у советов и
// честная оговорка: ALS учитывает сам факт оценки, а не число звёзд (так модель обучалась и проверялась)
// basis – по скольким первым советам посчитан influence (страницы «Показать ещё» его не меняют)
const props = defineProps<{ influence: Because[]; recs: Film[]; weight: number; basis: number }>()
const SHOWN = 6

const { t, locale } = useI18n()
const lang = computed(() => locale.value as AppLocale)
const { ratings } = useRatings()
const pct = (x: number) => formatPercent(x, lang.value)
const dir = (d: string) => t(`dir.${d}`).replace('\n', ' ')

const rated = computed(() => new Map(ratings.value.map((r) => [r.id, r])))
const split = computed(() => splitInfluence(props.influence))
const top = computed(() => split.value.strong[0])
const widest = computed(() => top.value?.share || 1) // полоса самого влиятельного фильма – во всю ширину
const genres = computed(() => directionCounts(props.recs).slice(0, 3))
const compass = computed(() => needle(ratings.value).top)
// «советы согласны с компасом» – только если его сторона в советах самая частая или хотя бы у четверти советов
const compassInRecs = computed(() =>
  genres.value.some(([d, n]) => d === compass.value && (n === genres.value[0][1] || n >= props.recs.length / 4)),
)
// низко оценённый фильм, который всё равно заметно влияет, – пример к оговорке про звёзды
const low = computed(() => split.value.strong.map((f) => ({ f, r: rated.value.get(f.id) })).find(({ r }) => r && r.rating <= 2.5))
</script>

<template>
  <details class="group rounded-2xl border border-line bg-surface">
    <summary class="flex cursor-pointer list-none items-center gap-3 p-4 [&::-webkit-details-marker]:hidden">
      <Lightbulb class="h-5 w-5 shrink-0 text-accent" />
      <span class="min-w-0 flex-1">
        <span class="block font-semibold">{{ t('insight.title') }}</span>
        <span v-if="top" class="block truncate text-sm text-muted">{{ t('insight.teaser', { title: top.title, share: pct(top.share) }) }}</span>
      </span>
      <ChevronDown class="h-5 w-5 shrink-0 text-muted transition group-open:rotate-180" />
    </summary>

    <!-- grid-cols-1 – колонка minmax(0, 1fr): длинное название в одну строку не растягивает панель шире экрана -->
    <div class="grid grid-cols-1 gap-6 border-t border-line p-4 sm:p-5 lg:grid-cols-2">
      <!-- вклад ваших фильмов во всю подборку -->
      <section class="space-y-3">
        <h3 class="text-sm font-semibold">{{ t('insight.strong') }}</h3>
        <ul class="space-y-2.5">
          <li v-for="f in split.strong.slice(0, SHOWN)" :key="f.id" class="flex items-center gap-3">
            <img v-if="rated.get(f.id)?.poster" :src="posterUrl(rated.get(f.id)!.poster, 'w185') ?? ''" alt="" class="h-10 w-7 shrink-0 rounded object-cover" />
            <div v-else class="flex h-10 w-7 shrink-0 items-center justify-center rounded bg-surface-2 text-muted"><FilmIcon class="h-3.5 w-3.5" /></div>
            <div class="min-w-0 flex-1 space-y-1">
              <div class="flex items-baseline justify-between gap-2 text-sm">
                <RouterLink :to="{ name: 'film', params: { id: f.id } }" class="min-w-0 truncate hover:text-accent">{{ f.title }}</RouterLink>
                <span class="tabular shrink-0 font-semibold">{{ pct(f.share) }}</span>
              </div>
              <div class="h-1.5 rounded-full bg-surface-2">
                <div class="h-full rounded-full bg-accent" :style="{ width: `${(f.share / widest) * 100}%` }" />
              </div>
            </div>
            <span v-if="rated.get(f.id)" class="tabular w-10 shrink-0 text-right text-xs text-muted">★ {{ rated.get(f.id)!.rating.toLocaleString(lang) }}</span>
          </li>
        </ul>
        <p v-if="split.strong.length > SHOWN" class="text-xs text-muted">{{ t('insight.moreFilms', { n: split.strong.length - SHOWN }) }}</p>
        <p class="text-xs text-muted">{{ t('insight.strongHint', { n: basis }) }}</p>
        <p v-if="split.weak.length" class="text-sm text-muted">
          <span class="text-ink">{{ t('insight.weak') }}:</span> {{ split.weak.map((f) => `«${f.title}»`).join(', ') }}. {{ t('insight.weakText') }}
        </p>
      </section>

      <div class="space-y-5">
        <!-- популярность и вкус -->
        <section class="space-y-2">
          <h3 class="text-sm font-semibold">{{ t('insight.mix') }}</h3>
          <div class="flex h-3 gap-0.5" aria-hidden="true">
            <div v-if="weight > 0" class="rounded-l-full bg-muted/40" :style="{ width: `${weight * 100}%` }" />
            <div class="bg-accent" :class="weight > 0 ? 'rounded-r-full' : 'rounded-full'" :style="{ width: `${(1 - weight) * 100}%` }" />
          </div>
          <p class="text-sm text-muted">{{ t('insight.mixText', { pop: pct(weight), taste: pct(1 - weight) }) }}</p>
        </section>

        <!-- стороны компаса у советов -->
        <section v-if="genres.length" class="space-y-2">
          <h3 class="text-sm font-semibold">{{ t('insight.genres') }}</h3>
          <ul class="flex flex-wrap gap-2">
            <li v-for="[d, n] in genres" :key="d" class="tabular rounded-full border border-line px-2.5 py-0.5 text-xs">
              {{ t('insight.genreItem', { dir: dir(d), n, total: recs.length }) }}
            </li>
          </ul>
          <p v-if="compass" class="text-sm text-muted">
            {{ compassInRecs ? t('insight.compassMatch', { dir: dir(compass) }) : t('insight.compassOther', { dir: dir(compass) }) }}
          </p>
        </section>

        <!-- честно: звёзды и модель ALS -->
        <section class="flex gap-2 rounded-xl bg-surface-2 p-3 text-xs leading-relaxed text-muted">
          <Info class="mt-0.5 h-4 w-4 shrink-0" />
          <p>
            {{ t('insight.stars') }}
            <span v-if="low" class="text-ink">{{ t('insight.starsExample', { title: low.f.title, n: low.r!.rating.toLocaleString(lang) }) }}</span>
          </p>
        </section>
      </div>
    </div>
  </details>
</template>
