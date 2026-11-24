import data from '../data/personas.json'
import type { AppLocale, Rated } from '../types'

// готовые вкусы: по 7 известных фильмов с оценками – чтобы увидеть советы в один клик (на защите не нужно ставить
// оценки при всех). Названия на трёх языках, постеры и жанры взяты из API 24.11.2026 (data/personas.json)
export type PersonaKey = 'scifi' | 'animation' | 'classic' | 'horror'

export interface Persona {
  key: PersonaKey
  films: {
    id: number
    rating: number
    titles: Record<AppLocale, string>
    poster: string | null
    genres: string[]
    year: number | null
  }[]
}

export const PERSONAS = data as Persona[]

/** Оценки профиля с названиями на языке сайта – в том же виде, что и поставленные вручную. */
export function personaRatings(persona: Persona, lang: AppLocale): Rated[] {
  return persona.films.map(({ id, rating, titles, poster, genres, year }) => ({
    id,
    rating,
    title: titles[lang],
    poster,
    genres,
    year,
  }))
}
