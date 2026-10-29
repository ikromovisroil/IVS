import { useCallback, useState } from 'react'
import EmptyState from '../../components/EmptyState'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Button, CellUser } from '../../ds'
import ConfirmDialog from '../../components/ConfirmDialog'
import { useToast } from '../../components/toast'
import type { PageTab } from '../../components/PageTabs'
import { api } from '../../api/client'
import { can, useMe } from '../../auth/me'
import { avatarColor, initials } from '../../lib/format'
import { useT } from '../../i18n'
import CreateOrderModal from './CreateOrderModal'
import OrderDetailModal from './OrderDetailModal'
import OrdersShell from './OrdersShell'
import OrderTable from './OrderTable'
import { orderColumns } from './columns'
import { useOrderList } from './hooks'
import type { Order, OrderDetail, OrderRole } from './types'
import './orders.css'

function useSentTabs(): PageTab[] {
  const me = useMe()
  return [
    { path: '/orders/sent', label: 'Arizalar', icon: 'ri-file-list-3-line' },
    { path: '/orders/sent/archive', label: 'Tarix', icon: 'ri-history-line' },
    ...(can(me, 'main.add_order') ? [{ path: '/orders/sent/on-behalf', label: 'Ariza berish', icon: 'ri-user-shared-line' }] : []),
  ]
}

/** Xizmat sifatini baholash (1–5 yulduz). */
function RatingPicker({ value, onChange }: { value: number; onChange: (v: number) => void }) {
  const t = useT()
  return (
    <div className="ivs-orders-rate" role="radiogroup" aria-label={t('Xizmat sifatini baholang')}>
      <span className="type-label-sm">{t('Xizmat sifatini baholang!')}</span>
      <div className="ivs-orders-stars is-input">
        {[1, 2, 3, 4, 5].map((i) => (
          <Button
            key={i}
            variant="ghost"
            size="md"
            iconOnly
            icon={i <= value ? 'ri-star-fill' : 'ri-star-line'}
            className={i <= value ? 'is-on' : undefined}
            role="radio"
            aria-checked={i === value}
            aria-label={t('{n} yulduz', { n: i })}
            title={t('{n} yulduz', { n: i })}
            onClick={() => onChange(i)}
          />
        ))}
      </div>
    </div>
  )
}

/** order_decide: yuboruvchi (yoki nomidan yuborgan xodim) — bajarilgan arizani baho bilan qabul qiladi yoki bekor qiladi. */
function DecideModal({ order, onClose }: { order: Order; onClose: () => void }) {
  const t = useT()
  const qc = useQueryClient()
  const toast = useToast()
  const [rating, setRating] = useState(0)
  const [confirmCancel, setConfirmCancel] = useState(false)

  const decide = useMutation({
    mutationFn: (body: { action: 'accepted' | 'canceled'; rating?: number }) =>
      api(`/orders/${order.id}/decide/`, { method: 'POST', body: JSON.stringify(body) }),
    onSuccess: (_, body) => {
      qc.invalidateQueries({ queryKey: ['orders'] })
      toast(body.action === 'canceled' ? 'Ariza bekor qilindi' : 'Ariza qabul qilindi')
      onClose()
    },
    onError: (e) => {
      setConfirmCancel(false)
      toast(e.message, 'error')
    },
  })

  const footer = (o: OrderDetail) => (
    <>
      <Button variant="stroke" size="lg" icon="ri-close-line" onClick={onClose}>
        {t('Yopish')}
      </Button>
      {(o.status === 'viewed' || o.status === 'process') && (
        <Button variant="error" size="lg" icon="ri-close-circle-line" onClick={() => setConfirmCancel(true)}>
          {t('Arizani bekor qilish')}
        </Button>
      )}
      {o.status === 'finished' && (
        <Button
          size="lg"
          icon="ri-checkbox-circle-line"
          disabled={!rating}
          title={rating ? undefined : t('Avval xizmat sifatini baholang')}
          loading={decide.isPending}
          onClick={() => decide.mutate({ action: 'accepted', rating })}
        >
          {t('Qabul qilish')}
        </Button>
      )}
    </>
  )

  return (
    <>
      <OrderDetailModal id={order.id} onClose={onClose} footer={footer} showRating>
        {(o) => (o.status === 'finished' ? <RatingPicker value={rating} onChange={setRating} /> : null)}
      </OrderDetailModal>
      {confirmCancel && (
        <ConfirmDialog
          title={t('#{id} arizani bekor qilasizmi?', { id: order.id })}
          message="Bekor qilingan ariza tarixga o'tadi va bajarilmaydi."
          confirmLabel="Arizani bekor qilish"
          danger
          loading={decide.isPending}
          onConfirm={() => decide.mutate({ action: 'canceled' })}
          onClose={() => setConfirmCancel(false)}
        />
      )}
    </>
  )
}

function SentList({ role, onBehalf = false }: { role: OrderRole; onBehalf?: boolean }) {
  const { list, page, setPage } = useOrderList(role)
  const [open, setOpen] = useState<Order | null>(null)
  const close = useCallback(() => setOpen(null), [])
  const rows = list.data?.results ?? []
  const archive = role === 'sender_archive'
  const t = useT()

  const columns = orderColumns({
    page,
    rows,
    person: 'receiver',
    onOpen: setOpen,
    t,
    extra: [
      ...(onBehalf
        ? [
            {
              key: 'author',
              label: t('Muallif'),
              width: '20%',
              render: (r: Order) =>
                r.sender_name ? <CellUser name={r.sender_name} initials={initials(r.sender_name)} color={avatarColor(r.sender ?? 0)} /> : '—',
            },
          ]
        : []),
      ...(archive
        ? [{ key: 'rating', label: t('Baho'), width: 80, render: (r: Order) => (r.rating ? `${r.rating}/5 ★` : null) }]
        : []),
    ],
  })

  return (
    <>
      <OrderTable list={list} page={page} setPage={setPage} columns={columns} onOpen={setOpen} caption="ATMga yuborilgan arizalar"
        minWidth={onBehalf ? 1080 : 900}
        emptyText={archive ? "Tarixda ariza yo'q" : "Faol ariza yo'q"}
        emptyDescription={archive ? 'Bajarilgan va yopilgan arizalar shu yerda saqlanadi.' : 'Texnik muammo bo‘lsa, «Ariza yaratish» orqali ATMga ariza yuboring.'}
      />
      {open &&
        (archive ? (
          <OrderDetailModal
            id={open.id}
            onClose={close}
            showRating
            footer={() => (
              <Button variant="stroke" size="lg" onClick={close}>
                {t('Yopish')}
              </Button>
            )}
          />
        ) : (
          <DecideModal order={open} onClose={close} />
        ))}
    </>
  )
}

const SUBTITLE = 'ATM (Axborot texnologiyalari markazi)ga yuborilgan texnik xizmat arizalari.'

/** /orders/sent — order_sender: yangi, jarayonda va tayyorlangan arizalar. */
export function SentPage() {
  const t = useT()
  const tabs = useSentTabs()
  const [creating, setCreating] = useState(false)
  return (
    <OrdersShell
      icon="ri-send-plane-line"
      title="ATMga arizalar"
      subtitle={SUBTITLE}
      subTabs={tabs}
      subLabel="Yuborilgan arizalar"
      actions={
        <Button size="lg" icon="ri-add-line" onClick={() => setCreating(true)}>
          {t('Ariza yaratish')}
        </Button>
      }
    >
      <SentList role="sender" />
      {creating && <CreateOrderModal onClose={() => setCreating(false)} />}
    </OrdersShell>
  )
}

/** /orders/sent/archive — order_sender_arxiv: tasdiqlangan, qabul qilingan, bekor qilingan, rad etilgan. */
export function SentArchivePage() {
  const tabs = useSentTabs()
  return (
    <OrdersShell icon="ri-send-plane-line" title="ATMga arizalar" subtitle={SUBTITLE} subTabs={tabs} subLabel="Yuborilgan arizalar">
      <SentList role="sender_archive" />
    </OrdersShell>
  )
}

/** /orders/sent/on-behalf — order_sender_user: boshqa xodim nomidan berilgan arizalar ('add_order'). */
export function OnBehalfPage() {
  const t = useT()
  const me = useMe()
  const tabs = useSentTabs()
  const [creating, setCreating] = useState(false)
  if (!can(me, 'main.add_order')) {
    return (
      <OrdersShell icon="ri-send-plane-line" title="ATMga arizalar" subtitle={SUBTITLE} subTabs={tabs} subLabel="Yuborilgan arizalar">
        <EmptyState icon="ri-lock-line" title="Ruxsat yo'q" description="Bu sahifa uchun ruxsatingiz yo'q." />
      </OrdersShell>
    )
  }
  return (
    <OrdersShell
      icon="ri-send-plane-line"
      title="ATMga arizalar"
      subtitle="Xodimlar nomidan (masalan, telefon orqali) berilgan arizalar."
      subTabs={tabs}
      subLabel="Yuborilgan arizalar"
      actions={
        <Button size="lg" icon="ri-add-line" onClick={() => setCreating(true)}>
          {t('Ariza yaratish')}
        </Button>
      }
    >
      <SentList role="sender_user" onBehalf />
      {creating && <CreateOrderModal onBehalf onClose={() => setCreating(false)} />}
    </OrdersShell>
  )
}
