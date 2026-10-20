import type { Lang } from '../../i18n'
import { MONTHS, MONTHS_SHORT, WEEKDAYS } from '../../i18n/format'

/** "Dushanba, 20-oktabr 2026" / "Понедельник, 20 октября 2026" */
export function longDate(d: Date, lang: Lang): string {
  const day = WEEKDAYS[lang][d.getDay()]
  return lang === 'ru'
    ? `${day}, ${d.getDate()} ${MONTHS.ru[d.getMonth()]} ${d.getFullYear()}`
    : `${day}, ${d.getDate()}-${MONTHS.uz[d.getMonth()]} ${d.getFullYear()}`
}

/** "20 okt" */
export function shortDate(iso: string, lang: Lang): string {
  const d = new Date(iso)
  return `${d.getDate()} ${MONTHS_SHORT[lang][d.getMonth()]}`
}

/** "20.10.2026, 10:05" */
export function dateTime(iso: string): string {
  const d = new Date(iso)
  const p = (n: number) => String(n).padStart(2, '0')
  return `${p(d.getDate())}.${p(d.getMonth() + 1)}.${d.getFullYear()}, ${p(d.getHours())}:${p(d.getMinutes())}`
}

type T = (text: string, vars?: Record<string, string | number>) => string

/** "3 soat oldin", "2 kun oldin" */
export function ago(iso: string, t: T): string {
  const min = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 60000))
  if (min < 1) return t('hozirgina')
  if (min < 60) return t('{n} daqiqa oldin', { n: min })
  const h = Math.round(min / 60)
  if (h < 24) return t('{n} soat oldin', { n: h })
  return t('{n} kun oldin', { n: Math.round(h / 24) })
}

/** Soatlar: 5.2 → "5,2 soat", 30 → "1,3 kun" */
export function duration(hours: number | null, t: T): string {
  if (hours == null) return '—'
  if (hours < 1) return t('{n} daqiqa', { n: Math.max(1, Math.round(hours * 60)) })
  const fmt = (n: number) => n.toLocaleString('uz-UZ', { maximumFractionDigits: 1 }).replace('.', ',')
  return hours < 24 ? t('{n} soat', { n: fmt(hours) }) : t('{n} kun', { n: fmt(hours / 24) })
}

/**
 * Oldingi davrga nisbatan o'zgarish: "+12%", "−8%". Oldingi qiymat 0 yoki yo'q bo'lsa — null.
 * lowerIsBetter — vaqt kabi ko'rsatkichlar uchun (kamayish yaxshi).
 */
export function change(value: number | null, prev: number | null, lowerIsBetter = false) {
  if (value == null || prev == null || prev === 0) return null
  const pct = Math.round(((value - prev) / prev) * 100)
  if (pct === 0) return { text: '0%', tone: 'neutral' as const }
  const good = lowerIsBetter ? pct < 0 : pct > 0
  return { text: `${pct > 0 ? '+' : '−'}${Math.abs(pct)}%`, tone: good ? ('success' as const) : ('error' as const) }
}

/** Grafik tooltip sarlavhasi: kunlik — "Seshanba, 20 okt"; haftalik — "13–19 okt" */
export function bucketLabel(iso: string, bucketDays: number, lang: Lang): string {
  const d = new Date(iso)
  const m = MONTHS_SHORT[lang]
  if (bucketDays <= 1) return `${WEEKDAYS[lang][d.getDay()]}, ${d.getDate()} ${m[d.getMonth()]}`
  const e = new Date(d)
  e.setDate(d.getDate() + bucketDays - 1)
  return d.getMonth() === e.getMonth()
    ? `${d.getDate()}–${e.getDate()} ${m[e.getMonth()]}`
    : `${d.getDate()} ${m[d.getMonth()]} – ${e.getDate()} ${m[e.getMonth()]}`
}
