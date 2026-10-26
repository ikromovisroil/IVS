import { useQuery } from '@tanstack/react-query'
import { apiAll } from '../../api/client'
import type { Named } from '../../api/types'
import { sortById } from '../../lib/format'

const DAY = 24 * 60 * 60 * 1000

/** /api/v1/employees/ (api/serializers.py: EmployeeSerializer) */
export interface EmployeeRow {
  id: number
  username: string
  last_name: string | null
  first_name: string | null
  father_name: string | null
  full_name: string
  organization: number | null
  organization_name: string | null
  department: number | null
  department_name: string | null
  directorate: number | null
  division: number | null
  region: number | null
  region_name: string | null
  rank: number | null
  rank_name: string | null
  phone: string | null
  pinfl: string | null
}

/** /api/v1/employees/{id}/permissions/ (api/roles.py: state) */
export interface PermItem {
  key: string
  label: string
  group: string
  granted: boolean
  effective: boolean
  editable: boolean
}

export interface PickList<T = Named> {
  enabled: boolean
  options: T[]
  selected: number[]
}

export interface PermState {
  employee: { id: number; full_name: string; organization_type: 'worker' | 'client' | null }
  permissions: PermItem[]
  goals: PickList
  categories: PickList<Named & { group: string | null }>
  contracts: PickList
  material_categories: PickList
  ignored?: string[]
}

/** /api/v1/spa/people/profile/ */
export interface Profile {
  id: number
  username: string
  full_name: string
  last_name: string | null
  first_name: string | null
  father_name: string | null
  rank_name: string | null
  organization_name: string | null
  organization_type: 'worker' | 'client' | null
  department_name: string | null
  directorate_name: string | null
  division_name: string | null
  region_name: string | null
  phone: string | null
  email: string | null
  pinfl: string | null
  date_joined: string | null
  last_login: string | null
}

export type SignStatus = 'viewed' | 'approved' | 'rejected'

export interface DeedPerson {
  id: number
  full_name: string
  organization_name: string | null
  rank_name: string | null
}

/** /api/v1/spa/people/files/ */
export interface DeedRow {
  id: number
  code: string | null
  status: string
  status_display: string
  organization_name: string | null
  region_name: string | null
  date_creat: string
  file_url: string | null
  attachments_count: number
  user_edit: boolean
  overall: 'approved' | 'rejected' | 'pending'
  user: DeedPerson | null
  message_user: string | null
  sender: DeedPerson | null
  status_sender: SignStatus
  date_sender: string | null
  message_sender: string | null
  receiver: DeedPerson | null
  status_receiver: SignStatus | null
  date_receiver: string | null
  message_receiver: string | null
  consents: { id: number; employee: DeedPerson | null; status: SignStatus; date_edit: string | null; message: string | null }[]
}

/** /api/v1/notifications/ (api/notification_views.py) */
export interface NotificationRow {
  id: number
  kind: 'order' | 'deed' | 'meeting' | 'chat' | 'system'
  title: string
  body: string
  url: string
  count: number
  is_read: boolean
  date_creat: string
}

export const opts = (xs: Named[] | undefined) => (xs ?? []).map((x) => ({ value: x.id, label: x.name }))

/** Tashkilot, hudud, lavozim ro'yxatlari (ko'rish doirasi API'da: o'z tashkiloti/hududi yoki hammasi). */
export function usePeopleRefs() {
  const organizations = useQuery({ queryKey: ['people', 'organizations'], queryFn: () => apiAll<Named>('/organizations/'), staleTime: DAY })
  const regions = useQuery({ queryKey: ['people', 'regions'], queryFn: () => apiAll<Named>('/regions/'), staleTime: DAY })
  const ranks = useQuery({ queryKey: ['people', 'ranks'], queryFn: () => apiAll<Named>('/ranks/'), staleTime: DAY })
  return {
    organizationOptions: opts(sortById(organizations.data)),
    regionOptions: opts(sortById(regions.data)),
    rankOptions: opts(ranks.data),
  }
}

/** Departament → boshqarma → bo'lim zanjiri (saytdagi ajax/load-departments, load-directorate, load-division). */
export function useStructure(organization: number | string | null, region: number | string | null, department: number | string | null, directorate: number | string | null) {
  const deps = useQuery({
    queryKey: ['people', 'departments', organization, region],
    queryFn: () => apiAll<Named>('/departments/', { organization, region }),
    enabled: !!organization,
    staleTime: DAY,
  })
  const dirs = useQuery({
    queryKey: ['people', 'directorates', department],
    queryFn: () => apiAll<Named>('/directorates/', { department }),
    enabled: !!department,
    staleTime: DAY,
  })
  const divs = useQuery({
    queryKey: ['people', 'divisions', directorate],
    queryFn: () => apiAll<Named>('/divisions/', { directorate }),
    enabled: !!directorate,
    staleTime: DAY,
  })
  return {
    departmentOptions: organization ? opts(sortById(deps.data)) : [],
    directorateOptions: department ? opts(sortById(dirs.data)) : [],
    divisionOptions: directorate ? opts(sortById(divs.data)) : [],
  }
}

const dateFmt = new Intl.DateTimeFormat('ru-RU', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' })

/** ISO → "20.10.2026 14:05" (saytdagi d.m.Y H:i) */
export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return '—'
  return dateFmt.format(new Date(iso)).replace(',', '')
}

export const toId = (v: string | number | null) => (v == null || v === '' ? null : Number(v))
