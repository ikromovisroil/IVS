import { useCallback, useEffect, useState } from 'react'
import type { MouseEvent, ReactNode } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { AppShell, PageHeader } from '../ds'
import type { AvatarProps, DashboardNavItem } from '../ds'
import { useMe } from '../auth/me'
import SettingsPanel from '../components/SettingsPanel'
import { useT, useTMaybe } from '../i18n'
import { avatarColor, initials } from '../lib/format'
import { BASENAME } from '../routes'
import { useNavBadges } from './badges'
import { FOOTER_NAV, visibleNav } from './nav'

interface PageProps {
  /** O'zbekcha matn — tarjimasi shu yerda (t) qilinadi */
  title: string
  subtitle?: string
  /** Sarlavha belgisi: ikonka yoki (bosh sahifada) avatar */
  icon?: string
  avatar?: AvatarProps
  /** Kontent foni: gray (standart) — oq kartalar kulrang ustida; white — oq sahifa */
  background?: 'white' | 'gray'
  /** Sarlavha o'ngidagi tugmalar (Button size="lg") */
  actions?: ReactNode
  children?: ReactNode
}

// Profil va sozlamalar yon panelda (SettingsPanel); sidebar pastida faqat bildirishnomalar qoladi
const SIDEBAR_FOOTER = FOOTER_NAV.filter((it) => it.path !== '/profile')

/**
 * Sidebar pastidagi profil kartochkasi (AlignUI DashboardSidebar ichida, onClick qabul qilmaydi) —
 * tugmaga aylantiriladi: klaviatura va ekran o'quvchilari uchun role/tabIndex, bosilganda sozlamalar paneli.
 */
function useProfileButton(label: string, open: boolean, onOpen: () => void) {
  useEffect(() => {
    document.querySelectorAll<HTMLElement>('.aui-dside-user').forEach((el) => {
      el.setAttribute('role', 'button')
      el.setAttribute('tabindex', '0')
      el.setAttribute('aria-haspopup', 'dialog')
      el.setAttribute('aria-expanded', String(open))
      el.setAttribute('aria-label', label)
    })
  })

  useEffect(() => {
    const hit = (e: Event) => (e.target as HTMLElement | null)?.closest('.aui-dside-user')
    const onClick = (e: globalThis.MouseEvent) => hit(e) && onOpen()
    const onKey = (e: KeyboardEvent) => {
      if ((e.key === 'Enter' || e.key === ' ') && hit(e)) {
        e.preventDefault()
        onOpen()
      }
    }
    document.addEventListener('click', onClick)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('click', onClick)
      document.removeEventListener('keydown', onKey)
    }
  }, [onOpen])
}

/** Har bir sahifa: AlignUI AppShell (yon menyu) + PageHeader + kontent. */
export default function Page({ title, subtitle, icon, avatar, background = 'gray', actions, children }: PageProps) {
  const me = useMe()
  const t = useT()
  const tMaybe = useTMaybe()
  const navigate = useNavigate()
  const { pathname } = useLocation()
  const [settings, setSettings] = useState(false)

  const name = me.employee?.full_name || me.username
  const openSettings = useCallback(() => setSettings(true), [])
  useProfileButton(t('{name} — profil va sozlamalar', { name }), settings, openSettings)

  const go = (path: string) => (e: MouseEvent) => {
    if (e.metaKey || e.ctrlKey || e.shiftKey) return // yangi oynada ochish brauzerga qoldiriladi
    e.preventDefault()
    navigate(path)
  }

  const badges = useNavBadges()
  const nav = visibleNav(me)
  // Faol band — manzilga eng uzun mos keladigan yo'l (/technics/extra va /technics/5 → "Texnika va uskunalar")
  const activePath = nav
    .flatMap((s) => s.items.map((i) => i.path))
    .filter((p) => pathname === p || pathname.startsWith(p + '/'))
    .sort((a, b) => b.length - a.length)[0]

  const sections = nav.map((s) => ({
    label: t(s.label),
    items: s.items.map<DashboardNavItem>((it) => ({
      icon: it.icon,
      label: t(it.label),
      href: BASENAME + it.path,
      active: it.path === activePath,
      badge: badges[it.path] || undefined,
      onClick: go(it.path),
    })),
  }))

  const header = (
    <div>
      <PageHeader
        icon={avatar ? undefined : icon}
        avatar={avatar}
        title={tMaybe(title)}
        subtitle={subtitle ? tMaybe(subtitle) : undefined}
        search={false}
        notifications={false}
      >
        {actions}
      </PageHeader>
      <div className="ivs-page-rule" />
    </div>
  )

  return (
    <>
      <AppShell
        style={{ height: '100dvh' }}
        className={background === 'gray' ? 'ivs-bg-gray' : undefined}
        header={header}
        mobileHeader={{ search: false, notifications: false }}
        sidebar={{
          brand: { name: 'IVS', sub: t('Texnik xizmat platformasi'), icon: 'ri-server-fill' },
          sections,
          footerItems: SIDEBAR_FOOTER.map<DashboardNavItem>((it) => ({
            icon: it.icon,
            label: t(it.label),
            href: BASENAME + it.path,
            active: pathname === it.path,
            badge: badges[it.path] || undefined,
            onClick: go(it.path),
          })),
          user: {
            name,
            email: me.employee?.rank_name || me.employee?.organization_name || undefined,
            initials: initials(name),
            color: avatarColor(me.employee?.id ?? me.username),
          },
        }}
      >
        {children}
      </AppShell>
      <SettingsPanel open={settings} onClose={() => setSettings(false)} />
    </>
  )
}
