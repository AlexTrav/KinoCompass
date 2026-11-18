<script setup lang="ts">
import { Menu, Moon, Sun, X } from 'lucide-vue-next'
import { ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute } from 'vue-router'
import { useLocale } from '../composables/useLocale'
import { useTheme } from '../composables/useTheme'
import LogoMark from './LogoMark.vue'

const { t } = useI18n()
const { locale, locales } = useLocale()
const { theme, toggleTheme } = useTheme()
const route = useRoute()
const open = ref(false)
watch(() => route.fullPath, () => (open.value = false))

const LINKS = ['pick', 'compare', 'map', 'research', 'perf', 'about'] as const
</script>

<template>
  <header class="sticky top-0 z-30 border-b border-line bg-bg/85 backdrop-blur">
    <!-- меню целиком – только от 1280 px (шесть пунктов на трёх языках в строку не помещаются уже); ниже – «☰» -->
    <nav class="mx-auto flex max-w-7xl items-center gap-3 px-4 py-3 sm:px-6">
      <RouterLink to="/" class="flex shrink-0 items-center gap-2 font-semibold tracking-tight">
        <LogoMark class="h-7 w-7" />
        <span>Kino<span class="text-accent">Compass</span></span>
      </RouterLink>

      <ul class="ml-4 hidden items-center gap-0.5 xl:flex">
        <li v-for="name in LINKS" :key="name">
          <RouterLink
            :to="{ name }"
            class="whitespace-nowrap rounded-lg px-2.5 py-1.5 text-sm text-muted transition hover:bg-surface-2 hover:text-ink"
            active-class="!text-ink bg-surface-2"
            exact-active-class="!text-ink bg-surface-2"
          >
            {{ t(`nav.${name}`) }}
          </RouterLink>
        </li>
      </ul>

      <div class="ml-auto flex shrink-0 items-center gap-1">
        <div class="flex rounded-lg border border-line p-0.5 text-xs" role="group" :aria-label="t('nav.language')">
          <button
            v-for="l in locales"
            :key="l.code"
            type="button"
            class="rounded-md px-2 py-1 transition"
            :class="locale === l.code ? 'bg-accent text-accent-ink' : 'text-muted hover:text-ink'"
            :aria-pressed="locale === l.code"
            @click="locale = l.code"
          >
            {{ l.label }}
          </button>
        </div>
        <button
          type="button"
          class="rounded-lg p-2 text-muted transition hover:bg-surface-2 hover:text-ink"
          :aria-label="t('nav.theme')"
          :title="t('nav.theme')"
          @click="toggleTheme($event)"
        >
          <Sun v-if="theme === 'dark'" class="h-5 w-5" />
          <Moon v-else class="h-5 w-5" />
        </button>
        <button
          type="button"
          class="rounded-lg p-2 text-muted hover:bg-surface-2 xl:hidden"
          :aria-label="t('nav.menu')"
          :aria-expanded="open"
          @click="open = !open"
        >
          <X v-if="open" class="h-5 w-5" />
          <Menu v-else class="h-5 w-5" />
        </button>
      </div>
    </nav>
    <ul v-if="open" class="border-t border-line px-4 py-2 xl:hidden">
      <li v-for="name in LINKS" :key="name">
        <RouterLink :to="{ name }" class="block rounded-lg px-3 py-2.5 text-muted" active-class="!text-ink bg-surface-2">
          {{ t(`nav.${name}`) }}
        </RouterLink>
      </li>
    </ul>
  </header>
</template>
