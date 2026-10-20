import FilterBar from '../../components/FilterBar'
import EmptyState from '../../components/EmptyState'
import { useState } from 'react'
import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { Button, CellUser, DataTable, Icon, Pagination, Widget } from '../../ds'
import type { DataTableColumn } from '../../ds'
import Page from '../../layout/Page'
import Modal from '../../components/Modal'
import { api, withQuery } from '../../api/client'
import { avatarColor, formatNumber, initials } from '../../lib/format'
import { useT } from '../../i18n'
import { EMPTY_STRUCTURE, STRUCTURE_KEYS, formatDate, pickQuery, useParamState } from './shared'
import type { Structure } from './shared'
import { DateRange, Stat, StatsTabs, StructureFilters } from './ui'
import './stats.css'

interface Row {
  id: number
  full_name: string
  rank: string | null
  department: string | null
  directorate: string | null
  division: string | null
  order_count: number
}
interface OrgStats {
  filters: Structure & { date1: string; date2: string }
  names: Record<string, string | null>
  kind_label: string
  searched: boolean
  message: string | null
  totals: { employees: number; orders: number; active_senders: number }
  count: number
  page?: number
  page_size: number
  results: Row[]
}
interface EmployeeOrders {
  employee: { id: number; full_name: string; rank: string; organization: string; department: string; directorate: string; division: string }
  kind: string
  date1: string
  date2: string
  items: { goal_id: number; goal: string; count: number }[]
  total: number
}

const KEYS = [...STRUCTURE_KEYS, 'date1', 'date2', 'page'] as const

/** Qator bosilganda: xodimning tanlangan davrdagi arizalari kategoriyalar bo'yicha (main.views.org_status_employee). */
function EmployeeOrdersModal({ id, date1, date2, onClose }: { id: number; date1: string; date2: string; onClose: () => void }) {
  const t = useT()
  const q = useQuery({
    queryKey: ['stats', 'org-employee', id, date1, date2],
    queryFn: () => api<EmployeeOrders>(withQuery(`/spa/stats/organizations/employee/${id}/`, { date1, date2 })),
  })
  const e = q.data?.employee
  const sub = e ? [e.rank, e.department, e.directorate, e.division].filter(Boolean).join(' · ') : undefined
  const columns: DataTableColumn<EmployeeOrders['items'][number]>[] = [
    { key: 'n', label: t('T/r'), width: 56, render: (r) => (q.data?.items.indexOf(r) ?? 0) + 1 },
    { key: 'goal', label: t('Ariza kategoriyasi'), render: (r) => r.goal },
    { key: 'count', label: t('Soni'), align: 'right', width: 90, render: (r) => (r.count ? <b>{r.count}</b> : <span className="st-muted">0</span>) },
  ]

  return (
    <Modal
      open
      onClose={onClose}
      icon="ri-user-line"
      title={q.isError ? 'Xatolik' : (e?.full_name ?? 'Yuklanmoqda…')}
      subtitle={sub || undefined}
      width={760}
      footer={
        <Button variant="stroke" size="lg" onClick={onClose}>
          {t('Yopish')}
        </Button>
      }
    >
      {q.isError ? (
        <div className="ivs-empty" role="alert">
          {t("Ma'lumotni yuklab bo'lmadi")}
        </div>
      ) : q.isPending ? (
        <div className="ivs-empty" aria-busy="true">
          {t('Yuklanmoqda…')}
        </div>
      ) : q.data.items.length === 0 ? (
        <EmptyState title="Kategoriyalar topilmadi" />
      ) : (
        <>
          <p className="type-para-sm st-muted st-modal-note">
            {t(`${q.data.kind} yuborilgan arizalar`)}
            {(q.data.date1 || q.data.date2) && `, ${formatDate(q.data.date1) || '…'} — ${formatDate(q.data.date2) || '…'}`}
          </p>
          <DataTable rows={q.data.items} columns={columns} getRowId={(r) => r.goal_id} rowHeight={44} minWidth={0} caption={t('Ariza kategoriyalari')} />
          <div className="st-modal-total type-label-md">
            <span>{t('Jami:')}</span>
            <span>{formatNumber(q.data.total)}</span>
          </div>
        </>
      )}
    </Modal>
  )
}

export default function OrganizationsStatsPage() {
  const t = useT()
  const { params, set } = useParamState()
  const [openId, setOpenId] = useState<number | null>(null)
  const qs = pickQuery(params, KEYS)
  const page = Math.max(1, Number(params.get('page') ?? 1) || 1)

  const stats = useQuery({
    queryKey: ['stats', 'organizations', qs],
    queryFn: () => api<OrgStats>(`/spa/stats/organizations/${qs ? `?${qs}` : ''}`),
    placeholderData: keepPreviousData,
  })
  const data = stats.data
  const structure = Object.fromEntries(STRUCTURE_KEYS.map((k) => [k, params.get(k) ?? ''])) as Structure
  // Sana berilmasa server joriy oyni oladi — maydonlarda javobdagi sanalar ko'rinadi
  const hasDates = params.has('date1') || params.has('date2')
  const dates = {
    date1: hasDates ? (params.get('date1') ?? '') : (data?.filters.date1 ?? ''),
    date2: hasDates ? (params.get('date2') ?? '') : (data?.filters.date2 ?? ''),
  }
  const update = (patch: Partial<Structure & typeof dates>) => set({ ...EMPTY_STRUCTURE, ...structure, ...dates, ...patch })

  const rows = data?.results ?? []
  const start = (page - 1) * (data?.page_size ?? 20)
  const pageCount = Math.max(1, Math.ceil((data?.count ?? 0) / (data?.page_size ?? 20)))
  const names = data?.names
  const crumbs = data?.searched && names ? [names.organization, names.region, names.department, names.directorate, names.division].filter(Boolean) : []

  const columns: DataTableColumn<Row>[] = [
    { key: 'n', label: t('T/r'), width: 56, render: (r) => start + rows.indexOf(r) + 1 },
    {
      key: 'full_name',
      label: t('F.I.O'),
      width: '26%',
      render: (r) => <CellUser name={r.full_name} sub={r.rank ?? undefined} initials={initials(r.full_name)} color={avatarColor(r.id)} size={32} />,
    },
    { key: 'rank', label: t('Lavozim'), render: (r) => r.rank ?? '—' },
    { key: 'department', label: t('Departament'), render: (r) => r.department ?? '—' },
    { key: 'directorate', label: t('Boshqarma'), render: (r) => r.directorate ?? '—' },
    { key: 'division', label: t("Bo'lim"), render: (r) => r.division ?? '—' },
    {
      key: 'order_count',
      label: t('Soni'),
      align: 'right',
      width: 96,
      render: (r) => (
        <Button variant="lighter" size="sm" iconRight="ri-arrow-right-s-line" title={t("Kategoriyalar bo'yicha ko'rish")} onClick={() => setOpenId(r.id)}>
          {formatNumber(r.order_count)}
        </Button>
      ),
    },
  ]

  return (
    <Page icon="ri-pie-chart-line" title="Statistika" subtitle="Tanlangan tuzilmadagi xodimlar va ularning arizalari.">
      <StatsTabs />

      <FilterBar layout="grid">
        <StructureFilters value={structure} onChange={update} required={!!data?.message && !data.searched} />
        <DateRange date1={dates.date1} date2={dates.date2} onChange={update} />
      </FilterBar>

      {data?.message && (
        <div className="st-note" role="status">
          <Icon name="ri-information-line" size={20} />
          {t(data.message)}
        </div>
      )}

      {stats.isError ? (
        <div className="ivs-empty" role="alert">
          {stats.error.message}
        </div>
      ) : stats.isPending ? (
        <div className="ivs-empty" aria-busy="true">
          {t('Yuklanmoqda…')}
        </div>
      ) : (
        <div className={stats.isFetching ? 'ivs-loading' : undefined}>
          <div className="aui-stats st-stats st-stats-3">
            <Stat label={t('Xodimlar')} value={data?.totals.employees} />
            <Stat label={t('Ariza bergan xodimlar')} value={data?.totals.active_senders} />
            <Stat label={data?.kind_label ? t(`${data.kind_label} yuborilgan arizalar`) : t('Yuborilgan arizalar')} value={data?.totals.orders} />
          </div>

          <Widget
            icon="ri-building-line"
            title={crumbs.length ? crumbs.join(' / ') : t('Xodimlar')}
            extra={data?.searched ? <span className="type-para-xs st-muted">{t('{n} ta xodim', { n: formatNumber(data.count) })}</span> : undefined}
          >
            {rows.length === 0 ? (
              <EmptyState icon="ri-search-line" title={data?.searched ? "Ma'lumot topilmadi" : 'Tashkilot va hududni tanlang'} />
            ) : (
              <>
                <DataTable
                  rows={rows}
                  columns={columns}
                  getRowId={(r) => r.id}
                  rowHeight={56}
                  minWidth={900}
                  caption={t('Ariza bergan xodimlar')}
                />
                <p className="type-para-xs st-muted">{t("Kategoriyalar bo'yicha ko'rish uchun soni ustiga bosing.")}</p>
              </>
            )}
            {pageCount > 1 && (
              <Pagination pageCount={pageCount} page={page} onChange={(p) => set({ page: p > 1 ? String(p) : null })} />
            )}
          </Widget>
        </div>
      )}

      {openId !== null && <EmployeeOrdersModal id={openId} date1={dates.date1} date2={dates.date2} onClose={() => setOpenId(null)} />}
    </Page>
  )
}
