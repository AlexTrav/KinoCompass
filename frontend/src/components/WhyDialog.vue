<script setup lang="ts">
import { Film as FilmIcon, X } from 'lucide-vue-next'
import { computed, nextTick, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRatings } from '../composables/useRatings'
import type { AppLocale, Film } from '../types'
import { restShare } from '../utils/explain'
import { formatPercent, posterUrl } from '../utils/format'

// окно «Почему этот фильм»: из чего сложился балл. Совет (kind = taste) – доли популярности (ползунок «Новизна»)
// и вкуса, а вкус – вклады оценённых фильмов (точное разложение балла ALS на сервере). Новинка (kind = plot) –
// вклады оценённых фильмов в балл контентной модели (сходство описаний)
const props = defineProps<{ film: Film | null; kind: 'taste' | 'plot'; weight: number }>()
const emit = defineEmits<{ close: [] }>()
const { t, locale } = useI18n()
const lang = computed(() => locale.value as AppLocale)
const { ratings } = useRatings()
const dialog = ref<HTMLDialogElement | null>(null)

watch(
  () => props.film,
  async (film) => {
    await nextTick()
    if (film && !dialog.value?.open) dialog.value?.showModal()
    else if (!film && dialog.value?.open) dialog.value.close()
  },
)

const pct = (x: number) => formatPercent(x, lang.value)
const rated = computed(() => new Map(ratings.value.map((r) => [r.id, r])))
const because = computed(() => props.film?.because ?? [])
const rest = computed(() => (because.value.length ? restShare(because.value) : 0))

function close() {
  dialog.value?.close()
}

// нажатие на затемнение вокруг окна закрывает его (у самого окна отступов нет – клик внутри попадает в содержимое)
function onClick(event: MouseEvent) {
  if (event.target === dialog.value) close()
}
</script>

<template>
  <dialog
    ref="dialog"
    class="m-auto max-h-[85vh] w-[min(34rem,calc(100vw-2rem))] overflow-y-auto rounded-2xl border border-line bg-surface p-0 text-ink shadow-[0_20px_60px_rgba(0,0,0,0.35)] backdrop:bg-black/60 backdrop:backdrop-blur-sm"
    :aria-label="film ? t('why.title', { title: film.title }) : undefined"
    @close="emit('close')"
    @click="onClick"
  >
    <div v-if="film" class="space-y-6 p-5 sm:p-6">
      <header class="flex items-start gap-4">
        <img v-if="film.poster" :src="posterUrl(film.poster, 'w185') ?? ''" alt="" class="h-24 w-16 shrink-0 rounded-lg object-cover" />
        <div class="min-w-0 flex-1">
          <h2 class="text-xl font-semibold leading-tight">{{ t('why.title', { title: film.title }) }}</h2>
          <p class="mt-1 text-sm text-muted">{{ kind === 'plot' ? t('why.plotLead') : t('why.tasteLead') }}</p>
        </div>
        <button type="button" class="shrink-0 rounded-lg p-1 text-muted hover:text-ink" :aria-label="t('why.close')" @click="close">
          <X class="h-5 w-5" />
        </button>
      </header>

      <!-- совет: какая доля балла – популярность за год, какая – ваш вкус -->
      <section v-if="kind === 'taste'" class="space-y-2">
        <h3 class="text-sm font-semibold">{{ t('why.mix') }}</h3>
        <div class="flex h-3 gap-0.5" aria-hidden="true">
          <div v-if="weight > 0" class="rounded-l-full bg-muted/40" :style="{ width: `${weight * 100}%` }" />
          <div class="bg-accent" :class="weight > 0 ? 'rounded-r-full' : 'rounded-full'" :style="{ width: `${(1 - weight) * 100}%` }" />
        </div>
        <div class="tabular flex justify-between gap-3 text-xs">
          <span class="text-muted">{{ t('why.popularity', { n: pct(weight) }) }}</span>
          <span class="font-medium">{{ t('why.taste', { n: pct(1 - weight) }) }}</span>
        </div>
        <p class="text-xs text-muted">{{ t('why.mixText') }}</p>
      </section>

      <!-- вклады ваших фильмов: в вкусовую часть балла (совет) или в сходство описаний (новинка) -->
      <section class="space-y-3">
        <h3 class="text-sm font-semibold">{{ kind === 'plot' ? t('why.fromPlot') : t('why.fromFilms') }}</h3>
        <p v-if="!because.length" class="text-sm text-muted">{{ kind === 'plot' ? t('why.noPlot') : t('why.noTaste') }}</p>
        <ul v-else class="space-y-3">
          <li v-for="b in because" :key="b.id" class="flex items-center gap-3">
            <img v-if="rated.get(b.id)?.poster" :src="posterUrl(rated.get(b.id)!.poster, 'w185') ?? ''" alt="" class="h-12 w-8 shrink-0 rounded object-cover" />
            <div v-else class="flex h-12 w-8 shrink-0 items-center justify-center rounded bg-surface-2 text-muted"><FilmIcon class="h-4 w-4" /></div>
            <div class="min-w-0 flex-1 space-y-1">
              <div class="flex items-baseline justify-between gap-2 text-sm">
                <RouterLink :to="{ name: 'film', params: { id: b.id } }" class="truncate hover:text-accent" @click="close">{{ b.title }}</RouterLink>
                <span class="tabular shrink-0 font-semibold">{{ pct(b.share) }}</span>
              </div>
              <div class="h-1.5 rounded-full bg-surface-2">
                <div class="h-full rounded-full bg-accent" :style="{ width: `${b.share * 100}%` }" />
              </div>
              <p v-if="rated.get(b.id)" class="tabular text-xs text-muted">
                {{ t('why.yourStars', { n: rated.get(b.id)!.rating.toLocaleString(lang) }) }}
              </p>
            </div>
          </li>
          <li v-if="rest" class="tabular flex justify-between pl-11 text-sm text-muted">
            <span>{{ t('why.others') }}</span><span>{{ pct(rest) }}</span>
          </li>
        </ul>
      </section>

      <section class="space-y-1.5 rounded-xl bg-surface-2 p-4 text-xs leading-relaxed text-muted">
        <h3 class="font-semibold text-ink">{{ t('why.how') }}</h3>
        <p>{{ kind === 'plot' ? t('why.howPlot') : t('why.howTaste') }}</p>
        <p class="font-mono text-[11px]">{{ kind === 'plot' ? t('why.formulaPlot') : t('why.formula') }}</p>
      </section>
    </div>
  </dialog>
</template>
