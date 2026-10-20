import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../../api/client'
import type { Page as ApiPage } from '../../api/client'
import { useUrlFilters } from '../../lib/useUrlFilters'
import type { Order, OrderDetail, OrderRole } from './types'

export const PAGE_SIZE = 20

/** Ro'yxat: /api/v1/orders/?role=... ; poll — 1-sahifada har 20 soniyada yangilash (eski order_check_new) */
export function useOrderList(role: OrderRole, poll = false) {
  const { page, setPage } = useUrlFilters([])
  const list = useQuery({
    queryKey: ['orders', 'list', role, page],
    queryFn: () => api<ApiPage<Order>>('/orders/', { query: { role, page, page_size: PAGE_SIZE } }),
    placeholderData: keepPreviousData,
    refetchInterval: poll && page === 1 ? 20000 : false,
    refetchIntervalInBackground: false,
  })
  return { list, page, setPage }
}

export function useOrderDetail(id: number) {
  return useQuery({
    queryKey: ['orders', 'detail', id],
    queryFn: () => api<OrderDetail>(`/spa/orders/${id}/`),
  })
}

/** templates/base.html dagi qizil raqam: bajarish uchun kutayotgan yangi arizalar (context_processors.order_receiver_count). */
export function useReceiverPending(enabled: boolean) {
  return useQuery({
    queryKey: ['orders', 'badges'],
    queryFn: () => api<{ notifications: number; receiver_pending: number }>('/orders/badges/'),
    enabled,
    refetchInterval: 20000,
    refetchIntervalInBackground: false,
  })
}

export interface MaterialRow {
  key: number
  material: number | null
  number: string
}

export interface FinishState {
  technics: number | null
  rows: MaterialRow[]
}

/** Yakunlash: POST /api/v1/orders/{id}/finish/ (texnika + ombordan materiallar) */
export function useFinish(id: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (s: FinishState) =>
      api(`/orders/${id}/finish/`, {
        method: 'POST',
        body: JSON.stringify({
          technics_id: s.technics,
          materials: s.rows.filter((r) => r.material != null).map((r) => ({ material_id: r.material, number: Number(r.number) || 1 })),
        }),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['orders'] }),
  })
}

/** Yuborishdan oldingi tekshiruv (eski sahifadagi JS va order_material_post bilan bir xil). */
export function validateFinish(s: FinishState): string | null {
  const chosen = s.rows.filter((r) => r.material != null)
  if (chosen.length && s.technics == null) return "Material qo'shish uchun avval texnikani tanlang!"
  const ids = chosen.map((r) => r.material)
  if (new Set(ids).size !== ids.length) return 'Bir xil materialni bir necha marta kiritmang'
  if (chosen.some((r) => !(Number(r.number) >= 1))) return "Material soni 0 yoki manfiy bo'lishi mumkin emas"
  return null
}
