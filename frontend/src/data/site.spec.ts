import ru from '../locales/ru'
import site from './site.json'

// site.json собирает model/site_data.py из отчётов; страница утверждает то, что здесь проверяется
describe('цифры для страниц из отчётов', () => {
  it('все модели с цифрами валидации, теста и трёх сценариев, у каждой – подпись', () => {
    expect(site.models).toHaveLength(10)
    for (const m of site.models) {
      expect(m.validation).toBeGreaterThan(0)
      expect(m.test).toBeGreaterThan(0)
      expect(Object.keys(m.scenarios)).toEqual(['cold5', 'cold10', 'warm'])
      expect(ru.models).toHaveProperty(m.key)
    }
  })

  it('модель сайта – лучшая на тесте (так написано на странице «Сравнение моделей»)', () => {
    const best = [...site.models].sort((a, b) => b.test - a.test)[0]
    expect(best.key).toBe(site.site_model)
  })

  it('новинки: на тесте контент обошёл смесь, на валидации – наоборот (честный блок на странице)', () => {
    expect(site.new_items.test.content_text).toBeGreaterThan(site.new_items.test.hybrid_new)
    expect(site.new_items.validation.hybrid_new).toBeGreaterThan(site.new_items.validation.content_text)
  })
})
