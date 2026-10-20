import PageTabs from '../../components/PageTabs'
import { can, useMe } from '../../auth/me'

/** "Texnika va uskunalar" (barn_tex, view_technics) va "Texnikalarim" (technics_get, har bir xodim). */
export default function TechnicsTabs() {
  const me = useMe()
  const tabs = [
    ...(can(me, 'main.view_technics') ? [{ path: '/technics', label: 'Texnika va uskunalar', icon: 'ri-computer-line' }] : []),
    { path: '/technics/mine', label: 'Texnikalarim', icon: 'ri-macbook-line' },
  ]
  return tabs.length > 1 ? <PageTabs tabs={tabs} label="Texnika bo'limlari" /> : null
}
