import { nextTick } from 'vue'
import { STORAGE_KEY, useRatings } from './useRatings'

const film = (id: number) => ({ id, title: `Film ${id}`, poster: null, genres: ['Drama'], year: 2000 })

describe('оценки в браузере', () => {
  beforeEach(() => useRatings().clear())

  it('повторная оценка заменяет прежнюю, payload – только id и оценка', () => {
    const { rate, payload, byId } = useRatings()
    rate(film(1), 4)
    rate(film(2), 3.5)
    rate(film(1), 5)
    expect(payload.value).toEqual([
      { id: 2, rating: 3.5 },
      { id: 1, rating: 5 },
    ])
    expect(byId.value.get(1)).toBe(5)
  })

  it('сохраняются в localStorage и убираются', async () => {
    const { rate, remove, ratings } = useRatings()
    rate(film(7), 4.5)
    await nextTick()
    expect(JSON.parse(localStorage.getItem(STORAGE_KEY) ?? '[]')[0]).toMatchObject({ id: 7, rating: 4.5 })
    remove(7)
    expect(ratings.value).toEqual([])
  })
})
