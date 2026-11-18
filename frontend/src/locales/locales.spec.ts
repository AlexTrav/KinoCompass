import en from './en'
import kk from './kk'
import ru from './ru'

// все ключи сообщений одной строкой «раздел.ключ»
function keys(messages: object, prefix = ''): string[] {
  return Object.entries(messages).flatMap(([k, v]) =>
    typeof v === 'object' && v !== null ? keys(v, `${prefix}${k}.`) : [`${prefix}${k}`],
  )
}

function values(messages: object): string[] {
  return Object.values(messages).flatMap((v) => (typeof v === 'object' && v !== null ? values(v) : [String(v)]))
}

describe('переводы', () => {
  it('у казахского и английского те же ключи, что у русского', () => {
    expect(keys(kk).sort()).toEqual(keys(ru).sort())
    expect(keys(en).sort()).toEqual(keys(ru).sort())
  })

  it('подстановки {n} совпадают во всех языках', () => {
    const slots = (s: string) => (s.match(/\{\w+\}/g) ?? []).sort().join()
    const ruValues = values(ru)
    for (const other of [kk, en]) {
      values(other).forEach((v, i) => expect(slots(v)).toBe(slots(ruValues[i])))
    }
  })

  it('без длинного тире, «|» и «@» (в vue-i18n это служебные знаки: множественное число и ссылки)', () => {
    for (const v of [...values(ru), ...values(kk), ...values(en)]) {
      expect(v).not.toContain(String.fromCharCode(0x2014)) // длинное тире – кодом, чтобы его не было в файле
      expect(v).not.toContain('|')
      expect(v).not.toContain('@')
    }
  })

  it('в казахском – казахские буквы', () => {
    expect(values(kk).join(' ')).toMatch(/[әғқңөұүһі]/)
  })
})
