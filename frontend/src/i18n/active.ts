// Joriy til React tashqarisidagi kod uchun (masalan, api/client.ts xato matnlari).
import { storedLang, translate } from '.'
import type { Lang, Vars } from '.'

let active: Lang = storedLang()

export function setActiveLang(lang: Lang) {
  active = lang
}

/** Komponentdan tashqarida tarjima: tr('So‘rov bajarilmadi.') */
export function tr(text: string, vars?: Vars): string {
  return translate(active, text, vars)
}
