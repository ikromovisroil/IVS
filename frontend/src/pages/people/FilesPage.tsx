import EmptyState from '../../components/EmptyState'
import FilterBar from '../../components/FilterBar'
import DatePicker from '../../components/DatePicker'
import { useState } from 'react'
import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { Button, DataTable, Icon, Pagination, Select, StatusChip } from '../../ds'
import type { DataTableColumn, StatusChipProps } from '../../ds'
import Page from '../../layout/Page'
import SearchInput from '../../components/SearchInput'
import DataState from '../../components/DataState'
import { API, api } from '../../api/client'
import type { Page as ApiPage } from '../../api/client'
import type { Named } from '../../api/types'
import { can, useMe } from '../../auth/me'
import { useUrlFilters } from '../../lib/useUrlFilters'
import { formatNumber } from '../../lib/format'
import { useT } from '../../i18n'
import { formatDateTime, opts } from './api'
import type { DeedRow } from './api'
import { openPdf } from '../../lib/pdf'
import DeedStatusModal from './DeedStatusModal'
import './people.css'

const PAGE_SIZE = 20
const FILTERS = ['organization', 'region', 'date1', 'date2', 'status', 'name'] as const

const OVERALL: Record<DeedRow['overall'], { chip: StatusChipProps['status']; label: string }> = {
  approved: { chip: 'completed', label: 'Tasdiqlandi#hujjat' },
  rejected: { chip: 'failed', label: 'Rad etildi#hujjat' },
  pending: { chip: 'pending', label: 'Kutilmoqda#hujjat' },
}

interface Filters {
  organizations: Named[]
  regions: Named[]
  statuses: { value: string; label: string }[]
}

/** "Hujjatlar" — templates/main/files.html (main/views.py: files). */
export default function FilesPage() {
  const me = useMe()
  const t = useT()
  const { filters, page, hasFilters, setFilter, setPage } = useUrlFilters(FILTERS)
  const [opened, setOpened] = useState<number | null>(null)
  const canToggle = can(me, 'main.change_deed')

  const refs = useQuery({
    queryKey: ['people', 'files-filters'],
    queryFn: () => api<Filters>('/spa/people/files/filters/'),
    staleTime: 60 * 60 * 1000,
  })
  const list = useQuery({
    queryKey: ['people', 'files', filters, page],
    queryFn: () =>
      api<ApiPage<DeedRow>>('/spa/people/files/', {
        query: { ...filters, page, page_size: PAGE_SIZE },
      }),
    placeholderData: keepPreviousData,
    enabled: hasFilters,
  })

  const rows = hasFilters ? (list.data?.results ?? []) : []
  const pageCount = Math.max(1, Math.ceil((list.data?.count ?? 0) / PAGE_SIZE))
  const openedRow = rows.find((r) => r.id === opened) ?? null

  const foundText = t('Topildi: {n} ta').split('{n}')

  const columns: DataTableColumn<DeedRow>[] = [
    {
      key: 'n',
      label: t('T/r'),
      width: 52,
      render: (r) => (page - 1) * PAGE_SIZE + rows.indexOf(r) + 1,
    },
    {
      key: 'org',
      label: t('Tashkilot'),
      width: '15%',
      render: (r) => (
        <div className="aui-cell-text">
          <div className="aui-cell-primary" title={r.organization_name ?? undefined}>
            {r.organization_name || '—'}
          </div>
          <div className="aui-cell-secondary">{r.region_name || '—'}</div>
        </div>
      ),
    },
    {
      key: 'status',
      label: t('Hujjat turi / kodi'),
      width: '12%',
      render: (r) => (
        <div className="aui-cell-text">
          <div className="aui-cell-primary">{r.status_display}</div>
          <div className="aui-cell-secondary ivs-people-mono">{r.code || '—'}</div>
        </div>
      ),
    },
    {
      key: 'user',
      label: t("Jo'natuvchi"),
      width: '13%',
      render: (r) => (
        <div className="aui-cell-text">
          <div className="aui-cell-primary is-regular" title={r.user?.full_name}>
            {r.user?.full_name || '—'}
          </div>
        </div>
      ),
    },
    {
      key: 'signers',
      label: t('Imzolovchi'),
      width: '15%',
      render: (r) => (
        <div className="aui-cell-text">
          <div className="aui-cell-primary" title={r.sender?.full_name}>
            {r.sender?.full_name || '—'}
          </div>
          {r.receiver && (
            <div className="aui-cell-secondary" title={r.receiver.full_name}>
              {r.receiver.full_name}
            </div>
          )}
        </div>
      ),
    },
    {
      key: 'date',
      label: t('Yuborilgan sana'),
      width: '10%',
      render: (r) => formatDateTime(r.date_creat),
    },
    {
      key: 'files',
      label: t('Fayllar'),
      width: '9%',
      render: (r) => (
        <div className="ivs-people-actions is-left">
          {r.file_url ? (
            <Button
              variant="ghost"
              size="sm"
              iconOnly
              icon="ri-file-pdf-2-line"
              aria-label={t("Hujjatni ko'rish")}
              title={t("Ko'rish")}
              onClick={() => openPdf(r.file_url!)}
            />
          ) : null}
          {r.attachments_count > 0 && (
            <Button
              variant="ghost"
              size="sm"
              icon="ri-attachment-2"
              title={t('Ilovalarni yuklab olish ({n} ta fayl)', { n: r.attachments_count })}
              onClick={() => window.location.assign(`${API}/spa/people/files/${r.id}/attachments/`)}
            >
              {t('{n} ta', { n: r.attachments_count })}
            </Button>
          )}
          {!r.file_url && !r.attachments_count && '—'}
        </div>
      ),
    },
    {
      key: 'overall',
      label: t('Holati'),
      width: '14%',
      render: (r) => (
        <div className="ivs-people-actions is-left">
          <StatusChip status={OVERALL[r.overall].chip}>{t(OVERALL[r.overall].label)}</StatusChip>
          {canToggle && (
            <span className={r.user_edit ? 'ivs-people-ok' : 'ivs-people-no'} title={t(r.user_edit ? 'Tahrirlash ruxsati: bor' : "Tahrirlash ruxsati: yo'q")}>
              <Icon name={r.user_edit ? 'ri-check-line' : 'ri-close-line'} size={18} />
            </span>
          )}
          <Button variant="ghost" size="sm" iconOnly icon="ri-eye-line" aria-label={t('Hujjat holati')} title={t('Holati')} onClick={() => setOpened(r.id)} />
        </div>
      ),
    },
  ]

  // Holati — hujjat turidan keyin (keng jadvalda ham ko'rinib tursin)
  const ordered = [...columns.slice(0, 3), columns[columns.length - 1], ...columns.slice(3, -1)]

  return (
    <Page icon="ri-file-text-line" title="Hujjatlar" subtitle="Dalolatnoma, akt, reestr va hisobotlarni qidirish.">
      <FilterBar
        search={<SearchInput value={filters.name} onChange={(v) => setFilter('name', v)} placeholder="F.I.O, hujjat kodi, ariza raqami ..." />}
        summary={hasFilters && list.data ? <>{foundText[0]}<b>{formatNumber(list.data.count)}</b>{foundText[1]}</> : undefined}
      >
        <Select
          label={t('Tashkilot')}
          placeholder={t('Tanlang...')}
          options={opts(refs.data?.organizations)}
          value={filters.organization ? Number(filters.organization) : null}
          onChange={(v) => setFilter('organization', v)}
        />
        <Select
          label={t('Hududlar')}
          placeholder={t('Tanlang...')}
          options={opts(refs.data?.regions)}
          value={filters.region ? Number(filters.region) : null}
          onChange={(v) => setFilter('region', v)}
        />
        <Select
          label={t('Hujjat turi')}
          placeholder={t('Tanlang...')}
          searchable={false}
          options={refs.data?.statuses ?? []}
          value={filters.status || null}
          onChange={(v) => setFilter('status', v)}
        />
        <DatePicker label="Boshlang'ich sana" value={filters.date1} max={filters.date2 || undefined} onChange={(v) => setFilter('date1', v)} />
        <DatePicker label="Tugash sanasi" value={filters.date2} min={filters.date1 || undefined} onChange={(v) => setFilter('date2', v)} />
      </FilterBar>

      {!hasFilters ? (
        <EmptyState
          icon="ri-file-search-line"
          title="Hujjatlarni qidiring"
          description="Ko'rish uchun kamida bitta filtrni tanlang yoki qidiruvga F.I.O, hujjat kodi yoki ariza raqamini yozing."
        />
      ) : (
        <DataState isPending={list.isPending} isFetching={list.isFetching} error={list.error} empty={rows.length === 0} emptyText="Ma'lumot topilmadi.">
          <DataTable rows={rows} columns={ordered} getRowId={(r) => r.id} rowHeight={64} minWidth={1240} caption={t("Hujjatlar ro'yxati")} />
          {pageCount > 1 && (
            <div className="ivs-pager">
              <Pagination pageCount={pageCount} page={page} onChange={setPage} />
            </div>
          )}
        </DataState>
      )}

      {openedRow && <DeedStatusModal deed={openedRow} canToggle={canToggle} onClose={() => setOpened(null)} />}
    </Page>
  )
}
