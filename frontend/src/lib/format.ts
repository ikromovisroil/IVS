// Umumiy formatlash yordamchilari (raqam, ism bosh harflari, avatar rangi)

const numberFormat = new Intl.NumberFormat('ru-RU')

/** 12345.6 → "12 345,6"; null/undefined/NaN → "0" */
export function formatNumber(value: number | string | null | undefined): string {
  const n = typeof value === 'string' ? Number(value) : value
  if (n == null || !Number.isFinite(n)) return '0'
  return numberFormat.format(n)
}

/** "Ikromov Isroil" → "II"; bitta so'z → birinchi ikki harf */
export function initials(name: string | null | undefined): string {
  const parts = (name ?? '').trim().split(/\s+/).filter(Boolean)
  if (parts.length === 0) return '?'
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase()
  return (parts[0][0] + parts[1][0]).toUpperCase()
}

const AVATAR_COLORS = ['blue', 'purple', 'orange', 'green', 'teal', 'red', 'pink', 'sky', 'yellow'] as const
export type AvatarColor = (typeof AVATAR_COLORS)[number]

/** Bir xil id/kalit uchun doim bir xil rang */
export function avatarColor(key: string | number | null | undefined): AvatarColor {
  const s = String(key ?? '')
  let h = 0
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) | 0
  return AVATAR_COLORS[Math.abs(h) % AVATAR_COLORS.length]
}
