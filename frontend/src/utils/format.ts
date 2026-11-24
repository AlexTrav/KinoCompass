import type { AppLocale } from '../types'

// постеры – с серверов TMDb (подпись TMDb – в подвале и на странице «О проекте»)
export function posterUrl(path: string | null, width: 'w185' | 'w342' | 'w500' = 'w342'): string | null {
  return path ? `https://image.tmdb.org/t/p/${width}${path}` : null
}

const TAGS: Record<AppLocale, string> = { ru: 'ru-RU', kk: 'kk-KZ', en: 'en-US' }

// числа – по правилам языка: в русском и казахском десятичная запятая и пробел между разрядами
export function formatNumber(value: number, locale: AppLocale, digits = 0): string {
  return new Intl.NumberFormat(TAGS[locale], { minimumFractionDigits: digits, maximumFractionDigits: digits }).format(value)
}

// digits – знаков после запятой: покрытию каталога популярной модели (0,07 %) нужны сотые
export function formatPercent(share: number, locale: AppLocale, digits = 0): string {
  return new Intl.NumberFormat(TAGS[locale], { style: 'percent', maximumFractionDigits: digits }).format(share)
}

// вид слова по числу (1 оценка, 2 оценки, 5 оценок) – Intl.PluralRules знает правила всех трёх языков
export function pluralKey(count: number, locale: AppLocale): Intl.LDMLPluralRule {
  return new Intl.PluralRules(TAGS[locale]).select(count)
}
