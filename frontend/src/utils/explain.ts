import type { Because, Film } from '../types'
import { DIRECTIONS, type Direction, mainDirection } from './compass'

// объяснения советов: доли вкладов приходят с сервера (точное разложение балла модели), здесь – только раскладка
// для панели «Почему такие советы» и окна «Почему этот фильм»

export const WEAK = 0.02 // доля вклада в подборку меньше 2 % – «почти не повлиял»

/** Вклад ваших фильмов во всю подборку: заметные (по убыванию, как пришли с сервера) и почти не повлиявшие. */
export function splitInfluence(influence: Because[], weak = WEAK): { strong: Because[]; weak: Because[] } {
  return { strong: influence.filter((f) => f.share >= weak), weak: influence.filter((f) => f.share < weak) }
}

/** Самые характерные стороны компаса у советов: сколько фильмов на каждой, по убыванию (равные – по кругу компаса).
 * У фильма одна сторона – самая редкая из его жанров (как цвет точки на карте), поэтому сумма – число фильмов. */
export function directionCounts(films: Pick<Film, 'genres'>[]): [Direction, number][] {
  const counts = new Map<Direction, number>()
  for (const f of films) {
    const d = mainDirection(f.genres)
    if (d) counts.set(d, (counts.get(d) ?? 0) + 1)
  }
  return [...counts].sort((a, b) => b[1] - a[1] || DIRECTIONS.indexOf(a[0]) - DIRECTIONS.indexOf(b[0]))
}

/** Доля остальных оценённых фильмов: сервер присылает три самых больших вклада в совет, вместе они дают 100 %. */
export function restShare(because: Because[]): number {
  const rest = 1 - because.reduce((sum, b) => sum + b.share, 0)
  return rest > 0.005 ? rest : 0 // доли округлены до 0,1 %: остаток меньше половины процента – это округление
}
