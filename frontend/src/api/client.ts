import type { AppLocale, Compare, FilmDetail, Health, Items, MapFilm, MapMe, NewItems, Perf, Rated, Recommend } from '../types'

// адрес API: в сборке – аргумент Docker (по умолчанию API на Render)
export const API_BASE = import.meta.env.VITE_API_BASE_URL ?? 'https://kinocompass-backend.onrender.com'

// бесплатный Render засыпает через 15 минут без запросов и просыпается до минуты и дольше – ждём с запасом,
// иначе запрос оборвётся раньше, чем сервер проснулся
const TIMEOUT_MS = 150_000
// нет ответа дольше этого – скорее всего, сервер просыпается: показываем плашку
const SLOW_AFTER_MS = 2500
// пока Render будит сервис, его прокси отвечает 502/503/504
const WAKING = new Set([502, 503, 504])

export class ApiError extends Error {
  code: string
  status: number

  constructor(code: string, status = 0) {
    super(code)
    this.name = 'ApiError'
    this.code = code
    this.status = status
  }
}

// каждый запрос сообщает состояние сервера: плашка «Сервер просыпается…» видна на любой странице
export type ServerSignal = 'slow' | 'ok' | 'fail'
let onSignal: (signal: ServerSignal) => void = () => {}
export function listenServer(listener: (signal: ServerSignal) => void) {
  onSignal = listener
}

export async function request<T>(path: string, body?: unknown, signal?: AbortSignal): Promise<T> {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS)
  const slow = setTimeout(() => onSignal('slow'), SLOW_AFTER_MS)
  signal?.addEventListener('abort', () => controller.abort())
  let res: Response
  try {
    res = await fetch(`${API_BASE}${path}`, {
      method: body === undefined ? 'GET' : 'POST',
      headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: controller.signal,
    })
  } catch (err) {
    if (signal?.aborted) throw new ApiError('aborted')
    onSignal('fail')
    throw new ApiError((err as Error).name === 'AbortError' ? 'timeout' : 'network')
  } finally {
    clearTimeout(timer)
    clearTimeout(slow)
  }
  if (WAKING.has(res.status)) {
    onSignal('fail')
    throw new ApiError('waking', res.status)
  }
  onSignal('ok') // сервер ответил – даже ошибкой 4xx, значит, не спит
  if (!res.ok) throw new ApiError(`http_${res.status}`, res.status)
  return res.json() as Promise<T>
}

type Ratings = { id: number; rating: number }[]
const q = (params: Record<string, string | number>) =>
  new URLSearchParams(Object.entries(params).map(([k, v]) => [k, String(v)])).toString()

export const api = {
  health: () => request<Health>('/api/health'),
  // offset – с какого места списка: кнопка «Показать ещё» догружает следующую страницу
  films: (query: string, lang: AppLocale, k = 24, signal?: AbortSignal, offset = 0) =>
    request<Items>(`/api/films?${q({ q: query, lang, k, offset })}`, undefined, signal),
  search: (query: string, lang: AppLocale, k = 24, signal?: AbortSignal, offset = 0) =>
    request<Items>(`/api/search?${q({ q: query, lang, k, offset })}`, undefined, signal),
  recommend: (ratings: Ratings, lang: AppLocale, popularityWeight: number, signal?: AbortSignal, k = 12, offset = 0) =>
    request<Recommend>('/api/recommend', { ratings, lang, popularity_weight: popularityWeight, k, offset }, signal),
  newItems: (ratings: Ratings, lang: AppLocale, signal?: AbortSignal, k = 12, offset = 0) =>
    request<NewItems>('/api/new', { ratings, lang, k, offset }, signal),
  // k – сколько похожих фильмов: для карточек оценок из ссылки «Поделиться» хватает одного
  film: (id: number, lang: AppLocale, k = 12) => request<FilmDetail>(`/api/film/${id}?${q({ lang, k })}`),
  compare: (ratings: Ratings, lang: AppLocale) => request<Compare>('/api/compare', { ratings, lang, k: 10 }),
  map: (lang: AppLocale) => request<{ films: MapFilm[] }>(`/api/map?${q({ lang })}`),
  mapMe: (ratings: Ratings) => request<MapMe>('/api/map/me', { ratings }),
  perf: () => request<Perf>('/api/perf'),
}

/** Оценки из ссылки «Поделиться» с названием, постером и жанрами – как поставленные вручную. Карточки грузятся
 * по 4 одновременно (столько расчётов держит сервер); фильмы, которых нет в каталоге, пропускаются. */
export async function ratedCards(scores: Ratings, lang: AppLocale): Promise<Rated[]> {
  const out: (Rated | null)[] = scores.map(() => null)
  let next = 0
  async function worker() {
    while (next < scores.length) {
      const i = next++
      const { id, rating } = scores[i]
      try {
        const f = await api.film(id, lang, 1)
        out[i] = { id, rating, title: f.title, poster: f.poster, genres: f.genres, year: f.year }
      } catch {
        // фильма нет в каталоге или сеть – без него
      }
    }
  }
  await Promise.all(Array.from({ length: Math.min(4, scores.length) }, worker))
  return out.filter((r): r is Rated => r !== null)
}
