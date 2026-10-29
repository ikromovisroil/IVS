import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { Button, DataTable, Pagination, StatusChip } from '../../ds'
import type { DataTableColumn } from '../../ds'
import DataState from '../../components/DataState'
import SearchInput from '../../components/SearchInput'
import { api } from '../../api/client'
import type { Page as ApiPage } from '../../api/client'
import { useMe } from '../../auth/me'
import { useUrlFilters } from '../../lib/useUrlFilters'
import { sectionAllowed } from './access'
import { PAGE_SIZE, SPA, useBarnMutation, useCart } from './api'
import BarnPage from './BarnPage'
import MaterialImage from './MaterialImage'
import type { SelectableMaterial } from './types'
import { useT } from '../../i18n'

/** Material tanlash — order_sender_material_barn: o'z tashkiloti omborxonasidagi ruxsat etilgan materiallar, savatga saqlash. */
export default function MaterialsPage() {
  const me = useMe()
  const t = useT()
  const navigate = useNavigate()
  const allowed = sectionAllowed(me, 'sender')
  const { filters, page, setFilter, setPage, hasFilters } = useUrlFilters(['name'])

  const list = useQuery({
    queryKey: ['orders-barn', 'materials', filters.name, page],
    queryFn: () => api<ApiPage<SelectableMaterial>>('/orders/selectable-materials/', { query: { search: filters.name, page, page_size: PAGE_SIZE } }),
    placeholderData: keepPreviousData,
    enabled: allowed,
  })
  const cart = useCart(allowed)
  const inCart = new Set((cart.data ?? []).map((c) => c.material))

  const toggle = useBarnMutation(
    (m: SelectableMaterial) => api<{ action: 'added' | 'removed' }>(`${SPA}/cart/toggle/`, { method: 'POST', body: JSON.stringify({ material: m.id }) }),
    (m, d) => (d.action === 'added' ? t('«{name}» savatga saqlandi', { name: m.name }) : t('«{name}» savatdan olib tashlandi', { name: m.name })),
  )

  const rows = list.data?.results ?? []
  const pageCount = Math.max(1, Math.ceil((list.data?.count ?? 0) / PAGE_SIZE))

  const columns: DataTableColumn<SelectableMaterial>[] = [
    { key: 'n', label: t('T/r'), width: 64, render: (r) => (page - 1) * PAGE_SIZE + rows.indexOf(r) + 1 },
    { key: 'img', label: t('Rasm'), width: 72, render: (r) => <MaterialImage src={r.image} name={r.name} /> },
    {
      key: 'name',
      label: t('Nomi'),
      render: (r) => (
        <div className="aui-cell-text">
          <div className="aui-cell-primary">{r.name}</div>
          <div className="aui-cell-secondary">{r.category_name || ''}</div>
        </div>
      ),
    },
    { key: 'unit', label: t('Birligi'), width: 100, render: (r) => r.unit_name || '' },
    {
      key: 'state',
      label: t('Xolati'),
      width: 120,
      render: (r) => (r.number > 0 ? <StatusChip status="active">{t('Faol')}</StatusChip> : <StatusChip status="failed">{t('Tugagan')}</StatusChip>),
    },
    {
      key: 'cart',
      label: t('Savatga saqlash'),
      width: 170,
      align: 'right',
      render: (r) => {
        const saved = inCart.has(r.id)
        return (
          <Button
            size="sm"
            variant={saved ? 'lighter' : 'stroke'}
            icon={saved ? 'ri-bookmark-fill' : 'ri-bookmark-line'}
            aria-pressed={saved}
            loading={toggle.isPending && toggle.variables?.id === r.id}
            onClick={() => toggle.mutate(r)}
          >
            {saved ? t('Saqlangan') : t('Saqlash')}
          </Button>
        )
      },
    },
  ]

  return (
    <BarnPage
      section="sender"
      tools={
        <>
          <SearchInput value={filters.name} onChange={(v) => setFilter('name', v)} placeholder="Nomi ..." style={{ minWidth: 220, flex: '1 1 240px', maxWidth: 360 }} />
          <Button icon="ri-shopping-basket-2-line" onClick={() => navigate('/orders/barn/basket')}>
            {t('Savat')}
            {cart.data?.length ? ` (${cart.data.length})` : ''}
          </Button>
        </>
      }
    >
      <DataState
        isPending={list.isPending}
        isFetching={list.isFetching}
        error={list.error}
        empty={rows.length === 0}
        emptyText={hasFilters ? 'Qidiruvga mos material topilmadi' : "Sizga ruxsat etilgan material yo'q"}
        emptyDescription={hasFilters ? 'Boshqa nom bilan qidirib ko‘ring.' : 'Material kategoriyalari omborxona tomonidan biriktiriladi.'}
      >
        <DataTable rows={rows} columns={columns} getRowId={(r) => r.id} rowHeight={64} minWidth={760} caption={t('Omborxonadagi materiallar')} />
        {pageCount > 1 && (
          <div className="ivs-pager">
            <Pagination pageCount={pageCount} page={page} onChange={setPage} />
          </div>
        )}
      </DataState>
    </BarnPage>
  )
}
