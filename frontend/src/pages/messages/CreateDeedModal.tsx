import { useState } from 'react'
import type { FormEvent } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { Button, Select } from '../../ds'
import Modal from '../../components/Modal'
import { useToast } from '../../components/toast'
import { ApiError, api } from '../../api/client'
import { useT } from '../../i18n'
import { SPA, useRefresh } from './api'
import FilePicker from './FilePicker'
import MultiPicker from './MultiPicker'
import { KIND_OPTIONS } from './status'

const MAX_ATTACHMENTS = 10
const num = (v: string | number | null) => (v == null ? null : Number(v))

interface Option {
  id: number
  text: string
}
interface Agreement {
  id: number
  full_name: string
  rank: string
}

/** "Hujjatlar Yaratish" (contact_user.html → contact_post_deed; API: POST /api/v1/deeds/) */
export default function CreateDeedModal({ onClose }: { onClose: () => void }) {
  const [form, setForm] = useState({
    organization: null as number | null,
    status: null as string | null,
    senderOrg: null as number | null,
    sender: null as number | null,
    receiver: null as number | null,
    agreements: [] as number[],
  })
  const [file, setFile] = useState<File[]>([])
  const [attachments, setAttachments] = useState<File[]>([])
  const [errors, setErrors] = useState<Record<string, string>>({})
  const t = useT()
  const tr = (s?: string) => (s ? t(s) : undefined)
  const toast = useToast()
  const refresh = useRefresh()
  const isDocument = form.status === 'document'

  const orgs = useQuery({
    queryKey: ['messages', 'organizations'],
    queryFn: () => api<{ id: number; name: string }[]>(`${SPA}/organizations/`),
    staleTime: 5 * 60_000,
  })
  const employees = useQuery({
    queryKey: ['messages', 'employees', form.senderOrg],
    queryFn: () => api<{ results: Option[] }>(`${SPA}/employees/`, { query: { organization: form.senderOrg } }),
    enabled: form.senderOrg != null,
  })
  const agreementList = useQuery({
    queryKey: ['messages', 'agreements', form.senderOrg],
    queryFn: () => api<Agreement[]>(`${SPA}/agreements/`, { query: { org_id: form.senderOrg } }),
    enabled: form.senderOrg != null,
  })
  const workers = useQuery({
    queryKey: ['messages', 'workers'],
    queryFn: () => api<{ results: Option[] }>(`${SPA}/workers/`),
    enabled: isDocument,
    staleTime: 5 * 60_000,
  })

  const orgOptions = (orgs.data ?? []).map((o) => ({ value: o.id, label: o.name }))
  const toOptions = (xs?: Option[]) => (xs ?? []).map((o) => ({ value: o.id, label: o.text }))
  const agreementOptions = (agreementList.data ?? [])
    .filter((a) => a.id !== form.receiver)
    .map((a) => ({ value: a.id, label: a.rank ? `${a.full_name} (${a.rank})` : a.full_name }))

  const save = useMutation({
    mutationFn: () => {
      const fd = new FormData()
      fd.set('organization', String(form.organization))
      fd.set('status', String(form.status))
      fd.set('sender', String(form.sender))
      if (isDocument && form.receiver) fd.set('receiver', String(form.receiver))
      form.agreements.forEach((id) => fd.append('agreements', String(id)))
      fd.set('file', file[0])
      attachments.forEach((f) => fd.append('attachments', f))
      return api('/deeds/', { method: 'POST', body: fd })
    },
    onSuccess: () => {
      toast('Ariza muvaffaqiyatli yuborildi')
      refresh()
      onClose()
    },
    onError: (e) => setErrors(e instanceof ApiError ? e.fieldErrors : {}),
  })

  const submit = (e: FormEvent) => {
    e.preventDefault()
    const missing: Record<string, string> = {}
    if (form.organization == null) missing.organization = 'Hujjat tegishli tashkilot tanlanmagan.'
    if (!form.status) missing.status = "Hujjat turini tanlang."
    if (form.senderOrg == null) missing.senderOrg = 'Tashkilotni tanlang.'
    if (form.sender == null) missing.sender = 'Xodim tanlanmagan.'
    if (isDocument && form.receiver != null && form.receiver === form.sender)
      missing.receiver = "Imzolovchi va xizmat ko'rsatuvchi bir xil xodim bo'lishi mumkin emas."
    if (!form.agreements.length) missing.agreements = 'Kelishuvchilarni tanlang.'
    if (!file.length) missing.file = 'Fayl biriktirilmagan.'
    else if (!file[0].name.toLowerCase().endsWith('.pdf')) missing.file = 'Faqat PDF fayl yuklash mumkin!'
    if (attachments.length > MAX_ATTACHMENTS) missing.attachments = `Ilova fayllari ${MAX_ATTACHMENTS} tadan ko'p bo'lmasligi kerak.`
    setErrors(missing)
    if (!Object.keys(missing).length) save.mutate()
  }

  const known = ['organization', 'status', 'sender', 'receiver', 'agreements', 'file', 'attachments']
  const extra = Object.entries(errors).filter(([k]) => !known.includes(k) && k !== 'senderOrg')
  const formError = extra.length ? extra.map(([, v]) => t(v)).join(' ') : save.error && !Object.keys(errors).length ? t(save.error.message) : null

  return (
    <Modal
      open
      onClose={onClose}
      icon="ri-file-add-line"
      title="Hujjatlar yaratish"
      subtitle="* belgili maydonlar majburiy."
      footer={
        <>
          <Button variant="stroke" size="lg" onClick={onClose}>
            {t('Bekor qilish')}
          </Button>
          <Button size="lg" icon="ri-send-plane-line" type="submit" form="deed-create-form" loading={save.isPending}>
            {t('Yuborish')}
          </Button>
        </>
      }
    >
      <form id="deed-create-form" onSubmit={submit} noValidate>
        {formError && (
          <p className="ivs-form-error type-para-sm" role="alert">
            {formError}
          </p>
        )}
        <div className="ivs-form-grid">
          <div className="is-wide">
            <Select
              label={t('Hujjatlar qaysi tashkilotga tegishli *')}
              placeholder={t('Tanlang...')}
              options={orgOptions}
              value={form.organization}
              onChange={(v) => setForm((f) => ({ ...f, organization: num(v) }))}
              error={!!errors.organization}
              hint={tr(errors.organization)}
            />
          </div>
          <div className="is-wide">
            <Select
              label={t('Hujjatlar turi *')}
              placeholder={t('Tanlang...')}
              options={KIND_OPTIONS.map((o) => ({ ...o, label: t(o.label) }))}
              searchable={false}
              value={form.status}
              onChange={(v) => setForm((f) => ({ ...f, status: v == null ? null : String(v), receiver: v === 'document' ? f.receiver : null }))}
              error={!!errors.status}
              hint={tr(errors.status)}
            />
          </div>
          <Select
            label={t('Imzolovchi qaysi tashkilotdan *')}
            placeholder={t('Tanlang...')}
            options={orgOptions}
            value={form.senderOrg}
            onChange={(v) => setForm((f) => ({ ...f, senderOrg: num(v), sender: null, agreements: [] }))}
            error={!!errors.senderOrg}
            hint={tr(errors.senderOrg)}
          />
          <Select
            label={t('Imzolovchi xodim *')}
            placeholder={t(form.senderOrg == null ? 'Avval tashkilotni tanlang' : employees.isPending ? 'Yuklanmoqda...' : 'Tanlang...')}
            options={toOptions(employees.data?.results)}
            disabled={form.senderOrg == null}
            value={form.sender}
            onChange={(v) => setForm((f) => ({ ...f, sender: num(v) }))}
            error={!!errors.sender}
            hint={tr(errors.sender)}
          />
          {isDocument && (
            <div className="is-wide">
              <Select
                label={t("Xizmat ko'rsatuvchi xodim")}
                placeholder={t(workers.isPending ? 'Yuklanmoqda...' : 'Tanlang...')}
                options={toOptions(workers.data?.results)}
                value={form.receiver}
                onChange={(v) => setForm((f) => ({ ...f, receiver: num(v), agreements: f.agreements.filter((a) => a !== num(v)) }))}
                error={!!errors.receiver}
                hint={t(errors.receiver || 'Ixtiyoriy. Tanlansa, dalolatnoma ikki imzolovchi tomonidan imzolanadi.')}
              />
            </div>
          )}
          <div className="is-wide">
            <MultiPicker
              label={t('Kelishuvchilar *')}
              placeholder={t(form.senderOrg == null ? 'Avval tashkilotni tanlang' : 'Kelishuvchilarni tanlang...')}
              options={agreementOptions}
              value={form.agreements}
              onChange={(agreements) => setForm((f) => ({ ...f, agreements }))}
              disabled={form.senderOrg == null}
              error={tr(errors.agreements)}
            />
          </div>
          <div className="is-wide">
            <FilePicker
              label="Fayl (PDF) *"
              buttonLabel="Faylni tanlash"
              accept=".pdf,application/pdf"
              files={file}
              onChange={setFile}
              error={errors.file}
            />
          </div>
          <div className="is-wide">
            <FilePicker
              label="Ilovalar"
              buttonLabel="Ilova qo'shish"
              accept=".pdf,.doc,.docx,.xls,.xlsx"
              multiple
              files={attachments}
              onChange={setAttachments}
              error={errors.attachments}
              hint="Ixtiyoriy. Word, Excel yoki PDF; bir nechta fayl tanlash mumkin (10 tagacha, har biri 10 MB gacha)."
            />
          </div>
        </div>
      </form>
    </Modal>
  )
}
