import FilterBar from '../../components/FilterBar'
import EmptyState from '../../components/EmptyState'
import { useState } from 'react'
import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { Button, GaugeChart, HBarChart, Icon, Legend, ProgressBar, SegmentedControl, Widget } from '../../ds'
import Page from '../../layout/Page'
import { api } from '../../api/client'
import { can, useMe } from '../../auth/me'
import { formatNumber } from '../../lib/format'
import { useT } from '../../i18n'
import { EMPTY_STRUCTURE, STRUCTURE_KEYS, paletteColor, pickQuery, useParamState } from './shared'
import type { Structure } from './shared'
import { Stat, StatsTabs, StructureFilters } from './ui'
import './stats.css'

interface Category {
  id: number
  name: string
  count: number
  share: number
}
interface Group {
  id: number
  name: string
  total: number
  share: number
  color: number
  icon: string
  categories: Category[]
}
interface TechnicsStats {
  filters: Structure
  names: Record<string, string | null>
  ready: boolean
  message: string | null
  kpi: { total: number; groups: number; categories: number; top_name: string | null; top_count: number; top_share: number }
  groups: Group[]
}

// main/views.py: tex_group_icon (Bootstrap) → RemixIcon
const ICONS: Record<string, string> = {
  'bi-pc-display': 'ri-computer-line',
  'bi-printer': 'ri-printer-line',
  'bi-hdd-network': 'ri-router-line',
  'bi-phone': 'ri-smartphone-line',
  'bi-camera-video': 'ri-camera-line',
  'bi-cpu': 'ri-cpu-line',
  'bi-display': 'ri-tv-2-line',
  'bi-box-seam': 'ri-archive-line',
  'bi-car-front': 'ri-car-line',
}

const TOP_CATEGORIES = 5
const RANK_LIMIT = 10
const DONUT_LIMIT = 8

function GroupCard({ group, active, onSelect }: { group: Group; active: boolean; onSelect: () => void }) {
  const t = useT()
  const [open, setOpen] = useState(false)
  const color = paletteColor(group.color)
  const shown = open ? group.categories : group.categories.slice(0, TOP_CATEGORIES)
  const more = group.categories.length - TOP_CATEGORIES

  return (
    <div
      className={`st-group${active ? ' is-active' : ''}${group.total ? '' : ' is-empty'}`}
      style={{ '--st-color': color } as React.CSSProperties}
      role="button"
      tabIndex={0}
      aria-pressed={active}
      title={t("Tafsilotni ko'rish")}
      onClick={group.total ? onSelect : undefined}
      onKeyDown={(e) => {
        if (group.total && (e.key === 'Enter' || e.key === ' ')) {
          e.preventDefault()
          onSelect()
        }
      }}
    >
      <Widget
        icon={<span className="st-group-icon"><Icon name={ICONS[group.icon] ?? 'ri-archive-line'} size={20} /></span>}
        title={group.name}
        extra={
          <span className="st-group-count">
            <b>{formatNumber(group.total)}</b> {t('ta')}
          </span>
        }
      >
        <div className="st-share">
          <div className="st-share-label type-para-xs">
            <span>{t('Umumiy ulushi')}</span>
            <span>{group.share}%</span>
          </div>
          <ProgressBar value={group.share} max={100} color={color} />
        </div>
        {group.categories.length === 0 ? (
          <div className="type-para-xs st-muted">{t("Bu guruhda kategoriya yo'q")}</div>
        ) : (
          <div className="st-cats">
            {shown.map((c) => (
              <div key={c.id} className="st-cat">
                <span className="st-cat-name type-para-xs" title={c.name}>
                  {c.name}
                </span>
                <ProgressBar value={c.share} max={100} color={color} />
                <span className="st-cat-num type-label-sm">{c.count}</span>
              </div>
            ))}
          </div>
        )}
        {more > 0 && (
          <Button
            variant="ghost"
            size="sm"
            iconRight={open ? 'ri-arrow-up-s-line' : 'ri-arrow-down-s-line'}
            onClick={(e) => {
              e.stopPropagation()
              setOpen((o) => !o)
            }}
          >
            {open ? t('Kamroq') : t('yana {n} ta', { n: more })}
          </Button>
        )}
      </Widget>
    </div>
  )
}

export default function TechnicsStatsPage() {
  const t = useT()
  const me = useMe()
  const { params, set } = useParamState()
  const [rankGroup, setRankGroup] = useState<number | null>(null)
  const [rankExpanded, setRankExpanded] = useState(false)

  // Filtr kalitlari manzilda bo'lmasa server xodimning o'z tashkiloti/hududi/departmentini tanlaydi
  const qs = pickQuery(params, STRUCTURE_KEYS)
  const stats = useQuery({
    queryKey: ['stats', 'technics', qs],
    queryFn: () => api<TechnicsStats>(`/spa/stats/technics/${qs ? `?${qs}` : ''}`),
    placeholderData: keepPreviousData,
  })
  const data = stats.data
  // Tanlov manzilda bo'lsa — o'sha (javob kutilayotganda ham), aks holda server tanlagan standart
  const fromUrl = params.has('organization') || params.has('region')
  const value: Structure = fromUrl
    ? (Object.fromEntries(STRUCTURE_KEYS.map((k) => [k, params.get(k) ?? ''])) as Structure)
    : (data?.filters ?? EMPTY_STRUCTURE)

  const onFilter = (patch: Partial<Structure>) => {
    setRankGroup(null)
    // Tanlangan holat to'liq yoziladi: organization/region kalitlari bo'lsa server standartni qo'llamaydi
    set({ ...value, ...patch })
  }

  const groups = (data?.groups ?? []).filter((g) => g.total)
  const allCats = groups
    .flatMap((g) => g.categories.filter((c) => c.count).map((c) => ({ ...c, group: g })))
    .sort((a, b) => b.count - a.count || a.name.localeCompare(b.name))

  const rankList = allCats.filter((c) => rankGroup === null || c.group.id === rankGroup)
  const rankShown = rankExpanded ? rankList : rankList.slice(0, RANK_LIMIT)

  const donut = allCats.slice(0, DONUT_LIMIT).map((c, i) => ({ label: c.name, value: c.count, color: paletteColor(i) }))
  const rest = allCats.slice(DONUT_LIMIT).reduce((s, c) => s + c.count, 0)
  if (rest) donut.push({ label: t('Boshqalar'), value: rest, color: 'var(--gray-400)' })

  const selectGroup = (id: number) => {
    setRankExpanded(false)
    setRankGroup((g) => (g === id ? null : id))
    if (rankGroup !== id) document.getElementById('st-rank')?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
  }

  const kpi = data?.kpi
  const allRegions = can(me, 'main.all_region')

  return (
    <Page icon="ri-pie-chart-line" title="Statistika" subtitle="Tashkilotdagi texnikalar guruh va kategoriyalar bo'yicha.">
      <StatsTabs />

      <FilterBar>
        <StructureFilters value={value} onChange={onFilter} allRegions={allRegions} required={!!data && !data.ready} />
      </FilterBar>

      {data?.message && (
        <div className="st-note" role="status">
          <Icon name="ri-information-line" size={20} />
          {t(data.message)}
        </div>
      )}

      {stats.isError ? (
        <div className="ivs-empty" role="alert">
          {stats.error.message}
        </div>
      ) : stats.isPending ? (
        <div className="ivs-empty" aria-busy="true">
          {t('Yuklanmoqda…')}
        </div>
      ) : !kpi?.total ? (
        <EmptyState icon="ri-search-line" title={data?.ready ? "Ma'lumot topilmadi" : 'Tashkilot va hududni tanlang'} />
      ) : (
        <div className={stats.isFetching ? 'ivs-loading' : undefined}>
          <div className="aui-stats st-stats">
            <Stat label={t('Jami texnika')} value={kpi.total} note={t('dona')} />
            <Stat label={t('Guruhlar')} value={kpi.groups} />
            <Stat label={t('Kategoriyalar')} value={kpi.categories} />
            <Stat label={t("Eng ko'p guruh")} value={kpi.top_name ?? '—'} note={t('{n} ta · {share}%', { n: formatNumber(kpi.top_count), share: kpi.top_share })} />
          </div>

          <div className="st-groups">
            {(data?.groups ?? []).map((g) => (
              <GroupCard key={g.id} group={g} active={rankGroup === g.id} onSelect={() => selectGroup(g.id)} />
            ))}
          </div>

          <div className="aui-dgrid st-grid">
            <Widget
              className="aui-span-full"
              icon="ri-fire-line"
              title={t("Eng ko'p kategoriyalar")}
              extra={
                <span className="type-para-xs st-muted">
                  {t('{n} ta kategoriya · {m} ta texnika', { n: rankList.length, m: formatNumber(rankList.reduce((s, c) => s + c.count, 0)) })}
                </span>
              }
            >
              <div className="st-chips">
                <SegmentedControl
                  aria-label={t("Guruh bo'yicha")}
                  items={[{ value: 0, label: t('Hammasi') }, ...groups.map((g) => ({ value: g.id, label: g.name }))]}
                  value={rankGroup ?? 0}
                  onChange={(v) => {
                    setRankExpanded(false)
                    setRankGroup(Number(v) || null)
                  }}
                />
              </div>
              <div id="st-rank" className="st-rank">
                {rankShown.map((c, i) => (
                  <div key={`${c.group.id}-${c.id}`} className="st-rank-row">
                    <span className={`st-rank-no${i < 3 ? ' is-top' : ''}`}>{i + 1}</span>
                    <div className="st-rank-body">
                      <div className="st-rank-head">
                        <span className="type-label-sm st-ellipsis" title={c.name}>
                          {c.name}
                        </span>
                        <span className="type-para-xs st-muted">{c.group.name}</span>
                        <span className="type-label-sm st-rank-num">{t('{n} ta', { n: formatNumber(c.count) })}</span>
                      </div>
                      <ProgressBar value={c.count} max={rankList[0]?.count || 1} color={paletteColor(c.group.color)} />
                    </div>
                  </div>
                ))}
              </div>
              {rankList.length > RANK_LIMIT && (
                <div>
                  <Button variant="stroke" size="sm" iconRight={rankExpanded ? 'ri-arrow-up-s-line' : 'ri-arrow-down-s-line'} onClick={() => setRankExpanded((x) => !x)}>
                    {rankExpanded ? t('Kamroq') : t('Yana {n} ta', { n: rankList.length - RANK_LIMIT })}
                  </Button>
                </div>
              )}
            </Widget>

            <Widget icon="ri-donut-chart-line" title={t('Kategoriyalar ulushi')}>
              <div className="st-gauge">
                <GaugeChart segments={donut} total={kpi.total} caption={t('Jami')} value={formatNumber(kpi.total)} size={240} strokeWidth={32} label={t('Kategoriyalar ulushi')} />
              </div>
              <Legend items={donut.map((d) => ({ label: `${d.label} — ${d.value}`, color: d.color }))} />
            </Widget>

            <Widget className="aui-span-2" icon="ri-bar-chart-horizontal-line" title={t("Guruhlar bo'yicha texnika")}>
              <HBarChart
                className="st-hbars"
                data={groups.slice(0, 8).map((g) => ({ label: g.name, value: g.total, display: t('{n} ta', { n: g.total }), color: paletteColor(g.color) }))}
              />
              <Legend items={groups.slice(0, 8).map((g) => ({ label: t('{name}: {n} ta', { name: g.name, n: g.total }), color: paletteColor(g.color) }))} />
            </Widget>
          </div>
        </div>
      )}
    </Page>
  )
}
