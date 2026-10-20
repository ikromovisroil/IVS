import { useQuery, useQueryClient } from '@tanstack/react-query'
import { API, api } from '../../api/client'
import type { Deed } from './types'

export const SPA = '/spa/messages'

export function useCounts() {
  return useQuery({
    queryKey: ['messages', 'counts'],
    queryFn: () => api<{ sign: number; agree: number }>(`${SPA}/counts/`),
  })
}

export function useDeed(id: number | null) {
  return useQuery({
    queryKey: ['messages', 'deed', id],
    queryFn: () => api<Deed>(`${SPA}/deeds/${id}/`),
    enabled: id != null,
  })
}

/** Hujjat o'zgargach: ro'yxatlar, sonlar va ochiq hujjat yangilanadi */
export function useRefresh() {
  const qc = useQueryClient()
  return () => qc.invalidateQueries({ queryKey: ['messages'] })
}

/** Ilovalarni yuklab olish (bitta bo'lsa o'zi, bir nechta bo'lsa ZIP) — /api/v1/deeds/{id}/attachments/download/ */
export const attachmentsUrl = (id: number) => `${API}/deeds/${id}/attachments/download/`

/** Fayl manzili: API to'liq URL qaytaradi, brauzer shu domenda ochadi */
export const openFile = (url: string) => window.open(url, '_blank', 'noopener')

/** E-IMZO'dan qaytgach shu sahifa ochiladi; ?eimzo=1 — natija xabarini (Django messages) ko'rsatish uchun */
export const EIMZO_FLAG = 'eimzo'
