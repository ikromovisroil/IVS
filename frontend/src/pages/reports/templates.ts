

// Hujjatlarning boshlang‘ich HTML matni — eski TinyMCE shablonlaridan (templates/main/*.html, <textarea id="body">)
// o‘zgarishsiz ko‘chirilgan. Bu PDF va imzolanadigan hujjat MAZMUNI (interfeys emas): ichki inline uslublar
// (qora/oq chegaralar, jadval fonlari) PDF da aynan shunday chiqishi uchun saqlanadi.
import { esc, rankCase } from './format'

const SIGN_COLS = '<colgroup><col style="width:50%;"><col style="width:50%;"></colgroup>'

/** "Kelishildi / Lavozim — F.I.SH" kabi ikki ustunli imzo jadvali */
function signRow(left: string, right: string, align = 'left'): string {
  return `<div><table style="border-collapse:collapse;width:100%;">${SIGN_COLS}<tbody><tr>
    <td style="border:1px solid #fff;text-align:${align};">${left}</td>
    <td style="border:1px solid #fff;text-align:${align};">${right}</td>
  </tr></tbody></table></div>`
}

const th = (text: string, extra = '', bold = true) =>
  `<td style="border:1px solid #000;font-size:8pt;text-align:center;${bold ? 'font-weight:bold;' : ''}"${extra}>${text}</td>`

const TASDIQLAYMAN_SVOD = `<b>"Tasdiqlayman"<br>
  “O‘zbekiston Respublikasi<br>
  Iqtisodiyot va moliya vazirligi huzuridagi<br>
  Axborot texnologiyalari markazi” DUK<br>
  Direktori<br>
  Xujamqulov F.B.<br>
</b>
<b id="doc_date">__.__.____ y.</b>`

const COMMON_SIGNERS =
  signRow("<b>Kelishildi</b><br><b>Boshqarma boshlig‘i</b>", '<b>NARZULLAYEV ANVAR SHUHRAT O‘G‘LI.</b><br>') +
  signRow('<b>Tekshirdi va qabul qildi</b><br><b>Bosh mutaxassis</b>', '<b>YAKUSHINA YELENA ANATOLEVNA.</b><br>') +
  signRow('<b>Kelishildi</b><br><b>Bosh hisobchi</b>', '<b>ERGASHEVA NARGIZA RUSTAMOVNA.</b><br>')

// ─── Dalolatnoma (document.html) ───
export const DOCUMENT_TEMPLATE = `<div style="font-size:10pt;">
  <div style="text-align:center;"><b>DALOLATNOMA</b></div>
  <div style="text-align:right;line-height:2;"><span id="doc_date">__.__.____ y.</span></div>
  <div style="text-align:justify; text-indent:1.25cm;">
    Biz quyida imzo chekuvchilar,
    <span id="org_name"></span>
    <span id="dep_name"></span>
    <span id="receiver_rank"></span>
    <b id="receiver_name"></b><span id="receiver_comma"></span>
    va “O‘zbekiston Respublikasi Iqtisodiyot va moliya vazirligi
    huzuridagi Axborot texnologiyalari markazi” DUK
    <span id="sender_rank"></span>
    <b id="sender_name"></b>:
    <span id="org_name"></span> hamda
    O‘zbekiston Respublikasi Iqtisodiyot va moliya vazirligi
    huzuridagi Axborot texnologiyalari markazlari tomonidan
    <b><span id="date_contract"></span></b>
    <span id="dep_id2"></span>
    <span id="year"></span>-yil <span id="chorak"></span> chorak uchun quyidagi
    ishlar va xizmatlar bajarildi.
    Ishlar texnologik xaritaga muvofiq amalga oshirildi.
  </div>
  <div></div>
  <div id="liable_page1"></div>
  <div></div><div></div><div></div>
  ${signRow(
    `<b><span id="org_name"></span> <span id="dep_name"></span> <span id="receiver_rank"></span></b><br><br><b id="receiver_name"></b>`,
    `<b>“O‘zbekiston Respublikasi Iqtisodiyot va moliya vazirligi huzuridagi Axborot texnologiyalari markazi” DUK <span id="sender_rank"></span></b><br><br><b id="sender_name"></b>`,
    'center',
  )}
  <div style="page-break-after:always;"></div>
  <div style="text-align:center;line-height:2;"><b>DALOLATNOMAga 1-ilova</b><br></div>
  <div style="text-align:right;"><span id="doc_date2">__.__.____ y.</span></div>
  <div style="text-align:center;"><b>Kompyuter va printer texnikalariga tizimli va texnik xizmat
    ko‘rsatishni amalga oshirish hisoboti</b></div>
  <div style="text-align:center;"><b><u id="org_name"></u><br><u id="dep_name"></u></b><br>
    <span style="font-size:7pt;">(boshqarma nomi)</span></div><br>
  <div style="text-align:left;line-height:2;"><b>Xizmat ko‘rsatilayotgan texnikalarning rusumi va seriya raqami:</b></div>
  <div id="liable_page2"></div>
  <div></div>
  <div id="imv_block"></div><div></div>
  <div id="ivs_block"></div>
</div>`

// ─── Yakuniy hisobot (svod.html) ───
export const SVOD_TEMPLATE = `<div style="font-size:10pt;">
  ${signRow('', TASDIQLAYMAN_SVOD, 'center')}
  <div></div>
  <div style="text-align:center;"><b>Kompyuter va ofis uskunalariga servis xizmat ko‘rsatish jarayonida foydalanilgan</b></div>
  <div style="text-align:center;"><b>sarf materiallar, ehtiyot qismlar va uskunalar bo‘yicha</b></div>
  <div style="text-align:center;"><b>YAKUNIY HISOBOT</b></div>
  <div style="text-align:center;"><b id="report_period"></b></div>
  <div>
    <table style="border-collapse:collapse;width:100%;">
      <colgroup><col style="width:5%;"><col style="width:23%;"><col style="width:10%;"><col style="width:10%;"><col style="width:12%;"><col style="width:12%;"><col style="width:18%;"><col style="width:10%;"></colgroup>
      <thead>
        <tr>${th('№')}${th('Materiallarning nomi')}${th("O‘lchov birligi")}${th('Miqdor')}${th('Birlik narxi')}${th('Umumiy qiymati')}${th('Eslatma*')}${th('Kod 1C')}</tr>
        <tr>${[1, 2, 3, 4, 5, 6, 7, 8].map((n) => th(String(n), '', false)).join('')}</tr>
      </thead>
      <tbody id="materials_tbody"></tbody>
    </table>
  </div><br>
  <div style="text-align:left;"><b id="blok_summa_soz"> </b></div><br>
  <div style="text-align:left;"><b><span id="date_contract"></span></b></div>
  ${COMMON_SIGNERS}
  <div id="responsible_employees_block">
    <table style="border-collapse:collapse;width:100%;">${SIGN_COLS}<tbody id="responsible_employees_tbody"></tbody></table>
  </div>
</div>`

// ─── Reestr (reestr.html) ───
export const REESTR_TEMPLATE = `<div style="font-size:10pt;">
  <div style="text-align:center;"><b>Kompyuter va ofis uskunalariga servis xizmat ko‘rsatish jarayonida foydalanilgan</b></div>
  <div style="text-align:center;"><b>sarf materiallar, ehtiyot qismlar va uskunalar bo‘yicha</b></div>
  <div style="text-align:center;"><b>R E E S T R I</b></div>
  <div style="text-align:center;"><b><span id="org_id"></span></b></div>
  <div style="text-align:center;"><b><span id="reg_id"></span></b></div>
  <div style="text-align:center;"><b id="report_period"></b></div>
  <div>
    <table style="border-collapse:collapse;width:100%;">
      <colgroup>${[3, 8, 7, 12, 4, 5, 6, 8, 8, 12, 8, 6, 4, 5, 4].map((w) => `<col style="width:${w}%;">`).join('')}</colgroup>
      <thead>
        <tr>
          ${th('№', ' rowspan="2"')}${th('Qurilma nomi', ' rowspan="2"')}${th('Seriya №', ' rowspan="2"')}${th('Sarf materiallari nomi', ' rowspan="2"')}
          ${th('Soni', ' rowspan="2"')}${th('Birlikdagi narxi', ' rowspan="2"')}${th('Materiallarning umumiy qiymati', ' rowspan="2"')}
          ${th('Qurilmadan foydalanuvchi', ' colspan="2"')}${th("Tashkilot, bo‘lim nomi", ' rowspan="2"')}${th("Kim tomonidan o‘rnatilgan", ' rowspan="2"')}
          ${th("O‘rnatish sanasi", ' rowspan="2"')}${th("So‘rovnoma №", ' rowspan="2"')}${th("So‘rovnoma sanasi", ' rowspan="2"')}${th('1C kodi', ' rowspan="2"')}
        </tr>
        <tr>${th('F.I.Sh.')}${th('Lavozimi')}</tr>
      </thead>
      <tbody id="materials_tbody"></tbody>
    </table>
  </div><br>
  <div style="text-align:left;"><b id="blok_summa_soz"> </b></div><br>
  <div style="text-align:left;"><b><span id="date_contract"></span></b></div>
  ${COMMON_SIGNERS}
  <div><table style="border-collapse:collapse;width:100%;">${SIGN_COLS}<tbody id="service_employees_tbody"></tbody></table></div>
</div>`

// ─── Akt (akt.html) ───
export const AKT_HEADER_ROWS = `<tr>
  ${th('№', ' rowspan="2"')}${th('Ish bajarilgan qurilma nomi', ' rowspan="2"')}${th('Qurilma seriya raqami', ' rowspan="2"')}
  ${th('Sarf materiallari, ehtiyot qismlar, uskunalar nomi', ' rowspan="2"')}${th('Soni', ' rowspan="2"')}${th('O‘lchov birligi', ' rowspan="2"')}
  ${th('Kimga o‘rnatildi yoki o‘rnatilganligini tasdiqlovchi mas’ul shaxs (xarajatlar)', ' colspan="5"')}
</tr>
<tr>${th('F.I.Sh.')}${th('Lavozimi')}${th('Eslatma*')}${th('So‘rovnoma №')}${th('O‘rnatish sanasi')}</tr>`

export function aktTemplate(userName: string, userRank: string): string {
  return `<div style="font-size:10pt;">
  <div style="text-align:center;"><b>Sarf materiallari, ehtiyot qismlar va uskunalarni o‘rnatish ishlari haqida</b></div>
  <div style="text-align:center;"><b>DALOLATNOMA</b></div>
  <div style="text-align:right;"><u id="doc_date">_</u></div>
  <div style="text-align:center;">
    Biz, quyida imzo chekuvchilar, “O‘zbekiston Respublikasi Iqtisodiyot va moliya vazirligi huzuridagi
    Axborot texnologiyalari markazi” davlat unitar korxonasining vakillari:
  </div>
  <div style="text-align:center;"><b><u>${esc(userName)} (${esc(rankCase(userRank))})</u></b></div>
  <div style="text-align:center;font-size:8pt;">(F.I.Sh., ATM mutaxassisining lavozimi)</div>
  ${signRow(
    `<span><span id="org_id_1">Iqtisodiyot va Moliya vazirligi</span> tashkiloti xodimi:</span><br><b id="sender_name1"><u>_</u></b><br><span style="text-align:center;font-size:8pt;">(F.I.Sh., lavozimi)</span>`,
    `<span id="dep_id">Muvofiqlashtirish va axborot-tahlil departamenti</span><br><span>ushbu dalolatnoma quyidagi ishlar bajarilganligi uchun tuzilgan:</span>`,
    'center',
  )}
  <div style="text-align:center;margin-top:12px;">
    <b><u>Quyida ko‘rsatilgan materiallarni o‘rnatish</u></b><br>
    <span style="text-align:center;font-size:8pt;">(Mutaxassislar tomonidan bajarilgan ish turlari bo‘yicha tafsilotlar)</span>
  </div>
  <div style="margin-top:10px;">${signRow(
    '<strong>Qurilmalarga texnik xizmat ko‘rsatish bo‘limi mutaxassislari tomonidan</strong><br><strong>quyidagi sarf materiallari, ehtiyot qismlar va uskunalar o‘rnatildi:</strong>',
    '<strong><span id="date_contract"></span></strong>',
    'center',
  )}</div>
  <div>
    <table style="border-collapse:collapse;width:100%;">
      <colgroup>${[3, 13, 10, 22, 4, 6, 12, 12, 8, 5, 5].map((w) => `<col style="width:${w}%;">`).join('')}</colgroup>
      <tbody id="materials_tbody">${AKT_HEADER_ROWS}</tbody>
    </table>
  </div><br>
  <div style="text-align:left;"><b id="blok_summa_soz"> </b></div><br>
  <div style="text-align:left;"><b>Yaroqsiz ehtiyot qismlar foydalanuvchida qoldirildi.</b></div>
  <div style="text-align:left;">Izoh: o‘rnatilgan ehtiyot qismlar yoki asbob-uskunalarning birlik narxi buxgalteriya hisobi uchun ko‘rsatiladi.</div>
  ${signRow(
    `<b>Xizmat ko‘rsatuvchi mutaxassis:</b><br><span>${esc(userName)}</span><br><span style="text-align:center;font-size:8pt;">(F.I.Sh.)</span>`,
    `<b><span id="org_id_2">Tashkilot</span> tashkiloti xodimi:</b><br><span id="sender_name2">_</span><br><span style="text-align:center;font-size:8pt;">(F.I.Sh.)</span>`,
    'center',
  )}
</div>`
}

// ─── Sarf materiallar (service.html) ───
export const DUK_NAME = '“O‘zbekiston Respublikasi Iqtisodiyot va Moliya vazirligi huzuridagi Axborot texnologiyalari markazi” DUK'

const COMMISSION: [string, string][] = [
  ['Bo‘lim boshlig‘i Bosh buxgalter', 'N. Ergasheva'],
  ['Bosh buxgalter o‘rinbosari', 'G. Hatamova'],
  ['Boshqarma boshlig‘i', 'A. Narzullayev'],
  ['Bo‘lim boshlig‘i', 'I. Xabirov'],
  ['Boshqarma boshlig‘i ', 'O. Abduqodirov'],
  ['Boshqarma boshlig‘i', 'U. Muxtorov'],
  ['Ish boshqaruvchi', 'A. Abdukarimov'],
  ['Ombor mudiri', 'A. Sa’dullayev'],
]

export function serviceTemplate(year: string | number, quarter: string, regionName: string): string {
  return `<div style="font-size:10pt;">
  ${signRow(
    '',
    `<b>"Tasdiqlayman"<br>“O‘zbekiston Respublikasi<br>Iqtisodiyot va Moliya vazirligi huzuridagi<br>Axborot texnologiyalari markazi” DUK<br>Direktori<br>F. Xujamqulov<br></b><b id="doc_date">__.__.____ y.</b>`,
    'center',
  )}<br><br>
  <div style="text-align:center; font-size:12pt;"><b>
    O‘zbekiston Respublikasi Iqtisodiyot va Moliya vazirligi infratuzilmasini qo‘llab-quvvatlashda<br>
    ishning bajarilish jarayonidagi uskuna va materiallarni hisobdan chiqarish bo‘yicha</b></div>
  <div style="text-align:center;"><b>DALOLATNOMA</b></div>
  <div style="text-align:center;"><b><span id="year">${esc(year)}</span>-yil <span id="chorak">${esc(quarter)}</span> - chorak uchun</b></div><br>
  <div style="text-align:justify; text-indent:1.25cm;">
    Biz quyida imzo chekuvchilar “O‘zbekiston Respublikasi Iqtisodiyot va Moliya vazirligi huzuridagi Axborot texnologiyalari markazi”
    DUKning moddiy boyliklarini hisobdan chiqarish bo‘yicha doimiy komissiya raisi: Direktorning o‘rinbosari N. Nazarov, komissiya a’zolari:
    Bo‘lim boshlig‘i Bosh buxgalter N. Ergasheva, bosh buxgalter o‘rinbosari G. Hatamova, boshqarma boshlig‘i A. Narzullayev,
    bo‘lim boshlig‘i I. Xabirov, boshqarma boshlig‘i O. Abduqodirov, boshqarma boshlig‘i U. Muxtorov,
    ish boshqaruvchi A. Abdukarimov, ombor mudiri A. Sa’dullayev ushbu dalolatnomani
    <span id="blok_javobgar"></span> nomidagi jadvaldagi ro‘yxatda keltirilgan miqdor va tarkibda kiritilgan inventarizatsiya buyumlarini hisobdan chiqarish uchun tuzdik.
  </div><br>
  <div>
    <table style="border-collapse:collapse;width:100%;">
      <colgroup><col style="width:5%;"><col style="width:23%;"><col style="width:10%;"><col style="width:10%;"><col style="width:12%;"><col style="width:12%;"><col style="width:18%;"><col style="width:10%;"></colgroup>
      <thead>
        <tr>${th('№')}${th('Materiallarning nomi')}${th("O‘lchov birligi")}${th('Miqdor')}${th('Birlik narxi')}${th('Umumiy qiymati')}${th('Eslatma*')}${th('Kod 1C')}</tr>
        <tr>${[1, 2, 3, 4, 5, 6, 7, 8].map((n) => th(String(n), '', false)).join('')}</tr>
        <tr><td colspan="8" style="border:1px solid #000;font-size:8pt;text-align:center;font-weight:bold;background-color:rgb(191,237,210);">${DUK_NAME}</td></tr>
        <tr><td colspan="8" style="border:1px solid #000;font-size:8pt;text-align:center;font-weight:bold;background-color:rgb(191,213,237);">${esc(regionName)}</td></tr>
      </thead>
      <tbody id="materials_tbody"></tbody>
    </table>
  </div><br>
  <div style="text-align:left;"><b id="blok_summa_soz"> </b></div><br>
  <div style="text-align:left;">
    Moliya-iqtisod bo‘limi buxgalteriya hisobida aks etishi va yuqoridagi tovar-moddiy zaxiralarni <span id="blok_javobgar_ism"></span> hisobidan chiqarilishi uchun.
  </div><br>
  <div><b>Komissiya raisi:</b></div>
  ${signRow('<b>Direktorning o‘rinbosari</b>', '<b>N. Nazarov</b>')}<br>
  <div><b>Komissiya a’zolari:</b></div>
  ${COMMISSION.map(([r, n]) => signRow(`<b>${r}</b>`, `<b>${n}</b>`)).join('')}<br>
  <div id="blok_3"></div>
</div>`
}

/** Jadval qatorlari uchun: "Yuklanmoqda...", "ma’lumot topilmadi", xato */
export function messageRow(colspan: number, text: string, kind: 'loading' | 'empty' | 'error', border = '#000'): string {
  const color = kind === 'empty' ? 'color:#888;' : kind === 'error' ? 'color:red;' : ''
  const body = kind === 'loading' ? `<i>${esc(text)}</i>` : esc(text)
  return `<tr><td colspan="${colspan}" style="border:1px solid ${border};text-align:center;${color}padding:14px;font-size:10pt;">${body}</td></tr>`
}
