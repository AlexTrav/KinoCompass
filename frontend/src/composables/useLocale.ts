import { computed } from 'vue'
import { i18n, LOCALE_STORAGE_KEY, SUPPORTED_LOCALES } from '../i18n'
import type { AppLocale } from '../types'

// обёртка над locale из vue-i18n: сохраняет выбор в localStorage и обновляет <html lang>
export function useLocale() {
  const locale = computed<AppLocale>({
    get: () => i18n.global.locale.value as AppLocale,
    set: (value) => {
      i18n.global.locale.value = value
      document.documentElement.lang = value
      try {
        localStorage.setItem(LOCALE_STORAGE_KEY, value)
      } catch {
        // не критично – язык просто не запомнится между визитами
      }
    },
  })
  return { locale, locales: SUPPORTED_LOCALES }
}
