import type { MouseEvent } from 'react'
import { DataTable, Pagination } from '../../ds'
import type { DataTableColumn } from '../../ds'
import DataState from '../../components/DataState'
import { useT } from '../../i18n'
import { PAGE_SIZE } from './hooks'
import type { useOrderList } from './hooks'
import type { Order } from './types'

interface OrderTableProps {
  list: ReturnType<typeof useOrderList>['list']
  page: number
  setPage: (n: number) => void
  columns: DataTableColumn<Order>[]
  onOpen: (o: Order) => void
  caption: string
  minWidth?: number
  emptyText?: string
  emptyDescription?: string
}

export default function OrderTable({ list, page, setPage, columns, onOpen, caption, minWidth = 900, emptyText = "Ma'lumot topilmadi", emptyDescription }: OrderTableProps) {
  const t = useT()
  const rows = list.data?.results ?? []
  const pageCount = Math.max(1, Math.ceil((list.data?.count ?? 0) / PAGE_SIZE))
  // Qator ustiga bosish = ⋮ tugmasi (modalni ochadi); qator ichidagi tugma/havolalar o'z ishini qiladi
  const openRow = (e: MouseEvent<HTMLDivElement>) => {
    const target = e.target as HTMLElement
    if (target.closest('button, a, input, select, textarea, label, [role="button"]')) return
    target.closest('tbody tr')?.querySelector<HTMLButtonElement>('.aui-row-menu')?.click()
  }
  return (
    <DataState isPending={list.isPending} isFetching={list.isFetching} error={list.error} empty={rows.length === 0} emptyText={emptyText} emptyDescription={emptyDescription}>
      <div className="ivs-row-click" onClick={openRow}>
        <DataTable rows={rows} columns={columns} getRowId={(r) => r.id} rowHeight={64} minWidth={minWidth} rowActions={(r) => onOpen(r)} caption={t(caption)} />
      </div>
      {pageCount > 1 && (
        <div className="ivs-pager">
          <Pagination pageCount={pageCount} page={page} onChange={setPage} />
        </div>
      )}
    </DataState>
  )
}
