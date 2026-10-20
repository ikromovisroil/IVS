import FilterBar from '../../components/FilterBar'
import EmptyState from '../../components/EmptyState'
import DatePicker from '../../components/DatePicker'
import { useEffect, useState } from 'react'
import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { Button, DataTable, Pagination, Select } from '../../ds'
import type { DataTableColumn } from '../../ds'
import Page from '../../layout/Page'
import DataState from '../../components/DataState'
import Modal from '../../components/Modal'
import SearchInput from '../../components/SearchInput'
import { API, api, withQuery } from '../../api/client'
import type { Page as ApiPage } from '../../api/client'
import { useLang, useT } from '../../i18n'
import { formatNumber } from '../../lib/format'
import { useUrlFilters } from '../../lib/useUrlFilters'
import { money } from '../technics/util'
import type { ReportRow } from './api'
import { MOVEMENT_STATUS, useReportEmployees } from './api'
import MaterialTabs from './MaterialTabs'
import '../technics/technics.css'
import './warehouse.css'

const PAGE_SIZE = 20
const FILTER_KEYS = ['employee', 'date1', 'date2', 'name'] as const

const iso = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
const DATE_TIME = { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' } as const

function Pair({ count, sum }: { count: number; sum: string | number }) {
  return (
    <div className="ivs-pair">
      <span>{formatNumber(count)}</span>
      <small>{money(sum)}</small>
    </div>
  )
}

/** "Kirim - chiqim" (main/views.py:mat_info) — xodim materiallarining davr bo'yicha harakati. */
export default function MovementsPage() {
  const t = useT()
  const { lang } = useLang()
  const dateTime = new Intl.DateTimeFormat(lang === 'ru' ? 'ru-RU' : 'uz-UZ', DATE_TIME)
  const employees = useReportEmployees()
  const { filters, page, setFilter, setPage } = useUrlFilters(FILTER_KEYS)
  const [open, setOpen] = useState<ReportRow | null>(null)
  const today = new Date()
  // Sana kiritilmagan bo'lsa — joriy oy (saytdagidek)
  const date1 = filters.date1 || iso(new Date(today.getFullYear(), today.getMonth(), 1))
  const date2 = filters.date2 || iso(today)
  const employee = filters.employee ? Number(filters.employee) : null

  // Faqat bitta xodim bo'lsa (o'zi), u avtomatik tanlanadi
  const only = employees.options.length === 1 ? employees.options[0].value : null
  useEffect(() => {
    if (only != null && !filters.employee) setFilter('employee', only)
  }, [only, filters.employee, setFilter])

  const query = { employee, date1, date2, name: filters.name }
  const report = useQuery({
    queryKey: ['warehouse', 'report', query, page],
    queryFn: () => api<ApiPage<ReportRow>>('/materials/report/', { query: { ...query, page, page_size: PAGE_SIZE } }),
    enabled: !!employee,
    placeholderData: keepPreviousData,
  })
  const rows = report.data?.results ?? []
  const pageCount = Math.max(1, Math.ceil((report.data?.count ?? 0) / PAGE_SIZE))

  const columns: DataTableColumn<ReportRow>[] = [
    { key: 'n', label: t('T/r'), width: '5%', render: (r) => (page - 1) * PAGE_SIZE + rows.indexOf(r) + 1 },
    {
      key: 'name',
      label: t('Nomi'),
      width: '25%',
      render: (r) => (
        <div className="aui-cell-text">
          <div className="aui-cell-primary">
            <a
              href="#"
              className="ivs-link"
              onClick={(e) => {
                e.preventDefault()
                setOpen(r)
              }}
            >
              {r.name}
            </a>
          </div>
          <div className="aui-cell-secondary">{r.category || '—'}</div>
        </div>
      ),
    },
    { key: 'code', label: t('Kodi'), width: '9%', render: (r) => <span className="ivs-mono">{r.code || '—'}</span> },
    { key: 'price', label: t('Narxi'), width: '10%', align: 'right', render: (r) => money(r.price) },
    { key: 'unit', label: t('Birligi'), width: '7%', render: (r) => r.unit || '—' },
    { key: 'initial', label: t("Boshlang'ich"), width: '10%', align: 'right', render: (r) => formatNumber(r.initial_balance) },
    { key: 'income', label: t('Kirim'), width: '11%', align: 'right', render: (r) => <Pair count={r.income} sum={r.income_sum} /> },
    { key: 'outcome', label: t('Chiqim'), width: '11%', align: 'right', render: (r) => <Pair count={r.outcome} sum={r.outcome_sum} /> },
    { key: 'current', label: t('Qoldiq'), align: 'right', render: (r) => <Pair count={r.current_balance} sum={r.current_sum} /> },
  ]

  const exportUrl = withQuery(`${API}/export/material-report.xlsx`, query)

  return (
    <Page icon="ri-arrow-left-right-line" title="Kirim - chiqim" subtitle="Materiallar harakati: davr boshidagi qoldiq, kirim, chiqim va joriy qoldiq.">
      <MaterialTabs />
      <FilterBar
        search={<SearchInput value={filters.name} onChange={(v) => setFilter('name', v)} placeholder="Nomi, 1C kodi..." />}
        actions={
          <Button variant="stroke" icon="ri-file-excel-2-line" disabled={!employee} onClick={() => window.location.assign(exportUrl)}>
            {t('Excel')}
          </Button>
        }
      >
        <Select aria-label={t('Xodim')} placeholder={t('Xodim')} options={employees.options} value={employee} onChange={(v) => setFilter('employee', v)} />
        <DatePicker placeholder="Boshlang'ich sana" value={date1} max={date2} onChange={(v) => setFilter('date1', v)} />
        <DatePicker placeholder="Tugash sanasi" value={date2} min={date1} onChange={(v) => setFilter('date2', v)} />
      </FilterBar>

      {!employee ? (
        <EmptyState icon="ri-user-search-line" title="Xodimni tanlang" description="Kirim-chiqim hisobotini ko‘rish uchun moddiy javobgar xodimni tanlang." />
      ) : (
        <DataState isPending={report.isPending} isFetching={report.isFetching} error={report.error} empty={rows.length === 0} emptyText="Harakat topilmadi" emptyDescription="Tanlangan davrda bu xodim bo‘yicha kirim yoki chiqim qayd etilmagan.">
          <DataTable rows={rows} columns={columns} getRowId={(r) => r.id} rowHeight={60} minWidth={980} caption={t('Materiallar harakati')} />
          {pageCount > 1 && (
            <div className="ivs-pager">
              <Pagination pageCount={pageCount} page={page} onChange={setPage} />
            </div>
          )}
        </DataState>
      )}

      {open && (
        <Modal
          open
          onClose={() => setOpen(null)}
          icon="ri-history-line"
          title="Material harakatlar tarixi"
          subtitle={`${open.name} · ${date1} — ${date2}`}
          width={860}
          footer={
            <Button size="lg" onClick={() => setOpen(null)}>
              {t('Yopish')}
            </Button>
          }
        >
          {open.movements.length ? (
            <DataTable
              rows={open.movements.map((m, i) => ({ ...m, i }))}
              getRowId={(m) => m.i}
              rowHeight={52}
              minWidth={720}
              caption={t('Harakatlar')}
              columns={[
                { key: 'i', label: t('T/r'), width: '6%', render: (m) => m.i + 1 },
                { key: 'date', label: t('Sana'), width: '17%', render: (m) => dateTime.format(new Date(m.date)) },
                { key: 'user', label: t('Kimdan'), width: '20%', render: (m) => m.user || '—' },
                { key: 'employee', label: t('Kimga'), width: '20%', render: (m) => m.employee || '—' },
                { key: 'income', label: t('Kirim'), width: '9%', align: 'right', render: (m) => m.income ?? 0 },
                { key: 'outcome', label: t('Chiqim'), width: '9%', align: 'right', render: (m) => m.outcome ?? 0 },
                { key: 'status', label: t('Holati'), render: (m) => <span title={m.body || undefined}>{lang === 'ru' && MOVEMENT_STATUS[m.status] ? t(MOVEMENT_STATUS[m.status]) : m.status_display}</span> },
              ]}
            />
          ) : (
            <EmptyState size="compact" title="Ushbu davr uchun harakat topilmadi." />
          )}
        </Modal>
      )}
    </Page>
  )
}
