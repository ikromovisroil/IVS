// Omborxona (material) arizalari — /api/v1/orders/ (OrderSerializer) va /api/v1/spa/orders-barn/ javoblari.

export type BarnStatus = 'viewed' | 'process' | 'finished' | 'approved' | 'accepted' | 'canceled' | 'rejected'

/** /api/v1/orders/?role=... ro'yxatlari (api/views.py OrderViewSet._barn_role_queryset) */
export type BarnRole =
  | 'barn_sender'
  | 'barn_sender_archive'
  | 'barn_receiver_new'
  | 'barn_receiver_active'
  | 'barn_receiver_archive'
  | 'barn_agrement'
  | 'barn_agrement_archive'

export interface OrderMaterial {
  id: number
  material: number | null
  material_name: string
  unit_name: string
  price: string | null
  number: number
  given: number | null
  given_summa: string | null
}

export interface BarnOrder {
  id: number
  goal: number | null
  goal_name: string | null
  sender: number | null
  sender_name: string | null
  message_sender: string | null
  rating: number | null
  receiver: number | null
  receiver_name: string | null
  message_receiver: string | null
  user: number | null
  user_name: string | null
  status: BarnStatus
  status_display: string
  date_creat: string
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

/** /api/v1/spa/orders-barn/orders/<id>/ */
export interface BarnOrderDetail extends BarnOrder {
  materials: (OrderMaterial & { stock: number | null; image: string | null })[]
  people: { sender: Person | null; receiver: Person | null; user: Person | null }
}

/** /api/v1/spa/orders-barn/cart/ */
export interface CartItem {
  id: number
  material: number
  name: string
  unit_name: string | null
  image: string | null
  stock: number
  number: number
}

/** /api/v1/orders/selectable-materials/ (MaterialSerializer) */
export interface SelectableMaterial {
  id: number
  name: string
  unit_name: string | null
  category_name: string | null
  number: number
  image: string | null
}

export interface GoalRef {
  id: number
  name: string
}
