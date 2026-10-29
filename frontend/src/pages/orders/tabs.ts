import type { Me } from '../../api/types'
import { can } from '../../auth/me'
import type { PageTab } from '../../components/PageTabs'

// "Arizalar" bo'limining tablari — templates/base.html dagi "Arizalar" menyusi va uning shartlari.
// Ikkala bo'lim (pages/orders — ATM arizalari, pages/orders-barn — omborxona arizalari) shu ro'yxatni ishlatadi.
interface OrdersTab extends PageTab {
  visible: (me: Me) => boolean
}

const orgType = (me: Me) => me.organization_type

const ORDERS_TABS: OrdersTab[] = [
  { path: '/orders/sent', label: 'ATMga ariza', icon: 'ri-send-plane-line', visible: () => true },
  // Omborxona materiallar ro'yxatidan ochiladi (arizalar — shu bo'limning "Arizalar" sahifasida)
  { path: '/orders/barn', to: '/orders/barn/new', label: 'Omborxona', icon: 'ri-store-2-line', visible: (me) => orgType(me) === 'client' },
  {
    path: '/orders/execute',
    label: 'Arizalar holati',
    icon: 'ri-tools-line',
    visible: (me) => orgType(me) === 'worker' && can(me, 'main.change_order'),
  },
  {
    path: '/orders/barn-execute',
    label: 'Arizalar holati',
    icon: 'ri-inbox-unarchive-line',
    visible: (me) => orgType(me) === 'client' && can(me, 'main.change_order'),
  },
  {
    path: '/orders/confirm',
    label: 'Tasdiqlash',
    icon: 'ri-checkbox-circle-line',
    visible: (me) => orgType(me) === 'client' && can(me, 'main.confirm_order'),
  },
]

export function ordersTabs(me: Me): PageTab[] {
  return ORDERS_TABS.filter((t) => t.visible(me))
}
