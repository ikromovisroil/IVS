// Qo'shimcha qurilmalar va materiallar: /api/v1/ (structures, materials, units, ...) va /api/v1/spa/warehouse/ turlari.
import { useQuery } from '@tanstack/react-query'
import { api, apiAll } from '../../api/client'
import type { Named, TechnicsStatus } from '../../api/types'
import { SPA, toOptions } from '../technics/api'

const DAY = 24 * 60 * 60 * 1000

/** MaterialMovement.STATUS_CHOICES (serverdagi o'zbekcha nomlar aynan) — ruscha uchun t() kaliti */
export const MOVEMENT_STATUS: Record<string, string> = {
  created: "Qo'shildi",
  edited: 'Taxrirlandi',
  deleted: "O'chirildi",
  assigned: 'Biriktirildi',
  order: 'Ariza orqali berildi',
  service: 'Xizmat ko‘rsatildi',
}

export interface Structure {
  id: number
  category: number | null
  category_name: string | null
  organization: number | null
  organization_name: string | null
  region: number | null
  region_name: string | null
  technics: number | null
  technics_name: string | null
  technics_serial: string | null
  technics_inventory: string | null
  technics_employee_name: string | null
  status: TechnicsStatus
  status_display: string
  name: string
  parametr: string | null
  inventory: string | null
  serial: string | null
  price: string | null
  year: string | null
}

export interface Material {
  id: number
  category: number | null
  category_name: string | null
  employee: number | null
  employee_name: string | null
  unit: number | null
  unit_name: string | null
  name: string
  number: number
  code: string | null
  price: string | null
  year: string | null
  image: string | null
}

export interface BasketRow {
  id: number
  material: number
  name: string
  code: string | null
  price: string | null
  unit_name: string | null
  number: number
  available: number
  total_sum: string
  status: string
  status_display: string
  date_creat: string
}

export interface Movement {
  date: string
  user: string | null
  employee: string | null
  income: number | null
  outcome: number | null
  status: string
  status_display: string
  body: string | null
}

export interface ReportRow {
  id: number
  name: string
  code: string | null
  unit: string
  category: string
  price: string | null
  initial_balance: number
  income: number
  income_sum: string | number
  outcome: number
  outcome_sum: string | number
  current_balance: number
  current_sum: string | number
  movements: Movement[]
}

export interface PersonOption {
  id: number
  full_name: string
}

const opts = (xs: PersonOption[] | undefined) => (xs ?? []).map((e) => ({ value: e.id, label: e.full_name }))

export function useStructureCategories() {
  const q = useQuery({ queryKey: ['warehouse', 'structure-categories'], queryFn: () => apiAll<Named>('/structure-categories/'), staleTime: DAY })
  return toOptions(q.data)
}

export function useMaterialRefs() {
  const units = useQuery({ queryKey: ['warehouse', 'units'], queryFn: () => apiAll<Named>('/units/'), staleTime: DAY })
  const categories = useQuery({ queryKey: ['warehouse', 'material-categories'], queryFn: () => apiAll<Named>('/material-categories/'), staleTime: DAY })
  return { unitOptions: toOptions(units.data), categoryOptions: toOptions(categories.data) }
}

/** barn_mat dagi "Xodim" (moddiy javobgarlar) — materiallar ro'yxati va biriktirish uchun */
export function useMaterialEmployees() {
  const q = useQuery({ queryKey: ['warehouse', 'material-employees'], queryFn: () => api<PersonOption[]>(`${SPA}/materials/employees/`), staleTime: 5 * 60 * 1000 })
  return { ...q, options: opts(q.data) }
}

/** mat_info / mat_arxiv dagi xodimlar (o'zi yoki all_material_employee bo'lsa tashkilotdagi moddiy javobgarlar) */
export function useReportEmployees() {
  const q = useQuery({ queryKey: ['warehouse', 'report-employees'], queryFn: () => api<PersonOption[]>('/materials/report/employees/'), staleTime: 5 * 60 * 1000 })
  return { ...q, options: opts(q.data) }
}
