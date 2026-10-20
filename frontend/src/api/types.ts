// /api/v1/ javob turlari (api/serializers.py va api/views.py MeView bilan mos).

export interface Employee {
  id: number
  username: string
  last_name: string | null
  first_name: string | null
  father_name: string | null
  full_name: string
  organization: number | null
  organization_name: string | null
  department_name: string | null
  region_name: string | null
  rank_name: string | null
  phone: string | null
}

export interface Me {
  username: string
  is_superuser: boolean
  employee: Employee | null
  /** worker — ATM vakili, client — mijoz */
  organization_type: 'worker' | 'client' | null
  orders: {
    can_create: boolean
    can_create_on_behalf: boolean
    can_execute: boolean
    can_confirm: boolean
    can_assign: boolean
  }
  /** "app_label.codename" */
  permissions: string[]
}

export type TechnicsStatus = 'free' | 'active' | 'repair' | 'defect'

export interface Technics {
  id: number
  group: number | null
  group_name: string | null
  category: number | null
  category_name: string | null
  region_name: string | null
  organization: number | null
  organization_name: string | null
  department_name: string | null
  employee: number | null
  employee_name: string | null
  status: TechnicsStatus
  status_display: string
  name: string
  parametr: string | null
  inventory: string | null
  serial: string | null
  mac: string | null
  ip: string | null
  price: string | null
  year: string | null
  address: string | null
  is_online: boolean
}

export interface TechnicsInput {
  group: number | null
  category: number | null
  organization: number | null
  name: string
  parametr: string
  inventory: string
  serial: string
  mac: string
  ip: string
  year: string
  price: string | null
  address: string
  is_online: boolean
}

export interface Named {
  id: number
  name: string
}

export interface Category extends Named {
  group: number | null
}
