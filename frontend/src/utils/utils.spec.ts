import { angleOf, directionsOf, mainDirection, needle } from './compass'
import { directionCounts, restShare, splitInfluence } from './explain'
import { formatNumber, formatPercent, posterUrl } from './format'

describe('объяснение советов', () => {
  const b = (id: number, share: number) => ({ id, title: `Фильм ${id}`, share })

  it('фильмы с долей меньше 2 % – «почти не повлияли», порядок с сервера сохраняется', () => {
    const { strong, weak } = splitInfluence([b(1, 0.6), b(2, 0.385), b(3, 0.015)])
    expect(strong.map((f) => f.id)).toEqual([1, 2])
    expect(weak.map((f) => f.id)).toEqual([3])
  })

  it('стороны компаса у советов – по самому характерному жанру фильма, чаще встречающиеся первыми', () => {
    const films = [
      { genres: ['Action', 'Sci-Fi', 'Thriller'] }, // фантастика
      { genres: ['Adventure', 'Fantasy'] }, // фантастика
      { genres: ['Crime', 'Drama'] }, // триллер
      { genres: ['IMAX'] }, // без стороны – не считается
    ]
    expect(directionCounts(films)).toEqual([['scifi', 2], ['thriller', 1]])
  })

  it('остаток «остальные ваши фильмы» – только если три самых больших вклада не дают 100 %', () => {
    expect(restShare([b(1, 0.5), b(2, 0.3), b(3, 0.1)])).toBeCloseTo(0.1)
    expect(restShare([b(1, 0.667), b(2, 0.333)])).toBe(0)
    expect(restShare([])).toBe(1)
  })
})

describe('компас вкуса', () => {
  it('жанры MovieLens попадают в свои стороны, служебные – никуда', () => {
    expect(directionsOf(['Adventure', 'Animation', 'Children', 'IMAX'])).toEqual(['action', 'animation'])
    expect(directionsOf(['(no genres listed)'])).toEqual([])
  })

  it('цвет точки на карте – самая редкая группа фильма, а не первый жанр в списке', () => {
    expect(mainDirection(['Action', 'Sci-Fi', 'Thriller'])).toBe('scifi') // Матрица
    expect(mainDirection(['Adventure', 'Animation', 'Children', 'Comedy', 'Fantasy'])).toBe('animation') // История игрушек
    expect(mainDirection(['Crime', 'Drama'])).toBe('thriller') // Побег из Шоушенка
    expect(mainDirection(['IMAX'])).toBeNull()
  })

  it('без оценок или только с плохими – покой', () => {
    expect(needle([]).strength).toBe(0)
    expect(needle([{ rating: 1, genres: ['Comedy'] }]).top).toBeNull()
  })

  it('понравившаяся фантастика – стрелка ровно на фантастику', () => {
    const liked = needle([{ rating: 5, genres: ['Sci-Fi'] }])
    expect(liked.angle).toBe(angleOf('scifi'))
    expect(liked.top).toBe('scifi')
    expect(liked.strength).toBeCloseTo(1)
  })

  it('редкий жанр весит больше частого: одна пятёрка ужасам сильнее одной пятёрки драме', () => {
    const n = needle([
      { rating: 5, genres: ['Drama'] },
      { rating: 5, genres: ['Horror'] },
    ])
    expect(n.top).toBe('horror')
    expect(n.weights.horror! / n.weights.drama!).toBeCloseTo(Math.log(1 / 0.112) / Math.log(1 / 0.523))
  })

  it('боевики и фэнтези впереди драмы и триллеров (случай из проверки 19.11)', () => {
    const ratings = [
      { rating: 5, genres: ['Crime', 'Drama'] }, // Побег из Шоушенка
      { rating: 4.5, genres: ['Action', 'Sci-Fi', 'Thriller'] }, // Матрица
      { rating: 4.5, genres: ['Action', 'Crime', 'Drama', 'Thriller'] }, // Бойцовский клуб
      { rating: 4, genres: ['Action', 'Adventure', 'Drama', 'Fantasy'] }, // Властелин колец: Возвращение короля
      { rating: 3.5, genres: ['Adventure', 'Fantasy'] }, // Властелин колец: Братство Кольца
    ]
    const n = needle(ratings)
    expect(n.top).toBe('action')
    const order = (Object.entries(n.weights) as [string, number][]).sort((a, b) => b[1] - a[1]).map(([d]) => d)
    expect(order.slice(0, 3)).toEqual(['action', 'scifi', 'thriller'])
    expect(order.indexOf('drama')).toBeGreaterThan(2)
  })

  it('разнородный вкус – стрелка короче', () => {
    const mixed = needle([
      { rating: 5, genres: ['Romance'] },
      { rating: 5, genres: ['Sci-Fi'] },
    ])
    expect(mixed.strength).toBeLessThan(0.55)
  })
})

describe('форматирование', () => {
  it('постер TMDb по пути, без пути – null', () => {
    expect(posterUrl('/abc.jpg')).toBe('https://image.tmdb.org/t/p/w342/abc.jpg')
    expect(posterUrl(null)).toBeNull()
  })

  it('десятичная запятая в русском и казахском, точка в английском', () => {
    expect(formatNumber(3.9, 'ru', 2)).toBe('3,90')
    expect(formatNumber(3.9, 'en', 2)).toBe('3.90')
    expect(formatPercent(0.38, 'en')).toBe('38%')
  })
})
