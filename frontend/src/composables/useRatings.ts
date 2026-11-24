import { computed, ref, watch } from 'vue'
import type { Film, Rated } from '../types'

// оценки – только в браузере человека (базы у проекта нет): переживают перезагрузку, на сервер уходят лишь
// id и оценки при каждом запросе советов
export const STORAGE_KEY = 'kinocompass-ratings'
export const ENOUGH = 5 // столько оценок советуем поставить: на них модель проверялась («новичок с 5 оценками»)

function load(): Rated[] {
  try {
    const raw = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? '[]')
    return Array.isArray(raw)
      ? raw.filter((r) => typeof r?.id === 'number' && typeof r?.rating === 'number' && r.rating >= 0.5 && r.rating <= 5)
      : []
  } catch {
    return []
  }
}

const ratings = ref<Rated[]>(load())
// свои оценки, когда их заменили готовым профилем или оценками из ссылки, – для кнопки «Вернуть мои оценки»;
// только в памяти вкладки: после перезагрузки остаётся то, что на экране
const backup = ref<Rated[] | null>(null)

watch(
  ratings,
  (value) => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(value))
    } catch {
      // приватный режим – оценки живут до закрытия вкладки
    }
  },
  { deep: true },
)

export function useRatings() {
  const byId = computed(() => new Map(ratings.value.map((r) => [r.id, r.rating])))
  const payload = computed(() => ratings.value.map(({ id, rating }) => ({ id, rating })))

  function rate(film: Pick<Film, 'id' | 'title' | 'poster' | 'genres' | 'year'>, rating: number) {
    const rest = ratings.value.filter((r) => r.id !== film.id)
    const { id, title, poster, genres, year } = film
    ratings.value = [...rest, { id, title, poster, genres, year, rating }]
  }

  function remove(id: number) {
    ratings.value = ratings.value.filter((r) => r.id !== id)
  }

  function clear() {
    ratings.value = []
  }

  /** Заменить все оценки (готовый профиль, ссылка); свои уходят в резервную копию, если её ещё нет – так после
   * двух профилей подряд «Вернуть» отдаёт именно свои оценки, а не первый профиль. */
  function replace(list: Rated[]) {
    if (backup.value === null && ratings.value.length) backup.value = ratings.value
    ratings.value = list
  }

  function restore() {
    if (backup.value === null) return
    ratings.value = backup.value
    backup.value = null
  }

  return { ratings, byId, payload, backup, rate, remove, clear, replace, restore }
}
