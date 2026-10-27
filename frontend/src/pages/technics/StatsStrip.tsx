import { useT } from '../../i18n'
import { formatNumber } from '../../lib/format'
import './technics.css'

export interface StatusCounts {
  total: number
  active: number
  free: number
  repair: number
  defect: number
}

function Stat({ label, value, note }: { label: string; value: number | undefined; note: string }) {
  const t = useT()
  return (
    <div>
      <div className="ivs-stat-label">{t(label)}</div>
      <div className="ivs-stat-value">
        {value === undefined ? '—' : formatNumber(value)}
        <small>{note}</small>
      </div>
    </div>
  )
}

/** Holatlar bo'yicha sonlar: Jami · Aktiv · Bo'sh · Ta'mirda · Yaroqsiz (Texnika va Qo'shimcha qurilmalar sahifalari). */
export default function StatsStrip({ stats, totalLabel }: { stats: StatusCounts | undefined; totalLabel: string }) {
  const t = useT()
  const share = stats?.total ? Math.round((stats.active * 100) / stats.total) : 0
  return (
    <div className="aui-stats aui-stats-5">
      <Stat label={totalLabel} value={stats?.total} note={t('dona')} />
      <Stat label="Aktiv" value={stats?.active} note={t('{n}% jami ichida', { n: share })} />
      <Stat label="Bo'sh" value={stats?.free} note={t('foydalanishga tayyor')} />
      <Stat label="Ta'mirda" value={stats?.repair} note={t("e'tibor talab qiladi")} />
      <Stat label="Yaroqsiz" value={stats?.defect} note={t('hisobdan chiqarish uchun')} />
    </div>
  )
}
