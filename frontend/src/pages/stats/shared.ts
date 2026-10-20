import { useSearchParams } from 'react-router-dom'

export const TABS = [
  { path: '/stats/technics', label: 'Texnikalar', icon: 'ri-computer-line' },
  { path: '/stats/employees', label: 'Xodimlar', icon: 'ri-user-star-line' },
  { path: '/stats/organizations', label: 'Tashkilotlar', icon: 'ri-building-line' },
]

/** Guruh ranglari: eski sahifadagi 8 rangli palitra tartibida (tokenlar orqali). */
export const PALETTE = [
  'var(--primary-base)',
  'var(--purple-500)',
  'var(--sky-500)',
  'var(--green-500)',
  'var(--orange-500)',
  'var(--red-500)',
  'var(--pink-500)',
  'var(--teal-500)',
]
export const paletteColor = (i: number) => PALETTE[((i % PALETTE.length) + PALETTE.length) % PALETTE.length]

export const STRUCTURE_KEYS = ['organization', 'region', 'department', 'directorate', 'division'] as const
export type StructureKey = (typeof STRUCTURE_KEYS)[number]
export type Structure = Record<StructureKey, string>
export const EMPTY_STRUCTURE: Structure = { organization: '', region: '', department: '', directorate: '', division: '' }

/** Manzil satridagi parametrlar: bir nechta kalitni bir yo'la o'zgartirish (bog'liq filtrlar tozalanadi), sahifa 1 ga qaytadi. */
export function useParamState() {
  const [params, setParams] = useSearchParams()
  const set = (patch: Record<string, string | null>) =>
    setParams(
      (p) => {
        for (const [k, v] of Object.entries(patch)) {
          if (v === null) p.delete(k)
          else p.set(k, v)
        }
        if (!('page' in patch)) p.delete('page')
        return p
      },
      { replace: true },
    )
  return { params, set }
}

/** Manzildagi kalitlardan so'rov satri (bo'sh qiymatlar ham saqlanadi: "organization=" — tanlov tozalangan). */
export function pickQuery(params: URLSearchParams, keys: readonly string[]): string {
  return new URLSearchParams(keys.filter((k) => params.has(k)).map((k) => [k, params.get(k) ?? ''])).toString()
}

/** "2026-10-01" → "01.10.2026" */
export function formatDate(iso: string): string {
  if (!iso) return ''
  const [y, m, d] = iso.split('-')
  return `${d}.${m}.${y}`
}
