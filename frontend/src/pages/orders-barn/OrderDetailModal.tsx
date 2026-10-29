import DatePicker from '../../components/DatePicker'
import { useState } from 'react'
import type { ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'
import { Button, DataTable, Icon, TextInput } from '../../ds'
import type { DataTableColumn } from '../../ds'
import { openPdf } from '../../lib/pdf'
import Modal from '../../components/Modal'
import ConfirmDialog from '../../components/ConfirmDialog'
import { api } from '../../api/client'
import { useMe } from '../../auth/me'
import { formatNumber } from '../../lib/format'
import { SPA, formatDate, mediaPath, useBarnMutation, useOrderDetail } from './api'
import { OrderStatus } from './status'
import type { BarnOrderDetail, Person } from './types'
import { useT } from '../../i18n'
import { useCtxT } from './i18n'

/**
 * Qaysi sahifadan ochilgani — pastki tugmalar va materiallar jadvali shunga qarab:
 *  sender  — yuboruvchi (Bekor qilish / Qabul qilish)            — order_sender_barn
 *  view    — faqat ko'rish (tarix sahifalari)                       — *_arxiv_barn, order_agrement_arxiv
 *  review  — omborxonachi, yangi ariza (Rad etish / Qabul qilish)   — order_receiver_barn
 *  finish  — omborxonachi, materiallarni berish (Yakunlash)         — order_receiver_activ_barn
 *  confirm — tasdiqlovchi (Bekor qilish / Tasdiqlash)               — order_agrement
 */
export type DetailMode = 'sender' | 'view' | 'review' | 'finish' | 'confirm'

type Om = BarnOrderDetail['materials'][number]

interface Pending {
  title: string
  /** Satr — o'zbekcha kalit (ConfirmDialog tarjima qiladi); o'zgaruvchili matn — tayyor tugun */
  message: ReactNode
  label: string
  danger?: boolean
  run: () => void
}

export default function OrderDetailModal({ id, mode, onClose }: { id: number; mode: DetailMode; onClose: () => void }) {
  const t = useT()
  const detail = useOrderDetail(id)
  return detail.data ? (
    <DetailBody key={detail.data.id} order={detail.data} mode={mode} onClose={onClose} />
  ) : (
    <Modal open onClose={onClose} icon="ri-file-text-line" title={t('Ariza tafsilotlari #{id}', { id })}>
      <div className="ivs-empty" role={detail.isError ? 'alert' : undefined} aria-busy={detail.isPending}>
        {detail.isError ? t(detail.error.message) : t('Yuklanmoqda…')}
      </div>
    </Modal>
  )
}

function DetailBody({ order, mode, onClose }: { order: BarnOrderDetail; mode: DetailMode; onClose: () => void }) {
  const me = useMe()
  const t = useT()
  const ct = useCtxT()
  const navigate = useNavigate()
  const [pending, setPending] = useState<Pending | null>(null)
  const [date, setDate] = useState('')
  const [given, setGiven] = useState<Record<number, string>>(() =>
    Object.fromEntries(order.materials.map((m) => [m.id, String(m.given || m.number)])),
  )
  const [error, setError] = useState('')

  const editable = (mode === 'finish' && ['process', 'finished'].includes(order.status)) || (mode === 'confirm' && order.status === 'finished')
  // ordermaterial_delete faqat arizani qabul qilgan xodimga ruxsat beradi
  const canDelete = editable && order.receiver === me.employee?.id
  const closeAll = () => {
    setPending(null)
    onClose()
  }

  const post = (path: string, body?: unknown) => api<unknown>(path, { method: 'POST', body: body === undefined ? undefined : JSON.stringify(body) })

  const decide = useBarnMutation(
    (action: 'canceled' | 'accepted') => post(`/orders/${order.id}/decide/`, { action }),
    (a) => (a === 'canceled' ? 'Ariza bekor qilindi' : 'Ariza yakunlandi'),
    closeAll,
  )
  const review = useBarnMutation(
    (action: 'process' | 'rejected') => post(`/orders/${order.id}/${action === 'process' ? 'accept' : 'reject'}/`),
    (a) => (a === 'process' ? 'Ariza qabul qilindi' : 'Ariza rad etildi'),
  )
  const finish = useBarnMutation(
    (items: { ordermaterial_id: number; given: number }[]) => post(`/orders/${order.id}/finish/`, { items, date }),
    'Ariza tasdiqlandi',
    closeAll,
  )
  const confirm = useBarnMutation(
    (v: { action: 'approved' | 'rejected'; items?: { ordermaterial_id: number; given: number }[] }) => post(`/orders/${order.id}/confirm/`, v),
    (v) => (v.action === 'approved' ? 'Ariza tasdiqlandi' : 'Ariza rad etildi. Materiallar omborga qaytarildi'),
  )
  const removeOm = useBarnMutation((omId: number) => post(`${SPA}/order-materials/${omId}/delete/`), "Material o'chirildi", () => setPending(null))

  const busy = decide.isPending || review.isPending || finish.isPending || confirm.isPending || removeOm.isPending

  /** Kiritilgan sonlarni tekshiradi: finish — kamida 1 (order_material_barn), confirm — 0 ham mumkin. */
  const items = (min: number) => {
    const out: { ordermaterial_id: number; given: number }[] = []
    for (const m of order.materials) {
      const raw = (given[m.id] ?? '').trim()
      const n = Number(raw)
      if (!raw || !Number.isInteger(n) || n < min) {
        setError(
          min === 1
            ? t("{name} uchun beriladigan son kamida 1 bo'lishi kerak", { name: m.material_name })
            : t("{name} uchun beriladigan son manfiy bo'lmasligi kerak", { name: m.material_name }),
        )
        return null
      }
      out.push({ ordermaterial_id: m.id, given: n })
    }
    setError('')
    return out
  }

  const ask = (p: Pending) => setPending(p)

  const footer: ReactNode = (() => {
    const dismiss = (
      <Button variant="stroke" size="lg" icon="ri-close-line" onClick={onClose}>
        {t('Yopish')}
      </Button>
    )
    if (mode === 'sender')
      return (
        <>
          {dismiss}
          {['viewed', 'process'].includes(order.status) && (
            <Button
              variant="error"
              size="lg"
              icon="ri-close-circle-line"
              loading={decide.isPending && decide.variables === 'canceled'}
              disabled={busy}
              onClick={() =>
                ask({ title: 'Arizani bekor qilish', message: <>{t('#{id} arizani bekor qilasizmi?', { id: order.id })}</>, label: ct('Bekor qilish', 'ariza'), danger: true, run: () => decide.mutate('canceled') })
              }
            >
              {ct('Bekor qilish', 'ariza')}
            </Button>
          )}
          {order.status === 'approved' && (
            <Button
              size="lg"
              icon="ri-checkbox-circle-line"
              loading={decide.isPending && decide.variables === 'accepted'}
              disabled={busy}
              onClick={() =>
                ask({
                  title: 'Materiallarni qabul qilish',
                  message: 'Materiallarni olganingizni tasdiqlaysizmi? Ariza yakunlanadi va akt yaratiladi.',
                  label: 'Qabul qilish',
                  run: () => decide.mutate('accepted'),
                })
              }
            >
              {t('Qabul qilish')}
            </Button>
          )}
        </>
      )
    if (mode === 'review')
      return (
        <>
          <Button
            variant="error"
            size="lg"
            icon="ri-close-circle-line"
            disabled={busy}
            loading={review.isPending && review.variables === 'rejected'}
            onClick={() =>
              ask({ title: 'Rad etish', message: 'Rad etishni tasdiqlang?', label: 'Rad etish', danger: true, run: () => review.mutate('rejected', { onSuccess: closeAll }) })
            }
          >
            {t('Rad etish')}
          </Button>
          <Button
            variant="success"
            size="lg"
            icon="ri-checkbox-circle-line"
            disabled={busy}
            loading={review.isPending && review.variables === 'process'}
            onClick={() =>
              ask({
                title: 'Qabul qilish',
                message: 'Qabul qilishni tasdiqlang?',
                label: 'Qabul qilish',
                // eski order_accepted_barn: qabul qilingach "Bajarish" sahifasiga o'tadi
                run: () => review.mutate('process', { onSuccess: () => (closeAll(), navigate('/orders/barn-execute/active')) }),
              })
            }
          >
            {t('Qabul qilish')}
          </Button>
        </>
      )
    if (mode === 'finish' && editable)
      return (
        <>
          {dismiss}
          <Button
            size="lg"
            icon="ri-checkbox-circle-line"
            disabled={busy}
            loading={finish.isPending}
            onClick={() => {
              const list = items(1)
              if (list) ask({ title: 'Yakunlash', message: 'Yakunlashni tasdiqlang?', label: 'Yakunlash', run: () => finish.mutate(list) })
            }}
          >
            {t('Yakunlash')}
          </Button>
        </>
      )
    if (mode === 'confirm' && editable)
      return (
        <>
          <Button
            variant="error"
            size="lg"
            icon="ri-close-circle-line"
            disabled={busy}
            loading={confirm.isPending && confirm.variables?.action === 'rejected'}
            onClick={() =>
              ask({
                title: 'Arizani rad etish',
                message: 'Bekor qilishni tasdiqlang? Berilgan materiallar omborga qaytariladi.',
                label: ct('Bekor qilish', 'rad'),
                danger: true,
                run: () => confirm.mutate({ action: 'rejected' }, { onSuccess: () => (closeAll(), navigate('/orders/confirm/archive')) }),
              })
            }
          >
            {ct('Bekor qilish', 'rad')}
          </Button>
          <Button
            size="lg"
            icon="ri-checkbox-circle-line"
            disabled={busy}
            loading={confirm.isPending && confirm.variables?.action === 'approved'}
            onClick={() => {
              const list = items(0)
              if (list)
                ask({
                  title: 'Tasdiqlash',
                  message: 'Tasdiqlashni tasdiqlang?',
                  label: 'Tasdiqlash',
                  run: () => confirm.mutate({ action: 'approved', items: list }, { onSuccess: () => (closeAll(), navigate('/orders/confirm/archive')) }),
                })
            }}
          >
            {t('Tasdiqlash')}
          </Button>
        </>
      )
    return (
      <Button variant="stroke" size="lg" onClick={onClose}>
        {t('Yopish')}
      </Button>
    )
  })()

  const columns: DataTableColumn<Om>[] = [
    { key: 'n', label: t('T/r'), width: 56, render: (m) => order.materials.indexOf(m) + 1 },
    { key: 'name', label: t('Material nomi'), render: (m) => <span className="aui-cell-primary">{m.material_name}</span> },
    { key: 'unit', label: t('Birligi'), width: 88, render: (m) => m.unit_name || '' },
    { key: 'number', label: t("So'ralgan"), width: 96, align: 'right', render: (m) => formatNumber(m.number) },
    editable
      ? {
          key: 'given',
          label: t('Beriladi'),
          width: 128,
          render: (m) => (
            <TextInput
              className="ob-given"
              type="number"
              inputMode="numeric"
              min={mode === 'finish' ? 1 : 0}
              aria-label={t('{name}: beriladigan son', { name: m.material_name })}
              value={given[m.id] ?? ''}
              onChange={(e) => setGiven((g) => ({ ...g, [m.id]: e.target.value }))}
            />
          ),
        }
      : { key: 'given', label: t('Berildi'), width: 96, align: 'right', render: (m) => (m.given ? formatNumber(m.given) : null) },
    ...(mode === 'finish' && editable
      ? [{ key: 'stock', label: t('Omborda'), width: 96, align: 'right' as const, render: (m: Om) => (m.stock == null ? null : formatNumber(m.stock)) }]
      : []),
    { key: 'price', label: t('Narxi'), width: 112, align: 'right', render: (m) => (m.price == null ? null : formatNumber(Number(m.price))) },
    ...(canDelete
      ? [
          {
            key: 'del',
            label: t("O'chirish"),
            width: 88,
            align: 'center' as const,
            render: (m: Om) => (
              <Button
                variant="error-lighter"
                size="sm"
                icon="ri-delete-bin-line"
                iconOnly
                aria-label={t("{name} — o'chirish", { name: m.material_name })}
                disabled={busy}
                onClick={() =>
                  ask({
                    title: "Materialni o'chirish",
                    message: <>{t("«{name}» arizadan o'chirilsinmi? Berilgan miqdor omborga qaytariladi.", { name: m.material_name })}</>,
                    label: "O'chirish",
                    danger: true,
                    run: () => removeOm.mutate(m.id),
                  })
                }
              />
            ),
          },
        ]
      : []),
  ]

  const { sender, receiver, user } = order.people
  const timeline = [
    { at: order.date_creat, label: 'Ariza yaratildi', icon: 'ri-file-add-line', tone: 'pending' },
    { at: order.date_process, label: 'Ish boshlandi', icon: 'ri-settings-3-line', tone: 'process' },
    { at: order.date_finished, label: 'Ish tugallandi', icon: 'ri-checkbox-circle-line', tone: 'done' },
    { at: order.date_approved, label: 'Ariza tasdiqlandi', icon: 'ri-shield-check-line', tone: 'ok' },
    { at: order.date_accepted, label: 'Qabul qilindi', icon: 'ri-thumb-up-line', tone: 'ok' },
    { at: order.date_canceled, label: 'Bekor qilindi', icon: 'ri-close-circle-line', tone: 'muted' },
    { at: order.date_rejected, label: 'Rad etildi', icon: 'ri-forbid-line', tone: 'bad' },
  ].filter((tl) => tl.at)

  return (
    <>
      <Modal open onClose={onClose} icon="ri-file-text-line" title={t('Ariza tafsilotlari #{id}', { id: order.id })} subtitle={order.goal_name ?? undefined} width={820} footer={footer}>
        <div className="ob-detail">
          <section>
            <dl className="ob-kv">
              <Row label="Ariza holati" icon="ri-information-line">
                <OrderStatus status={order.status} label={order.status_display} />
              </Row>
              <Row label="Ariza maqsadi" icon="ri-focus-3-line">
                {order.goal_name || ''}
              </Row>
              <Row label="Ro'yxatga olingan sana" icon="ri-calendar-event-line">
                {formatDate(order.date_creat)}
              </Row>
              <PersonRows person={sender} title="Ariza muallifi" icon="ri-user-line" />
              {order.message_sender && (
                <Row label="Qo'shimcha ma'lumot" icon="ri-chat-3-line">
                  {order.message_sender}
                </Row>
              )}
            </dl>
          </section>

          {receiver && (
            <section>
              <h3 className="ob-section-title type-label-sm">{t("Mas'ul xodim ma'lumotlari")}</h3>
              <dl className="ob-kv">
                <PersonRows person={receiver} title="Mas'ul xodim" icon="ri-user-follow-line" />
                {order.message_receiver && (
                  <Row label="Qo'shimcha ma'lumot" icon="ri-chat-3-line">
                    {order.message_receiver}
                  </Row>
                )}
              </dl>
            </section>
          )}

          {user && (
            <section>
              <h3 className="ob-section-title type-label-sm">{t("Tasdiqlovchi xodim ma'lumotlari")}</h3>
              <dl className="ob-kv">
                <PersonRows person={user} title="Tasdiqlovchi xodim" icon="ri-user-star-line" />
              </dl>
            </section>
          )}

          {order.materials.length > 0 && (
            <section>
              <h3 className="ob-section-title type-label-sm">{t('Materiallar')}</h3>
              <DataTable rows={order.materials} columns={columns} getRowId={(m) => m.id} rowHeight={52} minWidth={canDelete ? 720 : 600} caption={t('Arizadagi materiallar')} />
              {error && (
                <p className="ivs-form-error type-para-sm" role="alert">
                  {error}
                </p>
              )}
            </section>
          )}

          {mode === 'finish' && editable && (
            <section>
              <div style={{ maxWidth: 280 }}>
                <DatePicker
                  withTime
                  label="Materialni qabul qilish vaqtini tanlang"
                  hint="Ixtiyoriy: yuboruvchiga materiallarni qachon olib ketishi mumkinligi yuboriladi."
                  value={date}
                  onChange={setDate}
                />
              </div>
            </section>
          )}

          {order.deeds.some((d) => d.file) && (
            <section>
              <h3 className="ob-section-title type-label-sm">{t('Fayllar')}</h3>
              <DeedLinks deeds={order.deeds} />
            </section>
          )}

          <section>
            <h3 className="ob-section-title type-label-sm">{t('Jarayon tarixi')}</h3>
            <ol className="ob-timeline">
              {timeline.map((tl) => (
                <li key={tl.label} className={`ob-tl is-${tl.tone}`}>
                  <span className="ob-tl-icon">
                    <Icon name={tl.icon} size={18} />
                  </span>
                  <span className="type-para-xs ob-muted">{formatDate(tl.at)}</span>
                  <span className="type-label-sm">{t(tl.label)}</span>
                </li>
              ))}
            </ol>
          </section>

          {order.rating ? (
            <section className="ob-rating">
              <span className="type-label-sm">{t('Xizmat sifatiga berilgan baho')}</span>
              <span aria-label={`${order.rating} / 5`}>
                {Array.from({ length: order.rating }, (_, i) => (
                  <Icon key={i} name="ri-star-fill" size={24} color="var(--state-warning-base)" />
                ))}
              </span>
            </section>
          ) : null}
        </div>
      </Modal>
      {pending && (
        <ConfirmDialog
          title={pending.title}
          message={pending.message}
          confirmLabel={pending.label}
          danger={pending.danger}
          loading={busy}
          onConfirm={() => pending.run()}
          onClose={() => setPending(null)}
        />
      )}
    </>
  )
}

/** label — o'zbekcha kalit, shu yerda tarjima qilinadi */
function Row({ label, icon, children }: { label: string; icon: string; children: ReactNode }) {
  const t = useT()
  return (
    <div className="ob-kv-row">
      <dt className="type-para-sm">
        <Icon name={icon} size={16} />
        {t(label)}
      </dt>
      <dd className="type-para-sm">{children}</dd>
    </div>
  )
}

function PersonRows({ person, title, icon }: { person: Person | null; title: string; icon: string }) {
  if (!person) return null
  const org = [person.organization, person.department, person.directorate, person.division].filter(Boolean)
  return (
    <>
      <Row label={title} icon={icon}>
        <span className="type-label-sm">{person.full_name}</span> {person.rank && <span className="ob-muted">{person.rank}</span>}
      </Row>
      <Row label="Tashkilot" icon="ri-building-line">
        {org.length ? org.map((o) => <div key={o}>{o}</div>) : null}
      </Row>
      <Row label="Telefon raqami" icon="ri-phone-line">
        {person.phone ? <a href={`tel:${person.phone.replace(/\s/g, '')}`}>{person.phone}</a> : null}
      </Row>
    </>
  )
}

export function DeedLinks({ deeds }: { deeds: BarnOrderDetail['deeds'] }) {
  const t = useT()
  const files = deeds.filter((d) => d.file)
  if (!files.length) return null
  return (
    <div className="ob-files">
      {files.map((d) => (
        <Button
          key={d.id}
          variant="stroke"
          size="sm"
          icon="ri-file-pdf-2-line"
          title={d.code ?? undefined}
          onClick={() => openPdf(mediaPath(d.file) ?? '', d.code ?? t('Hujjat'))}
        >
          {files.length > 1 && d.code ? `${t("Ko'rish")} · ${d.code}` : t("Ko'rish")}
        </Button>
      ))}
    </div>
  )
}
