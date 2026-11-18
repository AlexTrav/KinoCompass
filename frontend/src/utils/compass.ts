import type { Rated } from '../types'

// роза жанров: 8 сторон, каждая – группа жанров MovieLens с точным названием («Боевики и приключения»,
// «Фантастика и фэнтези», …); IMAX и «(no genres listed)» – без стороны
export const DIRECTIONS = ['action', 'scifi', 'animation', 'comedy', 'romance', 'drama', 'thriller', 'horror'] as const
export type Direction = (typeof DIRECTIONS)[number]

const GROUP: Record<string, Direction> = {
  Action: 'action', Adventure: 'action', War: 'action', Western: 'action',
  'Sci-Fi': 'scifi', Fantasy: 'scifi',
  Animation: 'animation', Children: 'animation', Musical: 'animation',
  Comedy: 'comedy',
  Romance: 'romance',
  Drama: 'drama', Documentary: 'drama',
  Thriller: 'thriller', Crime: 'thriller', Mystery: 'thriller', 'Film-Noir': 'thriller',
  Horror: 'horror',
}

// доля фильмов каталога сайта (23 349) с группой – посчитано по catalog.json.gz 19.11.2026; драма есть у
// каждого второго фильма и о вкусе почти ничего не говорит, ужасы – у каждого девятого и говорят много
export const SHARE: Record<Direction, number> = {
  drama: 0.523, comedy: 0.324, thriller: 0.261, action: 0.24,
  romance: 0.141, scifi: 0.136, animation: 0.116, horror: 0.112,
}

// угол стороны: север – 0°, по часовой стрелке через 45°
export const angleOf = (d: Direction) => DIRECTIONS.indexOf(d) * 45

export function directionsOf(genres: string[]): Direction[] {
  return [...new Set(genres.map((g) => GROUP[g]).filter((d): d is Direction => d !== undefined))]
}

/** Самая характерная сторона фильма – самая редкая из его групп: «Матрица» (боевик, фантастика, триллер) –
 * фантастика, «История игрушек» – мультфильмы; без групп – null. Ею красится точка на карте вкусов. */
export function mainDirection(genres: string[]): Direction | null {
  const dirs = directionsOf(genres)
  return dirs.length ? dirs.reduce((a, b) => (SHARE[b] < SHARE[a] ? b : a)) : null
}

export interface Needle {
  angle: number // градусы, 0 – север
  strength: number // 0..1: доля самой сильной стороны среди положительных
  top: Direction | null
  weights: Partial<Record<Direction, number>>
}

/** Стрелка компаса. Каждый оценённый фильм добавляет всем своим сторонам вес (оценка − 2,5) · log(1/доля):
 * понравилось – тянет, 1–2 звезды – отталкивает, а редкий жанр говорит о вкусе больше частого (как IDF в
 * поиске). Стрелка указывает ровно на самую сильную сторону – так она совпадает с подписью. */
export function needle(ratings: Pick<Rated, 'rating' | 'genres'>[]): Needle {
  const weights: Partial<Record<Direction, number>> = {}
  for (const r of ratings) {
    for (const d of directionsOf(r.genres)) {
      weights[d] = (weights[d] ?? 0) + (r.rating - 2.5) * Math.log(1 / SHARE[d])
    }
  }
  const positive = (Object.entries(weights) as [Direction, number][]).filter(([, w]) => w > 0).sort((a, b) => b[1] - a[1])
  if (!positive.length) return { angle: 0, strength: 0, top: null, weights }
  const total = positive.reduce((sum, [, w]) => sum + w, 0)
  const [top, w] = positive[0]
  return { angle: angleOf(top), strength: w / total, top, weights }
}
