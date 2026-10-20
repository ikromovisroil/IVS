import type { ReactNode } from 'react'
import { Navigate } from 'react-router-dom'
import Page from '../../layout/Page'
import PageTabs from '../../components/PageTabs'
import type { PageTab } from '../../components/PageTabs'
import { useReceiverPending } from './hooks'
import { useMe } from '../../auth/me'
import { ordersTabs } from './tabs'

const EXECUTE = '/orders/execute'

/** "Arizalar" bo'limining yuqori tablari ("Bajarish" yonida kutayotganlar soni bilan). */
function useTopTabs(): PageTab[] {
  const me = useMe()
  const tabs = ordersTabs(me)
  const showsExecute = tabs.some((t) => t.path === EXECUTE)
  const badges = useReceiverPending(showsExecute)
  const pending = badges.data?.receiver_pending
  return tabs.map((t) => (t.path === EXECUTE && pending ? { ...t, count: pending } : t))
}

interface ShellProps {
  title: string
  subtitle: string
  icon: string
  actions?: ReactNode
  /** Tab ichidagi holatlar (Arizalar / Tarix ...) */
  subTabs: PageTab[]
  subLabel: string
  children: ReactNode
}

/** Har bir ATM arizalari sahifasi: sarlavha, bo'lim tablari, ichki tablar. */
export default function OrdersShell({ title, subtitle, icon, actions, subTabs, subLabel, children }: ShellProps) {
  const tabs = useTopTabs()
  return (
    <Page icon={icon} title={title} subtitle={subtitle} actions={actions}>
      <PageTabs tabs={tabs} label="Arizalar bo'limlari" />
      {subTabs.length > 1 && <PageTabs tabs={subTabs} label={subLabel} variant="segment" />}
      {children}
    </Page>
  )
}

/** /orders — foydalanuvchiga ko'rinadigan birinchi tabga yo'naltiradi. */
export function OrdersIndex() {
  const me = useMe()
  const first = ordersTabs(me)[0]
  return <Navigate to={first?.path ?? '/orders/sent'} replace />
}
