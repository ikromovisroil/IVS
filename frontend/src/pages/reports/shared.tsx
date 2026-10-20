import { useState } from 'react'
import EmptyState from '../../components/EmptyState'
import type { ReactNode } from 'react'
import { useMutation } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { Button, Select, Tag, Textarea, Widget } from '../../ds'
import type { SelectOption } from '../../ds'
import Page from '../../layout/Page'
import PageTabs from '../../components/PageTabs'
import ConfirmDialog from '../../components/ConfirmDialog'
import { useToast } from '../../components/toast'
import { useT } from '../../i18n'
import { downloadPdf, encodeBody, submitReport, useReportForm, useReportsMeta } from './api'
import type { ReportForm, ReportKind, ReportsMeta } from './api'
import type { DocApi } from './doc'
import { REPORT_TABS } from './tabs'

/**
 * Bo'lim sahifasi: sarlavha + ruxsat bo'yicha filtrlangan tablar. Ruxsat (meta) va forma ro'yxatlari yuklangach
 * sahifa tarkibini chizadi: children(form, meta).
 */
export function ReportShell({ kind, children }: { kind: ReportKind; children: (form: ReportForm, meta: ReportsMeta) => ReactNode }) {
  const t = useT()
  const meta = useReportsMeta()
  const allowed = !!meta.data?.reports[kind]
  const form = useReportForm(kind, allowed)
  const tab = REPORT_TABS.find((x) => x.kind === kind)!
  const tabs = REPORT_TABS.filter((x) => meta.data?.reports[x.kind])

  let body: ReactNode
  const error = meta.error || form.error
  if (error) body = <div className="ivs-empty" role="alert">{t(error.message)}</div>
  else if (meta.isPending) body = <div className="ivs-empty" aria-busy="true">{t('Yuklanmoqda…')}</div>
  else if (!allowed) body = <EmptyState icon="ri-lock-line" title="Ruxsat yo'q" description="Bu hisobot uchun ruxsatingiz yo'q." />
  else if (form.isPending) body = <div className="ivs-empty" aria-busy="true">{t('Yuklanmoqda…')}</div>
  else body = children(form.data, meta.data)

  return (
    <Page icon="ri-bar-chart-box-line" title={tab.label} subtitle={tab.subtitle}>
      {tabs.length > 1 && <PageTabs label="Hisobotlar" tabs={tabs.map((x) => ({ path: x.path, label: x.label, icon: x.icon }))} />}
      {body}
    </Page>
  )
}

/** Chapda filtr va imzo kartalari, o'ngda hujjat (telefon kengligida — ustma-ust). */
export function ReportGrid({ side, children }: { side: ReactNode; children: ReactNode }) {
  return (
    <div className="rep-grid">
      <div className="rep-side">{side}</div>
      <div className="rep-main">{children}</div>
    </div>
  )
}

/** Chap ustundagi "Filtrlash" kartasi: maydonlar + "Qidirish" + "PDF yuklab olish". */
export function FilterCard({
  children,
  onSearch,
  doc,
  orientation,
  filename,
}: {
  children: ReactNode
  onSearch: () => void
  doc: DocApi
  orientation: 'Portrait' | 'Landscape'
  filename: string
}) {
  const t = useT()
  const toast = useToast()
  const pdf = useMutation({
    mutationFn: () => {
      const body = doc.html()
      if (!body) throw new Error('Hujjat matni bo\'sh — avval "Qidirish" tugmasini bosing.')
      return downloadPdf(body, orientation, filename)
    },
    onError: (e) => toast(e.message || 'PDF yuklab olishda xatolik yuz berdi', 'error'),
  })

  return (
    <Widget icon="ri-filter-3-line" title={t('Filtrlash')}>
      <form
        className="rep-fields"
        onSubmit={(e) => {
          e.preventDefault()
          onSearch()
        }}
      >
        {children}
        <Button type="submit" size="md" icon="ri-search-line" className="rep-full">
          {t('Qidirish')}
        </Button>
        <Button type="button" variant="stroke" size="md" icon="ri-download-2-line" className="rep-full" loading={pdf.isPending} onClick={() => pdf.mutate()}>
          {pdf.isPending ? t('Tayyorlanmoqda...') : t('PDF yuklab olish')}
        </Button>
      </form>
    </Widget>
  )
}

/** "Imzolashga yuborish" kartasi: maydonlar + izoh + tasdiqlash oynasi. Muvaffaqiyatda — Xabarlar sahifasi. */
export function SignCard({
  kind,
  doc,
  children,
  fields,
}: {
  kind: ReportKind
  doc: DocApi
  children: ReactNode
  /** Eski formadagi qo'shimcha maydonlar (sender, receiver, agreements[], organization, ...) */
  fields: () => Record<string, string | number | null | undefined | (string | number)[] | File[]>
}) {
  const t = useT()
  const toast = useToast()
  const navigate = useNavigate()
  const [message, setMessage] = useState('')
  const [confirm, setConfirm] = useState(false)

  const send = useMutation({
    mutationFn: () => {
      const form = new FormData()
      for (const [k, v] of Object.entries(fields())) {
        if (Array.isArray(v)) v.forEach((x) => form.append(k, x instanceof File ? x : String(x)))
        else if (v !== null && v !== undefined) form.append(k, String(v))
      }
      form.append('message', message)
      form.append('body_encoded', encodeBody(doc.html()))
      return submitReport(kind, form)
    },
    onSuccess: (r) => {
      toast(r.detail || 'Imzolashga yuborildi')
      navigate('/messages') // eski: redirect("contact_user")
    },
    onError: (e) => {
      setConfirm(false)
      toast(e.message, 'error')
    },
  })

  return (
    <Widget icon="ri-quill-pen-line" title={t('Imzolashga yuborish')}>
      <form
        className="rep-fields"
        onSubmit={(e) => {
          e.preventDefault()
          setConfirm(true)
        }}
      >
        {children}
        <Textarea label={t('Izoh')} rows={4} placeholder={t('Izoh yozing...')} value={message} onChange={(e) => setMessage(e.target.value)} />
        <Button type="submit" size="md" icon="ri-send-plane-line" className="rep-full">
          {t('Imzolashga yuborish')}
        </Button>
      </form>
      {confirm && (
        <ConfirmDialog
          title="Imzolashga yuborish"
          message="Imzolashga yuborishni tasdiqlang?"
          confirmLabel="Yuborish"
          loading={send.isPending}
          onConfirm={() => send.mutate()}
          onClose={() => setConfirm(false)}
        />
      )}
    </Widget>
  )
}


/** Bir nechta tanlov (Kelishuvchilar, Tashkilotlar): Select dan qo'shiladi, tanlanganlar teg sifatida. */
export function MultiPicker({
  label,
  options,
  value,
  onChange,
  placeholder = "Qo'shish...",
  required = false,
}: {
  label: string
  options: SelectOption[]
  value: number[]
  onChange: (v: number[]) => void
  placeholder?: string
  /** Kamida bittasi tanlanishi shart — yorlig'iga * qo'shiladi */
  required?: boolean
}) {
  const t = useT()
  const chosen = value.map((id) => options.find((o) => Number(o.value) === id)).filter((o): o is SelectOption => !!o)
  const rest = options.filter((o) => !value.includes(Number(o.value)))
  return (
    <div className="rep-multi">
      <Select
        label={required ? `${t(label)} *` : t(label)}
        placeholder={rest.length ? t(placeholder) : options.length ? t('Hammasi tanlangan') : t("Ro'yxat bo'sh")}
        options={rest}
        value={null}
        disabled={!rest.length}
        onChange={(v) => v != null && onChange([...value, Number(v)])}
      />
      {chosen.length > 0 && (
        <div className="rep-tags">
          {chosen.map((o) => (
            <Tag key={o.value} removable onRemove={() => onChange(value.filter((id) => id !== Number(o.value)))}>
              {o.label}
            </Tag>
          ))}
        </div>
      )}
    </div>
  )
}
