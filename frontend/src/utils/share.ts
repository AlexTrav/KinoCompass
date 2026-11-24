// ссылка «Поделиться»: оценки живут внутри адреса, сервер их не хранит. Формат – «id-полузвёзды» через точку:
// ?r=2571-10.318-9 (10 полузвёзд = 5 звёзд). Дефис и точка в адресе не кодируются – ссылка короткая, QR-код простой
export interface Score {
  id: number
  rating: number
}

export const SHARE_PARAM = 'r'
export const SHARE_MAX = 100 // больше оценок в ссылке не берём: адрес и QR-код становятся слишком длинными

export function encodeRatings(ratings: Score[]): string {
  return ratings
    .slice(0, SHARE_MAX)
    .map(({ id, rating }) => `${id}-${Math.round(rating * 2)}`)
    .join('.')
}

/** Оценки из адреса: неверные части пропускаются, у повторённого фильма – последняя оценка. */
export function decodeRatings(text: string): Score[] {
  const out = new Map<number, number>()
  for (const part of text.split('.')) {
    const match = /^(\d{1,7})-(\d{1,2})$/.exec(part.trim())
    if (!match) continue
    const id = Number(match[1])
    const half = Number(match[2])
    if (id > 0 && half >= 1 && half <= 10) out.set(id, half / 2)
    if (out.size >= SHARE_MAX) break
  }
  return [...out].map(([id, rating]) => ({ id, rating }))
}

/** Полный адрес главной страницы с оценками: base – адрес сайта (origin + базовый путь). */
export function shareUrl(base: string, ratings: Score[]): string {
  return `${base.replace(/\/?$/, '/')}?${SHARE_PARAM}=${encodeRatings(ratings)}`
}
