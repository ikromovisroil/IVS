// "Ombor" bo'limi: /api/v1/spa/warehouse/ (api/spa/warehouse.py) javob turlari va umumiy so'rovlar.
import { useQuery } from '@tanstack/react-query'
import { api, apiAll } from '../../api/client'
import type { Named, Technics, TechnicsStatus } from '../../api/types'
import { sortById } from '../../lib/format'

export const SPA = '/spa/warehouse'

export interface ExtraDevice {
  id: number
  name: string
  category_name: string | null
  parametr: string | null
  inventory: string | null
  serial: string | null
  year: string | null
  price: string | null
  status: TechnicsStatus
  status_display: string
}

/** TechnicsSerializer + lavozim va qurilma kategoriyasi (spa/warehouse/technics/) */
export interface TechnicsRow extends Technics {
  region: number | null
  department: number | null
  directorate: number | null
  directorate_name: string | null
  division: number | null
  division_name: string | null
  employee_rank: string | null
  qr_code: string | null
  date_creat: string
  extra_devices: ExtraDevice[]
}

export interface TechnicsStats {
  total: number
  active: number
  free: number
  repair: number
  defect: number
}

export interface TechnicsCard {
  id: number
  name: string
  category_name: string | null
  parametr: string | null
  inventory: string | null
  serial: string | null
  mac: string | null
  ip: string | null
  employee_name: string | null
  status: TechnicsStatus
  status_display: string
  qr_code: string | null
  extra_devices: ExtraDevice[]
}

export interface MyTechnics {
  count: number
  is_boss: boolean
  results: TechnicsRow[]
  employees_without_technics: { id: number; full_name: string; rank_name: string | null }[]
}

/** Bridge javobi (main/views.py funksiyalari qoldirgan xabarlar) */
export interface BridgeResult {
  ok: boolean
  detail: string
  messages: { level: string; text: string }[]
}

const DAY = 24 * 60 * 60 * 1000
const HOUR = 60 * 60 * 1000
/** Tuzilma ro'yxatlari (hudud, departament, boshqarma, bo'lim): id bo'yicha */
export const toOptions = (xs: Named[] | undefined) => sortById(xs).map((x) => ({ value: x.id, label: x.name }))

/** Hududlar (ko'rish doirasi bo'yicha) */
export function useRegions() {
  return useQuery({ queryKey: ['regions'], queryFn: () => apiAll<Named>('/regions/'), staleTime: DAY })
}

/** Departament → boshqarma → bo'lim zanjiri (saytdagi ajax_load_* o'rniga /api/v1/ ro'yxatlari). */
export function useOrgTree(p: { organization?: number | null; region?: number | null; department?: number | null; directorate?: number | null }) {
  const departments = useQuery({
    queryKey: ['technics', 'departments', p.organization, p.region],
    queryFn: () => apiAll<Named>('/departments/', { organization: p.organization, region: p.region }),
    enabled: !!p.organization,
    staleTime: HOUR,
  })
  const directorates = useQuery({
    queryKey: ['technics', 'directorates', p.department],
    queryFn: () => apiAll<Named>('/directorates/', { department: p.department }),
    enabled: !!p.department,
    staleTime: HOUR,
  })
  const divisions = useQuery({
    queryKey: ['technics', 'divisions', p.directorate],
    queryFn: () => apiAll<Named>('/divisions/', { directorate: p.directorate }),
    enabled: !!p.directorate,
    staleTime: HOUR,
  })
  return {
    departments: p.organization ? toOptions(departments.data) : [],
    directorates: p.department ? toOptions(directorates.data) : [],
    divisions: p.directorate ? toOptions(divisions.data) : [],
  }
}

/** Tashkilot (va hudud) xodimlari — main/ajax_views.py:ajax_employees_org */
export function useOrgEmployees(organization: number | null, region: number | null) {
  return useQuery({
    queryKey: ['technics', 'employees', organization, region],
    queryFn: () =>
      api<{ results: { id: number; text: string }[] }>(`${SPA}/employees/`, { query: { organization, region } }).then((d) =>
        d.results.map((e) => ({ value: e.id, label: e.text })),
      ),
    enabled: !!organization || !!region,
    staleTime: 5 * 60 * 1000,
  })
}
