// Tarjima tizimi (gettext uslubida): kalit — o'zbekcha (lotin) matnning o'zi.
//   const t = useT()
//   t('Arizalar')                         → "Заявки" (ru) / "Arizalar" (uz)
//   t('Qurilmalar: {n} ta', { n: 23 })    → "Устройств: 23"
// Ruscha tarjima topilmasa o'zbekcha matn ko'rsatiladi (interfeys hech qachon bo'sh qolmaydi).
// Lug'atlar: src/i18n/ru/*.ts — har bo'lim o'z faylida.
// Ўзбекча (кирилл, 'uzc'): lug'at yo'q — lotin matn avtomatik o'giriladi (cyrillic.ts).
import { createContext, useCallback, useContext } from 'react'
import { toCyrillic } from './cyrillic'
import { RU } from './ru'

export type Lang = 'uz' | 'uzc' | 'ru'
export const LANGS: { value: Lang; label: string; short: string }[] = [
  { value: 'uz', label: "O'zbekcha", short: 'UZ' },
  { value: 'uzc', label: 'Ўзбекча (кирилл)', short: 'ЎЗ' },
  { value: 'ru', label: 'Русский', short: 'RU' },
]

export type Vars = Record<string, string | number | null | undefined>

const missing = new Set<string>()

// Kontekstli kalit: "Bekor qilish#ariza" — bir xil o'zbekcha matn turli joyda turlicha tarjima qilinsa.
// O'zbekchada "#kontekst" ko'rinmaydi; ruschada avval kontekstli, keyin oddiy kalit qidiriladi.
const CTX = /^(.*)#([a-z][a-z_-]*)$/

/** React tashqarisida ham ishlaydi (masalan, toast matni yasashda). */
export function translate(lang: Lang, text: string, vars?: Vars): string {
  const ctx = CTX.exec(text)
  const base = ctx ? ctx[1] : text
  let out = base
  if (lang === 'ru') {
    const hit = RU[text] ?? (ctx ? RU[base] : undefined)
    if (hit !== undefined) out = hit
    else if (import.meta.env.DEV && text && !missing.has(text)) {
      missing.add(text)
      console.debug('[i18n] ru tarjimasi yo‘q:', JSON.stringify(text))
    }
  }
  if (vars) out = out.replace(/\{(\w+)\}/g, (m, k: string) => (vars[k] == null ? m : String(vars[k])))
  // Kirillga o'zgaruvchilar o'rniga qo'yilgandan keyin o'giriladi (ismlar ham kirillga o'tadi)
  return lang === 'uzc' ? toCyrillic(out) : out
}

export interface I18n {
  lang: Lang
  setLang: (lang: Lang) => void
}

export const I18nContext = createContext<I18n>({ lang: 'uz', setLang: () => {} })

export function useLang(): I18n {
  return useContext(I18nContext)
}

/** Tarjima funksiyasi: t('Matn', { n: 1 }) */
export function useT() {
  const { lang } = useContext(I18nContext)
  return useCallback((text: string, vars?: Vars) => translate(lang, text, vars), [lang])
}

const KEY = 'ivs.lang'

export function storedLang(): Lang {
  try {
    const v = localStorage.getItem(KEY)
    if (v === 'uz' || v === 'uzc' || v === 'ru') return v
  } catch {
    /* brauzer xotirasi yopiq — standart til */
  }
  return 'uz'
}

export function storeLang(lang: Lang) {
  try {
    localStorage.setItem(KEY, lang)
  } catch {
    /* saqlab bo'lmasa ham joriy sessiyada ishlayveradi */
  }
}

/**
 * Lug'atda bo'lsa tarjima qiladi, bo'lmasa matnni o'zgarishsiz qaytaradi va ogohlantirmaydi.
 * Tarjimasi oldindan qilingan bo'lishi mumkin bo'lgan propslar uchun (masalan, Page sarlavhasi).
 */
export function useTMaybe() {
  const { lang } = useContext(I18nContext)
  return useCallback(
    (text: string) => {
      if (lang === 'ru' && RU[text] !== undefined) return RU[text]
      const base = CTX.exec(text)?.[1] ?? text
      return lang === 'uzc' ? toCyrillic(base) : base
    },
    [lang],
  )
}
