// Django REST API (/api/v1/) bilan ishlash. SPA Django bilan bir domenda ishlaydi va
// SessionAuthentication'dan foydalanadi: cookie avtomatik yuboriladi, yozish so'rovlariga CSRF qo'shiladi.

import { tr } from '../i18n/active'

export const API = '/api/v1'

export class ApiError extends Error {
  status: number
  data: unknown

  constructor(status: number, data: unknown) {
    super(errorMessage(status, data))
    this.status = status
    this.data = data
  }

  /** DRF tekshiruv xatolari: {"maydon": ["..."]} → {maydon: "..."} */
  get fieldErrors(): Record<string, string> {
    if (!this.data || typeof this.data !== 'object') return {}
    const out: Record<string, string> = {}
    for (const [k, v] of Object.entries(this.data as Record<string, unknown>)) {
      if (k !== 'detail') out[k] = tr(Array.isArray(v) ? String(v[0]) : String(v))
    }
    return out
  }
}

function errorMessage(status: number, data: unknown): string {
  // Server xabarlari o'zbekcha; lug'atda bo'lsa ruschasi ko'rsatiladi
  if (data && typeof data === 'object' && 'detail' in data) return tr(String((data as { detail: unknown }).detail))
  if (status === 403) return tr("Bu amal uchun ruxsatingiz yo'q.")
  if (status === 404) return tr('Topilmadi.')
  if (status >= 500) return tr("Serverda xatolik. Birozdan so'ng qayta urinib ko'ring.")
  return tr('So‘rov bajarilmadi.')
}

function csrfToken(): string {
  const m = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/)
  return m ? decodeURIComponent(m[1]) : ''
}

export type Query = Record<string, string | number | boolean | null | undefined>

export function withQuery(path: string, query?: Query): string {
  if (!query) return path
  const qs = new URLSearchParams()
  for (const [k, v] of Object.entries(query)) {
    if (v !== undefined && v !== null && v !== '') qs.set(k, String(v))
  }
  const s = qs.toString()
  return s ? `${path}?${s}` : path
}

export async function api<T>(path: string, init: RequestInit & { query?: Query } = {}): Promise<T> {
  const { query, ...rest } = init
  const method = (rest.method || 'GET').toUpperCase()
  const headers = new Headers(rest.headers)
  headers.set('Accept', 'application/json')
  if (rest.body && !(rest.body instanceof FormData)) headers.set('Content-Type', 'application/json')
  if (method !== 'GET' && method !== 'HEAD') headers.set('X-CSRFToken', csrfToken())

  const res = await fetch(withQuery(API + path, query), { ...rest, method, headers, credentials: 'same-origin' })
  if (res.status === 204) return undefined as T
  const data = res.headers.get('content-type')?.includes('json') ? await res.json() : await res.text()
  if (!res.ok) throw new ApiError(res.status, data)
  return data as T
}

export interface Page<T> {
  count: number
  next: string | null
  previous: string | null
  results: T[]
}

/** Ma'lumotnoma ro'yxatlari (guruh, kategoriya, tashkilot...) — barcha sahifalarni yig'adi. */
export async function apiAll<T>(path: string, query?: Query): Promise<T[]> {
  const out: T[] = []
  for (let page = 1; ; page++) {
    const data = await api<Page<T> | T[]>(path, { query: { ...query, page, page_size: 100 } })
    if (Array.isArray(data)) return data
    out.push(...data.results)
    if (!data.next) return out
  }
}
