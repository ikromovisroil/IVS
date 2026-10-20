import { can } from '../../auth/me'
import type { Me } from '../../api/types'

export type BarnSection = 'sender' | 'execute' | 'confirm'

// templates/base.html: omborxona sahifalari faqat mijoz (client) tashkiloti xodimlari uchun; bajarish — change_order,
// tasdiqlash — confirm_order (eski view'lar boshqa holatda 403 qaytaradi).
export function sectionAllowed(me: Me, section: BarnSection): boolean {
  if (me.organization_type !== 'client' || !me.employee) return false
  if (section === 'execute') return can(me, 'main.change_order')
  if (section === 'confirm') return can(me, 'main.confirm_order')
  return true
}
