import { useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { useLocation } from 'react-router-dom'
import { Button, Icon, Textarea } from '../../ds'
import Modal from '../../components/Modal'
import ConfirmDialog from '../../components/ConfirmDialog'
import { useToast } from '../../components/toast'
import { api } from '../../api/client'
import { useT } from '../../i18n'
import { EIMZO_FLAG, SPA, useRefresh } from './api'
import type { Deed } from './types'

interface Props {
  deed: Deed
  onClose: () => void
}

/** FaceID veb SDK ulanmaguncha veb-versiyada FaceID tanlab bo'lmaydi (mobil ilovada ishlaydi). SDK ulangach true qilinadi. */
const FACEID_WEB_READY = false

/** "Tasdiqlash" bosilgach: tasdiqlash usuli tanlanadi — E-IMZO yoki FaceID. */
function SignMethodDialog({ deed, loading, onEimzo, onBack }: { deed: Deed; loading: boolean; onEimzo: () => void; onBack: () => void }) {
  const t = useT()
  const config = useQuery({
    queryKey: ['faceid', 'config'],
    queryFn: () => api<{ enabled: boolean }>('/faceid/config/'),
    staleTime: 60_000,
  })
  const faceEnabled = !!config.data?.enabled
  const faceReady = faceEnabled && FACEID_WEB_READY
  const faceHint = !faceEnabled ? t('FaceID hozircha yoqilmagan') : t('Veb-versiyada tez orada. Mobil ilovada mavjud')

  return (
    <Modal
      open
      onClose={onBack}
      icon="ri-shield-check-line"
      title="Tasdiqlash usulini tanlang"
      subtitle={`${t(deed.status_display)} #${deed.code ?? deed.id}`}
      width={520}
      footer={
        <Button variant="stroke" size="lg" icon="ri-arrow-left-line" disabled={loading} onClick={onBack}>
          {t('Orqaga')}
        </Button>
      }
    >
      <div className="msg-method-list">
        <button type="button" className="msg-method" disabled={loading} onClick={onEimzo}>
          <span className="msg-method-icon">
            <Icon name="ri-quill-pen-line" size={24} />
          </span>
          <span className="msg-method-text">
            <span className="type-label-md">E-IMZO</span>
            <span className="type-para-xs">{t('Elektron raqamli imzo (USB-token yoki kalit)')}</span>
          </span>
          <Icon name="ri-arrow-right-s-line" size={20} />
        </button>
        <button type="button" className="msg-method" disabled={!faceReady || loading}>
          <span className="msg-method-icon">
            <Icon name="ri-user-smile-line" size={24} />
          </span>
          <span className="msg-method-text">
            <span className="type-label-md">FaceID</span>
            <span className="type-para-xs">{faceReady ? t('Yuzni tekshirish orqali tasdiqlash') : faceHint}</span>
          </span>
          <Icon name="ri-arrow-right-s-line" size={20} />
        </button>
      </div>
    </Modal>
  )
}


/**
 * "Tasdiqlang" (contact.html, deed_action): izoh + Rad etish / Tasdiqlash.
 * "Tasdiqlash" bosilgach usul tanlanadi (E-IMZO yoki FaceID). E-IMZO: server sessiyaga imzolash ma'lumotini yozadi,
 * brauzer /sso/start/approve/ ga o'tadi, imzolangach main/sso_views.py:eimzo_return shu sahifaga qaytaradi.
 */
export function SignDialog({ deed, onClose }: Props) {
  const [message, setMessage] = useState('')
  const [confirmReject, setConfirmReject] = useState(false)
  const [choosing, setChoosing] = useState(false)
  const { pathname } = useLocation()
  const t = useT()
  const toast = useToast()
  const refresh = useRefresh()

  const reject = useMutation({
    mutationFn: () => api(`/deeds/${deed.id}/reject/`, { method: 'POST', body: JSON.stringify({ message: message.trim() }) }),
    onSuccess: () => {
      toast('Dalolatnoma rad etildi')
      refresh()
      onClose()
    },
    onError: (e) => {
      setConfirmReject(false)
      toast(e.message, 'error')
    },
  })

  const approve = useMutation({
    mutationFn: () =>
      api<{ redirect: string }>(`${SPA}/deeds/${deed.id}/approve/`, {
        method: 'POST',
        body: JSON.stringify({ message: message.trim(), return_to: `${pathname}?${EIMZO_FLAG}=1` }),
      }),
    onSuccess: (r) => window.location.assign(r.redirect),
    onError: (e) => toast(e.message, 'error'),
  })

  if (choosing) {
    return <SignMethodDialog deed={deed} loading={approve.isPending} onEimzo={() => approve.mutate()} onBack={() => setChoosing(false)} />
  }

  return (
    <>
      <Modal
        open
        onClose={onClose}
        icon="ri-quill-pen-line"
        title="Tasdiqlash"
        subtitle={`${t(deed.status_display)} #${deed.code ?? deed.id}`}
        width={560}
        footer={
          <>
            <Button variant="stroke" size="lg" icon="ri-close-line" onClick={onClose}>
              {t('Yopish')}
            </Button>
            <Button variant="error-lighter" size="lg" icon="ri-close-circle-line" onClick={() => setConfirmReject(true)}>
              {t('Rad etish')}
            </Button>
            <Button size="lg" icon="ri-checkbox-circle-line" onClick={() => setChoosing(true)}>
              {t('Tasdiqlash')}
            </Button>
          </>
        }
      >
        <p className="type-para-sm msg-info">
          {t("Tasdiqlangandan so'ng hujjat yuridik kuchga ega bo'ladi va rasmiylashtiriladi. Tasdiqlash usulini keyingi oynada tanlaysiz.")}
        </p>
        <Textarea label={t('Izoh')} placeholder={t('Izoh yozing...')} rows={4} value={message} onChange={(e) => setMessage(e.target.value)} />
      </Modal>
      {confirmReject && (
        <ConfirmDialog
          title="Rad etishga rozimisiz?"
          message={message.trim() ? <>{t('Izoh: {text}', { text: message.trim() })}</> : undefined}
          confirmLabel="Rad etish"
          danger
          loading={reject.isPending}
          onConfirm={() => reject.mutate()}
          onClose={() => setConfirmReject(false)}
        />
      )}
    </>
  )
}

/** "Kelishish" (contact_agrement.html, deedconsent_action): izoh + Rad etish (izoh majburiy) / Kelishish. */
export function AgreeDialog({ deed, onClose }: Props) {
  const [message, setMessage] = useState('')
  const [confirm, setConfirm] = useState<'approve' | 'reject' | null>(null)
  const t = useT()
  const toast = useToast()
  const refresh = useRefresh()

  const act = useMutation({
    mutationFn: (action: 'approve' | 'reject') =>
      api(`/deed-consents/${deed.my_consent_id}/${action}/`, { method: 'POST', body: JSON.stringify({ message: message.trim() }) }),
    onSuccess: (_, action) => {
      toast(action === 'approve' ? 'Hujjat muvaffaqiyatli kelishildi' : 'Hujjat rad etildi')
      refresh()
      onClose()
    },
    onError: (e) => {
      setConfirm(null)
      toast(e.message, 'error')
    },
  })

  const rejectBlocked = !message.trim()

  return (
    <>
      <Modal
        open
        onClose={onClose}
        icon="ri-shake-hands-line"
        title="Kelishish"
        subtitle={`${t(deed.status_display)} #${deed.code ?? deed.id}`}
        width={560}
        footer={
          <>
            <Button variant="stroke" size="lg" icon="ri-close-line" onClick={onClose}>
              {t('Yopish')}
            </Button>
            <Button variant="error-lighter" size="lg" icon="ri-close-circle-line" disabled={rejectBlocked} title={rejectBlocked ? t('Rad etish uchun izoh yozing') : undefined} onClick={() => setConfirm('reject')}>
              {t('Rad etish')}
            </Button>
            <Button size="lg" icon="ri-checkbox-circle-line" onClick={() => setConfirm('approve')}>
              {t('Kelishish')}
            </Button>
          </>
        }
      >
        <p className="type-para-sm msg-info">{t("Kelishilgandan so'ng hujjat yuridik kuchga ega bo'ladi va rasmiylashtiriladi.")}</p>
        <Textarea label={t('Izoh')} placeholder={t('Izoh yozing...')} hint={t('Rad etishda izoh majburiy.')} rows={4} value={message} onChange={(e) => setMessage(e.target.value)} />
      </Modal>
      {confirm && (
        <ConfirmDialog
          title={confirm === 'approve' ? 'Kelishishga rozimisiz?' : 'Rad etishga rozimisiz?'}
          confirmLabel={confirm === 'approve' ? 'Kelishish' : 'Rad etish'}
          danger={confirm === 'reject'}
          loading={act.isPending}
          onConfirm={() => act.mutate(confirm)}
          onClose={() => setConfirm(null)}
        />
      )}
    </>
  )
}
