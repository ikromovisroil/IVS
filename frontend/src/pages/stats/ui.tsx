import DatePicker from '../../components/DatePicker'
import { useQuery } from '@tanstack/react-query'
import { Select } from '../../ds'
import type { SelectOption } from '../../ds'
import PageTabs from '../../components/PageTabs'
import { apiAll } from '../../api/client'
import type { Named } from '../../api/types'
import { formatNumber, sortById } from '../../lib/format'
import { TABS } from './shared'
import { useT } from '../../i18n'
import type { Structure } from './shared'

export function StatsTabs() {
  return <PageTabs tabs={TABS} label="Statistika bo'limlari" />
}

const toOptions = (rows: Named[] | undefined): SelectOption[] => sortById(rows).map((r) => ({ value: String(r.id), label: r.name }))

/**
 * Tashkilot → Hudud → Department → Boshqarma → Bo'lim. Ro'yxatlar mavjud API dan (ko'rish doirasi serverda):
 * /organizations/, /regions/, /departments/?organization&region, /directorates/?department, /divisions/?directorate.
 * Yuqori daraja o'zgarsa pastdagilar tozalanadi (eski sahifadagi kabi).
 */
export function StructureFilters({
  value,
  onChange,
  allRegions,
  required,
}: {
  value: Structure
  onChange: (patch: Partial<Structure>) => void
  /** "Barcha hududlar" varianti (faqat main.all_region bilan) */
  allRegions?: boolean
  /** Tashkilot yoki hudud tanlanmagan bo'lsa qizil chegara */
  required?: boolean
}) {
  const orgs = useQuery({ queryKey: ['stats', 'ref', 'organizations'], queryFn: () => apiAll<Named>('/organizations/'), staleTime: 300_000 })
  const regions = useQuery({ queryKey: ['stats', 'ref', 'regions'], queryFn: () => apiAll<Named>('/regions/'), staleTime: 300_000 })
  const deps = useQuery({
    queryKey: ['stats', 'ref', 'departments', value.organization, value.region],
    queryFn: () =>
      apiAll<Named>('/departments/', { organization: value.organization, region: value.region === 'all' ? undefined : value.region }),
    enabled: !!value.organization,
    staleTime: 300_000,
  })
  const dirs = useQuery({
    queryKey: ['stats', 'ref', 'directorates', value.department],
    queryFn: () => apiAll<Named>('/directorates/', { department: value.department }),
    enabled: !!value.department,
    staleTime: 300_000,
  })
  const divs = useQuery({
    queryKey: ['stats', 'ref', 'divisions', value.directorate],
    queryFn: () => apiAll<Named>('/divisions/', { directorate: value.directorate }),
    enabled: !!value.directorate,
    staleTime: 300_000,
  })

  const t = useT()
  const regionOptions = [...(allRegions ? [{ value: 'all', label: t('Barcha hududlar') }] : []), ...toOptions(regions.data)]
  const pick = (v: SelectOption['value'] | null) => (v == null ? '' : String(v))
  const below = { department: '', directorate: '', division: '' }

  return (
    <>
      <div className="st-filter">
        <Select
          placeholder={t('Tashkilot')}
          options={toOptions(orgs.data)}
          value={value.organization || null}
          error={required && !value.organization}
          onChange={(v) => onChange({ ...below, organization: pick(v) })}
        />
      </div>
      <div className="st-filter">
        <Select
          placeholder={t('Hudud')}
          options={regionOptions}
          value={value.region || null}
          error={required && !value.region}
          onChange={(v) => onChange({ ...below, region: pick(v) })}
        />
      </div>
      <div className="st-filter">
        <Select
          placeholder={t('Departament')}
          options={toOptions(deps.data)}
          value={value.department || null}
          disabled={!value.organization}
          onChange={(v) => onChange({ department: pick(v), directorate: '', division: '' })}
        />
      </div>
      <div className="st-filter">
        <Select
          placeholder={t('Boshqarma')}
          options={toOptions(dirs.data)}
          value={value.directorate || null}
          disabled={!value.department}
          onChange={(v) => onChange({ directorate: pick(v), division: '' })}
        />
      </div>
      <div className="st-filter">
        <Select
          placeholder={t("Bo'lim")}
          options={toOptions(divs.data)}
          value={value.division || null}
          disabled={!value.directorate}
          onChange={(v) => onChange({ division: pick(v) })}
        />
      </div>
    </>
  )
}

export function DateRange({ date1, date2, onChange }: { date1: string; date2: string; onChange: (patch: { date1?: string; date2?: string }) => void }) {
  return (
    <>
      <div className="st-filter st-date">
        <DatePicker placeholder="Boshlang'ich sana" value={date1} max={date2 || undefined} onChange={(v) => onChange({ date1: v })} />
      </div>
      <div className="st-filter st-date">
        <DatePicker placeholder="Tugash sanasi" value={date2} min={date1 || undefined} onChange={(v) => onChange({ date2: v })} />
      </div>
    </>
  )
}

export function Stat({ label, value, note }: { label: string; value: number | string | undefined; note?: string }) {
  return (
    <div>
      <div className="st-stat-label">{label}</div>
      <div className="st-stat-value">
        <span className="st-stat-main">{value === undefined ? '—' : typeof value === 'number' ? formatNumber(value) : value}</span>
        {note && <small>{note}</small>}
      </div>
    </div>
  )
}
