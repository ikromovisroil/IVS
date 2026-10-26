// O'zbek lotin → o'zbek kirill (Ўзбекча): interfeys matnlarini avtomatik o'giradi, shuning uchun alohida lug'at yo'q.
// Matnlar kodda lotinda yoziladi; "uzc" tilida translate() shu funksiyadan o'tkazadi.
// O'girilmaydi: {o'rinbosarlar}, havolalar, raqam aralash so'zlar (kodlar, "1C"), mahsulot nomlari (PROTECTED).

// Himoyalangan bo'laklarni vaqtincha almashtirish belgisi (private-use, matnda uchramaydi)
const MARK = String.fromCharCode(0xe000)

const APOS ="['ʻʼ‘’`´]"

// Brend/texnik nomlar: kirillga o'tmaydi
const PROTECTED = [
  'IVS', 'ATM', 'PDF', 'Excel', 'Word', 'Zoom', 'Telegram', 'E-IMZO', 'MAC', 'IP', 'SMS', 'QR', 'ID', 'URL', 'API',
  'Gateway', 'Android', 'iOS', 'Windows', 'Google', 'Chrome', 'Claude', 'OneID', 'ERI',
]

// Qoidaga to'g'ri kelmaydigan so'zlar (kichik harf, o'zak bo'yicha)
const EXCEPTIONS: [RegExp, string][] = [
  [/kompyuter/gi, 'компьютер'],
  [/tsiya/gi, 'ция'],
  [/reestr/gi, 'реэстр'],
  [/F\.I\.O/g, 'Ф.И.Ш'],
]

const SINGLE: Record<string, string> = {
  a: 'а', b: 'б', d: 'д', f: 'ф', g: 'г', h: 'ҳ', i: 'и', j: 'ж', k: 'к', l: 'л', m: 'м', n: 'н', o: 'о', p: 'п',
  q: 'қ', r: 'р', s: 'с', t: 'т', u: 'у', v: 'в', x: 'х', y: 'й', z: 'з', c: 'с', w: 'в',
}

const isUpper = (ch: string) => ch !== ch.toLowerCase()
const cased = (src: string, out: string) => (isUpper(src[0]) ? out.charAt(0).toUpperCase() + out.slice(1) : out)

// Bitta so'zni (lotin harflari va tutuq belgisi) o'giradi
function word(w: string): string {
  const allCaps = w.length > 1 && w === w.toUpperCase()
  const low = w.toLowerCase().replace(new RegExp(APOS, 'g'), "'")
  let out = ''
  for (let i = 0; i < low.length; ) {
    const c = low[i]
    const next = low[i + 1]
    const src = w[i]
    const up = (s: string) => (allCaps ? s.toUpperCase() : cased(src, s))
    if ((c === 'o' || c === 'g') && next === "'") {
      out += up(c === 'o' ? 'ў' : 'ғ')
      i += 2
    } else if (c === 's' && next === 'h') {
      out += up('ш')
      i += 2
    } else if (c === 'c' && next === 'h') {
      out += up('ч')
      i += 2
    } else if (c === 'n' && next === 'g') {
      out += allCaps ? 'НГ' : cased(src, 'нг')
      i += 2
    } else if (c === 'y' && (next === 'a' || next === 'u' || (next === 'o' && low[i + 2] !== "'"))) {
      out += up(next === 'a' ? 'я' : next === 'u' ? 'ю' : 'ё')
      i += 2
    } else if (c === 'y' && next === 'e') {
      out += up('е')
      i += 2
    } else if (c === 'e') {
      const prev = low[i - 1]
      // э: so'z boshida, tutuqdan keyin va a/o dan keyin (аэропорт, поэт); реестр, проект kabilarda — е
      out += up(i === 0 || prev === 'a' || prev === 'o' || prev === "'" ? 'э' : 'е')
      i += 1
    } else if (c === "'") {
      out += 'ъ'
      i += 1
    } else if (SINGLE[c]) {
      out += up(SINGLE[c])
      i += 1
    } else {
      out += w[i]
      i += 1
    }
  }
  return out
}

const PROTECTED_RE = new RegExp(`\\b(?:${PROTECTED.map((p) => p.replace(/[-/\\^$*+?.()|[\]{}]/g, '\\$&')).join('|')})\\b`, 'g')
// {o'rinbosar}, havola, e-pochta, raqam aralash so'z — o'zgarishsiz qoladi
const KEEP_RE = /\{\w+\}|https?:\/\/\S+|[\w.+-]+@[\w-]+\.[\w.-]+|[A-Za-z]*\d[A-Za-z\d]*/g
const WORD_RE = new RegExp(`[A-Za-z](?:[A-Za-z]|${APOS}(?=[A-Za-z]))*`, 'g')

/** Lotin o'zbekchani kirillga o'giradi: toCyrillic("Hujjatlar ro'yxati") → "Ҳужжатлар рўйхати" */
export function toCyrillic(text: string): string {
  if (!text) return text
  const kept: string[] = []
  const hold = (m: string) => `${MARK}${kept.push(m) - 1}${MARK}`
  let s = text.replace(KEEP_RE, hold).replace(PROTECTED_RE, hold)
  for (const [re, rep] of EXCEPTIONS) s = s.replace(re, (m) => (isUpper(m[0]) ? rep.charAt(0).toUpperCase() + rep.slice(1) : rep))
  s = s.replace(WORD_RE, word)
  return s.replace(new RegExp(`${MARK}(\\d+)${MARK}`, 'g'), (_, i: string) => kept[Number(i)])
}
