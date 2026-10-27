// Hujjat matni uchun yordamchilar — eski shablonlardagi JS funksiyalari bilan bir xil natija beradi
// (templates/main/{document,svod,reestr,akt,service}.html).

export function esc(s: unknown): string {
  if (s === null || s === undefined) return ''
  const map: Record<string, string> = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' }
  return String(s).replace(/[&<>"']/g, (c) => map[c])
}

const pad = (n: number) => String(n).padStart(2, '0')

/** Bugun: "20.10.2026" */
export function todayDmy(): string {
  const d = new Date()
  return `${pad(d.getDate())}.${pad(d.getMonth() + 1)}.${d.getFullYear()}`
}

/** Mahalliy sana "YYYY-MM-DD" (toISOString UTC ga o'tkazib, kunni surib yuboradi). */
export function isoDate(d: Date): string {
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

/** Sana oralig'ining boshlang'ich qiymati: joriy oy boshidan bugungacha. */
export function monthRange(): { date1: string; date2: string } {
  const t = new Date()
  return { date1: isoDate(new Date(t.getFullYear(), t.getMonth(), 1)), date2: isoDate(t) }
}

const MONTHS = ['yanvar', 'fevral', 'mart', 'aprel', 'may', 'iyun', 'iyul', 'avgust', 'sentabr', 'oktabr', 'noyabr', 'dekabr']

/** "2026-yil avgust oyi uchun" / "2026-yil iyul-avgust oylari uchun" / "2025-yil dekabr - 2026-yil yanvar oylari uchun" */
export function formatMonthYearRange(date1: string, date2: string): string {
  const now = new Date()
  const fallback = `${now.getFullYear()}-yil ${MONTHS[now.getMonth()]} oyi uchun`
  if (!date1 || !date2) return fallback
  const d1 = new Date(date1)
  const d2 = new Date(date2)
  if (isNaN(d1.getTime()) || isNaN(d2.getTime())) return fallback
  const [y1, m1, y2, m2] = [d1.getFullYear(), d1.getMonth(), d2.getFullYear(), d2.getMonth()]
  if (y1 === y2 && m1 === m2) return `${y1}-yil ${MONTHS[m1]} oyi uchun`
  if (y1 === y2) return `${y1}-yil ${MONTHS[m1]}-${MONTHS[m2]} oylari uchun`
  return `${y1}-yil ${MONTHS[m1]} - ${y2}-yil ${MONTHS[m2]} oylari uchun`
}

/** Svod/Reestr/Sarf: 1234567.5 → "1 234 567,50", 15000 → "15 000" */
export function formatNumber(num: unknown): string {
  if (num === null || num === undefined || num === '' || isNaN(Number(num))) return '0'
  const s = String(num)
  if (s.includes('.')) {
    const [i, f] = s.split('.')
    const frac = f.length === 1 ? f + '0' : f.substring(0, 2)
    return i.replace(/\B(?=(\d{3})+(?!\d))/g, ' ') + ',' + frac
  }
  return s.replace(/\B(?=(\d{3})+(?!\d))/g, ' ')
}

/** Akt: bo'sh → "-", kasr bo'lsa 2 xona */
export function formatNumberAkt(value: unknown): string {
  if (value === null || value === undefined) return '-'
  let s = String(value).trim()
  if (!s) return '-'
  s = s.replace(/\s+/g, '')
  const num = Number(s.replace(',', '.'))
  if (!isFinite(num)) return '-'
  const hasFraction = /[,.]\d+/.test(s)
  const [rawInt, frac] = (hasFraction ? num.toFixed(2) : Math.trunc(num).toString()).split('.')
  const sign = rawInt.startsWith('-') ? '-' : ''
  const int = rawInt.replace('-', '').replace(/\B(?=(\d{3})+(?!\d))/g, ' ')
  return hasFraction ? `${sign}${int},${frac}` : `${sign}${int}`
}

/** Hujjat matnida o'zbekcha apostroflar yagona: o‘ va g‘ (U+2018), tutuq belgisi ’ (U+2019). */
export function normalizeApostrophes(text: string): string {
  return text.replace(/(?<=[oOgG])['ʻʼ’‘`´](?=[A-Za-z])/g, '‘').replace(/(?<=[aeiuAEIU])['ʻʼ‘`´](?=[A-Za-z])/g, '’')
}

/** Xuddi shu qoida HTML uchun: faqat matn qismida (teg va atributlarga tegmaydi). */
export function normalizeApostrophesHtml(html: string): string {
  return html.replace(/(<[^>]*>)|([^<]+)/g, (_, tag: string | undefined, txt: string | undefined) => (tag ? tag : normalizeApostrophes(txt ?? '')))
}

/** Pul: doim 2 xonali tiyin — 15000 → "15 000,00" */
export function formatMoney(num: unknown): string {
  const n = Number(num)
  const cents = Math.round((isFinite(n) ? n : 0) * 100)
  const sign = cents < 0 ? '-' : ''
  const abs = Math.abs(cents)
  return sign + String(Math.floor(abs / 100)).replace(/\B(?=(\d{3})+(?!\d))/g, ' ') + ',' + pad(abs % 100)
}

const UZ_ONES = ['', 'bir', 'ikki', 'uch', 'to‘rt', 'besh', 'olti', 'yetti', 'sakkiz', 'to‘qqiz']
const UZ_TENS = ['', 'o‘n', 'yigirma', 'o‘ttiz', 'qirq', 'ellik', 'oltmish', 'yetmish', 'sakson', 'to‘qson']
const UZ_SCALES = ['', 'ming', 'million', 'milliard', 'trillion']

function belowThousand(n: number): string {
  const parts: string[] = []
  const h = Math.floor(n / 100)
  const t = Math.floor((n % 100) / 10)
  const o = n % 10
  if (h) parts.push(UZ_ONES[h] + ' yuz')
  if (t) parts.push(UZ_TENS[t])
  if (o) parts.push(UZ_ONES[o])
  return parts.join(' ')
}

function numberWords(n: number): string {
  if (n === 0) return 'nol'
  const parts: string[] = []
  let scale = 0
  while (n > 0 && scale < UZ_SCALES.length) {
    const g = n % 1000
    if (g) parts.unshift(belowThousand(g) + (UZ_SCALES[scale] ? ' ' + UZ_SCALES[scale] : ''))
    n = Math.floor(n / 1000)
    scale++
  }
  return parts.join(' ')
}

/** 16980445.02 → "JAMI SO‘Z BILAN: O‘n olti million ... so‘m 02 tiyin" */
export function amountInWords(total: number): string {
  const cents = Math.max(0, Math.round((Number(total) || 0) * 100))
  const text = numberWords(Math.floor(cents / 100)) + ' so‘m ' + pad(cents % 100) + ' tiyin'
  return 'JAMI SO‘Z BILAN: ' + text.charAt(0).toUpperCase() + text.slice(1)
}

/** "Ikromov Isroil Ilhom o'g'li" → "Ikromov I.I." (o'g'li/qizi qisqartirilmaydi) */
export function shortenFullName(fullname: string): string {
  const parts = (fullname || '').trim().split(/\s+/).filter(Boolean)
  if (!parts.length) return ''
  const strip = (s: string) => s.replace(/['’‘ʻʼ`]/g, '')
  const initials = parts
    .slice(1)
    .filter((p) => !['ogli', 'qizi', 'ogil'].includes(strip(p).toLowerCase()))
    .map((p) => p.charAt(0).toUpperCase() + '.')
    .join('')
  return initials ? `${parts[0]} ${initials}` : parts[0]
}

/** "Narzullayev Anvar Shuhrat o'g'li" → "A.Narzullayev" (space=true: "A. Narzullayev") */
export function initialSurname(fullname: string, space = false): string {
  const parts = (fullname || '').trim().split(/\s+/).filter(Boolean)
  if (!parts.length) return ''
  const first = parts[1] ? parts[1].charAt(0).toUpperCase() : ''
  return first ? `${first}.${space ? ' ' : ''}${parts[0]}` : parts[0]
}

export function lowerFirst(text: string): string {
  const t = (text || '').trim()
  return t ? t.charAt(0).toLowerCase() + t.slice(1) : ''
}

/** ["A","B","C"] → "A, B va C" */
export function joinWithVa(items: string[]): string {
  if (items.length <= 1) return items.join('')
  return items.slice(0, -1).join(', ') + ' va ' + items[items.length - 1]
}

/** Oy → chorak (I..IV); "YYYY-MM-DD" dan yil va chorak */
export function quarterOfDate(iso: string): { year: string; quarter: string } | null {
  const m = /^(\d{4})-(\d{2})-\d{2}/.exec(iso || '')
  if (!m) return null
  const month = Number(m[2])
  if (month < 1 || month > 12) return null
  return { year: m[1], quarter: ['I', 'II', 'III', 'IV'][Math.ceil(month / 3) - 1] }
}

/** Xodim varianti: "F.I.Sh (lavozim)" — eski select2 ro'yxatlari kabi */
export function empLabel(e: { full_name: string; rank?: string }): string {
  return e.rank ? `${e.full_name} (${rankCase(e.rank)})` : e.full_name
}

/**
 * Hujjatdagi lavozim: faqat birinchi harf katta, qolgani kichik ("Direktor Birinchi O'rinbosari" → "Direktor birinchi o'rinbosari").
 * Qisqa bosh harfli so'zlar (ATM, IT, DUK) o'zgarmaydi. inline=true — gap ichida: birinchi harf ham kichik.
 */
export function rankCase(text: string | null | undefined, inline = false): string {
  const parts = (text || '').trim().split(/(\s+)/)
  let first = true
  return parts
    .map((w) => {
      if (!w.trim()) return w
      const keep = /^[A-ZА-Я]{2,4}$/.test(w.replace(/[().,;:]/g, ''))
      let out = keep ? w : w.toLowerCase()
      if (first) {
        first = false
        if (!keep && !inline) out = out.charAt(0).toUpperCase() + out.slice(1)
      }
      return out
    })
    .join('')
}
