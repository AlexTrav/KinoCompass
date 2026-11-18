// ответы API KinoCompass (backend/app/main.py)
export type AppLocale = 'ru' | 'kk' | 'en'

export interface Because {
  id: number
  title: string
  share: number
}

export interface Film {
  id: number
  title: string
  original_title: string
  year: number | null
  genres: string[]
  poster: string | null
  mean_rating: number
  n_ratings: number
  score?: number
  because?: Because[]
  by?: 'title' | 'meaning'
}

export interface FilmDetail extends Film {
  titles: Record<AppLocale, string>
  overview: string | null
  imdb_id: string | null
  tmdb_id: number | null
  similar: Film[]
}

// оценка человека – хранится только в его браузере (useRatings), вместе с тем, что нужно показать без запроса
export interface Rated {
  id: number
  rating: number
  title: string
  poster: string | null
  genres: string[]
  year: number | null
}

export interface Items {
  items: Film[]
}

export interface Recommend extends Items {
  popularity_weight: number
  tested_weight: number
  unknown: number[]
}

export interface NewItems extends Items {
  rule: string
  unknown: number[]
}

export type ModelKey = 'popular' | 'als' | 'content' | 'hybrid'

export interface Compare {
  models: Record<ModelKey, { items: Film[]; ms: number }>
  unknown: number[]
}

export interface MapFilm {
  id: number
  x: number
  y: number
  title: string
  genres?: string[]
  genre?: string // прежний формат API (один первый жанр) – пока Render не обновился, сайт не должен падать
}

export interface MapMe {
  x: number | null
  y: number | null
  used: number
}

export interface Perf {
  endpoints: Record<string, { count: number; p50_ms: number; p95_ms: number }>
  memory_mb: { now?: number; peak?: number }
  load_seconds: number
  uptime_seconds: number
  limit_mb: number
}

export interface Health {
  status: string
  data_until: string
  catalog: number
  new_items: number
  map_films: number
}
