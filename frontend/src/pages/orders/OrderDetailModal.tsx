import type { ReactNode } from 'react'
import { DataTable, Icon, StatusChip } from '../../ds'
import type { DataTableColumn } from '../../ds'
import Modal from '../../components/Modal'
import { useT } from '../../i18n'
import { useOrderDetail } from './hooks'
import { ORDER_STATUS, formatDateTime, formatPrice } from './types'
import type { OrderDetail, OrderMaterial, Person } from './types'

function Row({ icon, label, children }: { icon: string; label: string; children: ReactNode }) {
  const t = useT()
  return (
    <div className="ivs-orders-row">
      <dt>
        <Icon name={icon} size={16} />
        {t(label)}
      </dt>
      <dd>{children}</dd>
    </div>
  )
}

function PersonName({ p }: { p: Person | null }) {
  if (!p) return null
  return (
    <>
      {p.full_name} {p.rank && <span className="ivs-orders-muted">{p.rank}</span>}
    </>
  )
}

function Place({ p }: { p: Person | null }) {
  const parts = p ? [p.organization, p.department, p.directorate, p.division].filter(Boolean) : []
  if (!parts.length) return null
  return (
    <span className="ivs-orders-lines">
      {parts.map((x) => (
        <span key={x} className="ivs-orders-muted">
          {x}
        </span>
      ))}
    </span>
  )
}

const TIMELINE: { key: keyof OrderDetail; label: string; icon: string; tone: string }[] = [
  { key: 'date_creat', label: 'Ariza yaratildi', icon: 'ri-file-add-line', tone: 'is-away' },
  { key: 'date_process', label: 'Ish boshlandi', icon: 'ri-settings-3-line', tone: 'is-warning' },
  { key: 'date_finished', label: 'Ish tugallandi', icon: 'ri-checkbox-circle-line', tone: 'is-info' },
  { key: 'date_approved', label: 'Ariza tasdiqlandi', icon: 'ri-shield-check-line', tone: 'is-success' },
  { key: 'date_accepted', label: 'Qabul qilindi', icon: 'ri-thumb-up-line', tone: 'is-success' },
  { key: 'date_canceled', label: 'Bekor qilindi', icon: 'ri-close-circle-line', tone: 'is-faded' },
  { key: 'date_rejected', label: 'Rad etildi', icon: 'ri-forbid-line', tone: 'is-error' },
]

export function Stars({ value, size = 24 }: { value: number; size?: number }) {
  return (
    <span className="ivs-orders-stars" aria-label={`${value}/5`}>
      {[1, 2, 3, 4, 5].map((i) => (
        <Icon key={i} name={i <= value ? 'ri-star-fill' : 'ri-star-line'} size={size} className={i <= value ? 'is-on' : undefined} />
      ))}
    </span>
  )
}

export function Section({ title, extra, children }: { title: string; extra?: ReactNode; children: ReactNode }) {
  const t = useT()
  return (
    <section className="ivs-orders-section">
      <div className="ivs-orders-section-head">
        <h3 className="type-label-sm">{t(title)}</h3>
        {extra}
      </div>
      {children}
    </section>
  )
}

interface Props {
  id: number
  onClose: () => void
  /** Pastki tugmalar (holatga qarab) */
  footer?: (o: OrderDetail) => ReactNode
  /** Jarayon tarixidan oldin qo'shimcha bo'limlar (masalan, yakunlash formasi) */
  children?: (o: OrderDetail) => ReactNode
  /** Materiallar jadvalidagi qo'shimcha ustun (masalan, o'chirish) */
  materialAction?: DataTableColumn<OrderMaterial>
  /** Bahoni ko'rsatish (tarix sahifalari) */
  showRating?: boolean
}

/** Eski sahifadagi "Ariza tafsilotlari" oynasi. */
export default function OrderDetailModal({ id, onClose, footer, children, materialAction, showRating }: Props) {
  const t = useT()
  const q = useOrderDetail(id)
  const o = q.data

  const materialColumns: DataTableColumn<OrderMaterial>[] = [
    { key: 'n', label: t('T/r'), width: 56, render: (m) => (o?.materials.indexOf(m) ?? 0) + 1 },
    { key: 'name', label: t('Material nomi'), render: (m) => m.material_name },
    { key: 'number', label: t('Soni'), width: 80, render: (m) => `${m.number} ${m.unit_name || ''}`.trim() },
    { key: 'price', label: t('Narxi'), width: 120, render: (m) => formatPrice(m.price) },
    ...(materialAction ? [materialAction] : []),
  ]

  return (
    <Modal open onClose={onClose} icon="ri-file-text-line" title={t('Ariza tafsilotlari #{id}', { id })} subtitle={o?.goal_name ?? undefined} width={880} footer={o && footer?.(o)}>
      {q.isError ? (
        <div className="ivs-empty" role="alert">
          {t(q.error.message)}
        </div>
      ) : !o ? (
        <div className="ivs-empty" aria-busy="true">
          {t('Yuklanmoqda…')}
        </div>
      ) : (
        <div className="ivs-orders-detail">
          <dl className="ivs-orders-card">
            <Row icon="ri-information-line" label="Ariza holati">
              <StatusChip status={ORDER_STATUS[o.status]}>{t(o.status_display)}</StatusChip>
            </Row>
            <Row icon="ri-calendar-event-line" label="Ro'yxatga olingan sana">
              {formatDateTime(o.date_creat)}
            </Row>
            <Row icon="ri-user-line" label="Ariza muallifi">
              <PersonName p={o.sender_info} />
            </Row>
            {o.user_info && (
              <Row icon="ri-user-shared-line" label="Ariza bergan xodim">
                <PersonName p={o.user_info} />
              </Row>
            )}
            <Row icon="ri-focus-3-line" label="Ariza maqsadi">
              {o.goal_name || ''}
            </Row>
            <Row icon="ri-building-line" label="Tashkilot">
              <Place p={o.sender_info} />
            </Row>
            <Row icon="ri-phone-line" label="Telefon raqami">
              {o.sender_info?.phone || ''}
            </Row>
            {o.technics_name && (
              <Row icon="ri-cpu-line" label="Xizmat ko'rsatilgan texnika">
                {o.technics_name}
              </Row>
            )}
            {o.message_sender && (
              <Row icon="ri-chat-3-line" label="Qo'shimcha ma'lumot">
                <span className="ivs-orders-pre">{o.message_sender}</span>
              </Row>
            )}
          </dl>

          {o.receiver_info && (
            <Section title="Mas'ul xodim ma'lumotlari">
              <dl className="ivs-orders-card">
                <Row icon="ri-user-follow-line" label="Mas'ul xodim">
                  <PersonName p={o.receiver_info} />
                </Row>
                <Row icon="ri-building-line" label="Tashkilot">
                  <Place p={o.receiver_info} />
                </Row>
                <Row icon="ri-phone-line" label="Telefon raqami">
                  {o.receiver_info.phone || ''}
                </Row>
                {o.message_receiver && (
                  <Row icon="ri-chat-3-line" label="Qo'shimcha ma'lumot">
                    <span className="ivs-orders-pre">{o.message_receiver}</span>
                  </Row>
                )}
              </dl>
            </Section>
          )}

          {children?.(o)}

          {o.materials.length > 0 && (
            <Section title={materialAction ? 'Biriktirilgan materiallar' : 'Materiallar'}>
              <DataTable rows={o.materials} columns={materialColumns} getRowId={(m) => m.id} rowHeight={48} minWidth={0} caption={t('Arizadagi materiallar')} />
            </Section>
          )}

          <Section title="Jarayon tarixi">
            <ol className="ivs-orders-timeline">
              {TIMELINE.filter((step) => o[step.key]).map((step) => (
                <li key={step.key}>
                  <span className={`ivs-orders-tl-icon ${step.tone}`}>
                    <Icon name={step.icon} size={18} />
                  </span>
                  <span className="type-para-xs ivs-orders-muted">{formatDateTime(o[step.key] as string)}</span>
                  <span className="type-label-sm">{t(step.label)}</span>
                </li>
              ))}
            </ol>
          </Section>

          {showRating && o.rating ? (
            <Section title="Xizmat sifatiga berilgan baho">
              <div className="ivs-orders-rating">
                <Stars value={o.rating} size={28} />
              </div>
            </Section>
          ) : null}
        </div>
      )}
    </Modal>
  )
}
