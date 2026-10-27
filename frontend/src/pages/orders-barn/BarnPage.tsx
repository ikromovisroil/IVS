import type { ReactNode } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { SegmentedControl } from '../../ds'
import Page from '../../layout/Page'
import PageTabs from '../../components/PageTabs'
import EmptyState from '../../components/EmptyState'
import { useMe } from '../../auth/me'
import { ordersTabs } from '../orders/tabs'
import { sectionAllowed } from './access'
import type { BarnSection } from './access'
import { useBarnCount, useCart } from './api'
import { useT } from '../../i18n'
import './orders-barn.css'

interface SubTab {
  path: string
  label: string
  icon: string
  count?: number
}

// Sarlavha va belgi "Arizalar" tablaridagi (orders/tabs.ts) bo'lim bilan bir xil
const HEAD: Record<BarnSection, { title: string; icon: string }> = {
  sender: { title: 'Omborxona arizalari', icon: 'ri-store-2-line' },
  execute: { title: 'Omborxona arizalarini bajarish', icon: 'ri-inbox-unarchive-line' },
  confirm: { title: 'Arizalarni tasdiqlash', icon: 'ri-checkbox-circle-line' },
}

const SUBTITLE: Record<BarnSection, string> = {
  sender: "O'z tashkilotingiz omborxonasidan material so'rash: materiallarni savatga yig'ing va ariza yuboring.",
  execute: 'Omborxonaga kelgan arizalarni qabul qiling, materiallarni bering va yakunlang.',
  confirm: "Omborxonachi tayyorlagan arizalarni tasdiqlang yoki rad eting.",
}

const DENIED: Record<BarnSection, string> = {
  sender: 'Bu sahifa mijoz tashkiloti xodimlari uchun.',
  execute: 'Bu sahifa arizalarni bajarish huquqiga ega mijoz tashkiloti xodimlari uchun.',
  confirm: 'Bu sahifa arizalarni tasdiqlash huquqiga ega mijoz tashkiloti xodimlari uchun.',
}

function useSubTabs(section: BarnSection): SubTab[] {
  const me = useMe()
  const allowed = sectionAllowed(me, section)
  const cart = useCart(allowed && section === 'sender')
  const fresh = useBarnCount('barn_receiver_new', allowed && section === 'execute')
  const toConfirm = useBarnCount('barn_agrement', allowed && section === 'confirm')

  if (section === 'sender')
    return [
      { path: '/orders/barn', label: 'Arizalar', icon: 'ri-file-list-3-line' },
      { path: '/orders/barn/archive', label: 'Tarix', icon: 'ri-history-line' },
      { path: '/orders/barn/new', label: 'Material', icon: 'ri-archive-line' },
      { path: '/orders/barn/basket', label: 'Savat', icon: 'ri-shopping-basket-2-line', count: cart.data?.length || undefined },
    ]
  if (section === 'execute')
    return [
      { path: '/orders/barn-execute', label: 'Yangi arizalar', icon: 'ri-inbox-line', count: fresh.data || undefined },
      { path: '/orders/barn-execute/active', label: 'Qabul qilingan', icon: 'ri-tools-line' },
      { path: '/orders/barn-execute/archive', label: 'Tarix', icon: 'ri-history-line' },
    ]
  return [
    { path: '/orders/confirm', label: 'Yangi arizalar', icon: 'ri-checkbox-multiple-line', count: toConfirm.data || undefined },
    { path: '/orders/confirm/archive', label: 'Tarix', icon: 'ri-history-line' },
  ]
}

interface BarnPageProps {
  section: BarnSection
  /** Pastki tablar qatorining o'ng tomoni (qidiruv, "Ariza yaratish" ...) */
  tools?: ReactNode
  /** Sarlavha o'ng tomonidagi asosiy amal (masalan, "Ariza yaratish") */
  actions?: ReactNode
  children: ReactNode
}

/** Bo'lim qobig'i: "Arizalar" tablari (ordersTabs) + bo'lim ichidagi tablar + ruxsat tekshiruvi. */
export default function BarnPage({ section, tools, actions, children }: BarnPageProps) {
  const me = useMe()
  const { pathname } = useLocation()
  const navigate = useNavigate()
  const t = useT()
  const tabs = useSubTabs(section)
  const allowed = sectionAllowed(me, section)
  const active = tabs
    .filter((s) => pathname === s.path || pathname.startsWith(s.path + '/'))
    .sort((a, b) => b.path.length - a.path.length)[0]

  return (
    <Page icon={HEAD[section].icon} title={HEAD[section].title} subtitle={SUBTITLE[section]} actions={allowed ? actions : undefined}>
      <PageTabs tabs={ordersTabs(me)} label="Arizalar bo'limlari" />
      {allowed ? (
        <>
          <div className="aui-toolbar ob-toolbar">
            <SegmentedControl
              className="ob-subtabs"
              aria-label={t("Bo'lim sahifalari")}
              items={tabs.map((s) => ({ value: s.path, label: t(s.label), icon: s.icon, count: s.count }))}
              value={active?.path ?? tabs[0].path}
              onChange={(v) => navigate(String(v))}
            />
            {tools && (
              <>
                <span className="aui-toolbar-grow" />
                {tools}
              </>
            )}
          </div>
          {children}
        </>
      ) : (
        <EmptyState icon="ri-lock-line" title="Ruxsat yo'q" description={DENIED[section]} />
      )}
    </Page>
  )
}
