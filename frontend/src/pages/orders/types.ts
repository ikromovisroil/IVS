// /api/v1/orders/ (api/serializers.py OrderSerializer) va /api/v1/spa/orders/ javob turlari.
import type { StatusChipProps } from '../../ds'

export type OrderStatus = 'viewed' | 'process' | 'finished' | 'approved' | 'accepted' | 'canceled' | 'rejected'

export interface OrderMaterial {
  id: number
  material: number | null
  material_name: string
  unit_name: string
  price: string | null
  number: number
  given: number | null
}

export interface Order {
  id: number
  goal: number | null
  goal_name: string | null
  sender: number | null
  sender_name: string | null
  message_sender: string | null
  technics: number | null
  technics_name: string | null
  rating: number | null
  receiver: number | null
  receiver_name: string | null
  message_receiver: string | null
  user: number | null
  user_name: string | null
  status: OrderStatus
  status_display: string
  date_creat: string
  date_edit: string
  date_process: string | null
  date_finished: string | null
  date_approved: string | null
  date_accepted: string | null
  date_canceled: string | null
  date_rejected: string | null
  materials: OrderMaterial[]
  deeds: { id: number; code: string | null; file: string | null }[]
}

export interface Person {
  id: number
  full_name: string
  rank: string | null
  organization: string | null
  department: string | null
  directorate: string | null
  division: string | null
  phone: string | null
}

export interface OrderDetail extends Order {
  sender_info: Person | null
  receiver_info: Person | null
  user_info: Person | null
}

/** /api/v1/orders/?role=... (api/views.py OrderViewSet._role_queryset) */
export type OrderRole = 'sender' | 'sender_archive' | 'sender_user' | 'receiver_new' | 'receiver_active' | 'receiver_archive'

// main/models.py Order.status → AlignUI StatusChip (eski sahifadagi rang mantiqi bilan)
export const ORDER_STATUS: Record<OrderStatus, StatusChipProps['status']> = {
  viewed: 'pending',
  process: 'in-progress',
  finished: 'active',
  approved: 'completed',
  accepted: 'completed',
  canceled: 'absent',
  rejected: 'failed',
}

const pad = (n: number) => String(n).padStart(2, '0')

/** "20.10.2026, 14:05" (eski sahifadagi d.m.Y, H:i) */
export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return '—'
  const d = new Date(iso)
  return `${pad(d.getDate())}.${pad(d.getMonth() + 1)}.${d.getFullYear()}, ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

/** "450 000" — narx (intcomma) */
export function formatPrice(v: string | number | null | undefined): string {
  if (v == null || v === '') return '—'
  const n = Number(v)
  if (Number.isNaN(n)) return String(v)
  return new Intl.NumberFormat('uz-UZ', { maximumFractionDigits: 2 }).format(n).replace(/[\s,]/g, ' ')
}
