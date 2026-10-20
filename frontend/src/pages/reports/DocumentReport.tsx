import FileUpload from '../../components/FileUpload'
import { useEffect, useState } from 'react'
import { Select } from '../../ds'
import { useToast } from '../../components/toast'
import { useT } from '../../i18n'
import { reportData, useDepartments, useOrgEmployees } from './api'
import type { ReportForm, ReportsMeta } from './api'
import DocEditor from './DocEditor'
import { useDoc } from './doc'
import type { DocApi } from './doc'
import { esc, shortenFullName, todayDmy } from './format'
import { FilterCard, MultiPicker, ReportGrid, ReportShell, SignCard } from './shared'
import { empOptions, toId } from './options'
import { DOCUMENT_TEMPLATE } from './templates'

// templates/main/document.html — "Dalolatnoma" (main.views.document_get / document_post)

interface Contract {
  contract_id: number
  contract_name: string
  count: number
  items: { id: number; name: string; serial: string; extra_serials?: string[] }[]
  hide_page2: boolean
}

const GROUP_TITLES: Record<string, string> = {
  '1': "1. Kompyuter va boshqa elektron qurilmalarga texnik va tizimli xizmat ko'rsatish: (1-ilova varoqda)",
  '2': "2. Server, umumiy va ma'lumot almashiladigan tarmoqlarlarga texnik va tizimli xizmat ko'rsatish:",
}

const QUARTERS = ['I', 'II', 'III', 'IV'].map((q) => ({ value: q, label: q }))

function contractRows(c: Contract): string {
  const isPC = c.contract_id === 1
  const cell = (s: string, center = false) => `<td style="border:1px solid #000;${center ? 'text-align:center;' : ''}">${s}</td>`
  const head = (s: string) => `<td style="border:1px solid #000;font-size:10pt;text-align:center;">${s}</td>`
  let html = '<tr>' + head('№') + head('Rusumi') + (isPC ? head('Kompyuter SR') + head('Monitor SR') : head('Seriya raqami')) + '</tr>'
  c.items.forEach((x, i) => {
    html += '<tr>' + cell(String(i + 1), true) + cell(esc(x.name)) + cell(esc(x.serial))
    if (isPC) html += cell((x.extra_serials || []).map((s) => `<div>${s.split('\n').map(esc).join('<br>')}</div>`).join(''))
    html += '</tr>'
  })
  return html
}

/** 1-sahifa (shartnomalar soni bilan) va 2-sahifa (1-ilova jadvallari) */
function liablePages(contracts: Record<string, Contract>): [string, string] {
  let page1 = ''
  let page2 = ''
  let group: string | null = null
  Object.values(contracts)
    .sort((a, b) => a.contract_id - b.contract_id)
    .forEach((c) => {
      const key = (c.contract_name || '').match(/^(\d+)\./)?.[1] ?? null
      if (key !== group) {
        if (key && GROUP_TITLES[key]) page1 += `<div style="text-align:left;line-height:2;"><b>${esc(GROUP_TITLES[key])}</b></div><div></div>`
        group = key
      }
      page1 += `<div id="block1_c${c.contract_id}" style="text-align:left;line-height:2;"><b><span>${esc(c.contract_name)}</span> - <span id="count_c${c.contract_id}">${c.count}</span> dona.</b></div>`
      if (!c.hide_page2 && c.items?.length) {
        if (page2) page2 += '<br>'
        const cols = c.contract_id === 1 ? [8, 30, 31, 31] : [8, 46, 46]
        page2 += `<div id="block2_c${c.contract_id}"><div style="text-align:left;"><b>${esc(c.contract_name)}</b></div><div>
          <table style="border-collapse:collapse;width:100%;"><colgroup>${cols.map((w) => `<col style="width:${w}%;">`).join('')}</colgroup>
          <tbody id="tbody_c${c.contract_id}">${contractRows(c)}</tbody></table></div></div>`
      }
    })
  return [page1, page2]
}

function DocumentPage({ form, meta, doc }: { form: ReportForm; meta: ReportsMeta; doc: DocApi }) {
  const t = useT()
  const toast = useToast()
  const regions = form.regions ?? []
  const [org, setOrg] = useState<number | null>(null)
  const [region, setRegion] = useState<number | null>(regions.length === 1 ? regions[0].id : null)
  const [dep, setDep] = useState<number | null>(null)
  const [rim, setRim] = useState<string | null>(null)
  const [sender, setSender] = useState<number | null>(null)
  const [receiver, setReceiver] = useState<number | null>(null)
  const [agreements, setAgreements] = useState<number[]>([])
  const [files, setFiles] = useState<File[]>([])

  const ready = !!org && !!region
  const deps = useDepartments(org, region, ready)
  const receivers = useOrgEmployees('signatories', org, dep, ready)
  const negotiators = useOrgEmployees('negotiators', org, dep, ready)

  const orgObj = form.organizations?.find((o) => o.id === org)
  const orgName = orgObj?.name ?? ''
  const depName = deps.data?.find((d) => d.id === dep)?.name ?? ''
  const contract = orgObj?.contract ?? ''
  const senderObj = form.senders?.find((e) => e.id === sender)
  const receiverObj = receivers.data?.find((e) => e.id === receiver)
  const agreementObjs = (negotiators.data ?? []).filter((e) => agreements.includes(e.id))
  const agreementsKey = agreementObjs.map((e) => e.id).join(',')

  // syncEditorTexts: sana, tashkilot/departament, chorak, shartnoma
  useEffect(() => {
    doc.setText('#doc_date, #doc_date2', `${todayDmy()} y`)
    doc.setText('#org_name', orgName)
    doc.setText('#dep_id2', depName ? `${depName} bo'yicha` : '')
    doc.setText('#dep_name', depName)
    doc.setText('#chorak', rim ?? '')
    doc.setText('#date_contract', contract || "Shartnoma ma'lumoti kiritilmagan")
  }, [doc, orgName, depName, rim, contract])

  const senderName = senderObj?.full_name ?? ''
  const senderRank = senderObj?.rank ?? ''
  useEffect(() => {
    doc.setText('#sender_name', senderName)
    doc.setText('#sender_rank', senderRank.trim() || 'direktor')
  }, [doc, senderName, senderRank])

  const receiverName = receiverObj?.full_name ?? ''
  const receiverRank = receiverObj?.rank ?? ''
  useEffect(() => {
    doc.setText('#receiver_name', receiverName)
    doc.setText('#receiver_rank', receiverRank.trim() || "boshlig'i")
  }, [doc, receiverName, receiverRank])

  // buildAgreementTables: imv_block — tashkilot vakili + shu tashkilot kelishuvchilari;
  // ivs_block — ATM vakili + joriy foydalanuvchi hududidagi kelishuvchilar (boshqalari chiqmaydi)
  const myRegion = meta.employee?.region_id ?? null
  useEffect(() => {
    const row = (rank: string, name: string) =>
      `<tr><td style="border:1px solid #fff;padding:4px 8px;vertical-align:top;line-height:2;">${esc(rank)}</td><td style="border:1px solid #fff;padding:4px 8px;vertical-align:top;line-height:2;">${esc(shortenFullName(name))}</td></tr>`
    let imv = receiverName ? row(receiverRank, receiverName) : ''
    let ivs = senderName ? row(senderRank, senderName) : ''
    agreementObjs.forEach((e) => {
      if (org && e.organization_id && e.organization_id === org) imv += row(e.rank, e.full_name)
      else if (myRegion && e.region_id && e.region_id === myRegion) ivs += row(e.rank, e.full_name)
    })
    const block = (heading: string, rows: string) =>
      rows ? `<div>${heading}</div><div><table style="border-collapse:collapse;width:100%;"><colgroup><col style="width:50%;"><col style="width:50%;"></colgroup><tbody>${rows}</tbody></table></div>` : ''
    doc.setHTML('#imv_block', block(`<b>O‘zbekiston Respublikasi ${esc(orgName)} ${esc(depName)} vakili:</b>`, imv))
    doc.setHTML('#ivs_block', block('<b>O‘zbekiston Respublikasi Iqtisodiyot va moliya vazirligi huzuridagi ATM vakillari:</b>', ivs))
    // agreementObjs agreementsKey orqali kuzatiladi
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [doc, org, orgName, depName, senderName, senderRank, receiverName, receiverRank, agreementsKey, myRegion])

  const search = async () => {
    if (!org && !dep) {
      doc.setHTML('#liable_page1', '')
      doc.setHTML('#liable_page2', '')
      return
    }
    try {
      const res = await reportData<{ contracts: Record<string, Contract> }>('document-preview', { organization: org, department: dep, region })
      const [p1, p2] = liablePages(res.contracts || {})
      doc.setHTML('#liable_page1', p1)
      doc.setHTML('#liable_page2', p2)
    } catch (e) {
      toast((e as Error).message || 'Xatolik yuz berdi', 'error')
    }
  }

  const resetDeps = () => {
    setDep(null)
    setReceiver(null)
    setAgreements([])
  }

  return (
    <ReportGrid
      side={
        <>
          <FilterCard onSearch={search} doc={doc} orientation="Portrait" filename="dalolatnoma">
            <Select
              label={t("Tashkilot")}
              placeholder={t("Tanlang...")}
              options={(form.organizations ?? []).map((o) => ({ value: o.id, label: o.name }))}
              value={org}
              onChange={(v) => {
                setOrg(toId(v))
                resetDeps()
              }}
            />
            <Select
              label={t("Hududlar")}
              placeholder={t("Tanlang...")}
              options={regions.map((r) => ({ value: r.id, label: r.name }))}
              value={region}
              clearable={form.has_full_region}
              onChange={(v) => {
                setRegion(toId(v))
                resetDeps()
              }}
            />
            <Select
              label={t("Departament")}
              placeholder={ready ? (deps.isFetching ? t('Yuklanmoqda...') : t('Tanlang...')) : t('Avval tashkilot va hududni tanlang')}
              options={(deps.data ?? []).map((d) => ({ value: d.id, label: d.name }))}
              value={dep}
              disabled={!ready}
              onChange={(v) => {
                setDep(toId(v))
                setReceiver(null)
                setAgreements([])
              }}
            />
            <Select label={t("Chorak")} placeholder={t("Tanlang...")} options={QUARTERS} searchable={false} value={rim} onChange={(v) => setRim(v == null ? null : String(v))} />
          </FilterCard>

          <SignCard
            kind="document"
            doc={doc}
            fields={() => ({ organization: org, region, department: dep, rim_id: rim, sender, receiver, 'agreements[]': agreements, attachments: files })}
          >
            <Select label={t("Xizmat ko'rsatuvchining vakili")} placeholder={t("Tanlang...")} options={empOptions(form.senders)} value={sender} onChange={(v) => setSender(toId(v))} />
            <Select
              label={t("Tashkilot vakili")}
              placeholder={receivers.isFetching ? t('Yuklanmoqda...') : t('Tanlang...')}
              options={empOptions(receivers.data)}
              value={receiver}
              disabled={!ready}
              onChange={(v) => setReceiver(toId(v))}
            />
            <MultiPicker label="Kelishuvchilar" options={empOptions(negotiators.data)} value={agreements} onChange={setAgreements} />
            <FileUpload
              label="Ilovalar"
              multiple
              compact
              accept=".pdf,.doc,.docx,.xls,.xlsx"
              maxFiles={10}
              maxSizeMB={10}
              files={files}
              onChange={setFiles}
              hint="Ixtiyoriy."
            />
          </SignCard>
        </>
      }
    >
      <DocEditor doc={doc} template={DOCUMENT_TEMPLATE} />
    </ReportGrid>
  )
}

export default function DocumentReport() {
  const doc = useDoc()
  return <ReportShell kind="document">{(form, meta) => <DocumentPage form={form} meta={meta} doc={doc} />}</ReportShell>
}
