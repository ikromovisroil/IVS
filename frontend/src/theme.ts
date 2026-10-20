// Mavzu: yorug' / tungi / tizim (brauzer sozlamasiga ergashadi).
// AlignUI tokenlari <html data-theme="dark"> bo'lganda tungi qiymatlarga o'tadi (ds/tokens.css).
import { createContext, useContext } from 'react'

export type Theme = 'light' | 'dark' | 'system'

const KEY = 'ivs.theme'
const media = () => window.matchMedia('(prefers-color-scheme: dark)')

export function storedTheme(): Theme {
  try {
    const v = localStorage.getItem(KEY)
    if (v === 'light' || v === 'dark' || v === 'system') return v
  } catch {
    /* brauzer xotirasi yopiq */
  }
  return 'light'
}

export function storeTheme(theme: Theme) {
  try {
    localStorage.setItem(KEY, theme)
  } catch {
    /* saqlab bo'lmasa ham joriy sessiyada ishlaydi */
  }
}

/** Mavzuni <html> ga qo'llaydi; qo'llangan (light/dark) qiymatni qaytaradi. */
export function applyTheme(theme: Theme): 'light' | 'dark' {
  const resolved = theme === 'system' ? (media().matches ? 'dark' : 'light') : theme
  document.documentElement.dataset.theme = resolved
  document.documentElement.style.colorScheme = resolved
  return resolved
}

/** Tizim mavzusi o'zgarsa (kechqurun avtomatik tungi rejim) qayta qo'llash */
export function watchSystemTheme(onChange: () => void): () => void {
  const m = media()
  m.addEventListener('change', onChange)
  return () => m.removeEventListener('change', onChange)
}

export interface ThemeState {
  theme: Theme
  setTheme: (theme: Theme) => void
}

export const ThemeContext = createContext<ThemeState>({ theme: 'light', setTheme: () => {} })

export function useTheme(): ThemeState {
  return useContext(ThemeContext)
}
