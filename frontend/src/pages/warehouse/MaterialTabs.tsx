import PageTabs from '../../components/PageTabs'
import { can, useMe } from '../../auth/me'

/** templates/base.html: Materiallar → Materiallar, Savat (all_material_employee), Kirim - chiqim */
export default function MaterialTabs() {
  const me = useMe()
  const tabs = [
    { path: '/materials', label: 'Materiallar', icon: 'ri-archive-line' },
    ...(can(me, 'main.all_material_employee') ? [{ path: '/materials/basket', label: 'Savat', icon: 'ri-shopping-basket-2-line' }] : []),
    { path: '/materials/movements', label: 'Kirim - chiqim', icon: 'ri-arrow-left-right-line' },
  ]
  return <PageTabs tabs={tabs} label="Materiallar bo'limlari" />
}
