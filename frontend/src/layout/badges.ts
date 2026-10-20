import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'

const MINUTE = 60 * 1000

/**
 * Yon menyudagi qizil sonlar (eski base.html dagi nishonlar):
 * Arizalar — yangi bildirishnomalar yoki bajarishni kutayotganlar, qaysi biri ko'p bo'lsa (/orders/badges/),
 * Xabarlar — imzolash va kelishish uchun kutayotgan hujjatlar (/spa/messages/counts/).
 */
export function useNavBadges(): Record<string, number> {
  const orders = useQuery({
    queryKey: ['badges', 'orders'],
    queryFn: () => api<{ notifications: number; receiver_pending: number }>('/orders/badges/'),
    refetchInterval: MINUTE,
    staleTime: MINUTE / 2,
  })
  const messages = useQuery({
    queryKey: ['badges', 'messages'],
    queryFn: () => api<{ sign: number; agree: number }>('/spa/messages/counts/'),
    refetchInterval: MINUTE,
    staleTime: MINUTE / 2,
  })

  const notifications = useQuery({
    queryKey: ['badges', 'notifications'],
    queryFn: () => api<{ unread: number }>('/notifications/unread-count/'),
    refetchInterval: MINUTE,
    staleTime: MINUTE / 2,
  })

  return {
    '/notifications': notifications.data?.unread ?? 0,
    // notifications tayinlanmagan (bajarishni kutayotgan) arizalarni ham sanaydi — yig'indi ikki marta sanardi
    '/orders': Math.max(orders.data?.notifications ?? 0, orders.data?.receiver_pending ?? 0),
    '/messages': (messages.data?.sign ?? 0) + (messages.data?.agree ?? 0),
  }
}
