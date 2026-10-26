import { useEffect, useState } from 'react'
import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { Button, CellUser, DataTable, Pagination, StatusChip } from '../../ds'
import type { DataTableColumn } from '../../ds'
import Page from '../../layout/Page'
import PageTabs from '../../components/PageTabs'
import DataState from '../../components/DataState'
import { useToast } from '../../components/toast'
import { api } from '../../api/client'
import type { Page as ApiPage } from '../../api/client'
import { can, useMe } from '../../auth/me'
import { useUrlFilters } from '../../lib/useUrlFilters'
import { useT } from '../../i18n'
import { EIMZO_FLAG, SPA, attachmentsUrl, openFile, useCounts, useRefresh } from './api'
import { BOXES, archiveTabs, groupTabs } from './boxes'
import type { Box } from './boxes'
import { AgreeDialog, SignDialog } from './ActionDialogs'
import CreateDeedModal from './CreateDeedModal'
import DeedStatusModal from './DeedStatusModal'
import RowClick from '../../components/RowClick'
import { SIGN_STATUS, deedStatus, formatDateTime } from './status'
import type { Deed } from './types'
import './messages.css'

const PAGE_SIZE = 20

/** E-IMZO'dan qaytgach (?eimzo=1): eimzo_return qoldirgan xabarlarni ko'rsatadi va ro'yxatni yangilaydi. */
function useEimzoReturn() {
  const [params, setParams] = useSearchParams()
  const toast = useToast()
  const refresh = useRefresh()
  const back = params.has(EIMZO_FLAG)

  useEffect(() => {
    if (!back) return
    setParams(
      (p) => {
        p.delete(EIMZO_FLAG)
        return p
      },
      { replace: true },
    )
    api<{ text: string; tone: 'success' | 'error' | 'info' }[]>(`${SPA}/flash/`)
      .then((items) => items.forEach((m) => toast(m.text, m.tone)))
      .catch(() => {})
      .finally(() => refresh())
  }, [back, setParams, toast, refresh])
}

/** Imzolashga yuborish / Imzolash uchun / Kelishish uchun va ularning arxivi (contact*.html). */
export default function DeedListPage({ box }: { box: Box }) {
  const cfg = BOXES[box]
  const t = useT()
  const me = useMe()
  const navigate = useNavigate()
  const { page, setPage } = useUrlFilters([])
  const counts = useCounts()
  const [creating, setCreating] = useState(false)
  const [statusOf, setStatusOf] = useState<number | null>(null)
  const [acting, setActing] = useState<Deed | null>(null)
  useEimzoReturn()

  const list = useQuery({
    queryKey: ['messages', 'list', box, page],
    queryFn: () => api<ApiPage<Deed>>(`${SPA}/deeds/`, { query: { box, page, page_size: PAGE_SIZE } }),
    placeholderData: keepPreviousData,
  })

  const rows = list.data?.results ?? []
  const pageCount = Math.max(1, Math.ceil((list.data?.count ?? 0) / PAGE_SIZE))
  const meId = me.employee?.id

  const columns: DataTableColumn<Deed>[] = [
    { key: 'n', label: t('T/r'), width: 48, render: (r) => (page - 1) * PAGE_SIZE + rows.indexOf(r) + 1 },
    {
      key: 'kind',
      label: t('Hujjat'),
      width: 156,
      render: (r) => (
        <div className="aui-cell-text">
          <div className="aui-cell-primary">{t(r.status_display)}</div>
          <div className="aui-cell-secondary ivs-mono">{r.code || '—'}</div>
        </div>
      ),
    },
    {
      key: 'org',
      label: t('Tashkilot / Hudud'),
      render: (r) => (
        <div className="aui-cell-text">
          <div className="aui-cell-primary">{r.organization_name || '—'}</div>
          <div className="aui-cell-secondary">{r.user_info?.region_name || '—'}</div>
        </div>
      ),
    },
    {
      key: 'user',
      label: t("Jo'natuvchi"),
      render: (r) => <CellUser avatar={false} name={r.user_info?.full_name || '—'} sub={r.user_info?.rank_name || undefined} />,
    },
    {
      key: 'signers',
      label: t('Imzolovchi'),
      render: (r) => (
        <div className="aui-cell-text">
          <div className="aui-cell-primary">{r.sender_info?.full_name || '—'}</div>
          {r.receiver_info && <div className="aui-cell-primary">{r.receiver_info.full_name}</div>}
        </div>
      ),
    },
    {
      key: 'date',
      label: t('Yuborilgan sana'),
      width: 112,
      render: (r) => {
        const [day, time] = formatDateTime(r.date_creat).split(' ')
        return (
          <div className="aui-cell-text">
            <div className="aui-cell-primary">{day}</div>
            <div className="aui-cell-secondary">{time}</div>
          </div>
        )
      },
    },
    {
      key: 'files',
      label: t('Fayllar'),
      width: 108,
      render: (r) => (
        <div className="msg-files">
          {r.file ? (
            <Button variant="stroke" size="sm" icon="ri-file-pdf-2-line" onClick={() => openFile(r.file!)}>
              {t("Ko'rish")}
            </Button>
          ) : (
            '—'
          )}
          {r.attachments.length > 0 && (
            <Button
              variant="stroke"
              size="sm"
              icon="ri-attachment-2"
              title={t('Ilovalarni yuklab olish ({n} ta fayl)', { n: r.attachments.length })}
              onClick={() => window.location.assign(attachmentsUrl(r.id))}
            >
              {t('{n} ta', { n: r.attachments.length })}
            </Button>
          )}
        </div>
      ),
    },
    {
      key: 'status',
      label: t('Holati'),
      width: 128,
      render: (r) => {
        const s = SIGN_STATUS[deedStatus(r)]
        return <StatusChip status={s.chip}>{t(s.label)}</StatusChip>
      },
    },
  ]

  if (!cfg.archive) {
    columns.push({
      key: 'actions',
      label: t('Amallar'),
      width: 130,
      render: (r) => {
        if (box === 'send')
          return r.can_edit ? (
            <Button size="sm" variant="stroke" icon="ri-edit-line" onClick={() => navigate(`/messages/deed/${r.id}/edit`)}>
              {t('Tahrirlash')}
            </Button>
          ) : null
        if (box === 'sign') {
          const mine = (r.receiver === meId && r.status_receiver === 'viewed') || (r.sender === meId && r.status_sender === 'viewed')
          return mine ? (
            <Button size="sm" icon="ri-quill-pen-line" onClick={() => setActing(r)}>
              {t('Tasdiqlang')}
            </Button>
          ) : (
            '—'
          )
        }
        return r.my_consent_id ? (
          <Button size="sm" icon="ri-shake-hands-line" onClick={() => setActing(r)}>
            {t('Kelishish')}
          </Button>
        ) : (
          '—'
        )
      },
    })
  }

  return (
    <Page
      icon="ri-mail-line"
      title="Xabarlar"
      subtitle={`${cfg.title}: ${cfg.subtitle.charAt(0).toLowerCase()}${cfg.subtitle.slice(1)}`}
      actions={
        cfg.group === 'send' &&
        can(me, 'main.add_deed') && (
          <Button size="lg" icon="ri-add-line" onClick={() => setCreating(true)}>
            {t('Hujjatlar yaratish')}
          </Button>
        )
      }
    >
      <PageTabs label="Xabarlar bo'limlari" tabs={groupTabs(counts.data)} />
      <PageTabs label={cfg.title} tabs={archiveTabs(cfg.group)} variant="segment" />

      <DataState isPending={list.isPending} isFetching={list.isFetching} error={list.error} empty={rows.length === 0} emptyText={cfg.empty}>
        <div className="msg-list">
          <RowClick rows={rows} onOpen={(r) => setStatusOf(r.id)}>
            <DataTable rows={rows} columns={columns} getRowId={(r) => r.id} rowHeight={64} minWidth={1000} caption={t(cfg.title)} />
          </RowClick>
        </div>
        {pageCount > 1 && (
          <div className="ivs-pager">
            <Pagination pageCount={pageCount} page={page} onChange={setPage} />
          </div>
        )}
      </DataState>

      {creating && <CreateDeedModal onClose={() => setCreating(false)} />}
      {statusOf != null && <DeedStatusModal id={statusOf} onClose={() => setStatusOf(null)} />}
      {acting && box === 'sign' && <SignDialog deed={acting} onClose={() => setActing(null)} />}
      {acting && box === 'agree' && <AgreeDialog deed={acting} onClose={() => setActing(null)} />}
    </Page>
  )
}
