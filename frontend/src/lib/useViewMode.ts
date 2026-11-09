import { useCallback, useState } from 'react'

export type ViewMode = 'table' | 'cards'

/** Ro'yxat ko'rinishi (jadval / karta): har bir foydalanuvchi o'zi tanlaydi, brauzerda eslab qolinadi. */
export function useViewMode(key: string, initial: ViewMode = 'table'): [ViewMode, (mode: ViewMode) => void] {
  const storageKey = `ivs.view.${key}`
  const [mode, setMode] = useState<ViewMode>(() => {
    try {
      const v = localStorage.getItem(storageKey)
      if (v === 'table' || v === 'cards') return v
    } catch {
      /* brauzer xotirasi yopiq */
    }
    return initial
  })
  const change = useCallback(
    (next: ViewMode) => {
      setMode(next)
      try {
        localStorage.setItem(storageKey, next)
      } catch {
        /* saqlab bo'lmasa ham joriy sessiyada ishlaydi */
      }
    },
    [storageKey],
  )
  return [mode, change]
}
