// слепой тест на странице «Сравнение моделей»: те же четыре списка советов без названий и в случайном порядке;
// счёт выборов – только в браузере человека
export const BLIND_KEY = 'kinocompass-blind'

export interface Tally {
  tries: number
  site: number // сколько раз выбран список модели сайта
}

/** Перемешивание Фишера – Йетса: каждый порядок равновероятен; random – для проверки в тестах. */
export function shuffle<T>(items: readonly T[], random: () => number = Math.random): T[] {
  const out = [...items]
  for (let i = out.length - 1; i > 0; i--) {
    const j = Math.floor(random() * (i + 1))
    ;[out[i], out[j]] = [out[j], out[i]]
  }
  return out
}

export function loadTally(): Tally {
  try {
    const raw = JSON.parse(localStorage.getItem(BLIND_KEY) ?? 'null')
    if (Number.isInteger(raw?.tries) && Number.isInteger(raw?.site) && raw.site <= raw.tries) return raw
  } catch {
    // приватный режим или испорченная запись – счёт с нуля
  }
  return { tries: 0, site: 0 }
}

export function saveTally(tally: Tally) {
  try {
    localStorage.setItem(BLIND_KEY, JSON.stringify(tally))
  } catch {
    // приватный режим – счёт живёт до закрытия вкладки
  }
}
