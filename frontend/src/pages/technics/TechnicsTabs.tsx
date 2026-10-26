import PageTabs from '../../components/PageTabs'
import { can, useMe } from '../../auth/me'

/** "Texnika va uskunalar" (barn_tex) va "Qo'shimcha qurilmalar" (extra_tex): ikkalasi ham view_technics huquqi bilan. */
export default function TechnicsTabs() {
  const me = useMe()
  if (!can(me, 'main.view_technics')) return null
  const tabs = [
    { path: '/technics', label: 'Texnika va uskunalar', icon: 'ri-computer-line' },
    { path: '/technics/extra', label: "Qo'shimcha qurilmalar", icon: 'ri-usb-line' },
  ]
  return <PageTabs tabs={tabs} label="Texnika bo'limlari" />
}
