import { useSearchParams } from 'react-router-dom'
import { Button, CellUser, DataTable, Pagination } from '../../ds'
import type { DataTableColumn } from '../../ds'
import DataState from '../../components/DataState'
import { useUrlFilters } from '../../lib/useUrlFilters'
import { avatarColor, initials } from '../../lib/format'
import { PAGE_SIZE, formatDate, useBarnList } from './api'
import OrderDetailModal, { DeedLinks } from './OrderDetailModal'
import type { DetailMode } from './OrderDetailModal'
import { OrderStatus } from './status'
import type { BarnOrder, BarnRole } from './types'
import { useT } from '../../i18n'

/** Jadval ustunlari — eski sahifalardagi tartibda */
export type ColumnKey = 'sender' | 'receiver' | 'user' | 'files'

interface Props {
  role: BarnRole
  mode: DetailMode
  columns: ColumnKey[]
  /** Ko'rish tugmasi matni, o'zbekcha (masalan, "Bajarish") — shu yerda tarjima qilinadi */
  actionLabel?: string
  poll?: boolean
  emptyText: string
  emptyDescription?: string
}

function person(name: string | null, id: number | null, sub?: string) {
  if (!name) return <span className="ob-muted">—</span>
  return <CellUser name={name} sub={sub} initials={initials(name)} color={avatarColor(id ?? name)} size={32} />
}

/** Arizalar ro'yxati (20 tadan, sahifalash serverda) + tafsilotlar oynasi (?order=<id> — havola bilan ochiladi). */
export default function OrdersList({ role, mode, columns, actionLabel = "Ko'rish", poll, emptyText, emptyDescription }: Props) {
  const t = useT()
  const { page, setPage } = useUrlFilters([])
  const [params, setParams] = useSearchParams()
  const list = useBarnList(role, page, { poll })
  const rows = list.data?.results ?? []
  const pageCount = Math.max(1, Math.ceil((list.data?.count ?? 0) / PAGE_SIZE))
  const openId = Number(params.get('order')) || null

  const open = (id: number | null) =>
    setParams(
      (p) => {
        if (id) p.set('order', String(id))
        else p.delete('order')
        return p
      },
      { replace: !id },
    )

  const cols: DataTableColumn<BarnOrder>[] = [
    { key: 'n', label: t('T/r'), width: 64, render: (r) => (page - 1) * PAGE_SIZE + rows.indexOf(r) + 1 },
    {
      key: 'id',
      label: t('Ariza №'),
      width: 150,
      render: (r) => (
        <div className="aui-cell-text">
          <div className="aui-cell-primary ob-id">#{r.id}</div>
          <div className="aui-cell-secondary">{r.goal_name || '—'}</div>
        </div>
      ),
    },
  ]
  if (columns.includes('sender')) cols.push({ key: 'sender', label: t('Muallif'), render: (r) => person(r.sender_name, r.sender) })
  if (columns.includes('receiver')) cols.push({ key: 'receiver', label: t('Ijrochi'), render: (r) => person(r.receiver_name, r.receiver) })
  if (columns.includes('user')) cols.push({ key: 'user', label: t('Tasdiqladi'), render: (r) => person(r.user_name, r.user) })
  cols.push(
    {
      key: 'status',
      label: t('Holati'),
      width: 150,
      render: (r) => (
        <button type="button" className="ob-row-link" onClick={() => open(r.id)} aria-label={t('#{id} ariza tafsilotlari', { id: r.id })}>
          <OrderStatus status={r.status} label={r.status_display} />
        </button>
      ),
    },
    { key: 'date', label: t('Yuborilgan sana'), width: 160, render: (r) => <span className="ob-muted">{formatDate(r.date_creat)}</span> },
  )
  if (columns.includes('files')) cols.push({ key: 'files', label: t('Fayllar'), width: 140, render: (r) => <DeedLinks deeds={r.deeds} /> })
  cols.push({
    key: 'act',
    label: '',
    width: 132,
    align: 'right',
    render: (r) => (
      <Button variant="stroke" size="sm" icon="ri-eye-line" onClick={() => open(r.id)} aria-label={`#${r.id} — ${t(actionLabel)}`}>
        {t(actionLabel)}
      </Button>
    ),
  })

  return (
    <>
      <DataState isPending={list.isPending} isFetching={list.isFetching && !poll} error={list.error} empty={rows.length === 0} emptyText={emptyText} emptyDescription={emptyDescription}>
        <DataTable rows={rows} columns={cols} getRowId={(r) => r.id} rowHeight={64} minWidth={columns.length > 2 ? 980 : 820} caption={t("Arizalar ro'yxati")} />
        {pageCount > 1 && (
          <div className="ivs-pager">
            <Pagination pageCount={pageCount} page={page} onChange={setPage} />
          </div>
        )}
      </DataState>
      {openId && <OrderDetailModal id={openId} mode={mode} onClose={() => open(null)} />}
    </>
  )
}
