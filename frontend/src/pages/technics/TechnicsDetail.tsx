import type { ReactNode } from 'react'
import { Badge, StatusChip } from '../../ds'
import { API } from '../../api/client'
import { useLang, useT } from '../../i18n'
import type { TechnicsStatus } from '../../api/types'
import type { ExtraDevice, TechnicsCard, TechnicsRow } from './api'
import { TECHNICS_STATUS } from './status'
import { money } from './util'

/** label — o'zbekcha matn, shu yerda tarjima qilinadi */
export function Kv({ label, children }: { label: string; children: ReactNode }) {
  const t = useT()
  return (
    <div className="ivs-kv">
      <dt>{t(label)}</dt>
      <dd>{children}</dd>
    </div>
  )
}

/** uz: server status_display (avvalgidek); ru: ma'lum holat uchun mahalliy nomning tarjimasi. */
export function StatusTag({ status, label }: { status: TechnicsStatus; label?: string }) {
  const t = useT()
  const { lang } = useLang()
  const known = TECHNICS_STATUS[status]
  const s = known ?? TECHNICS_STATUS.free
  const text = lang === 'ru' && known ? t(known.label) : label || t(s.label)
  return <StatusChip status={s.chip}>{text}</StatusChip>
}

function Device({ d }: { d: ExtraDevice }) {
  const t = useT()
  return (
    <div className="ivs-device">
      <div className="ivs-device-head">
        <span className="type-label-sm">
          {d.category_name ? `${d.category_name} / ` : ''}
          {d.name}
        </span>
        <StatusTag status={d.status} label={d.status_display} />
      </div>
      <dl className="ivs-kvs is-compact">
        {d.parametr && <Kv label="Parametr">{d.parametr}</Kv>}
        {d.inventory && <Kv label="Inventar">{d.inventory}</Kv>}
        {d.serial && <Kv label="Serial">{d.serial}</Kv>}
        {d.year && <Kv label="Yili">{d.year}</Kv>}
        {Number(d.price) > 0 && <Kv label="Narxi">{t("{sum} so'm", { sum: money(d.price) })}</Kv>}
      </dl>
    </div>
  )
}

export function DevicesBlock({ devices }: { devices: ExtraDevice[] }) {
  const t = useT()
  return (
    <section className="ivs-detail-section">
      <h3 className="type-label-md">
        <i className="ri-hard-drive-2-line" aria-hidden /> {t("Qo'shimcha qurilmalar")}
      </h3>
      {devices.length ? devices.map((d) => <Device key={d.id} d={d} />) : <p className="type-para-sm ivs-muted">{t("Biriktirilgan qurilma yo'q.")}</p>}
    </section>
  )
}

export function QrBlock({ id, src }: { id: number; src: string | null }) {
  const t = useT()
  return (
    <section className="ivs-detail-section">
      <h3 className="type-label-md">
        <i className="ri-qr-code-line" aria-hidden /> {t('QR kod')}
      </h3>
      {src ? (
        <a className="ivs-qr" href={`${API}/technics/${id}/qr/`} download={`technics_${id}_qr.png`} title={t('QR kodni yuklab olish')}>
          <img src={src} alt={t('Uskuna #{id} QR kodi', { id })} width={160} height={160} />
          <span className="type-para-xs">
            <i className="ri-download-2-line" aria-hidden /> {t('Yuklab olish')}
          </span>
        </a>
      ) : (
        <p className="type-para-sm ivs-muted">{t('QR kod hali yaratilmagan.')}</p>
      )}
    </section>
  )
}

/** "Texnika tafsiloti" — barn_tex dagi tafsilot oynasi bilan bir xil maydonlar. */
export default function TechnicsDetail({ t: item }: { t: TechnicsRow }) {
  const t = useT()
  const place = [item.department_name, item.directorate_name, item.division_name].filter(Boolean)
  return (
    <div className="ivs-detail">
      <section className="ivs-detail-section">
        <h3 className="type-label-md">
          <i className="ri-information-line" aria-hidden /> {t("Umumiy ma'lumot")}
        </h3>
        <dl className="ivs-kvs">
          <Kv label="Xodim">{item.employee_name || ''}</Kv>
          <Kv label="Lavozim">{item.employee_rank || ''}</Kv>
          <Kv label="Tashkilot">
            {item.organization_name || ''}
            {place.map((p) => (
              <div key={p} className="ivs-muted">
                {p}
              </div>
            ))}
          </Kv>
          <Kv label="Turi">{item.group_name || ''}</Kv>
          <Kv label="Kategoriya">{item.category_name || ''}</Kv>
          <Kv label="Nomi">{item.name || ''}</Kv>
          {item.parametr && <Kv label="Parametr">{item.parametr}</Kv>}
          {item.inventory && <Kv label="Inventar">{item.inventory}</Kv>}
          {item.serial && <Kv label="Serial">{item.serial}</Kv>}
          {item.mac && <Kv label="MAC">{item.mac}</Kv>}
          {item.ip && <Kv label="IP">{item.ip}</Kv>}
          {item.year && <Kv label="Yili">{item.year}</Kv>}
          {Number(item.price) > 0 && <Kv label="Narxi">{t("{sum} so'm", { sum: money(item.price) })}</Kv>}
          {item.address && <Kv label="Joylashuvi">{item.address}</Kv>}
          <Kv label="Holati">
            <StatusTag status={item.status} label={item.status_display} />
          </Kv>
          <Kv label="Tarmoq qurilmasi">{item.is_online ? <Badge tone="sky" size="sm" icon="ri-router-line">{t('Ha')}</Badge> : t("Yo'q")}</Kv>
          <Kv label="Hududi">{item.region_name || ''}</Kv>
        </dl>
      </section>
      <DevicesBlock devices={item.extra_devices} />
      <QrBlock id={item.id} src={item.qr_code} />
    </div>
  )
}

/** QR kod sahifasi (main/views.py:technics_detail) — ko'rish huquqi bo'lmaganda ham ochiladi. */
export function TechnicsCardView({ c }: { c: TechnicsCard }) {
  const t = useT()
  return (
    <div className="ivs-detail">
      <section className="ivs-detail-section">
        <h3 className="type-label-md">
          <i className="ri-information-line" aria-hidden /> {t("Asosiy ma'lumotlar")}
        </h3>
        <dl className="ivs-kvs">
          <Kv label="Kategoriya">{c.category_name || ''}</Kv>
          <Kv label="Parametr">{c.parametr || ''}</Kv>
          <Kv label="Inventar">{c.inventory || ''}</Kv>
          <Kv label="Serial">{c.serial || ''}</Kv>
          <Kv label="MAC">{c.mac || ''}</Kv>
          <Kv label="IP">{c.ip || ''}</Kv>
          <Kv label="Xodim">{c.employee_name || ''}</Kv>
          <Kv label="Holati">
            <StatusTag status={c.status} label={c.status_display} />
          </Kv>
        </dl>
      </section>
      <DevicesBlock devices={c.extra_devices} />
      {c.qr_code && (
        <section className="ivs-detail-section">
          <h3 className="type-label-md">
            <i className="ri-qr-code-line" aria-hidden /> {t('QR kod')}
          </h3>
          <div className="ivs-qr">
            <img src={c.qr_code} alt={t('QR kod')} width={160} height={160} />
          </div>
        </section>
      )}
    </div>
  )
}
