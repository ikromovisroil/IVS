import type { Me } from '../api/types'
import { can } from '../auth/me'

export interface NavEntry {
  path: string
  label: string
  icon: string
  /** Eski Django sahifasi (hali React'ga ko'chirilmagan bo'lsa) */
  legacy?: string
  visible?: (me: Me) => boolean
}

export interface NavSection {
  label: string
  items: NavEntry[]
}

const isWorker = (me: Me) => me.is_superuser || me.organization_type === 'worker'

// templates/base.html dagi menyu va ruxsat shartlari bilan bir xil.
export const NAV: NavSection[] = [
  {
    label: 'Asosiy',
    items: [
      // Superuser — butun tizim; "Statistikani ko'rish" huquqi bor xodim — o'z ko'rish doirasida (serverda cheklanadi)
      { path: '/dashboard', label: 'Bosh sahifa', icon: 'ri-layout-grid-line', visible: (me) => can(me, 'main.status_employee') },
      { path: '/orders', label: 'Arizalar', icon: 'ri-file-list-3-line', legacy: '/order/sender/' },
      { path: '/messages', label: 'Xabarlar', icon: 'ri-mail-line', legacy: '/contact/user/' },
      {
        path: '/reports',
        label: 'Hisobotlar',
        icon: 'ri-bar-chart-box-line',
        legacy: '/svod/',
        visible: (me) =>
          isWorker(me) &&
          ['main.change_order', 'main.report_employee', 'main.shop_employee', 'main.material_service'].some((p) => can(me, p)),
      },
      { path: '/files', label: 'Hujjatlar', icon: 'ri-file-text-line', legacy: '/files/' },
    ],
  },
  {
    label: 'Ombor',
    items: [
      // Har bir xodim o'z texnikasini ko'radi (eski technics_get), ruxsat sharti yo'q
      { path: '/technics/mine', label: 'Texnikalarim', icon: 'ri-macbook-line', legacy: '/technics_get/' },
      { path: '/technics', label: 'Texnika va uskunalar', icon: 'ri-computer-line', visible: (me) => can(me, 'main.view_technics') },
      // "Qo'shimcha qurilmalar" menyuda yo'q: "Texnika va uskunalar" sahifasidagi tab orqali ochiladi (/technics/extra)
      { path: '/materials', label: 'Materiallar', icon: 'ri-archive-line', legacy: '/barn_mat/', visible: (me) => can(me, 'main.view_material') },
    ],
  },
  {
    label: 'Boshqaruv',
    items: [
      { path: '/stats', label: 'Statistika', icon: 'ri-pie-chart-line', legacy: '/tex_status/', visible: (me) => can(me, 'main.status_employee') },
      { path: '/employees', label: 'Xodimlar', icon: 'ri-group-line', legacy: '/employee/', visible: (me) => can(me, 'main.view_employee') },
    ],
  },
  {
    label: 'Aloqa',
    items: [
      { path: '/chat', label: 'Chat', icon: 'ri-chat-3-line', legacy: '/chat/' },
      {
        path: '/meetings',
        label: 'Zoom',
        icon: 'ri-video-chat-line',
        legacy: '/chat/meetings/',
        visible: (me) => can(me, 'chat.add_meeting') || can(me, 'chat.view_meeting'),
      },
    ],
  },
]

export function visibleNav(me: Me): NavSection[] {
  return NAV.map((s) => ({ ...s, items: s.items.filter((i) => !i.visible || i.visible(me)) })).filter((s) => s.items.length)
}

export function findNav(path: string): NavEntry | undefined {
  return [...NAV.flatMap((s) => s.items), ...FOOTER_NAV].find((i) => i.path === path)
}

/** Yon menyuning pastki qismi (Page.tsx footerItems) */
export const FOOTER_NAV: NavEntry[] = [
  { path: '/notifications', label: 'Bildirishnomalar', icon: 'ri-notification-3-line', legacy: '/notifications/' },
  { path: '/profile', label: 'Profil', icon: 'ri-user-line', legacy: '/profil/' },
]
