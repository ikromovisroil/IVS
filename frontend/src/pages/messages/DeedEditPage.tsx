import { useEffect, useRef, useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { useNavigate, useParams } from 'react-router-dom'
import { Button, Select, Switch, Widget } from '../../ds'
import Page from '../../layout/Page'
import DataState from '../../components/DataState'
import ConfirmDialog from '../../components/ConfirmDialog'
import { useToast } from '../../components/toast'
import { ApiError, api } from '../../api/client'
import { useT } from '../../i18n'
import { htmlOf, useRichEdit } from '../../components/richText'
import { SPA, useDeed, useRefresh } from './api'
import MultiPicker from './MultiPicker'
import type { Deed, EditOptions, EmployeeOption } from './types'
import './messages.css'

const label = (e: EmployeeOption) => (e.rank_name ? `${e.full_name} (${e.rank_name})` : e.full_name)
const toOptions = (xs: EmployeeOption[]) => xs.map((e) => ({ value: e.id, label: label(e) }))

/** Ko'rsatishdan oldin xavfli teg va atributlarni olib tashlaydi (server saqlashda sanitize_deed_body ishlatadi). */
function cleanHtml(html: string): string {
  const doc = new DOMParser().parseFromString(html, 'text/html')
  doc.querySelectorAll('script, style, iframe, object, embed, link, meta').forEach((n) => n.remove())
  doc.body.querySelectorAll('*').forEach((el) => {
    for (const a of Array.from(el.attributes)) {
      if (a.name.startsWith('on') || /^\s*javascript:/i.test(a.value)) el.removeAttribute(a.name)
    }
  })
  return doc.body.innerHTML
}

/** deed_edit: imzolovchi, xizmat ko'rsatuvchi, kelishuvchilar va hujjat matni. Saqlanganda PDF qayta yaratiladi. */
export default function DeedEditPage() {
  const id = Number(useParams().id)
  const deed = useDeed(id)
  const options = useQuery({
    queryKey: ['messages', 'edit-options', id],
    queryFn: () => api<EditOptions>(`${SPA}/deeds/${id}/edit-options/`),
  })
  const ready = deed.data && options.data
  const t = useT()

  return (
    <Page icon="ri-edit-line" title="Tahrirlash" subtitle={deed.data ? `${t(deed.data.status_display)} #${deed.data.code ?? deed.data.id}` : undefined}>
      <DataState
        isPending={deed.isPending || options.isPending}
        error={deed.error || options.error}
        empty={!!deed.data && !deed.data.can_edit}
        emptyText="Bu hujjatni tahrirlab bo'lmaydi: tahrirlash yopilgan yoki hujjat bo'yicha javob berilgan."
      >
        {ready && <EditForm deed={deed.data} options={options.data} />}
      </DataState>
    </Page>
  )
}

function EditForm({ deed, options }: { deed: Deed; options: EditOptions }) {
  const navigate = useNavigate()
  const toast = useToast()
  const refresh = useRefresh()
  const t = useT()
  const tr = (s?: string) => (s ? t(s) : undefined)
  const editor = useRef<HTMLDivElement>(null)
  const [manual, setManual] = useState(false)
  const { toolbar } = useRichEdit(editor, manual)      // TinyMCE doim ko'rinadi; "Qo'lda tahrirlash" yoqilganda tahrirlanadi
  const [confirming, setConfirming] = useState(false)
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [form, setForm] = useState({
    sender: deed.sender,
    receiver: deed.receiver,
    agreements: options.selected_agreements,
  })

  useEffect(() => {
    if (editor.current) editor.current.innerHTML = cleanHtml(deed.body ?? '')
  }, [deed.body])

  const save = useMutation({
    mutationFn: () => {
      const body: Record<string, unknown> = {
        sender: form.sender,
        body: htmlOf(editor.current),
        agreements: form.agreements.filter((a) => a !== form.sender && a !== form.receiver),
      }
      if (deed.receiver) body.receiver = form.receiver
      return api(`/deeds/${deed.id}/`, { method: 'PATCH', body: JSON.stringify(body) })
    },
    onSuccess: () => {
      toast('Hujjat muvaffaqiyatli tahrirlandi')
      refresh()
      navigate('/messages/send')
    },
    onError: (e) => {
      setConfirming(false)
      setErrors(e instanceof ApiError ? e.fieldErrors : {})
      toast(e.message, 'error')
    },
  })

  const submit = () => {
    const missing: Record<string, string> = {}
    if (form.sender == null) missing.sender = 'Imzolovchi xodim tanlanmadi.'
    if (deed.receiver && form.receiver == null) missing.receiver = 'Qabul qiluvchi tanlanmadi.'
    if (!editor.current?.textContent?.trim()) missing.body = "Hujjat matni bo'sh bo'lmasin."
    setErrors(missing)
    if (!Object.keys(missing).length) setConfirming(true)
  }

  return (
    <div className="msg-edit">
      <Widget icon="ri-user-settings-line" title={t('Imzolovchilar')} className="msg-edit-side">
        <div className="msg-edit-fields">
          <Select
            label={t('Imzolovchi xodim *')}
            options={toOptions(options.sender)}
            value={form.sender}
            clearable={false}
            onChange={(v) => setForm((f) => ({ ...f, sender: v == null ? null : Number(v) }))}
            error={!!errors.sender}
            hint={t(errors.sender || "Imzolovchi o'zgarsa, uning javobi qaytadan kutiladi.")}
          />
          {deed.receiver && (
            <Select
              label={t("Imzolovchi xodim (xizmat ko'rsatuvchi) *")}
              options={toOptions(options.receiver)}
              value={form.receiver}
              clearable={false}
              onChange={(v) => setForm((f) => ({ ...f, receiver: v == null ? null : Number(v) }))}
              error={!!errors.receiver}
              hint={tr(errors.receiver)}
            />
          )}
          <MultiPicker
            label={t('Kelishuvchilar')}
            placeholder={t("Kelishuvchini qo'shing...")}
            options={toOptions(options.agreements)}
            value={form.agreements}
            onChange={(agreements) => setForm((f) => ({ ...f, agreements }))}
            error={tr(errors.agreements)}
          />
          {errors.detail && (
            <p className="ivs-form-error type-para-sm" role="alert">
              {t(errors.detail)}
            </p>
          )}
          <div className="msg-edit-buttons">
            <Button variant="stroke" size="lg" onClick={() => navigate(-1)}>
              {t('Bekor qilish')}
            </Button>
            <Button size="lg" icon="ri-check-line" loading={save.isPending} onClick={submit}>
              {t('Saqlash')}
            </Button>
          </div>
        </div>
      </Widget>

      <Widget
        icon="ri-file-text-line"
        title={t('Hujjat matni')}
        className="msg-edit-main"
        extra={<Switch label={t("Qo'lda tahrirlash")} checked={manual} onChange={setManual} />}
      >
        {errors.body && (
          <p className="ivs-form-error type-para-sm" role="alert">
            {t(errors.body)}
          </p>
        )}
        <div ref={toolbar} className="ivs-rich-toolbar" />
        <div
          ref={editor}
          className="msg-editor"
          role="textbox"
          aria-multiline="true"
          aria-label={t('Hujjat matni')}
          aria-readonly={!manual}
        />
      </Widget>

      {confirming && (
        <ConfirmDialog
          title="Yangilanishlarni saqlashga rozimisiz?"
          message="Hujjat PDF fayli qayta yaratiladi."
          confirmLabel="Saqlash"
          loading={save.isPending}
          onConfirm={() => save.mutate()}
          onClose={() => setConfirming(false)}
        />
      )}
    </div>
  )
}
