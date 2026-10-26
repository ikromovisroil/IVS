import { useEffect, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate, useParams } from 'react-router-dom'
import { Button, Select, Switch, Textarea, Widget } from '../../ds'
import ConfirmDialog from '../../components/ConfirmDialog'
import { useToast } from '../../components/toast'
import { ApiError, api } from '../../api/client'
import { useT } from '../../i18n'
import { htmlOf, useRichEdit } from '../../components/richText'
import { ExecuteShell } from './ExecutePages'
import './orders.css'

interface DeedData {
  order: { id: number; sender_name: string; organization_name: string | null }
  employees: { id: number; full_name: string; rank: string | null }[]
  /** Hujjat matni (HTML) — server shablonidan, tozalangan */
  body: string
}

/** UTF-8 matnni Base64 ga (eski sahifadagidek: WAF/firewall HTML ni to'smasligi uchun). */
function toBase64(text: string): string {
  const bytes = new TextEncoder().encode(text)
  let bin = ''
  bytes.forEach((b) => (bin += String.fromCharCode(b)))
  return btoa(bin)
}

/** /orders/execute/archive/:id/deed — order_receiver_deed: aktni imzolashga yuborish. */
export default function DeedPage() {
  const { id } = useParams()
  const t = useT()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const toast = useToast()
  const doc = useRef<HTMLDivElement>(null)
  const [signer, setSigner] = useState<number | null>(null)
  const [message, setMessage] = useState('')
  const [manual, setManual] = useState(false)
  const [confirm, setConfirm] = useState(false)
  const [errors, setErrors] = useState<Record<string, string>>({})

  const q = useQuery({
    queryKey: ['orders', 'deed', id],
    queryFn: () => api<DeedData>(`/spa/orders/${id}/deed/`),
    refetchOnMount: 'always',
    staleTime: Infinity,
  })
  const { toolbar } = useRichEdit(doc, manual, !!q.data)      // TinyMCE doim ko'rinadi; "Qo'lda tahrirlash" yoqilganda tahrirlanadi

  // Hujjat bir marta joylanadi; keyin qo'lda tahrirlar saqlanib qoladi (React qayta chizmaydi)
  useEffect(() => {
    if (q.data && doc.current && !doc.current.dataset.ready) {
      doc.current.innerHTML = q.data.body
      doc.current.dataset.ready = '1'
    }
  }, [q.data])

  // Imzolovchi tanlanganda hujjatdagi ismlar yangilanadi (sender_name1 — F.I.Sh. va lavozimi, sender_name2 — F.I.Sh.)
  useEffect(() => {
    const e = q.data?.employees.find((x) => x.id === signer)
    const root = doc.current
    if (!root || !e) return
    const n1 = root.querySelector('#sender_name1')
    const n2 = root.querySelector('#sender_name2')
    if (n1) n1.textContent = e.rank ? `${e.full_name} (${e.rank})` : e.full_name
    if (n2) n2.textContent = e.full_name
  }, [signer, q.data])

  const send = useMutation({
    mutationFn: () =>
      api<{ id: number; file: string | null }>(`/spa/orders/${id}/deed/`, {
        method: 'POST',
        body: JSON.stringify({ sender: signer, message: message.trim() || null, body_encoded: toBase64(htmlOf(doc.current)) }),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['orders'] })
      toast('Imzolashga yuborildi')
      navigate('/messages') // eski sahifa: contact_user
    },
    onError: (e) => {
      setConfirm(false)
      if (e instanceof ApiError && Object.keys(e.fieldErrors).length) setErrors(e.fieldErrors)
      else toast(e.message, 'error')
    },
  })

  const submit = () => {
    if (signer == null) {
      setErrors({ sender: 'Imzolovchi xodim tanlanmadi' })
      return
    }
    setErrors({})
    setConfirm(true)
  }

  return (
    <ExecuteShell>
      {q.isError ? (
        <div className="ivs-empty" role="alert">
          {t(q.error.message)}
        </div>
      ) : (
        <div className="ivs-orders-deed">
          <Widget icon="ri-quill-pen-line" title={t('Imzolashga yuborish')} className="ivs-orders-deed-side">
            <div className="ivs-orders-deed-form">
              {q.data && (
                <p className="type-para-sm ivs-orders-muted">
                  {t('Ariza #{id}', { id: q.data.order.id })} · {q.data.order.sender_name}
                  {q.data.order.organization_name ? ` · ${q.data.order.organization_name}` : ''}
                </p>
              )}
              <Select
                label={t('Imzolovchi xodim *')}
                placeholder={t('Tanlang...')}
                options={(q.data?.employees ?? []).map((e) => ({ value: e.id, label: e.rank ? `${e.full_name} — ${e.rank}` : e.full_name }))}
                value={signer}
                onChange={(v) => setSigner(v == null ? null : Number(v))}
                error={!!errors.sender}
                hint={errors.sender && t(errors.sender)}
              />
              <Textarea label={t('Izoh')} rows={4} placeholder={t('Izoh yozing...')} value={message} onChange={(e) => setMessage(e.target.value)} />
              {errors.body && (
                <p className="ivs-form-error type-para-sm" role="alert">
                  {t(errors.body)}
                </p>
              )}
              <Button size="lg" icon="ri-send-plane-fill" onClick={submit} disabled={!q.data}>
                {t('Imzolashga yuborish')}
              </Button>
              <Button variant="stroke" size="lg" icon="ri-arrow-left-line" onClick={() => navigate('/orders/execute/archive')}>
                {t('Tarixga qaytish')}
              </Button>
            </div>
          </Widget>

          <Widget
            icon="ri-file-text-line"
            title={t('Dalolatnoma')}
            className="ivs-orders-deed-main"
            extra={<Switch label={t("Qo'lda tahrirlash")} checked={manual} onChange={setManual} />}
          >
            {!q.data && <div className="ivs-empty" aria-busy="true">{t('Yuklanmoqda…')}</div>}
            <div ref={toolbar} className="ivs-rich-toolbar" />
            <div className="ivs-orders-paper-wrap">
              <div
                ref={doc}
                className="ivs-orders-paper"
                role="textbox"
                aria-multiline="true"
                aria-readonly={!manual}
                aria-label={t('Hujjat matni')}
              />
            </div>
          </Widget>
        </div>
      )}

      {confirm && (
        <ConfirmDialog
          title="Imzolashga yuborishni tasdiqlang?"
          message="Akt PDF ko'rinishida yaratiladi va tanlangan xodimga imzolash uchun yuboriladi."
          confirmLabel="Yuborish"
          loading={send.isPending}
          onConfirm={() => send.mutate()}
          onClose={() => setConfirm(false)}
        />
      )}
    </ExecuteShell>
  )
}
