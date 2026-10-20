import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { Badge, Button, DataTable, Pagination, SegmentedControl } from '../../ds'
import type { BadgeProps, DataTableColumn } from '../../ds'
import Page from '../../layout/Page'
import DataState from '../../components/DataState'
import { useToast } from '../../components/toast'
import { api } from '../../api/client'
import type { Page as ApiPage } from '../../api/client'
import { NAV } from '../../layout/nav'
import { useUrlFilters } from '../../lib/useUrlFilters'
import { useT } from '../../i18n'
import { formatDateTime } from './api'
import type { NotificationRow } from './api'
import './people.css'

const PAGE_SIZE = 20

// core/views.py: TABS
const TABS = [
  { value: '', label: 'Hammasi' },
  { value: 'unread', label: "O'qilmagan" },
  { value: 'order', label: 'Ariza' },
  { value: 'deed', label: 'Hujjat' },
  { value: 'meeting', label: 'Zoom' },
  { value: 'chat', label: 'Chat' },
]

const KIND: Record<NotificationRow['kind'], { label: string; tone: BadgeProps['tone']; icon: string }> = {
  order: { label: 'Ariza', tone: 'primary', icon: 'ri-file-list-3-line' },
  deed: { label: 'Hujjat', tone: 'purple', icon: 'ri-file-text-line' },
  meeting: { label: 'Zoom', tone: 'sky', icon: 'ri-video-chat-line' },
  chat: { label: 'Chat', tone: 'teal', icon: 'ri-chat-3-line' },
  system: { label: 'Tizim', tone: 'neutral', icon: 'ri-settings-3-line' },
}

// Ishlab chiqishda Django alohida portda; productionda bir domenda (LegacyPage bilan bir xil).
const LEGACY_ORIGIN = import.meta.env.DEV ? 'http://127.0.0.1:8000' : ''
// Bildirishnoma manzili (eski sayt yo'li) → yangi interfeysdagi sahifa, menyudagi `legacy` bo'yicha
const EXTRA_ROUTES: Record<string, string> = { '/order/receiver/': '/orders/execute', '/': '/' }

/** core.notifications.safe_url: faqat sayt ichidagi yo'l */
const safeUrl = (url: string) => (url.startsWith('/') && !url.startsWith('//') ? url : '/')

function spaPath(url: string): string | null {
  const path = url.split(/[?#]/)[0]
  if (EXTRA_ROUTES[path]) return EXTRA_ROUTES[path]
  const entry = NAV.flatMap((s) => s.items).find((i) => i.legacy === path)
  return entry ? entry.path : null
}

/** "Bildirishnomalar" — templates/core/notifications.html (core/views.py). */
export default function NotificationsPage() {
  const navigate = useNavigate()
  const t = useT()
  const toast = useToast()
  const qc = useQueryClient()
  const { filters, page, setFilter, setPage } = useUrlFilters(['tab'] as const)
  const tab = TABS.some((x) => x.value === filters.tab) ? filters.tab : ''

  const list = useQuery({
    queryKey: ['people', 'notifications', tab, page],
    queryFn: () =>
      api<ApiPage<NotificationRow> & { unread: number }>('/notifications/', {
        query: { kind: tab && tab !== 'unread' ? tab : undefined, unread: tab === 'unread' ? 1 : undefined, page, page_size: PAGE_SIZE },
      }),
    placeholderData: keepPreviousData,
  })

  const readAll = useMutation({
    mutationFn: () => api<{ updated: number; unread: number }>('/notifications/read-all/', { method: 'POST', body: JSON.stringify({ kind: tab === 'unread' ? '' : tab }) }),
    onSuccess: (r) => {
      qc.invalidateQueries({ queryKey: ['people', 'notifications'] })
      qc.invalidateQueries({ queryKey: ['badges'] })
      toast(r.updated ? t("{n} ta bildirishnoma o'qilgan deb belgilandi", { n: r.updated }) : "O'qilmagan bildirishnoma yo'q", 'info')
    },
    onError: (e) => toast(e.message, 'error'),
  })

  const open = useMutation({
    mutationFn: (n: NotificationRow) => (n.is_read ? Promise.resolve(n) : api<NotificationRow>(`/notifications/${n.id}/read/`, { method: 'POST' })),
    onSettled: (_r, _e, n) => {
      qc.invalidateQueries({ queryKey: ['people', 'notifications'] })
      qc.invalidateQueries({ queryKey: ['badges'] })
      const url = safeUrl(n.url)
      const target = spaPath(url)
      if (target) navigate(target)
      else window.location.assign(LEGACY_ORIGIN + url)
    },
  })

  const rows = list.data?.results ?? []
  const unread = list.data?.unread ?? 0
  const pageCount = Math.max(1, Math.ceil((list.data?.count ?? 0) / PAGE_SIZE))

  const columns: DataTableColumn<NotificationRow>[] = [
    { key: 'n', label: t('T/r'), width: 52, render: (r) => (page - 1) * PAGE_SIZE + rows.indexOf(r) + 1 },
    {
      key: 'kind',
      label: t('Turi'),
      width: 120,
      render: (r) => (
        <Badge tone={KIND[r.kind]?.tone ?? 'neutral'} icon={KIND[r.kind]?.icon} size="sm">
          {KIND[r.kind] ? t(KIND[r.kind].label) : r.kind}
        </Badge>
      ),
    },
    {
      key: 'title',
      label: t('Bildirishnoma'),
      render: (r) => (
        <a
          href={spaPath(safeUrl(r.url)) ?? LEGACY_ORIGIN + safeUrl(r.url)}
          className={'ivs-people-notif' + (r.is_read ? '' : ' is-unread')}
          onClick={(e) => {
            if (e.metaKey || e.ctrlKey || e.shiftKey) return
            e.preventDefault()
            open.mutate(r)
          }}
        >
          <span className="aui-cell-primary">
            {!r.is_read && <span className="ivs-people-dot" aria-label={t("O'qilmagan")} />}
            {r.title}
            {r.count > 1 && <span className="ivs-people-note"> ({r.count})</span>}
          </span>
          {r.body && <span className="aui-cell-secondary">{r.body}</span>}
        </a>
      ),
    },
    { key: 'date', label: t('Vaqt'), width: 150, render: (r) => <span className="ivs-people-note">{formatDateTime(r.date_creat)}</span> },
  ]

  return (
    <Page
      icon="ri-notification-3-line"
      title="Bildirishnomalar"
      subtitle="Arizalar, hujjatlar, uchrashuvlar va chat bo'yicha xabarlar tarixi."
      actions={
        unread > 0 && (
          <Button size="lg" variant="stroke" icon="ri-check-double-line" loading={readAll.isPending} onClick={() => readAll.mutate()}>
            {t('Tozalash')}
          </Button>
        )
      }
    >
      <div className="ivs-tabs">
        <SegmentedControl
          aria-label={t('Bildirishnoma turi')}
          items={TABS.map((x) => ({ value: x.value || 'all', label: t(x.label), count: x.value === 'unread' && unread ? unread : undefined }))}
          value={tab || 'all'}
          onChange={(v) => setFilter('tab', v === 'all' ? null : String(v))}
        />
      </div>

      <DataState isPending={list.isPending} isFetching={list.isFetching} error={list.error} empty={rows.length === 0} emptyText="Bildirishnoma yo'q">
        <DataTable rows={rows} columns={columns} getRowId={(r) => r.id} rowHeight={64} minWidth={640} caption={t('Bildirishnomalar')} />
        {pageCount > 1 && (
          <div className="ivs-pager">
            <Pagination pageCount={pageCount} page={page} onChange={setPage} />
          </div>
        )}
      </DataState>
    </Page>
  )
}
