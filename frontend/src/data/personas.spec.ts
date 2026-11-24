import ru from '../locales/ru'
import { needle } from '../utils/compass'
import { PERSONAS, personaRatings } from '../utils/personas'

// готовые вкусы (personas.json, из API): данные полные, и каждый профиль действительно про свой жанр
describe('готовые вкусы', () => {
  it('четыре профиля по 7 фильмов: оценки в полузвёздах, названия на трёх языках, постеры', () => {
    expect(PERSONAS.map((p) => p.key)).toEqual(['scifi', 'animation', 'classic', 'horror'])
    for (const p of PERSONAS) {
      expect(ru.persona).toHaveProperty(p.key)
      expect(p.films).toHaveLength(7)
      expect(new Set(p.films.map((f) => f.id)).size).toBe(7)
      for (const f of p.films) {
        expect(f.rating * 2).toBe(Math.round(f.rating * 2))
        expect(f.rating).toBeGreaterThanOrEqual(3.5)
        expect(f.rating).toBeLessThanOrEqual(5)
        expect(f.titles.ru && f.titles.kk && f.titles.en).toBeTruthy()
        expect(f.poster).toBeTruthy()
      }
    }
  })

  it('компас вкуса каждого профиля указывает на его жанр', () => {
    const expected = { scifi: 'scifi', animation: 'animation', classic: 'drama', horror: 'horror' }
    for (const p of PERSONAS) expect(needle(personaRatings(p, 'ru')).top).toBe(expected[p.key])
  })

  it('названия – на языке сайта', () => {
    const scifi = PERSONAS[0]
    expect(personaRatings(scifi, 'en')[0]).toMatchObject({ id: 2571, rating: 5, title: 'The Matrix' })
    expect(personaRatings(scifi, 'ru')[0].title).toBe('Матрица')
  })
})
