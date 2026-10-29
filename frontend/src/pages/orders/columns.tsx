import { Button, CellUser, StatusChip } from '../../ds'
import type { DataTableColumn } from '../../ds'
import { avatarColor, initials } from '../../lib/format'
import type { useT } from '../../i18n'
import { PAGE_SIZE } from './hooks'
import { ORDER_STATUS, formatDateTime } from './types'
import type { Order } from './types'

/** Ustunlar: T/r, Ariza №, (Muallif | Ijrochi), Ariza maqsadi, Holati, ...qo'shimcha, Yuborilgan sana. */
export function orderColumns(opts: {
  page: number
  rows: Order[]
  person: 'sender' | 'receiver'
  onOpen: (o: Order) => void
  extra?: DataTableColumn<Order>[]
  tail?: DataTableColumn<Order>[]
  t: ReturnType<typeof useT>
}): DataTableColumn<Order>[] {
  const { page, rows, person, onOpen, extra = [], tail = [], t } = opts
  return [
    { key: 'n', label: t('T/r'), width: 56, render: (r) => (page - 1) * PAGE_SIZE + rows.indexOf(r) + 1 },
    {
      key: 'id',
      label: t('Ariza №'),
      width: 104,
      render: (r) => (
        <Button variant="ghost" size="sm" iconRight="ri-arrow-right-up-line" onClick={() => onOpen(r)} aria-label={t('#{id} ariza tafsilotlari', { id: r.id })}>
          #{r.id}
        </Button>
      ),
    },
    person === 'sender'
      ? {
          key: 'sender',
          label: t('Muallif'),
          width: '24%',
          render: (r) =>
            r.sender_name ? <CellUser name={r.sender_name} initials={initials(r.sender_name)} color={avatarColor(r.sender ?? 0)} /> : '—',
        }
      : {
          key: 'receiver',
          label: t('Ijrochi'),
          width: '22%',
          render: (r) =>
            r.receiver_name ? (
              <CellUser name={r.receiver_name} initials={initials(r.receiver_name)} color={avatarColor(r.receiver ?? 0)} />
            ) : (
              <span className="ivs-orders-muted">{t('Biriktirilmagan')}</span>
            ),
        },
    {
      key: 'goal',
      label: t('Ariza maqsadi'),
      render: (r) => (
        <div className="aui-cell-text">
          <div className="aui-cell-primary">{r.goal_name || ''}</div>
          {r.message_sender && <div className="aui-cell-secondary ivs-orders-clip">{r.message_sender}</div>}
        </div>
      ),
    },
    {
      key: 'status',
      label: t('Holati'),
      width: 150,
      render: (r) => <StatusChip status={ORDER_STATUS[r.status]}>{t(r.status_display)}</StatusChip>,
    },
    ...extra,
    { key: 'date', label: t('Yuborilgan sana'), width: 150, render: (r) => <span className="type-para-sm">{formatDateTime(r.date_creat)}</span> },
    ...tail,
  ]
}
