import { useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Button, Select } from '../../ds'
import ConfirmDialog from '../../components/ConfirmDialog'
import Modal from '../../components/Modal'
import { useToast } from '../../components/toast'
import { API, api } from '../../api/client'
import { useT } from '../../i18n'
import { formatNumber } from '../../lib/format'
import { errorText, money } from '../technics/util'
import { SPA } from '../technics/api'
import { Kv } from '../technics/TechnicsDetail'

interface Options {
  organizations: { id: number; name: string }[]
  employees: { id: number; full_name: string; rank: string }[]
  categories: { id: number; name: string }[]
  units: { id: number; name: string }[]
}

interface Summary {
  dry_run: boolean
  rows: number
  created: number
  skipped: number
  quantity: number
  sum: string
  sheets: { name: string; rows: number; created: number; skipped: number }[]
  unmatched_units: { name: string; count: number }[]
  unmatched_categories: string[]
  issues: { sheet: string; row: number; name: string; message: string }[]
  issues_truncated: boolean
}

const IMPORT = `${SPA}/materials/import`

/** Superuser: Excel'dan materiallarni import qilish — avval "Tekshirish" (hech narsa yozilmaydi), so'ng "Import qilish". */
export default function MaterialImportDialog({ onClose }: { onClose: () => void }) {
  const t = useT()
  const toast = useToast()
  const qc = useQueryClient()
  const fileInput = useRef<HTMLInputElement>(null)
  const [org, setOrg] = useState<number | null>(null)
  const [employee, setEmployee] = useState<number | null>(null)
  const [category, setCategory] = useState<number | null>(null)
  const [unitMap, setUnitMap] = useState<Record<string, number | null>>({})
  const [file, setFile] = useState<File | null>(null)
  const [confirmUnits, setConfirmUnits] = useState(false)
  const [result, setResult] = useState<Summary | null>(null)
  const [error, setError] = useState('')

  const options = useQuery({
    queryKey: ['warehouse', 'import-options', org],
    queryFn: () => api<Options>(`${IMPORT}/options/`, { query: { organization: org } }),
    staleTime: 60 * 1000,
  })

  const reset = () => {
    setResult(null)
    setUnitMap({})
    setError('')
  }

  const run = useMutation({
    mutationFn: (dryRun: boolean) => {
      const body = new FormData()
      body.set('file', file as File)
      body.set('organization', String(org))
      body.set('employee', String(employee))
      if (category) body.set('category', String(category))
      body.set('unit_map', JSON.stringify(unitMap))
      body.set('dry_run', dryRun ? '1' : '0')
      return api<Summary>(`${IMPORT}/`, { method: 'POST', body })
    },
    onSuccess: (r) => {
      setResult(r)
      setError('')
      if (!r.dry_run) {
        toast(`${t('Import bajarildi')}: ${r.created} ${t('ta material')}`)
        qc.invalidateQueries({ queryKey: ['warehouse'] })
        onClose()
      }
    },
    onError: (e) => {
      setResult(null)
      setError(errorText(e) ?? '')
    },
  })

  const ready = !!org && !!employee && !!file
  const importable = !!result?.dry_run && result.created > 0
  // bazada topilmagan va hali birlik tanlanmagan birliklar: ogohlantirish va import oldidan tasdiq
  const pendingUnits = (result?.unmatched_units ?? []).filter((u) => !unitMap[u.name])

  return (
    <>
    <Modal
      open
      onClose={onClose}
      icon="ri-file-excel-2-line"
      title="Materiallarni Excel'dan import qilish"
      subtitle="Faqat superuser uchun"
      width={720}
      footer={
        <>
          <Button variant="stroke" size="lg" onClick={onClose}>
            {t('Yopish')}
          </Button>
          <Button variant="stroke" size="lg" icon="ri-search-eye-line" disabled={!ready || run.isPending} loading={run.isPending && run.variables === true} onClick={() => run.mutate(true)}>
            {t('Tekshirish')}
          </Button>
          <Button size="lg" icon="ri-upload-2-line" disabled={!importable || run.isPending} loading={run.isPending && run.variables === false} onClick={() => (pendingUnits.length ? setConfirmUnits(true) : run.mutate(false))}>
            {t('Import qilish')}
          </Button>
        </>
      }
    >
      <p className="type-para-sm msg-info">
        {t("Jadval to'liq import qilinadi: har qator alohida material bo'ladi (nomi, narxi, soni yoki kodi bir xil bo'lsa ham birlashtirilmaydi) va miqdori bo'yicha kirim yoziladi.")}
      </p>

      <div className="ivs-form-grid">
        <div className="is-wide">
        <Select
          label={t('Tashkilot')}
          placeholder={t('Tanlang...')}
          options={(options.data?.organizations ?? []).map((o) => ({ value: o.id, label: o.name }))}
          value={org}
          onChange={(v) => {
            setOrg(v === null ? null : Number(v))
            setEmployee(null)
            setCategory(null)
            reset()
          }}
        />
        </div>
        <div className="is-wide">
        <Select
          label={t('Moddiy-javobgar xodim')}
          placeholder={org ? t('Tanlang...') : t('Avval tashkilotni tanlang')}
          disabled={!org}
          options={(options.data?.employees ?? []).map((e) => ({ value: e.id, label: e.rank ? `${e.full_name} (${e.rank})` : e.full_name }))}
          value={employee}
          onChange={(v) => {
            setEmployee(v === null ? null : Number(v))
            reset()
          }}
        />
        </div>

        <div className="is-wide">
        <Select
          label={t('Kategoriya (hamma qatorga)')}
          placeholder={org ? t('Kategoriyasiz') : t('Avval tashkilotni tanlang')}
          disabled={!org}
          options={(options.data?.categories ?? []).map((c) => ({ value: c.id, label: c.name }))}
          value={category}
          onChange={(v) => {
            setCategory(v === null ? null : Number(v))
            reset()
          }}
        />
        </div>

        <div className="is-wide">
          <span className="type-label-sm">{t('Excel fayl (.xlsx / .xlsm)')}</span>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 6 }}>
            <input
              ref={fileInput}
              type="file"
              accept=".xlsx,.xlsm"
              hidden
              onChange={(e) => {
                setFile(e.target.files?.[0] ?? null)
                reset()
              }}
            />
            <Button variant="stroke" icon="ri-attachment-2" onClick={() => fileInput.current?.click()}>
              {file ? file.name : t('Fayl tanlash')}
            </Button>
            <Button variant="ghost" icon="ri-download-2-line" onClick={() => window.location.assign(`${API}${IMPORT}/template/`)}>
              {t('Namuna')}
            </Button>
          </div>
        </div>
      </div>

      {error && (
        <p className="ivs-form-error type-para-sm" role="alert">
          {error}
        </p>
      )}

      {result && (
        <div style={{ marginTop: 16 }}>
          <dl className="ivs-kvs is-compact">
            <Kv label="Qatorlar">{formatNumber(result.rows)}</Kv>
            <Kv label="Import qilinadi">{formatNumber(result.created)}</Kv>
            <Kv label="O'tkazib yuboriladi">{formatNumber(result.skipped)}</Kv>
            <Kv label="Jami miqdor">{formatNumber(result.quantity)}</Kv>
            <Kv label="Jami summa">{money(result.sum)}</Kv>
          </dl>
          {result.sheets.length > 1 && (
            <p className="type-para-sm">
              {result.sheets.map((s) => `${s.name}: ${s.rows}`).join(' · ')}
            </p>
          )}
          {result.unmatched_categories.length > 0 && (
            <p className="type-para-sm">
              {t('Bazada topilmadi (kategoriyasiz bo‘ladi)')}: {result.unmatched_categories.join(', ')}
            </p>
          )}
          {result.unmatched_units.length > 0 && (
            <div className="ivs-form-grid" style={{ marginTop: 8 }}>
              <p
                className="type-para-sm is-wide"
                role="alert"
                style={{ background: 'var(--warning-lighter, #fff4d6)', border: '1px solid var(--warning-light, #f5c84c)', borderRadius: 10, padding: '10px 12px', margin: 0 }}
              >
                <i className="ri-error-warning-line" /> <b>{t("Diqqat: o'lchov birligi bazadagiga mos kelmadi")}</b> — {t("qaysi birlikka mos kelishini tanlang (tanlanmasa, material birliksiz yaratiladi)")}
              </p>
              {result.unmatched_units.map((u) => (
                <div key={u.name} className="is-wide">
                  <Select
                    label={`${u.name} (${u.count} ${t('qator')})`}
                    placeholder={t('Birliksiz')}
                    options={(options.data?.units ?? []).map((x) => ({ value: x.id, label: x.name }))}
                    value={unitMap[u.name] ?? null}
                    onChange={(v) => setUnitMap((m) => ({ ...m, [u.name]: v === null ? null : Number(v) }))}
                  />
                </div>
              ))}
            </div>
          )}
          {result.issues.length > 0 && (
            <>
              <p className="type-para-sm">
                <b>{t("O'tkazib yuboriladigan qatorlar")}</b>
                {result.issues_truncated ? ` (${t('birinchi')} ${result.issues.length})` : ''}
              </p>
              <ul style={{ margin: 0, paddingLeft: 18, maxHeight: 180, overflow: 'auto' }}>
                {result.issues.map((i, n) => (
                  <li key={n} className="type-para-sm">
                    {i.sheet}, {i.row}-{t('qator')}: {i.name} — {t(i.message)}
                  </li>
                ))}
              </ul>
            </>
          )}
        </div>
      )}
    </Modal>
      {confirmUnits && (
        <ConfirmDialog
          title="Birligi tanlanmagan materiallar bor"
          message={`${t("Bazada topilmagan o'lchov birliklari")}: ${pendingUnits.map((u) => `${u.name} (${u.count})`).join(', ')}. ${t("Bu materiallar birliksiz yaratiladi. Davom etasizmi?")}`}
          confirmLabel="Birliksiz import qilish"
          loading={run.isPending}
          onConfirm={() => {
            setConfirmUnits(false)
            run.mutate(false)
          }}
          onClose={() => setConfirmUnits(false)}
        />
      )}
    </>
  )
}
