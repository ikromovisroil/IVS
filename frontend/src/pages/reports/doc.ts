import { useMemo, useRef } from 'react'
import type { RefObject } from 'react'

/**
 * Hujjat matni (eski sahifalardagi TinyMCE o'rnida). Shablon bir marta yoziladi, keyin sahifa uni id bo'yicha
 * "yamaydi" (setText / setHTML) — xuddi eski JS dagidek, shuning uchun qo'lda kiritilgan tuzatishlar avtomatik
 * maydonlar yangilanganda yo'qolmaydi. Standart holatda faqat o'qish; "Qo'lda tahrirlash" yoqilsa tahrirlanadi.
 */
export interface DocApi {
  ref: RefObject<HTMLDivElement | null>
  /** Barcha mos elementlarga matn yozadi (bir xil id bir necha joyda bo'lishi mumkin) */
  setText: (selector: string, text: string) => void
  setHTML: (selector: string, html: string) => void
  html: () => string
}

export function useDoc(): DocApi {
  const ref = useRef<HTMLDivElement>(null)
  return useMemo<DocApi>(() => {
    const all = (selector: string) => Array.from(ref.current?.querySelectorAll<HTMLElement>(selector) ?? [])
    return {
      ref,
      setText: (selector, text) => all(selector).forEach((el) => (el.textContent = text)),
      setHTML: (selector, html) => all(selector).forEach((el) => (el.innerHTML = html)),
      html: () => ref.current?.innerHTML.trim() ?? '',
    }
  }, [])
}
