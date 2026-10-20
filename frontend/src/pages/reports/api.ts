// "Hisobotlar" bo'limi API si: /api/v1/spa/reports/ (api/spa/reports.py).
// Ma'lumot main/ajax_views.py dagi eski AJAX funksiyalaridan o'zgarishsiz keladi (data/<name>/).
import { useQuery } from '@tanstack/react-query'
import { API, ApiError, api } from '../../api/client'

export type ReportKind = 'document' | 'svod' | 'reestr' | 'akt' | 'service'

export interface ReportsMeta {
  reports: Record<ReportKind, boolean>
  has_full_region: boolean
  employee: {
    id: number
    full_name: string
    rank: string
    region_id: number | null
    region_name: string
    organization_id: number | null
    organization_name: string
  } | null
}

export interface Emp {
  id: number
  full_name: string
  rank: string
  organization_id?: number | null
  region_id?: number | null
}

export interface OrgRef {
  id: number
  name: string
  contract: string | null
}

export interface Ref {
  id: number
  name: string
}

export interface ReportForm {
  has_full_region: boolean
  user_region: number | null
  organizations?: OrgRef[]
  regions?: Ref[]
  senders?: Emp[]
  agreements?: Emp[]
  my_org?: Ref | null
  my_region?: Ref | null
  report_year?: number
  report_quarter?: string
}

export function useReportsMeta() {
  return useQuery({ queryKey: ['reports', 'meta'], queryFn: () => api<ReportsMeta>('/spa/reports/'), staleTime: 60_000 })
}

export function useReportForm(kind: ReportKind, enabled = true) {
  return useQuery({ queryKey: ['reports', 'form', kind], queryFn: () => api<ReportForm>(`/spa/reports/${kind}/form/`), enabled })
}

type Params = Record<string, string | number | null | undefined | (string | number)[]>

function qs(params: Params): string {
  const q = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) {
    if (Array.isArray(v)) v.forEach((x) => q.append(k, String(x)))
    else if (v !== undefined && v !== null) q.set(k, String(v))
  }
  return q.toString()
}

/** main/ajax_views.py dagi funksiya natijasi (departments, signatories, svod-materials, ...). */
export function reportData<T>(name: string, params: Params): Promise<T> {
  return api<T>(`/spa/reports/data/${name}/?${qs(params)}`)
}

/** Select uchun to'liq ro'yxat: ajax_load_departments → {results: [{id, name}]} */
export function useDepartments(organization: number | null, region: number | null, enabled = true) {
  return useQuery({
    queryKey: ['reports', 'departments', organization, region],
    queryFn: () => reportData<{ results: Ref[] }>('departments', { organization, region }).then((d) => d.results),
    enabled: enabled && !!organization,
  })
}

/** Imzolovchi (ajax_dep_signatory) yoki kelishuvchilar (ajax_dep_negotiator) ro'yxati. */
export function useOrgEmployees(name: 'signatories' | 'negotiators', organization: number | null, department: number | null, enabled = true) {
  return useQuery({
    queryKey: ['reports', name, organization, department],
    queryFn: () => reportData<Emp[]>(name, { organization, department }),
    enabled: enabled && (!!organization || !!department),
  })
}

function csrfToken(): string {
  const m = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/)
  return m ? decodeURIComponent(m[1]) : ''
}

/** main.ajax_views.download_pdf — tahrirlagichdagi HTML ni PDF qilib yuklab beradi. */
export async function downloadPdf(bodyHtml: string, orientation: 'Portrait' | 'Landscape', filename: string) {
  const res = await fetch(`${API}/spa/reports/pdf/`, {
    method: 'POST',
    credentials: 'same-origin',
    headers: { 'X-CSRFToken': csrfToken(), 'X-Requested-With': 'XMLHttpRequest' },
    body: new URLSearchParams({ body_html: bodyHtml, orientation, filename }),
  })
  const type = res.headers.get('content-type') || ''
  if (!res.ok) {
    const data = type.includes('json') ? await res.json() : null
    throw new ApiError(res.status, data && typeof data === 'object' && 'error' in data ? { detail: data.error } : data)
  }
  if (!type.includes('application/pdf')) throw new Error("Server PDF o'rniga boshqa formatda javob qaytardi")
  const url = URL.createObjectURL(await res.blob())
  const a = document.createElement('a')
  a.href = url
  a.download = `${filename}_${Date.now()}.pdf`
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}

/** UTF-8 matnni Base64 ga (eski forma: body_encoded — WAF chetlab o'tish uchun). */
export function encodeBody(html: string): string {
  const bytes = new TextEncoder().encode(html)
  let bin = ''
  bytes.forEach((b) => (bin += String.fromCharCode(b)))
  return btoa(bin)
}

/** main/views.py dagi *_post — Deed yaratib imzolashga yuboradi. */
export function submitReport(kind: ReportKind, form: FormData) {
  return api<{ detail: string }>(`/spa/reports/${kind}/submit/`, { method: 'POST', body: form })
}

const ERR: Record<number, string> = { 404: "So'rov yo'li topilmadi (404)", 500: 'Server xatoligi (500)', 403: "Ruxsat yo'q (403)", 400: "Noto'g'ri so'rov (400)" }
export const errText = (e: unknown) => (e instanceof ApiError && ERR[e.status]) || 'Xatolik yuz berdi'
