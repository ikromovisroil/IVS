import DatePicker from '../../components/DatePicker'
import { useEffect, useState } from 'react'
import { Select } from '../../ds'
import { useToast } from '../../components/toast'
import { useT } from '../../i18n'
import { reportData, useDepartments, useOrgEmployees } from './api'
import type { ReportForm, ReportsMeta } from './api'
import DocEditor from './DocEditor'
import { useDoc } from './doc'
import type { DocApi } from './doc'
import { amountInWords, empLabel, esc, formatNumberAkt, monthRange, rankCase, todayDmy } from './format'
import { FilterCard, ReportGrid, ReportShell, SignCard } from './shared'
import { empOptions, toId } from './options'
import { AKT_HEADER_ROWS, aktTemplate, messageRow } from './templates'

// templates/main/akt.html — "Akt" (main.views.akt_get / akt_post, ajax_akt_materials)

interface AktItem {
  order__id: number
  order__date_finished: string | null
  order__technics__name: string | null
  order__technics__serial: string | null
  material__name: string | null
  number: number
  material__unit__name: string | null
  material__price: string | number | null
  full_name: string | null
  rank_name: string | null
}

/** Akt jadvalida summa ustuni yo'q: jami = har bir materialning miqdori x birlik narxi */
function aktTotal(data: AktItem[]): number {
  return data.reduce((sum, it) => sum + (parseFloat(String(it.number ?? 0)) || 0) * (parseFloat(String(it.material__price ?? 0)) || 0), 0)
}

function aktRows(data: AktItem[]): string {
  const td = (s: string) => `<td style="border:1px solid #000;font-size:8pt;text-align:center;">${s}</td>`
  return data
    .map((it, i) => {
      let finished = '-'
      if (it.order__date_finished) {
        const dt = new Date(it.order__date_finished)
        if (!isNaN(dt.getTime())) finished = dt.toLocaleDateString('ru-RU')
      }
      return (
        '<tr>' +
        [
          `${i + 1}.`,
          esc(it.order__technics__name || '-'),
          esc(it.order__technics__serial || '-'),
          esc(it.material__name || '-'),
          formatNumberAkt(it.number),
          esc(it.material__unit__name || '-'),
          esc(it.full_name || '-'),
          esc(it.rank_name ? rankCase(it.rank_name) : '-'),
          formatNumberAkt(it.material__price),
          esc(it.order__id || '-'),
          finished,
        ]
          .map(td)
          .join('') +
        '</tr>'
      )
    })
    .join('')
}

function AktPage({ form, meta, doc }: { form: ReportForm; meta: ReportsMeta; doc: DocApi }) {
  const t = useT()
  const toast = useToast()
  const init = monthRange()
  const regions = form.regions ?? []
  const [org, setOrg] = useState<number | null>(null)
  const [region, setRegion] = useState<string>(form.has_full_region ? 'all' : regions[0] ? String(regions[0].id) : 'all')
  const [dep, setDep] = useState<number | null>(null)
  const [date1, setDate1] = useState(init.date1)
  const [date2, setDate2] = useState(init.date2)
  const [sender, setSender] = useState<number | null>(null)

  // Hudud tanlanmagan bo'lsa ("Barcha hududlar") bo'limlar joriy foydalanuvchi hududi bo'yicha (eski userRegion)
  const regionId = region === 'all' ? null : Number(region)
  const effectiveRegion = regionId ?? form.user_region
  const ready = !!org && !!effectiveRegion
  const deps = useDepartments(org, effectiveRegion, ready)
  const signers = useOrgEmployees('signatories', org, dep, ready)

  const orgObj = form.organizations?.find((o) => o.id === org)
  const depName = deps.data?.find((d) => d.id === dep)?.name ?? ''
  const senderObj = signers.data?.find((e) => e.id === sender)
  const regionOptions = [...(form.has_full_region ? [{ value: 'all', label: t('Barcha hududlar') }] : []), ...regions.map((r) => ({ value: String(r.id), label: r.name }))]

  useEffect(() => {
    doc.setText('#doc_date', `${todayDmy()} y.`)
  }, [doc])

  // updateEditorWithSelections
  const orgName = orgObj?.name ?? ''
  const contract = (orgObj?.contract ?? '').trim()
  const senderFull = senderObj ? empLabel(senderObj) : ''
  const senderName = senderObj?.full_name ?? ''
  useEffect(() => {
    doc.setText('#org_id_1, #org_id_2', orgName || 'Tashkilot')
    doc.setText('#dep_id', depName || 'Departament')
    doc.setText('#date_contract', contract ? `${contract}ga muvofiq` : '')
    doc.setText('#sender_name1', senderFull || '_')
    doc.setText('#sender_name2', senderName || senderFull || '_')
  }, [doc, orgName, depName, contract, senderFull, senderName])

  const search = async () => {
    if (!org || !regionId || !date1 || !date2) {
      toast("Iltimos, tashkilot, hudud va sanalarni to'liq tanlang!", 'error')
      return
    }
    doc.setText('#doc_date', `${todayDmy()} y.`)
    const setRows = (rows: string) => doc.setHTML('#materials_tbody', AKT_HEADER_ROWS + rows)
    doc.setText('#blok_summa_soz', '')
    setRows(`<tr><td colspan="11" style="text-align:center;padding:20px;"><i>Yuklanmoqda...</i></td></tr>`)
    try {
      const data = await reportData<AktItem[]>('akt-materials', { organization: org, department: dep, region: regionId, date1, date2 })
      setRows(data?.length ? aktRows(data) : `<tr><td colspan="11" style="text-align:center;color:#888;padding:20px;">Tanlangan sana oralig'ida ma'lumot topilmadi</td></tr>`)
      doc.setText('#blok_summa_soz', data?.length ? amountInWords(aktTotal(data)) : '')
    } catch (e) {
      setRows(messageRow(11, `Xatolik yuz berdi: ${(e as Error).message}`, 'error'))
    }
  }

  const resetDeps = () => {
    setDep(null)
    setSender(null)
  }

  return (
    <ReportGrid
      side={
        <>
          <FilterCard onSearch={search} doc={doc} orientation="Landscape" filename="akt">
            <Select
              label={`${t('Tashkilot')} *`}
              placeholder={t("Tanlang...")}
              options={(form.organizations ?? []).map((o) => ({ value: o.id, label: o.name }))}
              value={org}
              onChange={(v) => {
                setOrg(toId(v))
                resetDeps()
              }}
            />
            <Select
              label={t("Hudud")}
              options={regionOptions}
              value={region}
              onChange={(v) => {
                setRegion(v == null ? 'all' : String(v))
                resetDeps()
              }}
            />
            <Select
              label={t("Departament")}
              placeholder={deps.isFetching ? t('Yuklanmoqda...') : t('Tanlang...')}
              options={(deps.data ?? []).map((d) => ({ value: d.id, label: d.name }))}
              value={dep}
              disabled={!ready}
              onChange={(v) => {
                setDep(toId(v))
                setSender(null)
              }}
            />
            <DatePicker label="Boshlang'ich sanasi" required value={date1} max={date2} onChange={setDate1} />
            <DatePicker label="Tugash sanasi" required value={date2} min={date1} onChange={setDate2} />
          </FilterCard>

          <SignCard kind="akt" doc={doc} fields={() => ({ organization: org, region: regionId, department: dep, date1, date2, sender })}>
            <Select
              label={t("Imzolovchi xodim")}
              placeholder={signers.isFetching ? t('Yuklanmoqda...') : t('Tanlang...')}
              options={empOptions(signers.data)}
              value={sender}
              disabled={!ready}
              onChange={(v) => setSender(toId(v))}
            />
          </SignCard>
        </>
      }
    >
      <DocEditor doc={doc} template={aktTemplate(meta.employee?.full_name ?? '', meta.employee?.rank ?? '')} landscape />
    </ReportGrid>
  )
}

export default function AktReport() {
  const doc = useDoc()
  return <ReportShell kind="akt">{(form, meta) => <AktPage form={form} meta={meta} doc={doc} />}</ReportShell>
}
