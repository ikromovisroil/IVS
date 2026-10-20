import { ApiError } from '../../api/client'
import { formatNumber } from '../../lib/format'

/** 1234567.5 → "1 234 567.5"; 0 / bo'sh → "—" */
export function money(v: string | number | null | undefined): string {
  const n = Number(v ?? 0)
  return n ? formatNumber(Math.round(n * 100) / 100) : '—'
}

/** API xatosi matni: {"detail"} yoki maydon xatolari birlashtiriladi. */
export function errorText(e: unknown): string | null {
  if (!e) return null
  if (e instanceof ApiError) {
    if (e.data && typeof e.data === 'object' && 'detail' in e.data) return e.message
    const f = Object.values(e.fieldErrors)
    return f.length ? f.join(' ') : e.message
  }
  return (e as Error).message
}
