import DatePicker from '../../components/DatePicker'
import { useEffect, useState } from 'react'
import { Select } from '../../ds'
import { useToast } from '../../components/toast'
import { useT } from '../../i18n'
import { errText, reportData } from './api'
import type { ReportForm, ReportsMeta } from './api'
import DocEditor from './DocEditor'
import { useDoc } from './doc'
import type { DocApi } from './doc'
import { amountInWords, esc, formatMonthYearRange, formatNumber, monthRange } from './format'
import { FilterCard, MultiPicker, ReportGrid, ReportShell, SignCard } from './shared'
import { empOptions, toId } from './options'
import { REESTR_TEMPLATE, messageRow } from './templates'

// templates/main/reestr.html — "Reestr" (main.views.reestr_get / reest_post, ajax_reestr_materials)

interface ReestrItem {
  order_id: number
  date_finished: string
  date_creat: string
  technics_name: string | null
  technics_serial: string | null
  material_code: string
  material_name: string
  number: number
  material__price: number
  total_sum: number
  sender: string
  sender_rank: string | null
  department: string
  receiver: string
  receiver_rank: string | null
}

const td = (s: string) => `<td style="border:1px solid #000;font-size:7pt;text-align:center;">${s}</td>`

function totalRow(label: string, sum: number, size: string, bg: string) {
  return `<tr><td colspan="6" style="border:1px solid #000;font-size:${size};text-align:right;font-weight:bold;background-color:${bg};">${esc(label)}</td>
    <td style="border:1px solid #000;font-size:${size};text-align:center;font-weight:bold;background-color:${bg};">${formatNumber(sum)}</td>
    <td colspan="8" style="border:1px solid #000;background-color:${bg};"></td></tr>`
}

/** Bo'lim bo'yicha guruhlar (birinchi uchragan tartibda) → qatorlar → "{Bo'lim} jami" → "Jami" */
function reestrRows(data: ReestrItem[]): string {
  const groups: { name: string; items: ReestrItem[] }[] = []
  data.forEach((item) => {
    const name = (item.department || '').trim() || "Bo'lim ko'rsatilmagan"
    let g = groups.find((x) => x.name === name)
    if (!g) groups.push((g = { name, items: [] }))
    g.items.push(item)
  })
  let rows = ''
  let grand = 0
  groups.forEach((g) => {
    rows += `<tr><td colspan="15" style="border:1px solid #000;font-size:9pt;text-align:center;font-weight:bold;padding:4px;background-color: rgb(191, 237, 210);">${esc(g.name)}</td></tr>`
    let sum = 0
    g.items.forEach((it, i) => {
      const n = (v: unknown) => parseFloat(String(v ?? 0)) || 0
      sum += n(it.total_sum)
      rows +=
        '<tr>' +
        [
          `${i + 1}.`,
          esc(it.technics_name || ''),
          esc(it.technics_serial || ''),
          esc(it.material_name || ''),
          formatNumber(n(it.number)),
          formatNumber(n(it.material__price)),
          formatNumber(n(it.total_sum)),
          esc(it.sender || ''),
          esc(it.sender_rank || ''),
          esc(it.department || ''),
          esc(it.receiver || ''),
          esc(it.date_finished || ''),
          esc(it.order_id || ''),
          esc(it.date_creat || ''),
          esc(it.material_code || ''),
        ]
          .map(td)
          .join('') +
        '</tr>'
    })
    grand += sum
    rows += totalRow(`${g.name} jami:`, sum, '9pt', 'rgb(251,238,184)')
  })
  return rows + totalRow('Jami:', grand, '10pt', 'rgb(245,199,86)')
}

function ReestrPage({ form, meta, doc }: { form: ReportForm; meta: ReportsMeta; doc: DocApi }) {
  const t = useT()
  const toast = useToast()
  const init = monthRange()
  const regions = form.regions ?? []
  const [org, setOrg] = useState<number | null>(null)
  // Barcha hududlarni ko'ra oladigan xodim uchun "Barcha hududlar" (''), aks holda faqat o'z hududi
  const [region, setRegion] = useState<string>(form.has_full_region ? 'all' : regions[0] ? String(regions[0].id) : '')
  const [date1, setDate1] = useState(init.date1)
  const [date2, setDate2] = useState(init.date2)
  const [sender, setSender] = useState<number | null>(null)
  const [agreements, setAgreements] = useState<number[]>([])

  const orgObj = form.organizations?.find((o) => o.id === org)
  const regionName = regions.find((r) => String(r.id) === region)?.name ?? ''
  const regionOptions = [...(form.has_full_region ? [{ value: 'all', label: t('Barcha hududlar') }] : []), ...regions.map((r) => ({ value: String(r.id), label: r.name }))]

  useEffect(() => {
    doc.setText('#org_id', orgObj?.name || 'Tashkilot')
    doc.setText('#reg_id', regionName)
    doc.setText('#date_contract', orgObj?.contract?.trim() ?? '')
    doc.setText('#report_period', formatMonthYearRange(date1, date2))
  }, [doc, orgObj, regionName, date1, date2])

  const search = async () => {
    if (!org || !date1 || !date2) {
      toast("Iltimos, tashkilot va sanalarni to'liq tanlang!", 'error')
      return
    }
    doc.setText('#blok_summa_soz', '')
    doc.setHTML('#materials_tbody', messageRow(15, 'Yuklanmoqda...', 'loading'))
    try {
      const data = await reportData<ReestrItem[]>('reestr-materials', { organization: org, region, date1, date2 })
      if (!Array.isArray(data) || !data.length) {
        doc.setHTML('#materials_tbody', messageRow(15, "Tanlangan sana oralig'ida ma'lumot topilmadi", 'empty'))
        doc.setHTML('#service_employees_tbody', '')
        return
      }
      doc.setHTML('#materials_tbody', reestrRows(data))
      doc.setText('#blok_summa_soz', amountInWords(data.reduce((sum, it) => sum + (parseFloat(String(it.total_sum ?? 0)) || 0), 0)))
      // Xizmat ko'rsatgan xodimlar (receiver) — har biri bir marta, joriy foydalanuvchidan tashqari
      const seen = new Set<string>()
      const me = (meta.employee?.full_name || '').trim()
      if (me) seen.add(me)
      let service = ''
      data.forEach((it) => {
        const name = (it.receiver || '').trim()
        if (!name || seen.has(name)) return
        seen.add(name)
        service += `<tr><td style="border:1px solid #fff;text-align:left;"><b>${esc(it.receiver_rank || '')}</b><br></td><td style="border:1px solid #fff;text-align:left;"><b>${esc(name)}</b><br></td></tr>`
      })
      doc.setHTML('#service_employees_tbody', service)
    } catch (e) {
      doc.setHTML('#materials_tbody', messageRow(15, `${errText(e)}. Batafsil: ${(e as Error).message}`, 'error'))
    }
  }

  return (
    <ReportGrid
      side={
        <>
          <FilterCard onSearch={search} doc={doc} orientation="Landscape" filename="reestr">
            <Select
              label={`${t('Tashkilot')} *`}
              placeholder={t("Tanlang...")}
              options={(form.organizations ?? []).map((o) => ({ value: o.id, label: o.name }))}
              value={org}
              onChange={(v) => setOrg(toId(v))}
            />
            <Select label={t("Hududlar")} options={regionOptions} value={region} onChange={(v) => setRegion(v == null ? 'all' : String(v))} />
            <DatePicker label="Boshlang'ich sanasi" required value={date1} max={date2} onChange={setDate1} />
            <DatePicker label="Tugash sanasi" required value={date2} min={date1} onChange={setDate2} />
          </FilterCard>

          <SignCard kind="reestr" doc={doc} fields={() => ({ organization: org, region, date1, date2, sender, 'agreements[]': agreements })}>
            <Select label={t("Imzolovchi xodim")} placeholder={t("Tanlang...")} options={empOptions(form.senders)} value={sender} onChange={(v) => setSender(toId(v))} />
            <MultiPicker label="Kelishuvchilar" options={empOptions(form.agreements)} value={agreements} onChange={setAgreements} />
          </SignCard>
        </>
      }
    >
      <DocEditor doc={doc} template={REESTR_TEMPLATE} landscape />
    </ReportGrid>
  )
}

export default function ReestrReport() {
  const doc = useDoc()
  return <ReportShell kind="reestr">{(form, meta) => <ReestrPage form={form} meta={meta} doc={doc} />}</ReportShell>
}
