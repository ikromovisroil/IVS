import type { ReactNode } from 'react'

/** Har bir bo'lim o'z papkasidagi routes.tsx da shu ro'yxatni eksport qiladi; App.tsx ularni yig'adi. */
export interface AppRoute {
  /** To'liq yo'l, masalan "/orders/sent" yoki "/technics/:id" */
  path: string
  element: ReactNode
}

/** Yangi interfeys Django'da /app/ ostida (config/spa.py). Router shu yo'lni o'zi qo'shadi; oddiy <a href> uchun qo'lda. */
export const BASENAME = '/app'
