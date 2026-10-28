import DatePicker from '../../components/DatePicker'
import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Select } from '../../ds'
import { useToast } from '../../components/toast'
import { useT } from '../../i18n'
import { errText, reportData } from './api'
import type { Emp, ReportForm } from './api'
import DocEditor from './DocEditor'
import { useDoc } from './doc'
import type { DocApi } from './doc'
import { amountInWords, esc, formatMonthYearRange, formatNumber, monthRange, rankCase, todayDmy } from './format'
import { FilterCard, MultiPicker, ReportGrid, ReportShell, SignCard } from './shared'
import { empOptions, toId } from './options'
import { SVOD_TEMPLATE, messageRow } from './templates'

// templates/main/svod.html — "Yakuniy hisobot" (main.views.svod_get / svod_post, ajax_svod_materials)

export interface SvodMaterial {
  material__name: string
  material__unit__name: string
  total_number: number
  material__price: number
  total_sum: number
  order_info: string[]
  material__code: string
}

export interface SvodResponse {
  organizations: { organization_id: number; organization_name: string; regions: { region_id: number; region_name: string; materials: SvodMaterial[] }[] }[]
  employees: { id: number; full_name: string; rank: string }[]
  material_owners?: { id: number | null; full_name: string; rank: string; unit: string }[]
}

const td = (s: string, size = '8pt') => `<td style="border:1px solid #000;font-size:${size};text-align:center;">${s}</td>`

function totalRow(label: string, sum: number, size: string, bg: string) {
  return `<tr><td colspan="5" style="border:1px solid #000;font-size:${size};text-align:right;font-weight:bold;background-color:${bg};">${esc(label)}</td>
    <td style="border:1px solid #000;font-size:${size};text-align:center;font-weight:bold;background-color:${bg};">${formatNumber(sum)}</td>
    <td colspan="2" style="border:1px solid #000;background-color:${bg};"></td></tr>`
}

/** Tashkilot → Hudud → materiallar → "{Hudud} jami" → "{Tashkilot} jami" → "Jami" */
/** Svod bo'yicha umumiy jami (jadvaldagi "Jami:" qatori bilan bir xil) */
function svodGrandTotal(orgs: SvodResponse['organizations']): number {
  return orgs.reduce((sum, org) => sum + org.regions.reduce((s, r) => s + r.materials.reduce((t, m) => t + (Number(m.total_sum) || 0), 0), 0), 0)
}

function svodRows(orgs: SvodResponse['organizations']): string {
  let rows = ''
  let index = 1
  let grand = 0
  orgs.forEach((org) => {
    rows += `<tr><td colspan="8" style="border:1px solid #000;font-size:9pt;text-align:center;font-weight:bold;background-color:rgb(191,237,210);">${esc(org.organization_name)}</td></tr>`
    let orgTotal = 0
    org.regions.forEach((region) => {
      rows += `<tr><td colspan="8" style="border:1px solid #000;font-size:8pt;text-align:center;font-weight:bold;background-color:rgb(191,213,237);">${esc(region.region_name)}</td></tr>`
      let regionTotal = 0
      region.materials.forEach((m) => {
        regionTotal += m.total_sum
        orgTotal += m.total_sum
        grand += m.total_sum
        rows +=
          '<tr>' +
          td(`${index++}.`) +
          td(esc(m.material__name)) +
          td(esc(m.material__unit__name || 'dona')) +
          td(formatNumber(m.total_number)) +
          td(formatNumber(m.material__price)) +
          td(formatNumber(m.total_sum)) +
          td((m.order_info || []).map(esc).join(',<br>')) +
          td(esc(m.material__code)) +
          '</tr>'
      })
      rows += totalRow(`${region.region_name} jami:`, regionTotal, '8pt', 'rgb(253,246,220)')
    })
    rows += totalRow(`${org.organization_name} jami:`, orgTotal, '9pt', 'rgb(251,238,184)')
  })
  return rows + totalRow('Jami:', grand, '10pt', 'rgb(245,199,86)')
}


function SvodPage({ form, doc }: { form: ReportForm; doc: DocApi }) {
  const t = useT()
  const toast = useToast()
  const init = monthRange()
  const [orgs, setOrgs] = useState<number[]>([])
  const [region, setRegion] = useState<string | null>(form.has_full_region ? 'all' : form.regions?.[0] ? String(form.regions[0].id) : null)
  const [date1, setDate1] = useState(init.date1)
  const [date2, setDate2] = useState(init.date2)
  const [sender, setSender] = useState<number | null>(null)
  const [agreements, setAgreements] = useState<number[]>([])

  // Kelishuvchilar: birinchi tanlangan tashkilot (va o'z tashkiloti) xodimlari — ajax_agreements_employees
  const firstOrg = orgs[0] ?? null
  const agrList = useQuery({
    queryKey: ['reports', 'agreements', firstOrg],
    queryFn: () => reportData<Emp[]>('agreements', { org_id: firstOrg }),
    enabled: !!firstOrg,
  })
  const agreementOptions = firstOrg ? agrList.data : form.agreements

  const regionOptions = [
    ...(form.has_full_region ? [{ value: 'all', label: t('Barcha hududlar') }] : []),
    ...(form.regions ?? []).map((r) => ({ value: String(r.id), label: r.name })),
  ]

  const contractText =
    (form.organizations ?? [])
      .filter((o) => orgs.includes(o.id))
      .map((o) => (o.contract || '').trim())
      .filter(Boolean)
      .join(', ')

  // updateEditorWithSelections
  useEffect(() => {
    doc.setText('#doc_date', `${todayDmy()} y.`)
    doc.setText('#report_period', formatMonthYearRange(date1, date2))
    doc.setText('#date_contract', contractText ? `${contractText}ga muvofiq` : '')
  }, [doc, date1, date2, contractText, region])

  const search = async () => {
    if (!orgs.length || !date1 || !date2) {
      toast("Iltimos, kamida bitta tashkilot va sanalarni to'liq tanlang!", 'error')
      return
    }
    doc.setText('#blok_summa_soz', '')
    doc.setHTML('#materials_tbody', messageRow(8, 'Yuklanmoqda...', 'loading'))
    doc.setHTML('#responsible_employees_tbody', messageRow(2, 'Yuklanmoqda...', 'loading', '#fff'))
    try {
      const data = await reportData<SvodResponse>('svod-materials', { 'organizations[]': orgs, date1, date2, region: region ?? '' })
      const list = data.organizations || []
      const emps = data.employees || []
      doc.setHTML('#materials_tbody', list.length ? svodRows(list) : messageRow(8, "Tanlangan sana oralig'ida ma'lumot topilmadi", 'empty'))
      doc.setText('#blok_summa_soz', list.length ? amountInWords(svodGrandTotal(list)) : '')
      doc.setHTML(
        '#responsible_employees_tbody',
        list.length && emps.length
          ? emps
              .map(
                (e) =>
                  `<tr><td style="border:1px solid #fff;text-align:left;"><b>${esc(rankCase(e.rank))}</b><br></td><td style="border:1px solid #fff;text-align:left;"><b>${esc(e.full_name)}</b><br></td></tr>`,
              )
              .join('')
          : messageRow(2, 'Ariza bajargan xodimlar topilmadi', 'empty', '#fff'),
      )
    } catch (e) {
      const msg = errText(e)
      doc.setHTML('#materials_tbody', messageRow(8, `${msg}. Batafsil: ${(e as Error).message}`, 'error'))
      doc.setHTML('#responsible_employees_tbody', messageRow(2, msg, 'error', '#fff'))
    }
  }

  return (
    <ReportGrid
      side={
        <>
          <FilterCard onSearch={search} doc={doc} orientation="Landscape" filename="svod">
            <MultiPicker
              label="Tashkilotlar"
              required
              placeholder="Tanlang..."
              options={(form.organizations ?? []).map((o) => ({ value: o.id, label: o.name }))}
              value={orgs}
              onChange={(v) => {
                if (v[0] !== orgs[0]) setAgreements([])
                setOrgs(v)
              }}
            />
            <Select label={t("Hududlar")} options={regionOptions} value={region} onChange={(v) => setRegion(v == null ? null : String(v))} />
            <DatePicker label="Boshlang'ich sanasi" required value={date1} max={date2} onChange={setDate1} />
            <DatePicker label="Tugash sanasi" required value={date2} min={date1} onChange={setDate2} />
          </FilterCard>

          <SignCard kind="svod" doc={doc} fields={() => ({ 'organizations[]': orgs, region, date1, date2, sender, 'agreements[]': agreements })}>
            <Select label={t("Imzolovchi xodim")} placeholder={t("Tanlang...")} options={empOptions(form.senders)} value={sender} onChange={(v) => setSender(toId(v))} />
            <MultiPicker label="Kelishuvchilar" options={empOptions(agreementOptions)} value={agreements} onChange={setAgreements} />
          </SignCard>
        </>
      }
    >
      <DocEditor doc={doc} template={SVOD_TEMPLATE} landscape />
    </ReportGrid>
  )
}

export default function SvodReport() {
  const doc = useDoc()
  return <ReportShell kind="svod">{(form) => <SvodPage form={form} doc={doc} />}</ReportShell>
}
