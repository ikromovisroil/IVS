import { NavLink, useLocation, useNavigate } from 'react-router-dom'
import { Icon, SegmentedControl } from '../ds'
import { useT } from '../i18n'
import './PageTabs.css'

export interface PageTab {
  /** To'liq yo'l: "/orders/sent" */
  path: string
  /** Bosilganda ochiladigan sahifa (bo'sh bo'lsa — path): tab bo'limning boshqa sahifasidan boshlansin desak */
  to?: string
  label: string
  icon?: string
  count?: number
}

interface PageTabsProps {
  tabs: PageTab[]
  label: string
  /**
   * line — bo'lim sahifalari (1-daraja): chiziqli tablar, kontent kengligida, ostida ajratuvchi chiziq.
   * segment — bo'lim ichidagi holatlar (2-daraja: Yangi / Jarayonda / Arxiv): ixcham segment.
   */
  variant?: 'line' | 'segment'
}

/** Faol tab — manzilga eng uzun mos keladigan yo'l (/orders/execute/active → "Jarayonda", "Bajarish" emas). */
function activePath(tabs: PageTab[], pathname: string): string | undefined {
  return tabs
    .filter((t) => pathname === t.path || pathname.startsWith(t.path + '/'))
    .sort((a, b) => b.path.length - a.path.length)[0]?.path
}

/** Bo'lim ichidagi sahifalar navigatsiyasi (manzilga bog'langan). */
export default function PageTabs({ tabs, label, variant = 'line' }: PageTabsProps) {
  const t = useT()
  const { pathname } = useLocation()
  const navigate = useNavigate()
  const active = activePath(tabs, pathname) ?? tabs[0]?.path

  // Bitta tab — tanlov yo'q, navigatsiya ham kerak emas
  if (tabs.length < 2) return null

  if (variant === 'segment') {
    return (
      <div className="ivs-subtabs">
        <SegmentedControl
          aria-label={t(label)}
          items={tabs.map((tab) => ({ value: tab.path, label: t(tab.label), icon: tab.icon, count: tab.count }))}
          value={active}
          onChange={(v) => navigate(String(v))}
        />
      </div>
    )
  }

  return (
    <nav className="ivs-linetabs" aria-label={t(label)}>
      <ul>
        {tabs.map((tab) => {
          const on = tab.path === active
          return (
            <li key={tab.path}>
              {/* end: faollikni o'zimiz hisoblaymiz (eng uzun mos yo'l), NavLink'niki emas */}
              <NavLink to={tab.to ?? tab.path} end className={on ? 'is-active' : undefined} aria-current={on ? 'page' : undefined}>
                {tab.icon && <Icon name={tab.icon} size={18} />}
                <span>{t(tab.label)}</span>
                {tab.count != null && tab.count > 0 && <span className="ivs-linetabs-count">{tab.count}</span>}
              </NavLink>
            </li>
          )
        })}
      </ul>
    </nav>
  )
}
