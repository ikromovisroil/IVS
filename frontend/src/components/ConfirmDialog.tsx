import { useState } from 'react'
import type { ReactNode } from 'react'
import { Button, Textarea } from '../ds'
import { useT, useTMaybe } from '../i18n'
import Modal from './Modal'

interface ConfirmDialogProps {
  title: string
  message?: ReactNode
  confirmLabel?: string
  /** Xavfli amal (o'chirish, rad etish) — qizil tugma */
  danger?: boolean
  /** Izoh maydoni (masalan, rad etish sababi). required — bo'sh bo'lsa tasdiqlab bo'lmaydi */
  reason?: { label: string; required?: boolean }
  loading?: boolean
  onConfirm: (reason: string) => void
  onClose: () => void
}

/** Tasdiqlash oynasi: "Haqiqatan ham ...?" + ixtiyoriy izoh. */
export default function ConfirmDialog({ title, message, confirmLabel = 'Tasdiqlash', danger, reason, loading, onConfirm, onClose }: ConfirmDialogProps) {
  const t = useT()
  const tMaybe = useTMaybe()
  const [text, setText] = useState('')
  const blocked = !!reason?.required && !text.trim()

  return (
    <Modal
      open
      onClose={onClose}
      title={title}
      icon={danger ? 'ri-error-warning-line' : 'ri-question-line'}
      width={480}
      footer={
        <>
          <Button variant="stroke" size="lg" onClick={onClose}>
            {t('Bekor qilish')}
          </Button>
          <Button size="lg" variant={danger ? 'error' : 'primary'} disabled={blocked} loading={loading} onClick={() => onConfirm(text.trim())}>
            {t(confirmLabel)}
          </Button>
        </>
      }
    >
      {message && <div className="type-para-sm ivs-confirm-text">{typeof message === 'string' ? tMaybe(message) : message}</div>}
      {reason && <Textarea label={t(reason.label) + (reason.required ? ' *' : '')} rows={3} value={text} onChange={(e) => setText(e.target.value)} />}
    </Modal>
  )
}
