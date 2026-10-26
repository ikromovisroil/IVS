import type { PageTab } from '../../components/PageTabs'

/** Ro'yxat turi — api/spa/messages.py: BOXES (eski contact_user, contact, contact_agrement va arxivlari) */
export type Box =
  | 'send' | 'send_archive' | 'send_rejected'
  | 'sign' | 'sign_archive' | 'sign_rejected'
  | 'agree' | 'agree_archive' | 'agree_rejected'
export type Group = 'send' | 'sign' | 'agree'

export interface BoxConfig {
  group: Group
  archive: boolean
  path: string
  /** Eski sahifa sarlavhasi */
  title: string
  subtitle: string
  empty: string
}

export const BOXES: Record<Box, BoxConfig> = {
  send: {
    group: 'send',
    archive: false,
    path: '/messages/send',
    title: 'Imzolashga yuborish',
    subtitle: "Siz yaratgan va hali imzolanmagan yoki kelishilmagan hujjatlar.",
    empty: "Imzolanmagan hujjat yo'q.",
  },
  send_archive: {
    group: 'send',
    archive: true,
    path: '/messages/send/archive',
    title: 'Imzolashga yuborish',
    subtitle: 'Siz yaratgan va imzolangan hujjatlar.',
    empty: "Imzolangan hujjat yo'q.",
  },
  send_rejected: {
    group: 'send',
    archive: true,
    path: '/messages/send/rejected',
    title: 'Imzolashga yuborish',
    subtitle: 'Siz yaratgan va rad etilgan hujjatlar.',
    empty: "Rad etilgan hujjat yo'q.",
  },
  sign: {
    group: 'sign',
    archive: false,
    path: '/messages/sign',
    title: 'Imzolash uchun',
    subtitle: "Siz imzolashingiz kerak bo'lgan hujjatlar.",
    empty: "Imzolash uchun hujjat yo'q.",
  },
  sign_archive: {
    group: 'sign',
    archive: true,
    path: '/messages/sign/archive',
    title: 'Imzolash uchun',
    subtitle: 'Siz imzolagan hujjatlar.',
    empty: "Imzolangan hujjat yo'q.",
  },
  sign_rejected: {
    group: 'sign',
    archive: true,
    path: '/messages/sign/rejected',
    title: 'Imzolash uchun',
    subtitle: 'Siz rad etgan hujjatlar.',
    empty: "Rad etilgan hujjat yo'q.",
  },
  agree: {
    group: 'agree',
    archive: false,
    path: '/messages/agree',
    title: 'Kelishish uchun',
    subtitle: "Siz kelishishingiz kerak bo'lgan hujjatlar.",
    empty: "Kelishish uchun hujjat yo'q.",
  },
  agree_archive: {
    group: 'agree',
    archive: true,
    path: '/messages/agree/archive',
    title: 'Kelishish uchun',
    subtitle: 'Siz kelishgan hujjatlar.',
    empty: "Kelishilgan hujjat yo'q.",
  },
  agree_rejected: {
    group: 'agree',
    archive: true,
    path: '/messages/agree/rejected',
    title: 'Kelishish uchun',
    subtitle: 'Siz rad etgan hujjatlar.',
    empty: "Rad etilgan hujjat yo'q.",
  },
}

/** Bo'lim tablari (templates/base.html "Xabarlar" menyusi); sonlar — menyudagi nishonlar */
export function groupTabs(counts?: { sign: number; agree: number }): PageTab[] {
  return [
    { path: '/messages/send', label: 'Imzolashga yuborish', icon: 'ri-send-plane-line' },
    { path: '/messages/sign', label: 'Imzolash uchun', icon: 'ri-quill-pen-line', count: counts?.sign || undefined },
    { path: '/messages/agree', label: 'Kelishish uchun', icon: 'ri-shake-hands-line', count: counts?.agree || undefined },
  ]
}

/** Ichki tablar: Imzolanmagan / Imzolangan / Rad etilgan (Kelishilmagan / Kelishilgan / Rad etilgan) */
export function archiveTabs(group: Group): PageTab[] {
  const agree = group === 'agree'
  return [
    { path: `/messages/${group}`, label: agree ? 'Kelishilmagan' : 'Imzolanmagan', icon: 'ri-time-line' },
    { path: `/messages/${group}/archive`, label: agree ? 'Kelishilgan' : 'Imzolangan', icon: 'ri-archive-line' },
    { path: `/messages/${group}/rejected`, label: 'Rad etilgan', icon: 'ri-close-circle-line' },
  ]
}
