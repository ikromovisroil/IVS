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
  return (
    <DataState isPending={list.isPending} isFetching={list.isFetching} error={list.error} empty={rows.length === 0} emptyText={emptyText} emptyDescription={emptyDescription}>
      <DataTable rows={rows} columns={columns} getRowId={(r) => r.id} rowHeight={64} minWidth={minWidth} rowActions={(r) => onOpen(r)} caption={t(caption)} />
      {pageCount > 1 && (
        <div className="ivs-pager">
          <Pagination pageCount={pageCount} page={page} onChange={setPage} />
        </div>
      )}
    </DataState>
  )
}
