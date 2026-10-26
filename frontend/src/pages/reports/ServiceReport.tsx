import DatePicker from '../../components/DatePicker'
import { useEffect, useState } from 'react'
import { Select } from '../../ds'
import { useToast } from '../../components/toast'
import { useT } from '../../i18n'
import { reportData } from './api'
import type { ReportForm } from './api'
import DocEditor from './DocEditor'
import { useDoc } from './doc'
import type { DocApi } from './doc'
import { amountInWords, esc, formatMoney, formatNumber, initialSurname, joinWithVa, lowerFirst, monthRange, quarterOfDate, todayDmy } from './format'
import { FilterCard, MultiPicker, ReportGrid, ReportShell, SignCard } from './shared'
import { empOptions, toId } from './options'
import type { SvodMaterial, SvodResponse } from './SvodReport'
import { DUK_NAME, messageRow, serviceTemplate } from './templates'

// templates/main/service.html — "Sarf materiallar" (main.views.service_get / service_post,
// ajax_svod_materials?service_mode=1 + ajax_service_materials)

interface ServiceItem {
  outcome: number
  total_sum: string | number
  full_name: string | null
  rank_name: string | null
  owner_unit: string
  body: string | null
  material__name: string
  material__unit__name: string | null
  material__price: string | number | null
  material__code: string | null
}

interface Owner {
  full_name: string
  rank: string
  unit: string
}

/** Hujjat matni: "<Bo'lim>, <lavozim> <I. Familiya>" — "A va B" / "A, B va C" */
function peopleText(list: Owner[]) {
  return joinWithVa(
    list
      .map((p) => {
        const unit = (p.unit || '').trim()
        const person = [lowerFirst(p.rank), initialSurname(p.full_name, true)].filter(Boolean).join(' ')
        return unit && person ? `${unit}, ${person}` : unit || person
      })
      .filter(Boolean),
  )
}

function ServicePage({ form, doc }: { form: ReportForm; doc: DocApi }) {
  const t = useT()
  const toast = useToast()
  const init = monthRange()
  const [date1, setDate1] = useState(init.date1)
  const [date2, setDate2] = useState(init.date2)
  const [sender, setSender] = useState<number | null>(null)
  const [agreements, setAgreements] = useState<number[]>([])

  const myOrg = form.my_org
  const myRegion = form.my_region

  useEffect(() => {
    doc.setText('#doc_date', `${todayDmy()} y.`)
  }, [doc])

  // Hisobot davri: yil va chorak oraliqning oxirgi sanasidan
  useEffect(() => {
    const q = quarterOfDate(date2 || date1)
    if (!q) return
    doc.setText('#year', q.year)
    doc.setText('#chorak', q.quarter)
  }, [doc, date1, date2])

  /** Moddiy-javobgar shaxslar (dublikatsiz) → matn ichida va hujjat pastida */
  const renderResponsible = (people: Owner[]) => {
    const seen = new Set<string>()
    const list = people.filter((p) => {
      const key = (p.full_name || '').trim().toLowerCase()
      if (!p.full_name || seen.has(key)) return false
      seen.add(key)
      return true
    })
    doc.setText('#blok_javobgar', peopleText(list) || '_')
    doc.setText('#blok_javobgar_ism', joinWithVa(list.map((p) => initialSurname(p.full_name, true)).filter(Boolean)) || '_')
    doc.setHTML(
      '#blok_3',
      list.length
        ? '<div><b>Tovar-moddiy boyliklar uchun moddiy-javobgar shaxs:</b></div>' +
            list
              .map(
                (p) =>
                  `<div><table style="border-collapse:collapse;width:100%;"><colgroup><col style="width:50%;"><col style="width:50%;"></colgroup><tbody><tr>
                    <td style="border:1px solid #fff;text-align:left;"><b>${esc(p.rank || '')}</b></td>
                    <td style="border:1px solid #fff;text-align:left;"><b>${esc(initialSurname(p.full_name))}</b></td></tr></tbody></table></div>`,
              )
              .join('')
        : '',
    )
  }

  const search = async () => {
    if (!date1 || !date2) {
      toast("Iltimos, sanalarni to'liq tanlang!", 'error')
      return
    }
    if (!myOrg || !myRegion) {
      toast("Tashkilot yoki hudud aniqlanmadi. Administrator bilan bog'laning.", 'error')
      return
    }
    doc.setText('#doc_date', `${todayDmy()} y.`)
    doc.setHTML('#materials_tbody', messageRow(8, 'Yuklanmoqda...', 'loading'))
    try {
      // 1) ATM ning o'ziga yopilgan arizalar (Svod formatida), 2) qo'lda sarflangan materiallar — bitta jadvalda
      const [orders, service] = await Promise.all([
        reportData<SvodResponse>('svod-materials', { service_mode: 1, date1, date2, region: myRegion.id }),
        reportData<ServiceItem[]>('service-materials', { 'organizations[]': [myOrg.id], date1, date2, region: myRegion.id }),
      ])
      const orderItems: SvodMaterial[] = (orders.organizations || []).flatMap((o) => o.regions.flatMap((r) => r.materials))
      const serviceItems = Array.isArray(service) ? service : []
      const owners: Owner[] = [
        ...(orders.material_owners || []),
        ...serviceItems.map((it) => ({ full_name: it.full_name || '', rank: it.rank_name || '', unit: it.owner_unit })),
      ]

      if (!orderItems.length && !serviceItems.length) {
        renderResponsible([])
        doc.setText('#blok_summa_soz', '')
        doc.setHTML('#materials_tbody', messageRow(8, "Tanlangan sana oralig'ida ma'lumot topilmadi", 'empty'))
        return
      }

      const td = (s: string) => `<td style="border:1px solid #000;font-size:8pt;text-align:center;">${s}</td>`
      let index = 1
      let total = 0
      let rows = ''
      orderItems.forEach((m) => {
        total += Number(m.total_sum) || 0
        const info = (m.order_info || []).map(esc).join(',<br>')
        rows += '<tr>' + [`${index++}.`, esc(m.material__name), esc(m.material__unit__name || 'dona'), formatNumber(m.total_number), formatMoney(m.material__price), formatMoney(m.total_sum), info || '-', esc(m.material__code) || '-'].map(td).join('') + '</tr>'
      })
      serviceItems.forEach((m) => {
        total += Number(m.total_sum) || 0
        rows += '<tr>' + [`${index++}.`, esc(m.material__name), esc(m.material__unit__name || 'dona'), formatNumber(m.outcome), formatMoney(m.material__price), formatMoney(m.total_sum), esc(m.body) || '-', esc(m.material__code) || '-'].map(td).join('') + '</tr>'
      })
      const total_ = (label: string, size: string, bg: string) =>
        `<tr><td colspan="5" style="border:1px solid #000;font-size:${size};text-align:right;font-weight:bold;background-color:${bg};">${label} jami:</td>
          <td style="border:1px solid #000;font-size:${size};text-align:center;font-weight:bold;background-color:${bg};">${formatMoney(total)}</td>
          <td colspan="2" style="border:1px solid #000;background-color:${bg};"></td></tr>`
      rows += total_(DUK_NAME, '8pt', 'rgb(253,246,220)') + total_(esc(myRegion.name || "Noma'lum hudud"), '9pt', 'rgb(251,238,184)')
      rows += `<tr><td colspan="5" style="border:1px solid #000;font-size:10pt;text-align:right;font-weight:bold;background-color:rgb(245,199,86);">Jami:</td>
        <td style="border:1px solid #000;font-size:10pt;text-align:center;font-weight:bold;background-color:rgb(245,199,86);">${formatMoney(total)}</td>
        <td colspan="2" style="border:1px solid #000;background-color:rgb(245,199,86);"></td></tr>`

      doc.setHTML('#materials_tbody', rows)
      doc.setText('#blok_summa_soz', amountInWords(total))
      renderResponsible(owners)
    } catch (e) {
      doc.setHTML('#materials_tbody', messageRow(8, `Xatolik yuz berdi: ${(e as Error).message}`, 'error'))
    }
  }

  return (
    <ReportGrid
      side={
        <>
          <FilterCard onSearch={search} doc={doc} orientation="Landscape" filename="sarf_material">
            <div className="rep-note type-para-xs">
              {t("Hisobot o'z tashkilotingiz ({org}) va hududingiz ({region}) bo'yicha shakllanadi.", { org: myOrg?.name ?? '—', region: myRegion?.name ?? '—' })}
            </div>
            <DatePicker label="Boshlang'ich sanasi" required value={date1} max={date2} onChange={setDate1} />
            <DatePicker label="Tugash sanasi" required value={date2} min={date1} onChange={setDate2} />
          </FilterCard>

          <SignCard kind="service" doc={doc} fields={() => ({ date1, date2, sender, 'agreements[]': agreements })}>
            <Select label={t("Imzolovchi xodim")} placeholder={t("Tanlang...")} options={empOptions(form.senders)} value={sender} onChange={(v) => setSender(toId(v))} />
            <MultiPicker label="Kelishuvchilar" options={empOptions(form.agreements)} value={agreements} onChange={setAgreements} />
          </SignCard>
        </>
      }
    >
      <DocEditor doc={doc} template={serviceTemplate(form.report_year ?? '', form.report_quarter ?? '', myRegion?.name ?? '')} landscape />
    </ReportGrid>
  )
}

export default function ServiceReport() {
  const doc = useDoc()
  return <ReportShell kind="service">{(form) => <ServicePage form={form} doc={doc} />}</ReportShell>
}
