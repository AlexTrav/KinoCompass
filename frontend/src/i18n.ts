import { createI18n } from 'vue-i18n'
import en from './locales/en'
import kk from './locales/kk'
import ru from './locales/ru'
import type { AppLocale } from './types'

export const SUPPORTED_LOCALES: { code: AppLocale; label: string }[] = [
  { code: 'ru', label: 'RU' },
  { code: 'kk', label: 'ҚАЗ' },
  { code: 'en', label: 'EN' },
]

export const LOCALE_STORAGE_KEY = 'kinocompass-locale'

export function isAppLocale(value: string | null): value is AppLocale {
  return value === 'ru' || value === 'kk' || value === 'en'
}

// сначала – выбор из прошлого визита, иначе – язык браузера, иначе – русский
function detectInitialLocale(): AppLocale {
  try {
    const saved = localStorage.getItem(LOCALE_STORAGE_KEY)
    if (isAppLocale(saved)) return saved
  } catch {
    // localStorage недоступен (приватный режим)
  }
  const browser = navigator.language.slice(0, 2).toLowerCase()
  return isAppLocale(browser) ? browser : 'ru'
}

export const initialLocale = detectInitialLocale()

export const i18n = createI18n({
  legacy: false,
  locale: initialLocale,
  fallbackLocale: 'ru',
  messages: { ru, kk, en },
})
