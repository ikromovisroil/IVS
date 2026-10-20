import { useCallback } from 'react'
import { useLang, useT } from '../../i18n'
import ru from '../../i18n/ru/orders-barn'

/**
 * Bir xil o'zbekcha matn turli joyda turlicha tarjima qilinishi kerak bo'lganda (masalan, "Bekor qilish" —
 * dialogdagi "Отмена" va arizani bekor qilish amali "Отменить заявку").
 * Lug'atda kalit "<matn>#<kontekst>"; o'zbekchada matnning o'zi ko'rinadi.
 */
export function useCtxT() {
  const t = useT()
  const { lang } = useLang()
  return useCallback((text: string, ctx: string) => (lang === 'ru' && ru[`${text}#${ctx}`]) || t(text), [lang, t])
}
