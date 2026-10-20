import { useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { I18nContext, storeLang, storedLang } from '../i18n'
import type { Lang } from '../i18n'
import { setActiveLang } from '../i18n/active'
import { ThemeContext, applyTheme, storeTheme, storedTheme, watchSystemTheme } from '../theme'
import type { Theme } from '../theme'

/** Foydalanuvchi sozlamalari: til va mavzu (brauzerda saqlanadi). */
export default function SettingsProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(storedLang)
  const [theme, setThemeState] = useState<Theme>(storedTheme)

  useEffect(() => {
    document.documentElement.lang = lang === 'ru' ? 'ru' : 'uz'
    setActiveLang(lang)
  }, [lang])

  useEffect(() => {
    applyTheme(theme)
    if (theme !== 'system') return
    return watchSystemTheme(() => applyTheme('system'))
  }, [theme])

  const i18n = useMemo(
    () => ({
      lang,
      setLang: (l: Lang) => {
        storeLang(l)
        setLangState(l)
      },
    }),
    [lang],
  )
  const themeState = useMemo(
    () => ({
      theme,
      setTheme: (t: Theme) => {
        storeTheme(t)
        setThemeState(t)
      },
    }),
    [theme],
  )

  return (
    <I18nContext.Provider value={i18n}>
      <ThemeContext.Provider value={themeState}>{children}</ThemeContext.Provider>
    </I18nContext.Provider>
  )
}
