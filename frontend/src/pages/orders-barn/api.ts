import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../../api/client'
import type { Page as ApiPage } from '../../api/client'
import type { Me } from '../../api/types'
import { useToast } from '../../components/toast'
import type { BarnOrder, BarnOrderDetail, BarnRole, CartItem, GoalRef } from './types'

export const PAGE_SIZE = 20
export const SPA = '/spa/orders-barn'

/** Ro'yxat: /api/v1/orders/?role=barn_* (20 tadan, eski sahifalar bilan bir xil). */
export function useBarnList(role: BarnRole, page: number, opts: { poll?: boolean } = {}) {
  return useQuery({
    queryKey: ['orders-barn', 'list', role, page],
    queryFn: () => api<ApiPage<BarnOrder>>('/orders/', { query: { role, page, page_size: PAGE_SIZE } }),
    placeholderData: keepPreviousData,
    // Eski order_receiver_barn har 20 soniyada yangi arizalarni tekshirardi (faqat ko'rinib turgan oynada)
    refetchInterval: opts.poll ? 20_000 : false,
  })
}

/** Tab yonidagi son (masalan, bajarishni kutayotgan yangi arizalar — eski menyudagi qizil belgi). */
export function useBarnCount(role: BarnRole, enabled = true) {
  return useQuery({
    queryKey: ['orders-barn', 'list', role, 'count'],
    queryFn: () => api<ApiPage<BarnOrder>>('/orders/', { query: { role, page_size: 1 } }).then((d) => d.count),
    enabled,
    refetchInterval: 20_000,
  })
}

export function useOrderDetail(id: number | null) {
  return useQuery({
    queryKey: ['orders-barn', 'detail', id],
    queryFn: () => api<BarnOrderDetail>(`${SPA}/orders/${id}/`),
    enabled: id != null,
  })
}

export function useCart(enabled = true) {
  return useQuery({
    queryKey: ['orders-barn', 'cart'],
    queryFn: () => api<CartItem[]>(`${SPA}/cart/`),
    enabled,
  })
}

/** Holat o'zgartiruvchi amal: muvaffaqiyatda toast + bo'lim keshini yangilash, xatoda toast. */
export function useBarnMutation<V, D = unknown>(fn: (v: V) => Promise<D>, success: string | ((v: V, data: D) => string), onDone?: () => void) {
  const qc = useQueryClient()
  const toast = useToast()
  return useMutation({
    mutationFn: fn,
    onSuccess: (data, v) => {
      const warning = data && typeof data === 'object' && 'warning' in data ? String((data as { warning: unknown }).warning) : ''
      toast(typeof success === 'function' ? success(v, data) : success)
      if (warning) toast(warning, 'info')
      qc.invalidateQueries({ queryKey: ['orders-barn'] })
      onDone?.()
    },
    onError: (e) => {
      toast(e.message, 'error')
      qc.invalidateQueries({ queryKey: ['orders-barn'] })
    },
  })
}

/** /me/ dagi material arizasi turlari (o'z tashkilotining client maqsadlari). */
export function materialGoals(me: Me): GoalRef[] {
  return (me.orders as Me['orders'] & { material_goals?: GoalRef[] }).material_goals ?? []
}

/** DRF to'liq URL qaytaradi (http://127.0.0.1:8000/media/...) — Vite proxy orqali ochilishi uchun faqat yo'l olinadi. */
export function mediaPath(url: string | null): string | null {
  if (!url) return null
  try {
    const u = new URL(url, window.location.origin)
    return u.pathname + u.search
  } catch {
    return url
  }
}

const pad = (n: number) => String(n).padStart(2, '0')

/** "2026-10-20T13:03:44+05:00" → "20.10.2026, 13:03" */
export function formatDate(iso: string | null | undefined): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return '—'
  return `${pad(d.getDate())}.${pad(d.getMonth() + 1)}.${d.getFullYear()}, ${pad(d.getHours())}:${pad(d.getMinutes())}`
}
