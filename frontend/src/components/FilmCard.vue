<script setup lang="ts">
import { Film as FilmIcon } from 'lucide-vue-next'
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRatings } from '../composables/useRatings'
import type { AppLocale, Film } from '../types'
import { formatPercent, posterUrl } from '../utils/format'
import StarRating from './StarRating.vue'

// карточка фильма: постер, название, год; rateable – звёзды под постером; because – «потому что понравились»
const props = withDefaults(defineProps<{ film: Film; rateable?: boolean; showBecause?: boolean }>(), {
  rateable: true,
  showBecause: false,
})
const { t, locale } = useI18n()
const { byId, rate, remove } = useRatings()
const rating = computed({
  get: () => byId.value.get(props.film.id) ?? 0,
  set: (value: number) => (value ? rate(props.film, value) : remove(props.film.id)),
})
const poster = computed(() => posterUrl(props.film.poster))
</script>

<template>
  <article class="group flex flex-col gap-2">
    <RouterLink
      :to="{ name: 'film', params: { id: film.id } }"
      class="relative block aspect-[2/3] overflow-hidden rounded-xl border border-line bg-surface-2 shadow-sm transition group-hover:-translate-y-0.5 group-hover:shadow-[0_8px_30px_var(--glow)]"
    >
      <img
        v-if="poster"
        :src="poster"
        :alt="film.title"
        loading="lazy"
        decoding="async"
        class="h-full w-full object-cover"
      />
      <div v-else class="flex h-full w-full flex-col items-center justify-center gap-2 p-3 text-center text-muted">
        <FilmIcon class="h-8 w-8" />
        <span class="text-sm">{{ film.title }}</span>
      </div>
      <span
        v-if="rating"
        class="tabular absolute right-2 top-2 rounded-md bg-accent px-1.5 py-0.5 text-xs font-semibold text-accent-ink"
      >
        ★ {{ rating.toLocaleString(locale) }}
      </span>
      <span
        v-if="film.by"
        class="absolute left-2 top-2 rounded-md bg-bg/80 px-1.5 py-0.5 text-[11px] text-muted backdrop-blur"
      >
        {{ film.by === 'title' ? t('rate.byTitle') : t('rate.byMeaning') }}
      </span>
    </RouterLink>
    <div class="min-w-0">
      <RouterLink :to="{ name: 'film', params: { id: film.id } }" class="line-clamp-2 text-sm font-medium leading-snug hover:text-accent">
        {{ film.title }}
      </RouterLink>
      <p class="text-xs text-muted">{{ film.year ?? '' }}</p>
    </div>
    <StarRating v-if="rateable" v-model="rating" :size="18" />
    <p v-if="showBecause && film.because" class="text-xs leading-snug text-muted">
      <template v-if="film.because.length">
        {{ t('rec.because') }}:
        <span v-for="(b, i) in film.because.slice(0, 2)" :key="b.id">
          <span class="text-ink">{{ b.title }}</span>
          <span class="tabular"> ({{ formatPercent(b.share, locale as AppLocale) }})</span><span v-if="i < Math.min(film.because.length, 2) - 1">, </span>
        </span>
      </template>
      <template v-else>{{ t('rec.popularOnly') }}</template>
    </p>
  </article>
</template>
