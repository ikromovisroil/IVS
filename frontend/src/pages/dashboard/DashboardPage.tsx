import { useState } from 'react'
import type { ReactNode } from 'react'
import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { Link, useNavigate } from 'react-router-dom'
import {
  Avatar,
  Button,
  CellUser,
  DataTable,
  Delta,
  ProgressBar,
  Icon,
  Legend,
  SegmentedControl,
  StatusChip,
  Widget,
} from '../../ds'
import type { DataTableColumn, StatusChipProps } from '../../ds'
import Page from '../../layout/Page'
import { api } from '../../api/client'
import { can, useMe } from '../../auth/me'
import { useLang, useT } from '../../i18n'
import { useUrlFilters } from '../../lib/useUrlFilters'
import { avatarColor, formatNumber, initials } from '../../lib/format'
import { ago, bucketLabel, change, dateTime, duration, longDate, shortDate } from './format'
import { Donut, HoverTip, Sparkline, StackBar, TipRow, TrendChart } from './charts'
import type { Part } from './charts'
import type { Overview } from './types'
import './dashboard.css'

const PERIODS = ['7', '30', '90']

// Ranglar faqat AlignUI tokenlaridan; bir-biridan yorug'lik bo'yicha ham farq qiladi
const C = {
  created: 'var(--primary-base)',
  createdArea: 'var(--primary-alpha-24)',
  done: 'var(--state-success-base)',
  viewed: 'var(--state-information-base)',
  process: 'var(--state-warning-base)',
  closed: 'var(--state-faded-base)',
  finished: 'var(--state-feature-base)',
  repair: 'var(--state-warning-base)',
  defect: 'var(--state-error-base)',
}

// Ariza holati: StatusChip ko'rinishi va nomi (server status_display o'rniga — tarjima qilinadi)
const ORDER_STATUS: Record<string, { chip: StatusChipProps['status']; label: string }> = {
  viewed: { chip: 'pending', label: 'Yangi' },
  process: { chip: 'in-progress', label: 'Jarayonda' },
  finished: { chip: 'completed', label: 'Tayyorlandi' },
  approved: { chip: 'completed', label: 'Tasdiqlandi' },
  accepted: { chip: 'completed', label: 'Qabul qilindi' },
  canceled: { chip: 'absent', label: 'Bekor qilindi' },
  rejected: { chip: 'failed', label: 'Rad etildi' },
}

// Hujjat turi (Deed.status) nomlari — server kind_display o'rniga
const DEED_KIND: Record<string, string> = {
  document: 'Dalolatnoma',
  svod: 'Yakuniy hisobot',
  reestr: 'Reestr',
  act: 'Akt',
  petition: 'Talabnoma',
  service: 'Sarf material',
}

function KpiCard({
  icon,
  label,
  value,
  delta,
  note,
  spark,
  sparkLabels,
  sparkColor,
  to,
}: {
  icon: string
  label: string
  value: ReactNode
  delta?: { text: string; tone: 'success' | 'error' | 'neutral' } | null
  note: ReactNode
  spark?: number[]
  sparkLabels?: string[]
  sparkColor?: string
  to: string
}) {
  return (
    <Link to={to} className="ivs-kpi">
      <div className="ivs-kpi-head">
        <span className="ivs-kpi-icon">
          <Icon name={icon} size={20} />
        </span>
        <span className="type-label-sm ivs-kpi-label">{label}</span>
        <Icon name="ri-arrow-right-up-line" size={18} className="ivs-kpi-go" />
      </div>
      <div className="ivs-kpi-body">
        <div>
          <div className="ivs-kpi-value">{value}</div>
          <div className="ivs-kpi-note type-para-xs">
            {delta && <Delta value={delta.text} tone={delta.tone} />}
            <span>{note}</span>
          </div>
        </div>
        {spark && spark.length > 1 && (
          <div className="ivs-kpi-spark">
            <Sparkline values={spark} labels={sparkLabels ?? []} color={sparkColor ?? C.created} />
          </div>
        )}
      </div>
    </Link>
  )
}

function Stars({ value }: { value: number | null }) {
  const t = useT()
  if (value == null) return <span className="ivs-dash-muted type-para-xs">{t("Baho yo'q")}</span>
  const v = value.toFixed(1).replace('.', ',')
  return (
    <span className="ivs-dash-rating type-label-xs" title={t("O'rtacha baho: {v}", { v })}>
      <Icon name="ri-star-fill" size={14} />
      {v}
    </span>
  )
}

function Skeleton() {
  return (
    <div className="ivs-dash" aria-busy="true">
      <div className="ivs-kpis">
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className="ivs-kpi is-skeleton" />
        ))}
      </div>
      <div className="aui-dgrid ivs-dash-grid">
        {[0, 1, 2].map((i) => (
          <div key={i} className={`aui-widget ivs-dash-skeleton${i === 0 ? ' aui-span-2' : ''}`} />
        ))}
      </div>
    </div>
  )
}

/** Admin bosh sahifasi: tizim bo'yicha umumiy ko'rinish (api/spa/dashboard.py). */
export default function DashboardPage() {
  const me = useMe()
  const t = useT()
  const { lang } = useLang()
  const navigate = useNavigate()
  const { filters, setFilter } = useUrlFilters(['days', 'scope'] as const)
  const days = PERIODS.includes(filters.days) ? filters.days : '30'
  // Standart — o'z tashkiloti; "Barcha tashkilotlar" faqat huquqi borlarga (server tekshiradi)
  const wantAll = filters.scope === 'all'

  const q = useQuery({
    queryKey: ['dashboard', days, wantAll],
    queryFn: () => api<Overview>('/spa/dashboard/overview/', { query: { days, scope: wantAll ? 'all' : '' } }),
    placeholderData: keepPreviousData,
    refetchInterval: 5 * 60 * 1000,
  })
  const d = q.data
  // Grafik segmenti va ro'yxat qatori o'rtasida umumiy hover holati
  const [osActive, setOsActive] = useState<string | null>(null)
  const [tsActive, setTsActive] = useState<string | null>(null)

  const firstName = me.employee?.first_name || me.employee?.full_name?.split(' ')[1] || me.username
  const fullName = me.employee?.full_name || me.username
  const prevLabel = t('oldingi {n} kunga nisbatan', { n: days })
  const lastDays = t("so'nggi {n} kunda", { n: days })

  const scope = d?.scope
  const barn = !!scope?.barn
  // Mijoz — omborxona arizalari; qolganlar — ATM arizalari
  const ordersPath = barn ? '/orders/barn' : '/orders/execute'
  const ordersArchivePath = barn ? '/orders/barn/archive' : '/orders/execute/archive'
  const scopeText =
    scope && scope.mode !== 'all'
      ? [scope.organization, scope.region].filter(Boolean).join(' · ') || t('Sizning doirangiz')
      : t("Tizim bo'yicha umumiy ko'rinish")

  const header = {
    avatar: { initials: initials(fullName), color: avatarColor(me.employee?.id ?? me.username), name: fullName },
    title: t('Xush kelibsiz, {name}', { name: firstName }),
    subtitle: `${longDate(new Date(), lang)} · ${barn ? `${t('Omborxona bo‘yicha ko‘rinish')} · ` : ''}${scopeText}`,
  }

  const canReports = !barn && (me.is_superuser || can(me, 'main.report_employee') || can(me, 'main.shop_employee'))
  const canExecute = !barn && can(me, 'main.change_order')
  const actions = (
    <>
      {canReports && (
        <Button variant="stroke" size="lg" icon="ri-bar-chart-box-line" onClick={() => navigate('/reports')}>
          {t('Hisobotlar')}
        </Button>
      )}
      {canExecute && (
        <Button size="lg" icon="ri-tools-line" onClick={() => navigate('/orders/execute')}>
          {t('Arizalarni bajarish')}
        </Button>
      )}
      {barn && (
        <Button size="lg" icon="ri-store-2-line" onClick={() => navigate('/orders/barn/new')}>
          {t('Omborxonaga ariza')}
        </Button>
      )}
    </>
  )

  const totalParts = d
    ? [
        t('{n} xodim', { n: formatNumber(d.totals.employees) }),
        d.totals.organizations > 1 ? t('{n} tashkilot', { n: formatNumber(d.totals.organizations) }) : null,
        d.totals.technics != null ? t('{n} texnika', { n: formatNumber(d.totals.technics) }) : null,
        d.totals.materials != null ? t('{n} material', { n: formatNumber(d.totals.materials) }) : null,
      ].filter(Boolean)
    : []

  const toolbar = (
    <div className="ivs-dash-head">
      <div>
        <h2 className="type-label-lg">{t("Umumiy ko'rsatkichlar")}</h2>
        {d && <p className="type-para-xs ivs-dash-muted">{totalParts.join(' · ')}</p>}
      </div>
      <div className="ivs-dash-tools">
        {d?.scope.can_widen && (
          <SegmentedControl
            aria-label={t("Ko'rish doirasi")}
            items={[
              { value: 'own', label: t('Tashkilotim') },
              { value: 'all', label: t('Barcha tashkilotlar') },
            ]}
            value={d.scope.widened ? 'all' : 'own'}
            onChange={(v) => setFilter('scope', v === 'all' ? 'all' : '')}
          />
        )}
        <SegmentedControl
          aria-label={t('Davr')}
          items={PERIODS.map((p) => ({ value: p, label: t('{n} kun', { n: p }) }))}
          value={days}
          onChange={(v) => setFilter('days', v === '30' ? '' : String(v))}
        />
      </div>
    </div>
  )

  if (q.isError) {
    return (
      <Page {...header} background="gray" actions={actions}>
        {toolbar}
        <div className="ivs-empty" role="alert">
          {q.error.message}
        </div>
      </Page>
    )
  }

  if (!d) {
    return (
      <Page {...header} background="gray" actions={actions}>
        {toolbar}
        <Skeleton />
      </Page>
    )
  }

  const k = d.kpis
  const trendCreated = d.trend.map((p) => p.created)
  const trendDone = d.trend.map((p) => p.done)
  const trendLabels = d.trend.map((p) => bucketLabel(p.date, d.period.bucket_days, lang))
  // x o'qida ~6 ta sana: oxirgisi har doim, unga juda yaqin oraliq yorlig'i tashlab yuboriladi
  const step = Math.max(1, Math.round(d.trend.length / 6))
  const xLabels = d.trend.map((p, i) => {
    const last = d.trend.length - 1
    if (i === last) return shortDate(p.date, lang)
    return i % step === 0 && last - i >= step / 2 ? shortDate(p.date, lang) : ''
  })

  const os = d.orders_status
  const osTotal = os.viewed + os.process + os.done + os.closed
  const osParts: Part[] = [
    { key: 'approved', label: t('Tasdiqlangan'), value: os.approved, color: C.done },
    { key: 'finished', label: t('Tayyorlandi (tasdiq kutilmoqda)'), value: os.finished, color: C.finished },
    { key: 'process', label: t('Jarayonda'), value: os.process, color: C.process },
    { key: 'viewed', label: t('Yangi#plural'), value: os.viewed, color: C.viewed },
    { key: 'closed', label: t('Bekor / rad etilgan'), value: os.closed, color: C.closed },
  ]
  const ts = d.technics_status
  const tsTotal = ts ? ts.active + ts.free + ts.repair + ts.defect : 0
  const tsParts: Part[] = ts
    ? [
        { key: 'active', label: t('Aktiv'), value: ts.active, color: C.done },
        { key: 'free', label: t("Bo'sh"), value: ts.free, color: C.viewed },
        { key: 'repair', label: t("Ta'mirda"), value: ts.repair, color: C.repair },
        { key: 'defect', label: t('Yaroqsiz'), value: ts.defect, color: C.defect },
      ]
    : []
  const techGroups = d.technics_groups ?? []
  const groupMax = Math.max(1, ...techGroups.map((g) => g.count))
  const mats = d.materials
  const matMax = Math.max(1, ...(mats?.top ?? []).map((m) => m.number))
  const execMax = Math.max(1, ...d.top_executors.map((x) => x.done))
  const execTotal = Math.max(1, d.top_executors.reduce((a, x) => a + x.done, 0))
  const goalMax = Math.max(1, ...d.top_goals.map((g) => g.count))
  const pct = (v: number, total: number) => Math.round((v * 100) / Math.max(1, total))
  // Guruh nomi serverdan; faqat bizning "Boshqalar" / "Turi ko'rsatilmagan" yorliqlari tarjima qilinadi
  const groupName = (name: string) => (name === 'Boshqalar' || name === "Turi ko'rsatilmagan" ? t(name) : name)

  const recentColumns: DataTableColumn<Overview['recent_orders'][number]>[] = [
    { key: 'id', label: '№', width: 64, render: (r) => <span className="ivs-dash-mono">#{r.id}</span> },
    {
      key: 'sender',
      label: t('Muallif'),
      width: '28%',
      render: (r) =>
        r.sender ? (
          <CellUser name={r.sender.name} sub={r.sender.organization || r.sender.rank || undefined} initials={initials(r.sender.name)} color={avatarColor(r.sender.id)} />
        ) : (
          null
        ),
    },
    {
      key: 'goal',
      label: t('Ariza maqsadi'),
      render: (r) => (
        <div className="aui-cell-text">
          <div className="aui-cell-primary is-regular">{r.goal || ''}</div>
          <div className="aui-cell-secondary">{r.receiver ? t('Ijrochi: {name}', { name: r.receiver }) : t('Ijrochi biriktirilmagan')}</div>
        </div>
      ),
    },
    {
      key: 'status',
      label: t('Holati'),
      width: 148,
      render: (r) => (
        <div className="ivs-dash-status">
          <StatusChip status={ORDER_STATUS[r.status]?.chip ?? 'pending'}>{ORDER_STATUS[r.status] ? t(ORDER_STATUS[r.status].label) : r.status_display}</StatusChip>
          <span className="type-para-xs ivs-dash-muted">{dateTime(r.date)}</span>
        </div>
      ),
    },
  ]

  return (
    <Page {...header} background="gray" actions={actions}>
      {toolbar}
      <div className={q.isFetching ? 'ivs-dash ivs-loading' : 'ivs-dash'}>
        <div className="ivs-kpis">
          <KpiCard
            to={ordersPath}
            icon="ri-file-add-line"
            label={barn ? t('Yangi omborxona arizalari') : t('Yangi arizalar')}
            value={formatNumber(k.orders_new.value)}
            delta={change(k.orders_new.value, k.orders_new.prev)}
            note={change(k.orders_new.value, k.orders_new.prev) ? prevLabel : lastDays}
            spark={trendCreated}
            sparkLabels={trendLabels}
            sparkColor={C.created}
          />
          <KpiCard
            to={ordersArchivePath}
            icon="ri-checkbox-circle-line"
            label={barn ? t('Bajarilgan omborxona arizalari') : t('Bajarilgan arizalar')}
            value={formatNumber(k.orders_done.value)}
            delta={change(k.orders_done.value, k.orders_done.prev)}
            note={change(k.orders_done.value, k.orders_done.prev) ? prevLabel : lastDays}
            spark={trendDone}
            sparkLabels={trendLabels}
            sparkColor={C.done}
          />
          <KpiCard
            to="/stats/employees"
            icon="ri-timer-line"
            label={t("O'rtacha bajarish vaqti")}
            value={duration(k.avg_hours.value, t)}
            delta={change(k.avg_hours.value, k.avg_hours.prev, true)}
            note={change(k.avg_hours.value, k.avg_hours.prev, true) ? prevLabel : t('qabul qilingandan tayyor bo‘lguncha')}
          />
          <KpiCard
            to="/files"
            icon="ri-quill-pen-line"
            label={t('Imzo kutilayotgan hujjatlar')}
            value={formatNumber(k.deeds_pending.value)}
            note={
              k.deeds_pending.stale ? (
                <span className="ivs-dash-warn">{t('{n} tasi 3 kundan ortiq kutmoqda', { n: k.deeds_pending.stale })}</span>
              ) : (
                t('barchasi 3 kun ichida')
              )
            }
          />
        </div>

        <div className="aui-dgrid ivs-dash-grid">
          <Widget
            className="aui-span-2"
            icon="ri-line-chart-line"
            title={t('Arizalar dinamikasi')}
            extra={
              <Legend
                items={[
                  { label: t('Yaratilgan'), color: C.created },
                  { label: t('Bajarilgan'), color: C.done },
                ]}
              />
            }
          >
            <div className="ivs-dash-trend-sum">
              <div>
                <span className="type-para-xs ivs-dash-muted">{t('Yaratilgan')}</span>
                <strong className="type-h5">{formatNumber(trendCreated.reduce((a, b) => a + b, 0))}</strong>
              </div>
              <div>
                <span className="type-para-xs ivs-dash-muted">{t('Bajarilgan')}</span>
                <strong className="type-h5">{formatNumber(trendDone.reduce((a, b) => a + b, 0))}</strong>
              </div>
              <span className="type-para-xs ivs-dash-muted ivs-dash-trend-unit">{d.period.bucket_days === 7 ? t('haftalik') : t('kunlik')}</span>
            </div>
            {d.trend.length > 1 ? (
              <TrendChart
                height={300}
                labels={trendLabels}
                axisLabels={xLabels}
                label={t("So'nggi {n} kunda yaratilgan va bajarilgan arizalar", { n: days })}
                series={[
                  { key: 'created', label: t('Yaratilgan'), color: C.created, values: trendCreated },
                  { key: 'done', label: t('Bajarilgan'), color: C.done, values: trendDone },
                ]}
              />
            ) : (
              <div className="ivs-empty">{t("Ma'lumot yo'q")}</div>
            )}
          </Widget>

          <Widget icon="ri-donut-chart-line" title={t('Arizalar holati')} action={{ label: t('Barchasi'), onClick: () => navigate(ordersPath) }}>
            {osTotal ? (
              <div className="ivs-dash-gauge">
                <Donut parts={osParts} active={osActive} onActive={setOsActive} caption={t('Jami arizalar')} />
                <ul className="ivs-dash-list" aria-label={t("Arizalar holati bo'yicha")}>
                  {osParts.map((s) => (
                    <li
                      key={s.key}
                      tabIndex={0}
                      className={osActive && osActive !== s.key ? 'is-dim' : osActive === s.key ? 'is-on' : undefined}
                      onPointerEnter={() => setOsActive(s.key)}
                      onPointerLeave={() => setOsActive(null)}
                      onFocus={() => setOsActive(s.key)}
                      onBlur={() => setOsActive(null)}
                    >
                      <span className="aui-legend-dot" style={{ background: s.color }} />
                      <span className="type-para-sm">{s.label}</span>
                      <span className="type-label-sm">{formatNumber(s.value)}</span>
                      <span className="type-para-xs ivs-dash-muted">{pct(s.value, osTotal)}%</span>
                    </li>
                  ))}
                </ul>
              </div>
            ) : (
              <div className="ivs-empty">{t("Davr ichida ariza yo'q")}</div>
            )}
          </Widget>

          {ts && (
          <Widget icon="ri-computer-line" title={t('Texnika holati')} action={{ label: t("Ro'yxat"), onClick: () => navigate('/technics') }}>
            <div className="ivs-dash-big">
              <strong className="type-h4">{formatNumber(tsTotal)}</strong>
              <span className="type-para-sm ivs-dash-muted">{t('faol hisobdagi texnika')}</span>
            </div>
            {tsTotal ? (
              <>
                <StackBar parts={tsParts} active={tsActive} onActive={setTsActive} />
                <ul className="ivs-dash-list is-grid">
                  {tsParts.map((s) => (
                    <li key={s.key}>
                      <Link
                        to={`/technics?status=${s.key}`}
                        className={`ivs-dash-tile${tsActive && tsActive !== s.key ? ' is-dim' : ''}`}
                        onPointerEnter={() => setTsActive(s.key)}
                        onPointerLeave={() => setTsActive(null)}
                        onFocus={() => setTsActive(s.key)}
                        onBlur={() => setTsActive(null)}
                        aria-label={t("{label}: {n} ta, {p}%. Ro'yxatni ochish", { label: s.label, n: s.value, p: pct(s.value, tsTotal) })}
                      >
                        <span className="ivs-dash-tile-top">
                          <span className="aui-legend-dot" style={{ background: s.color }} />
                          <span className="type-para-xs ivs-dash-muted">{s.label}</span>
                          <span className="type-para-xs ivs-dash-muted ivs-dash-tile-pct">{pct(s.value, tsTotal)}%</span>
                        </span>
                        <span className="type-label-lg">{formatNumber(s.value)}</span>
                      </Link>
                    </li>
                  ))}
                </ul>
                {techGroups.length > 0 && (
                  <div className="ivs-dash-sub">
                    <div className="ivs-dash-sub-head">
                      <span className="type-label-sm">{t("Turlar bo'yicha")}</span>
                      <span className="type-para-xs ivs-dash-muted">{t('{n} ta guruh', { n: techGroups.length })}</span>
                    </div>
                    <ul className="ivs-dash-goals is-compact">
                      {techGroups.map((g) => (
                        <li key={g.name}>
                          <HoverTip
                            content={
                              <TipRow color={C.created} label={groupName(g.name)} value={t('{n} ta · {p}%', { n: formatNumber(g.count), p: pct(g.count, tsTotal) })} />
                            }
                          >
                            <span className="ivs-dash-group-row" tabIndex={0}>
                              <span className="type-para-sm ivs-dash-goal-name">{groupName(g.name)}</span>
                              <ProgressBar value={g.count} max={groupMax} label={t('{name}: {n} ta#plain', { name: groupName(g.name), n: g.count })} />
                              <span className="type-label-sm ivs-dash-group-count">{formatNumber(g.count)}</span>
                            </span>
                          </HoverTip>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </>
            ) : (
              <div className="ivs-empty">{t("Texnika yo'q")}</div>
            )}
          </Widget>
          )}

          {mats && (
            <Widget icon="ri-archive-line" title={t('Omborxona materiallari')} action={{ label: t("Ro'yxat"), onClick: () => navigate('/materials') }}>
              <div className="ivs-dash-big">
                <strong className="type-h4">{formatNumber(mats.items)}</strong>
                <span className="type-para-sm ivs-dash-muted">{t('xil material omborda bor')}</span>
              </div>
              <div className="ivs-dash-deed-stats is-two">
                <div>
                  <span className="type-para-xs ivs-dash-muted">{t('Umumiy qiymati')}</span>
                  <strong className="type-h5">{formatNumber(Math.round(Number(mats.total_sum)))}</strong>
                </div>
                <div>
                  <span className="type-para-xs ivs-dash-muted">{t('Tugagan')}</span>
                  <strong className="type-h5">{formatNumber(mats.empty)}</strong>
                </div>
              </div>
              {mats.top.length > 0 ? (
                <div className="ivs-dash-sub">
                  <div className="ivs-dash-sub-head">
                    <span className="type-label-sm">{t('Eng ko‘p qolgan materiallar')}</span>
                  </div>
                  <ul className="ivs-dash-goals">
                    {mats.top.map((m) => (
                      <li key={m.id} className="ivs-dash-mat">
                        <span className="ivs-dash-mat-head">
                          <span className="type-para-sm ivs-dash-goal-name" title={m.name}>
                            {m.name}
                          </span>
                          <span className="type-label-sm ivs-dash-mat-qty">
                            {formatNumber(m.number)} <span className="ivs-dash-muted">{m.unit || ''}</span>
                          </span>
                        </span>
                        <ProgressBar value={m.number} max={matMax} label={`${m.name}: ${m.number}`} />
                      </li>
                    ))}
                  </ul>
                </div>
              ) : (
                <div className="ivs-empty">{t("Omborda material yo'q")}</div>
              )}
            </Widget>
          )}

          <Widget icon="ri-medal-line" title={t('Eng faol ijrochilar')} action={{ label: t('Statistika'), onClick: () => navigate('/stats/employees') }}>
            {d.top_executors.length ? (
              <ul className="ivs-dash-people">
                {d.top_executors.map((p, i) => (
                  <li key={`${p.id}-${i}`}>
                    <span className="ivs-dash-rank type-label-xs">{i + 1}</span>
                    <Avatar size={40} initials={initials(p.name)} color={avatarColor(p.id)} name={p.name} />
                    <span className="ivs-dash-person">
                      <span className="type-label-sm">{p.name}</span>
                      <HoverTip
                        content={
                          <>
                            <div className="ivs-tip-title">{p.name}</div>
                            <TipRow color={C.created} label={t('Bajarilgan')} value={t('{n} ta#plain', { n: p.done })} />
                            <TipRow label={t('Top 5 ichidagi ulushi')} value={`${pct(p.done, execTotal)}%`} />
                            <TipRow label={t("O'rtacha baho")} value={p.rating != null ? p.rating.toFixed(1).replace('.', ',') : '—'} />
                            {p.organization && <TipRow label={t('Tashkilot')} value={p.organization} />}
                          </>
                        }
                      >
                        <span className="ivs-dash-bar" tabIndex={0} aria-label={t('{name}: {n} ta bajarilgan', { name: p.name, n: p.done })}>
                          <span style={{ width: `${(p.done * 100) / execMax}%` }} />
                        </span>
                      </HoverTip>
                    </span>
                    <span className="ivs-dash-person-end">
                      <span className="type-label-sm">{t('{n} ta#plain', { n: p.done })}</span>
                      <Stars value={p.rating} />
                    </span>
                  </li>
                ))}
              </ul>
            ) : (
              <div className="ivs-empty">{t("Davr ichida bajarilgan ariza yo'q")}</div>
            )}
            <div className="ivs-dash-deed-stats is-two ivs-dash-foot">
              <div>
                <span className="type-para-xs ivs-dash-muted">{t('Davrda bajarilgan')}</span>
                <strong className="type-h5">{formatNumber(k.orders_done.value)}</strong>
              </div>
              <div>
                <span className="type-para-xs ivs-dash-muted">{t('Top 5 ulushi')}</span>
                <strong className="type-h5">{k.orders_done.value ? `${Math.min(100, pct(execTotal, k.orders_done.value))}%` : '—'}</strong>
              </div>
            </div>
          </Widget>

          <Widget icon="ri-list-check-3" title={t('Ariza turlari')}>
            {d.top_goals.length ? (
              <ul className="ivs-dash-goals">
                {d.top_goals.map((g) => (
                  <li key={`${g.name}-${g.barn}`}>
                    <HoverTip
                      content={
                        <>
                          <div className="ivs-tip-title">{g.name}</div>
                          <TipRow color={C.created} label={t('Arizalar')} value={t('{n} ta#plain', { n: formatNumber(g.count) })} />
                          <TipRow label={t('Davrdagi ulushi')} value={`${pct(g.count, osTotal)}%`} />
                          <TipRow label={t("Yo'nalish")} value={g.barn ? t('Omborxona') : t('ATM')} />
                        </>
                      }
                    >
                      <span className="ivs-dash-goal-head" tabIndex={0}>
                        <span className="type-para-sm ivs-dash-goal-name">{g.name}</span>
                        {g.barn && <span className="type-para-xs ivs-dash-muted">{t('omborxona')}</span>}
                        <span className="type-label-sm">{formatNumber(g.count)}</span>
                      </span>
                      <ProgressBar value={g.count} max={goalMax} label={t('{name}: {n} ta#plain', { name: g.name, n: g.count })} />
                    </HoverTip>
                  </li>
                ))}
              </ul>
            ) : (
              <div className="ivs-empty">{t("Davr ichida ariza yo'q")}</div>
            )}
          </Widget>

          <Widget
            className="aui-span-2"
            icon="ri-time-line"
            title={t("So'nggi arizalar")}
            divider={false}
            action={{ label: t('Barchasi'), iconRight: 'ri-arrow-right-s-line', onClick: () => navigate(ordersPath) }}
          >
            <DataTable rows={d.recent_orders} columns={recentColumns} getRowId={(r) => r.id} rowHeight={68} minWidth={640} caption={t("So'nggi arizalar")} />
          </Widget>

          <Widget icon="ri-quill-pen-line" title={t('Hujjatlar')} action={{ label: t('Barchasi'), onClick: () => navigate('/files') }}>
            <div className="ivs-dash-deed-stats">
              <div>
                <span className="type-para-xs ivs-dash-muted">{t('Kutilmoqda')}</span>
                <strong className="type-h5">{formatNumber(d.deeds.pending)}</strong>
              </div>
              <div>
                <span className="type-para-xs ivs-dash-muted">{t('Tasdiqlangan')}</span>
                <strong className="type-h5">{formatNumber(d.deeds.approved)}</strong>
              </div>
              <div>
                <span className="type-para-xs ivs-dash-muted">{t('Rad etilgan')}</span>
                <strong className="type-h5">{formatNumber(d.deeds.rejected)}</strong>
              </div>
            </div>
            {d.deeds.recent.length ? (
              <ul className="ivs-dash-deeds">
                {d.deeds.recent.map((x) => (
                  <li key={x.id}>
                    <span className="ivs-dash-deed-icon">
                      <Icon name="ri-file-text-line" size={20} />
                    </span>
                    <span className="ivs-dash-person">
                      <span className="type-label-sm">
                        {DEED_KIND[x.kind] ? t(DEED_KIND[x.kind]) : x.kind_display} {x.code && <span className="ivs-dash-mono">{x.code}</span>}
                      </span>
                      <span className="type-para-xs ivs-dash-muted">{x.signer ? t('Imzolovchi: {name}', { name: x.signer }) : x.author}</span>
                    </span>
                    <span className="type-para-xs ivs-dash-muted ivs-dash-nowrap">{ago(x.date, t)}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <div className="ivs-empty">{t("Imzo kutilayotgan hujjat yo'q")}</div>
            )}
          </Widget>
        </div>
      </div>
    </Page>
  )
}
