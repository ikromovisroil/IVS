import { useMemo } from 'react'
import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { CellUser, DataTable, Pagination } from '../../ds'
import type { DataTableColumn } from '../../ds'
import Page from '../../layout/Page'
import DataState from '../../components/DataState'
import { api } from '../../api/client'
import { useMe } from '../../auth/me'
import { useT } from '../../i18n'
import { avatarColor, initials } from '../../lib/format'
import { useUrlFilters } from '../../lib/useUrlFilters'
import type { MyTechnics, TechnicsRow } from './api'
import { SPA } from './api'
import { StatusTag } from './TechnicsDetail'
import './technics.css'

const PAGE_SIZE = 20

type Row =
  | { kind: 'tex'; id: string; tex: TechnicsRow; group?: number }
  | { kind: 'head'; id: string }
  | { kind: 'emp'; id: string; n: number; emp: MyTechnics['employees_without_technics'][number] }

/** "Texnikalarim" (main/views.py:technics_get): o'z texnikalari, boss_employee bo'lsa bo'limdagi barcha texnikalar. */
export default function MyTechnicsPage() {
  const t = useT()
  const me = useMe()
  const { page, setPage } = useUrlFilters([])
  const data = useQuery({
    queryKey: ['technics', 'mine', page],
    queryFn: () => api<MyTechnics>(`${SPA}/technics/mine/`, { query: { page } }),
    placeholderData: keepPreviousData,
  })
  const pageCount = Math.max(1, Math.ceil((data.data?.count ?? 0) / PAGE_SIZE))

  const rows = useMemo<Row[]>(() => {
    const list = data.data?.results ?? []
    const out: Row[] = []
    let g = 0
    list.forEach((t, i) => {
      const first = i === 0 || (list[i - 1].employee ?? 0) !== (t.employee ?? 0)
      out.push({ kind: 'tex', id: `t${t.id}`, tex: t, group: first ? ++g : undefined })
    })
    // Texnikasi yo'q xodimlar — faqat oxirgi sahifada (saytdagidek)
    const without = data.data?.employees_without_technics ?? []
    if (page >= pageCount && without.length) {
      out.push({ kind: 'head', id: 'head' })
      const base = (page - 1) * PAGE_SIZE + list.length
      without.forEach((e, i) => out.push({ kind: 'emp', id: `e${e.id}`, n: base + i + 1, emp: e }))
    }
    return out
  }, [data.data, page, pageCount])

  const person = (name: string, rank: string | null, id: number) => <CellUser name={name} sub={rank ? `"${rank}"` : undefined} initials={initials(name)} color={avatarColor(id)} />

  const columns: DataTableColumn<Row>[] = [
    {
      key: 'n',
      label: t('T/r'),
      width: '6%',
      render: (r) => (r.kind === 'tex' ? (r.group ? (page - 1) * PAGE_SIZE + r.group : '') : r.kind === 'emp' ? r.n : ''),
    },
    {
      key: 'fio',
      label: t('F.I.O'),
      width: '28%',
      render: (r) =>
        r.kind === 'head' ? (
          <span className="type-label-sm ivs-muted">{t("Texnikasi yo'q xodimlar")}</span>
        ) : r.kind === 'emp' ? (
          person(r.emp.full_name, r.emp.rank_name, r.emp.id)
        ) : !r.group ? null : r.tex.employee_name ? (
          person(r.tex.employee_name, r.tex.employee_rank, r.tex.employee ?? 0)
        ) : (
          <CellUser name={t('Biriktirilmagan#ombor')} initials="—" color="gray" />
        ),
    },
    {
      key: 'name',
      label: t('Texnika nomi'),
      width: '28%',
      render: (r) =>
        r.kind === 'emp' ? (
          <span className="ivs-muted">{t('Texnika biriktirilmagan')}</span>
        ) : r.kind === 'tex' ? (
          <div className="aui-cell-text">
            <div className="aui-cell-primary">
              <Link to={`/technics/${r.tex.id}`} className="ivs-link">
                {r.tex.name}
              </Link>
            </div>
            <div className="ivs-device-lines">
              {r.tex.extra_devices.map((d) => (
                <div key={d.id}>
                  {d.category_name ? `${d.category_name} / ` : ''}
                  {d.name}
                </div>
              ))}
            </div>
          </div>
        ) : null,
    },
    {
      key: 'inventory',
      label: t('I/R'),
      width: '14%',
      render: (r) =>
        r.kind === 'tex' ? (
          <div className="ivs-mono">
            {r.tex.inventory || '—'}
            <div className="ivs-device-lines">
              {r.tex.extra_devices.map((d) => (
                <div key={d.id}>{d.inventory || '—'}</div>
              ))}
            </div>
          </div>
        ) : null,
    },
    {
      key: 'serial',
      label: t('S/R'),
      width: '14%',
      render: (r) =>
        r.kind === 'tex' ? (
          <div className="ivs-mono">
            {r.tex.serial || '—'}
            <div className="ivs-device-lines">
              {r.tex.extra_devices.map((d) => (
                <div key={d.id}>{d.serial || '—'}</div>
              ))}
            </div>
          </div>
        ) : null,
    },
    { key: 'status', label: t('Holati'), render: (r) => (r.kind === 'tex' ? <StatusTag status={r.tex.status} label={r.tex.status_display} /> : null) },
  ]

  return (
    <Page
      icon="ri-macbook-line"
      title="Texnikalarim"
      subtitle={data.data?.is_boss ? "Bo'limingizdagi texnikalar va ularning egalari." : me.employee?.full_name || 'Sizga biriktirilgan texnikalar.'}
    >
      <DataState isPending={data.isPending} isFetching={data.isFetching} error={data.error} empty={rows.length === 0} emptyText="Sizga texnika biriktirilmagan" emptyDescription="Ombor sizga texnika biriktirganda u shu yerda ko‘rinadi." emptyIcon="ri-macbook-line">
        <DataTable rows={rows} columns={columns} getRowId={(r) => r.id} rowHeight={64} minWidth={860} caption={t('Texnikalarim')} />
        {pageCount > 1 && (
          <div className="ivs-pager">
            <Pagination pageCount={pageCount} page={page} onChange={setPage} />
          </div>
        )}
      </DataState>
    </Page>
  )
}
