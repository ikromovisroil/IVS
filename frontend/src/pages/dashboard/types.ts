// /api/v1/spa/dashboard/overview/ (api/spa/dashboard.py)

export interface Person {
  id: number
  name: string
  rank: string | null
  organization: string | null
}

export interface Overview {
  /** Ko'rish doirasi (standart — o'z tashkiloti): all — barcha tashkilotlar, worker — xizmat tashkiloti (ATM arizalari), client — mijoz (omborxona arizalari) */
  scope: { mode: 'all' | 'worker' | 'client'; organization: string | null; region: string | null; barn: boolean; can_widen: boolean; widened: boolean }
  period: { days: number; start: string; end: string; bucket_days: number }
  kpis: {
    orders_new: { value: number; prev: number }
    orders_done: { value: number; prev: number }
    avg_hours: { value: number | null; prev: number | null }
    deeds_pending: { value: number; stale: number }
  }
  trend: { date: string; created: number; done: number }[]
  orders_status: { viewed: number; process: number; done: number; finished: number; approved: number; closed: number }
  /** null — 'Texnikalarni ko'rish' huquqi yo'q */
  technics_status: { active: number; free: number; repair: number; defect: number } | null
  technics_groups: { name: string; count: number }[] | null
  /** null — 'Materiallarni ko'rish' huquqi yo'q */
  materials: { items: number; empty: number; total_sum: string; top: { id: number; name: string; unit: string | null; number: number }[] } | null
  top_executors: (Person & { done: number; rating: number | null })[]
  top_goals: { name: string; barn: boolean; count: number }[]
  recent_orders: {
    id: number
    goal: string | null
    sender: Person | null
    receiver: string | null
    status: string
    status_display: string
    date: string
  }[]
  deeds: {
    pending: number
    approved: number
    rejected: number
    recent: { id: number; kind: string; kind_display: string; code: string | null; signer: string | null; author: string | null; date: string }[]
  }
  totals: { employees: number; organizations: number; technics: number | null; materials: number | null }
}
