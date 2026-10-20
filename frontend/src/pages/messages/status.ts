import type { StatusChipProps } from '../../ds'
import type { Deed, PublicDeed, SignStatus } from './types'

type Chip = StatusChipProps['status']

/** Imzolovchi holati (eski sahifadagi badge: sariq / yashil / qizil) */
export const SIGN_STATUS: Record<SignStatus, { label: string; chip: Chip }> = {
  viewed: { label: 'Kutilmoqda#hujjat', chip: 'pending' },
  approved: { label: 'Tasdiqlandi#hujjat', chip: 'completed' },
  rejected: { label: 'Rad etildi#hujjat', chip: 'failed' },
}

/** Kelishuvchi holati */
export const CONSENT_STATUS: Record<SignStatus, { label: string; chip: Chip }> = {
  viewed: { label: 'Kutilmoqda#hujjat', chip: 'pending' },
  approved: { label: 'Kelishildi', chip: 'completed' },
  rejected: { label: 'Rad etildi#hujjat', chip: 'failed' },
}

/** Hujjatning umumiy holati — contact*.html dagi "Holati" ustuni bilan bir xil qoida. */
export function deedStatus(d: Pick<Deed | PublicDeed, 'receiver' | 'status_sender' | 'status_receiver'>): SignStatus {
  if (d.receiver) {
    if (d.status_sender === 'rejected' || d.status_receiver === 'rejected') return 'rejected'
    if (d.status_sender === 'approved' && d.status_receiver === 'approved') return 'approved'
    return 'viewed'
  }
  return d.status_sender
}

/** "Hujjatlar yaratish" oynasidagi turlar (contact_user.html) */
export const KIND_OPTIONS = [
  { value: 'document', label: 'Dalolatnoma' },
  { value: 'svod', label: 'Yakuniy hisobot' },
  { value: 'reestr', label: 'Reestr' },
  { value: 'act', label: 'Akt' },
]

const dateFmt = new Intl.DateTimeFormat('ru-RU', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' })

/** "17.10.2026 11:03" */
export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return '—'
  return dateFmt.format(new Date(iso)).replace(',', '')
}
