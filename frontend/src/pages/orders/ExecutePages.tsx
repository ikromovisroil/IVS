import { useCallback, useState } from 'react'
import EmptyState from '../../components/EmptyState'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { Button, Select, StatusChip } from '../../ds'
import type { DataTableColumn } from '../../ds'
import ConfirmDialog from '../../components/ConfirmDialog'
import { useToast } from '../../components/toast'
import type { PageTab } from '../../components/PageTabs'
import { api } from '../../api/client'
import { can, useMe } from '../../auth/me'
import { useT } from '../../i18n'
import FinishSection from './FinishSection'
import { useFinish, useOrderList, useReceiverPending, validateFinish } from './hooks'
import type { FinishState } from './hooks'
import OrderDetailModal from './OrderDetailModal'
import OrdersShell from './OrdersShell'
import OrderTable from './OrderTable'
import { openPdf } from '../../lib/pdf'
import { orderColumns } from './columns'
import type { Order, OrderDetail, OrderMaterial } from './types'
import './orders.css'

const SUBTITLE = 'ATMga kelgan arizalarni qabul qilish, bajarish va akt rasmiylashtirish.'

function useExecuteTabs(): PageTab[] {
  const badges = useReceiverPending(true)
  const pending = badges.data?.receiver_pending
  return [
    { path: '/orders/execute', label: 'Yangi arizalar', icon: 'ri-inbox-line', count: pending || undefined },
    { path: '/orders/execute/active', label: 'Qabul qilingan', icon: 'ri-tools-line' },
    { path: '/orders/execute/archive', label: 'Tarix', icon: 'ri-history-line' },
  ]
}

/** order_receiver*: faqat worker tashkiloti va 'change_order' (tabs.ts dagi shart bilan bir xil). */
function useCanExecute() {
  const me = useMe()
  return me.organization_type === 'worker' && can(me, 'main.change_order')
}

function Shell({ children }: { children: React.ReactNode }) {
  const tabs = useExecuteTabs()
  const allowed = useCanExecute()
  return (
    <OrdersShell icon="ri-tools-line" title="Arizalarni bajarish" subtitle={SUBTITLE} subTabs={tabs} subLabel="Bajarish holatlari">
      {allowed ? (
        children
      ) : (
        <EmptyState icon="ri-lock-line" title="Ruxsat yo'q" description="Bu sahifa uchun ruxsatingiz yo'q." />
      )}
    </OrdersShell>
  )
}

/* ─────────────── Yangi arizalar (order_receiver) ─────────────── */

/** order_accepted: o'ziga qabul qilish yoki (superuser) boshqa xodimga biriktirish. */
function AcceptModal({ order, onClose }: { order: Order; onClose: () => void }) {
  const t = useT()
  const me = useMe()
  const qc = useQueryClient()
  const toast = useToast()
  const navigate = useNavigate()
  const [assignee, setAssignee] = useState<number | null>(null)
  const [confirm, setConfirm] = useState<'accept' | 'reject' | null>(null)

  const candidates = useQuery({
    queryKey: ['orders', 'assignees', order.id],
    queryFn: () => api<{ id: number; full_name: string }[]>(`/orders/${order.id}/assignees/`),
    enabled: me.is_superuser,
  })

  const accept = useMutation({
    mutationFn: () => api(`/orders/${order.id}/accept/`, { method: 'POST', body: JSON.stringify(assignee ? { receiver: assignee } : {}) }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['orders'] })
      if (assignee) {
        const name = candidates.data?.find((c) => c.id === assignee)?.full_name ?? t('xodim')
        toast(t('Ariza {name}ga biriktirildi', { name }))
        onClose()
      } else {
        toast('Ariza muvaffaqiyatli qabul qilindi')
        navigate('/orders/execute/active')
      }
    },
    onError: (e) => {
      setConfirm(null)
      toast(e.message, 'error')
    },
  })

  // Rad etish: ariza "Rad etildi"ga o'tadi, sabab muallifga ko'rinadi
  const dismiss = useMutation({
    mutationFn: (message: string) =>
      api(`/orders/${order.id}/reject/`, { method: 'POST', body: JSON.stringify({ message: message || undefined }) }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['orders'] })
      toast('Ariza rad etildi')
      onClose()
    },
    onError: (e) => {
      setConfirm(null)
      toast(e.message, 'error')
    },
  })

  const footer = () => (
    <div className="ivs-orders-foot">
      {me.is_superuser && (
        <div className="ivs-orders-foot-wide">
          <Select
            label={t('Ijrochi xodim')}
            placeholder={t("O'zimga qabul qilish")}
            options={(candidates.data ?? []).map((c) => ({ value: c.id, label: c.full_name }))}
            value={assignee}
            onChange={(v) => setAssignee(v == null ? null : Number(v))}
          />
        </div>
      )}
      <Button variant="stroke" size="lg" icon="ri-close-line" onClick={onClose}>
        {t('Yopish')}
      </Button>
      <Button variant="error" size="lg" icon="ri-close-circle-line" onClick={() => setConfirm('reject')}>
        {t('Rad etish')}
      </Button>
      <Button size="lg" icon="ri-checkbox-circle-line" onClick={() => setConfirm('accept')}>
        {t(assignee ? 'Biriktirish' : 'Qabul qilish')}
      </Button>
    </div>
  )

  return (
    <>
      <OrderDetailModal id={order.id} onClose={onClose} footer={footer} />
      {confirm === 'accept' && (
        <ConfirmDialog
          title="Qabul qilishni tasdiqlang?"
          message={
            <>
              {assignee
                ? t('#{id} ariza {name}ga biriktiriladi.', { id: order.id, name: candidates.data?.find((c) => c.id === assignee)?.full_name ?? '' })
                : t(`#{id} ariza sizga biriktiriladi va "Bajarish" bo'limiga o'tadi.`, { id: order.id })}
            </>
          }
          confirmLabel="Qabul qilish"
          loading={accept.isPending}
          onConfirm={() => accept.mutate()}
          onClose={() => setConfirm(null)}
        />
      )}
      {confirm === 'reject' && (
        <ConfirmDialog
          title="Rad etishni tasdiqlang?"
          message={t('#{id} ariza rad etiladi va muallifga sabab bilan xabar beriladi.', { id: order.id })}
          reason={{ label: 'Sabab', required: true }}
          confirmLabel="Rad etish"
          danger
          loading={dismiss.isPending}
          onConfirm={(message) => dismiss.mutate(message)}
          onClose={() => setConfirm(null)}
        />
      )}
    </>
  )
}

/** /orders/execute — yangi arizalar; har 20 soniyada yangilanadi (1-sahifada va oyna yopiq bo'lsa). */
export function ExecuteNewPage() {
  const [open, setOpen] = useState<Order | null>(null)
  const close = useCallback(() => setOpen(null), [])
  const t = useT()
  // Eski sahifadagidek: oyna ochiq bo'lsa jadval yangilanmaydi
  const { list, page, setPage } = useOrderList('receiver_new', open == null)
  const rows = list.data?.results ?? []
  const columns = orderColumns({ page, rows, person: 'sender', onOpen: setOpen, t })
  return (
    <Shell>
      <OrderTable list={list} page={page} setPage={setPage} columns={columns} onOpen={setOpen} caption="Bajarish uchun yangi arizalar" emptyText="Yangi ariza yo‘q" emptyDescription="Sizga yo‘naltirilgan yangi arizalar shu yerda paydo bo‘ladi." />
      {open && <AcceptModal order={open} onClose={close} />}
    </Shell>
  )
}

/* ─────────────── Bajarish (order_receiver_activ) ─────────────── */

function FinishModal({ order, onClose }: { order: Order; onClose: () => void }) {
  const t = useT()
  const qc = useQueryClient()
  const toast = useToast()
  const [state, setState] = useState<FinishState>({ technics: order.technics, rows: [] })
  const [confirm, setConfirm] = useState(false)
  const [removing, setRemoving] = useState<OrderMaterial | null>(null)
  const finish = useFinish(order.id)

  const remove = useMutation({
    mutationFn: (m: OrderMaterial) => api(`/spa/orders/materials/${m.id}/delete/`, { method: 'POST' }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['orders'] })
      toast("Material o'chirildi va omborga qaytarildi")
      setRemoving(null)
    },
    onError: (e) => {
      setRemoving(null)
      toast(e.message, 'error')
    },
  })

  const submit = () => {
    const err = validateFinish(state)
    if (err) {
      toast(err, 'error')
      return
    }
    setConfirm(true)
  }

  const deleteColumn: DataTableColumn<OrderMaterial> = {
    key: 'del',
    label: t("O'chirish"),
    width: 96,
    align: 'center',
    render: (m) => <Button variant="error-lighter" size="sm" iconOnly icon="ri-delete-bin-line" aria-label={t("{name} — o'chirish", { name: m.material_name })} onClick={() => setRemoving(m)} />,
  }

  const footer = (o: OrderDetail) => (
    <>
      <Button variant="stroke" size="lg" icon="ri-close-line" onClick={onClose}>
        {t('Yopish')}
      </Button>
      {(o.status === 'process' || o.status === 'finished') && (
        <Button size="lg" icon="ri-checkbox-circle-line" onClick={submit}>
          {t('Yakunlash')}
        </Button>
      )}
    </>
  )

  return (
    <>
      <OrderDetailModal id={order.id} onClose={onClose} footer={footer} materialAction={deleteColumn}>
        {(o) => <FinishSection order={o} state={state} onChange={setState} />}
      </OrderDetailModal>
      {confirm && (
        <ConfirmDialog
          title="Yakunlashni tasdiqlang?"
          message={
            state.rows.some((r) => r.material != null)
              ? "Tanlangan materiallar ombordan ayriladi va arizaga biriktiriladi."
              : 'Ariza "Tayyorlandi" holatiga o\'tadi va muallifga baholash uchun yuboriladi.'
          }
          reason={{ label: 'Izoh' }}
          confirmLabel="Yakunlash"
          loading={finish.isPending}
          onConfirm={(message) =>
            finish.mutate({ ...state, message }, {
              onSuccess: () => {
                toast('Ariza muvaffaqiyatli yakunlandi')
                setConfirm(false)
                onClose()      // yakunlangach ariza oynasi yopiladi
              },
              onError: (e) => {
                setConfirm(false)
                toast(e.message, 'error')
              },
            })
          }
          onClose={() => setConfirm(false)}
        />
      )}
      {removing && (
        <ConfirmDialog
          title="Biriktirilgan materialni o'chirasizmi?"
          message={<>{t('{name} ({n} {unit}) omborga qaytariladi.', { name: removing.material_name, n: removing.number, unit: removing.unit_name || t('dona') })}</>}
          confirmLabel="O'chirish"
          danger
          loading={remove.isPending}
          onConfirm={() => remove.mutate(removing)}
          onClose={() => setRemoving(null)}
        />
      )}
    </>
  )
}

/** /orders/execute/active — o'ziga biriktirilgan (jarayonda / tayyorlangan) arizalar. */
export function ExecuteActivePage() {
  const t = useT()
  const { list, page, setPage } = useOrderList('receiver_active')
  const [open, setOpen] = useState<Order | null>(null)
  const close = useCallback(() => setOpen(null), [])
  const rows = list.data?.results ?? []
  const columns = orderColumns({ page, rows, person: 'sender', onOpen: setOpen, t })
  return (
    <Shell>
      <OrderTable list={list} page={page} setPage={setPage} columns={columns} onOpen={setOpen} caption="Bajarilayotgan arizalar" emptyText="Jarayondagi ariza yo‘q" emptyDescription="Qabul qilingan arizalar bajarilguncha shu yerda turadi." />
      {open && <FinishModal order={open} onClose={close} />}
    </Shell>
  )
}

/* ─────────────── Tarix (order_receiver_arxiv) ─────────────── */

/** /orders/execute/archive — yakunlangan arizalar, baho va aktni imzolashga yuborish. */
export function ExecuteArchivePage() {
  const t = useT()
  const navigate = useNavigate()
  const { list, page, setPage } = useOrderList('receiver_archive')
  const [open, setOpen] = useState<Order | null>(null)
  const close = useCallback(() => setOpen(null), [])
  const rows = list.data?.results ?? []
  const columns = orderColumns({
    page,
    rows,
    person: 'sender',
    onOpen: setOpen,
    t,
    extra: [{ key: 'rating', label: t('Baho'), width: 80, render: (r) => (r.rating ? `${r.rating}/5 ★` : '—') }],
    tail: [
      {
        key: 'deed',
        label: t('Imzolashga yuborish'),
        width: 210,
        render: (r) =>
          r.deeds.length ? (
            r.deeds[0].file ? (
              <Button variant="stroke" size="sm" icon="ri-file-pdf-2-line" onClick={() => openPdf(r.deeds[0].file!, t('Yuborilgan'))}>
                {t('Yuborilgan')}
              </Button>
            ) : (
              <StatusChip status="completed">{t('Yuborilgan')}</StatusChip>
            )
          ) : r.materials.length ? (
            <Button variant="success" size="sm" icon="ri-send-plane-fill" onClick={() => navigate(`/orders/execute/archive/${r.id}/deed`)}>
              {t('Yuborish')}
            </Button>
          ) : (
            <span className="type-para-sm ivs-orders-muted">{t('Mavjud emas')}</span>
          ),
      },
    ],
  })
  return (
    <Shell>
      <OrderTable list={list} page={page} setPage={setPage} columns={columns} onOpen={setOpen} caption="Bajarilgan arizalar tarixi" minWidth={1140} emptyText="Tarixda ariza yo'q" emptyDescription="Siz bajargan arizalar shu yerda saqlanadi." />
      {open && (
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
      )}
    </Shell>
  )
}

export { Shell as ExecuteShell }
