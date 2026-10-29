import { useState } from 'react'
import type { FormEvent, MouseEvent } from 'react'
import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { Badge, Button, DataTable, Icon, Pagination, StatusChip, TextInput } from '../../ds'
import type { DataTableColumn } from '../../ds'
import DataState from '../../components/DataState'
import Modal from '../../components/Modal'
import SearchInput from '../../components/SearchInput'
import { api } from '../../api/client'
import type { Page as ApiPage } from '../../api/client'
import { useMe } from '../../auth/me'
import { formatNumber } from '../../lib/format'
import { useUrlFilters } from '../../lib/useUrlFilters'
import { money } from '../technics/util'
import { sectionAllowed } from './access'
import { PAGE_SIZE, SPA, mediaPath, useBarnMutation, useCart } from './api'
import BarnPage from './BarnPage'
import MaterialImage from './MaterialImage'
import type { CartItem, SelectableMaterial } from './types'
import { useT } from '../../i18n'

/** Material tanlash — order_sender_material_barn: o'z tashkiloti omborxonasidagi ruxsat etilgan materiallar; qatorni bosib to'liq ma'lumot ochiladi va soni bilan savatga saqlanadi. */
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

  const [active, setActive] = useState<SelectableMaterial | null>(null)

  const rows = list.data?.results ?? []
  const pageCount = Math.max(1, Math.ceil((list.data?.count ?? 0) / PAGE_SIZE))

  // Qatorning istalgan joyini bosish — modal (rasm kattalashtirish va nom tugmasining o'z amali bor)
  const openRow = (e: MouseEvent<HTMLDivElement>) => {
    const target = e.target as HTMLElement
    if (target.closest('button, a, input')) return
    const tr = target.closest('tbody tr')
    if (!tr) return
    const row = rows[Array.from(tr.parentElement?.children ?? []).indexOf(tr)]
    if (row) setActive(row)
  }

  const columns: DataTableColumn<SelectableMaterial>[] = [
    { key: 'n', label: t('T/r'), width: 64, render: (r) => (page - 1) * PAGE_SIZE + rows.indexOf(r) + 1 },
    { key: 'img', label: t('Rasm'), width: 72, render: (r) => <MaterialImage src={r.image} name={r.name} /> },
    {
      key: 'name',
      label: t('Nomi'),
      render: (r) => (
        <button type="button" className="ob-row-link" onClick={() => setActive(r)}>
          <span className="aui-cell-primary">{r.name}</span>
          <span className="aui-cell-secondary">{r.category_name || ''}</span>
        </button>
      ),
    },
    { key: 'unit', label: t('Birligi'), width: 100, render: (r) => r.unit_name || '' },
    {
      key: 'state',
      label: t('Xolati'),
      width: 120,
      render: (r) => (r.number > 0 ? <StatusChip status="active">{t('Faol')}</StatusChip> : <StatusChip status="failed">{t('Tugagan')}</StatusChip>),
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
        <div className="ob-clickable" onClick={openRow}>
          <DataTable rows={rows} columns={columns} getRowId={(r) => r.id} rowHeight={64} minWidth={760} caption={t('Omborxonadagi materiallar')} />
        </div>
        {pageCount > 1 && (
          <div className="ivs-pager">
            <Pagination pageCount={pageCount} page={page} onChange={setPage} />
          </div>
        )}
      </DataState>
      {active && <MaterialModal material={active} inCart={(cart.data ?? []).find((c) => c.material === active.id)} onClose={() => setActive(null)} />}
    </BarnPage>
  )
}

/** Material to'liq ma'lumoti; soni kiritilib savatga saqlanadi (savatda bo'lsa — soni yangilanadi). */
function MaterialModal({ material: m, inCart, onClose }: { material: SelectableMaterial; inCart: CartItem | undefined; onClose: () => void }) {
  const t = useT()
  const [number, setNumber] = useState(String(inCart?.number ?? 1))
  const [error, setError] = useState('')

  const save = useBarnMutation(
    (n: number) => api(`${SPA}/cart/add/`, { method: 'POST', body: JSON.stringify({ material: m.id, number: n }) }),
    () => t('«{name}» savatga saqlandi', { name: m.name }),
    onClose,
  )

  const submit = (e: FormEvent) => {
    e.preventDefault()
    const n = Number(number)
    if (!Number.isInteger(n) || n < 1) return setError(t("Soni kamida 1 bo'lishi kerak."))
    setError('')
    save.mutate(n)
  }

  const image = mediaPath(m.image)

  return (
    <Modal open onClose={onClose} icon="ri-archive-line" title="Material ma'lumotlari" subtitle={m.name} width={860}>
      <div className="ob-mat">
        <div className="ob-mat-media">
          {image ? <img src={image} alt={m.name} /> : <Icon name="ri-image-line" size={56} />}
        </div>

        <form className="ob-mat-info" onSubmit={submit} noValidate>
          <div className="ob-mat-head">
            {m.category_name && (
              <Badge tone="primary" size="sm" icon="ri-folder-3-line">
                {m.category_name}
              </Badge>
            )}
            <h3 className="type-h5">{m.name}</h3>
            {m.price && Number(m.price) > 0 && (
              <p className="ob-mat-price">
                {money(m.price)} <span>{t("so'm")}</span>
              </p>
            )}
          </div>

          <dl className="ob-mat-kv">
            <div>
              <dt>
                <Icon name="ri-archive-line" size={18} />
                {t('Omborda')}
              </dt>
              <dd>
                <Badge tone={m.number > 0 ? 'success' : 'error'} size="sm">
                  {formatNumber(m.number)} {m.unit_name || ''}
                </Badge>
              </dd>
            </div>
            {m.employee_name && (
              <div>
                <dt>
                  <Icon name="ri-user-3-line" size={18} />
                  {t('Moddiy javobgar')}
                </dt>
                <dd>{m.employee_name}</dd>
              </div>
            )}
            {m.code && (
              <div>
                <dt>
                  <Icon name="ri-barcode-line" size={18} />
                  {t('Kodi')}
                </dt>
                <dd className="ob-mono">{m.code}</dd>
              </div>
            )}
            {m.year && (
              <div>
                <dt>
                  <Icon name="ri-calendar-line" size={18} />
                  {t('Yili')}
                </dt>
                <dd>{m.year}</dd>
              </div>
            )}
          </dl>

          <div className="ob-mat-buy">
            <TextInput
              label={`${t('Soni *')}${m.unit_name ? ` (${m.unit_name})` : ''}`}
              type="number"
              inputMode="numeric"
              min={1}
              autoFocus
              value={number}
              onChange={(e) => setNumber(e.target.value)}
              error={!!error}
              hint={error || (inCart ? t('Savatda: {n}', { n: inCart.number }) : undefined)}
            />
            <Button size="xl" icon="ri-shopping-basket-2-line" type="submit" loading={save.isPending}>
              {t('Savatga saqlash')}
            </Button>
          </div>
        </form>
      </div>
    </Modal>
  )
}
