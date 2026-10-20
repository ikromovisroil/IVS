import { useContext, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate, useParams } from 'react-router-dom'
import { Button, StatusChip, Widget } from '../../ds'
import Page from '../../layout/Page'
import PublicPage from '../../layout/PublicPage'
import { MeContext } from '../../auth/me'
import DataState from '../../components/DataState'
import { api } from '../../api/client'
import { useT } from '../../i18n'
import { SPA, attachmentsUrl, openFile, useDeed } from './api'
import { AgreeDialog, SignDialog } from './ActionDialogs'
import DeedStatusPanel from './DeedStatusPanel'
import { SIGN_STATUS, deedStatus, formatDateTime } from './status'
import type { Deed, PublicDeed } from './types'
import './messages.css'

function Summary({ deed }: { deed: Deed | PublicDeed }) {
  const t = useT()
  const s = SIGN_STATUS[deedStatus(deed)]
  return (
    <div className="msg-summary">
      <div className="msg-kv">
        <span>{t('Hujjat turi')}</span>
        <b>{t(deed.status_display)}</b>
      </div>
      <div className="msg-kv">
        <span>{t('Hujjat kodi')}</span>
        <b className="ivs-mono">{deed.code || '—'}</b>
      </div>
      <div className="msg-kv">
        <span>{t('Tashkilot')}</span>
        <b>{deed.organization_name || '—'}</b>
      </div>
      <div className="msg-kv">
        <span>{t('Hudud')}</span>
        <b>{deed.user_info?.region_name || '—'}</b>
      </div>
      <div className="msg-kv">
        <span>{t('Yuborilgan sana')}</span>
        <b>{formatDateTime(deed.date_creat)}</b>
      </div>
      <div className="msg-kv">
        <span>{t('Holati')}</span>
        <StatusChip status={s.chip}>{t(s.label)}</StatusChip>
      </div>
    </div>
  )
}

/** Hujjat sahifasi: ma'lumot, fayllar, holat jadvallari va joriy foydalanuvchiga tegishli amallar. */
export default function DeedPage() {
  const id = Number(useParams().id)
  const deed = useDeed(id)
  const navigate = useNavigate()
  const [acting, setActing] = useState<'sign' | 'agree' | null>(null)
  const t = useT()
  const d = deed.data

  const actions = d && (
    <>
      {d.attachments.length > 0 && (
        <Button size="lg" variant="stroke" icon="ri-attachment-2" onClick={() => window.location.assign(attachmentsUrl(d.id))}>
          {t('Ilovalar ({n})', { n: d.attachments.length })}
        </Button>
      )}
      {d.file && (
        <Button size="lg" variant="stroke" icon="ri-file-pdf-2-line" onClick={() => openFile(d.file!)}>
          {t("Ko'rish")}
        </Button>
      )}
      {d.can_edit && (
        <Button size="lg" variant="stroke" icon="ri-edit-line" onClick={() => navigate(`/messages/deed/${d.id}/edit`)}>
          {t('Tahrirlash')}
        </Button>
      )}
      {d.can_reject && (
        <Button size="lg" icon="ri-quill-pen-line" onClick={() => setActing('sign')}>
          {t('Tasdiqlang')}
        </Button>
      )}
      {d.my_consent_id && (
        <Button size="lg" icon="ri-shake-hands-line" onClick={() => setActing('agree')}>
          {t('Kelishish')}
        </Button>
      )}
    </>
  )

  return (
    <Page icon="ri-file-text-line" title={d ? t('Dalolatnoma #{code}', { code: d.code ?? d.id }) : 'Dalolatnoma'} subtitle="Hujjat ma'lumoti va imzolash holati." actions={actions}>
      <div className="msg-back">
        <Button variant="ghost" size="sm" icon="ri-arrow-left-line" onClick={() => navigate(-1)}>
          {t('Orqaga')}
        </Button>
      </div>
      <DataState isPending={deed.isPending} isFetching={deed.isFetching} error={deed.error} empty={false} emptyText="">
        {d && (
          <div className="msg-stack">
            <Widget>
              <Summary deed={d} />
            </Widget>
            <DeedStatusPanel deed={d} />
          </div>
        )}
      </DataState>
      {d && acting === 'sign' && <SignDialog deed={d} onClose={() => setActing(null)} />}
      {d && acting === 'agree' && <AgreeDialog deed={d} onClose={() => setActing(null)} />}
    </Page>
  )
}

/** deed_status: hujjat kodi bo'yicha holat (PDF dagi QR havolasi bilan bir xil ma'lumot). */
export function DeedCodeStatusPage() {
  const { code = '', id = '' } = useParams()
  const deed = useQuery({
    queryKey: ['messages', 'status', code, id],
    queryFn: () => api<PublicDeed>(`${SPA}/status/${encodeURIComponent(code)}/${Number(id)}/`),
  })
  const d = deed.data
  const t = useT()
  // Kirmagan foydalanuvchi (QR havolasi) — yon menyusiz ommaviy qobiq
  const Shell = useContext(MeContext) ? Page : PublicPage

  return (
    <Shell
      icon="ri-qr-code-line"
      title={t('Dalolatnoma kodi: {code}', { code })}
      subtitle="Dalolatnoma holati."
      actions={
        d?.file && (
          <Button size="lg" variant="stroke" icon="ri-file-pdf-2-line" onClick={() => openFile(d.file!)}>
            {t("Ko'rish")}
          </Button>
        )
      }
    >
      <DataState isPending={deed.isPending} isFetching={deed.isFetching} error={deed.error} empty={false} emptyText="">
        {d && (
          <div className="msg-stack">
            <Widget>
              <Summary deed={d} />
            </Widget>
            <DeedStatusPanel deed={d} readOnly />
          </div>
        )}
      </DataState>
    </Shell>
  )
}
