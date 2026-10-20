import { useState } from 'react'

// Chat ko'rinishi (eski chat.js: fon va tema) — faqat shu brauzerda saqlanadi.
export const WALLPAPERS = [
  { value: 'plain', label: 'Oddiy' },
  { value: 'dots', label: 'Nuqtalar' },
  { value: 'grid', label: "To'r" },
  { value: 'waves', label: "To'lqin" },
] as const

export const THEMES = [
  { value: 'default', label: 'Standart', color: 'var(--primary-base)' },
  { value: 'violet', label: 'Violet', color: 'var(--purple-500)' },
  { value: 'ocean', label: 'Ocean', color: 'var(--teal-600)' },
  { value: 'emerald', label: 'Emerald', color: 'var(--green-600)' },
  { value: 'rose', label: 'Rose', color: 'var(--red-500)' },
] as const

export interface Appearance {
  wallpaper: string
  theme: string
}

const KEY = 'ivs.chat.appearance'

function load(): Appearance {
  try {
    const raw = JSON.parse(localStorage.getItem(KEY) || '{}')
    return { wallpaper: raw.wallpaper || 'plain', theme: raw.theme || 'default' }
  } catch {
    return { wallpaper: 'plain', theme: 'default' }
  }
}

export function useAppearance(): [Appearance, (a: Appearance) => void] {
  const [value, setValue] = useState(load)
  const set = (a: Appearance) => {
    setValue(a)
    try {
      localStorage.setItem(KEY, JSON.stringify(a))
    } catch {
      /* saqlab bo'lmasa — faqat shu sessiyada */
    }
  }
  return [value, set]
}

export const themeColor = (theme: string) => THEMES.find((t) => t.value === theme)?.color ?? THEMES[0].color
