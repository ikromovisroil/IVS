import FilterBar from '../../components/FilterBar'
import EmptyState from '../../components/EmptyState'
import { useCallback, useState } from 'react'
import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { Button, DataTable, Pagination, Select } from '../../ds'
import type { DataTableColumn } from '../../ds'
import Page from '../../layout/Page'
import ConfirmDialog from '../../components/ConfirmDialog'
import DataState from '../../components/DataState'
import Modal from '../../components/Modal'
import SearchInput from '../../components/SearchInput'
import { useToast } from '../../components/toast'
import { api } from '../../api/client'
import type { Page as ApiPage } from '../../api/client'
import { can, useMe } from '../../auth/me'
import { useT } from '../../i18n'
import { formatNumber } from '../../lib/format'
import { useUrlFilters } from '../../lib/useUrlFilters'
import ActionMenu from '../technics/ActionMenu'
import type { MenuAction } from '../technics/ActionMenu'
import { SPA, toOptions, useRegions } from '../technics/api'
import { useTechnicsRefs } from '../technics/refs'
import { useStatusOptions } from '../technics/status'
import { Kv, StatusTag } from '../technics/TechnicsDetail'
import { errorText, money } from '../technics/util'
import type { Structure } from './api'
import { useStructureCategories } from './api'
import StructureForm from './StructureForm'
import '../technics/technics.css'
import './warehouse.css'

const PAGE_SIZE = 20
const FILTER_KEYS = ['search', 'organization', 'region', 'status', 'category'] as const

/** "Qurilma tafsiloti" (extra_tex dagi oyna) */
function StructureDetail({ s }: { s: Structure }) {
  const t = useT()
  return (
    <div className="ivs-detail">
      <section className="ivs-detail-section">
        <h3 className="type-label-md">
          <i className="ri-information-line" aria-hidden /> {t("Umumiy ma'lumot")}
        </h3>
        <dl className="ivs-kvs">
          <Kv label="Xodim">{s.technics_employee_name || '—'}</Kv>
          <Kv label="Texnika">
            {s.technics ? (
              <Link to={`/technics/${s.technics}`} className="ivs-link">
                {[s.technics_name, s.technics_serial || '—', s.technics_inventory || '—'].join(' / ')}
              </Link>
            ) : (
              '—'
            )}
          </Kv>
          <Kv label="Tashkilot">{s.organization_name || '—'}</Kv>
          <Kv label="Nomi">{[s.category_name, s.name].filter(Boolean).join(' ') || '—'}</Kv>
          {s.parametr && <Kv label="Parametr">{s.parametr}</Kv>}
          {s.inventory && <Kv label="Inventar">{s.inventory}</Kv>}
          {s.serial && <Kv label="Serial">{s.serial}</Kv>}
          {s.year && <Kv label="Yili">{s.year}</Kv>}
          {Number(s.price) > 0 && <Kv label="Narxi">{t("{sum} so'm", { sum: money(s.price) })}</Kv>}
          <Kv label="Holati">
            <StatusTag status={s.status} label={s.status_display} />
          </Kv>
          <Kv label="Hududi">{s.region_name || '—'}</Kv>
        </dl>
      </section>
    </div>
  )
}

/** "Qo'shimcha qurilmalar" (main/views.py:extra_tex) — monitor, klaviatura, UPS va h.k. */
export default function ExtraDevicesPage() {
  const t = useT()
  const statusOptions = useStatusOptions()
  const me = useMe()
  const refs = useTechnicsRefs()
  const regions = useRegions()
  const categories = useStructureCategories()
  const toast = useToast()
  const qc = useQueryClient()
  const { filters, page, hasFilters, setFilter, setPage } = useUrlFilters(FILTER_KEYS)
  const [formItem, setFormItem] = useState<Structure | null | undefined>(undefined)
  const [active, setActive] = useState<{ row: Structure; dialog: 'detail' | 'delete' } | null>(null)
  const [menu, setMenu] = useState<{ row: Structure; anchor: HTMLElement } | null>(null)
  const closeMenu = useCallback(() => setMenu(null), [])

  // Saytda sahifa 'change_technics' bilan ochiladi (StructurePermission ham shunday)
  const allowed = can(me, 'main.change_technics')
  const list = useQuery({
    queryKey: ['warehouse', 'structures', filters, page],
    queryFn: () => api<ApiPage<Structure>>(`${SPA}/structures/`, { query: { ...filters, page, page_size: PAGE_SIZE } }),
    placeholderData: keepPreviousData,
    enabled: allowed,
  })
  const remove = useMutation({
    mutationFn: (id: number) => api(`/structures/${id}/`, { method: 'DELETE' }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['warehouse'] })
      qc.invalidateQueries({ queryKey: ['technics'] })
      toast("Qurilma muvaffaqiyatli o'chirildi")
      setActive(null)
    },
  })

  const rows = list.data?.results ?? []
  const pageCount = Math.max(1, Math.ceil((list.data?.count ?? 0) / PAGE_SIZE))
  const n = (k: (typeof FILTER_KEYS)[number]) => (filters[k] ? Number(filters[k]) : null)

  const actionsFor = (r: Structure): MenuAction[] => {
    const out: MenuAction[] = [{ label: 'Tafsilot', icon: 'ri-information-line', onClick: () => setActive({ row: r, dialog: 'detail' }) }]
    if (can(me, 'main.change_technics')) out.push({ label: 'Tahrirlash', icon: 'ri-pencil-line', onClick: () => setFormItem(r) })
    if (can(me, 'main.delete_technics')) out.push({ label: "O'chirish", icon: 'ri-delete-bin-line', danger: true, onClick: () => setActive({ row: r, dialog: 'delete' }) })
    return out
  }

  const columns: DataTableColumn<Structure>[] = [
    { key: 'n', label: t('T/r'), width: '6%', render: (r) => (page - 1) * PAGE_SIZE + rows.indexOf(r) + 1 },
    {
      key: 'name',
      label: t('Nomi'),
      width: '26%',
      render: (r) => (
        <div className="aui-cell-text">
          <div className="aui-cell-primary">
            <a
              href="#"
              className="ivs-link"
              onClick={(e) => {
                e.preventDefault()
                setActive({ row: r, dialog: 'detail' })
              }}
            >
              {r.name}
            </a>
          </div>
          <div className="aui-cell-secondary">{[r.category_name, r.parametr].filter(Boolean).join(' · ') || '—'}</div>
        </div>
      ),
    },
    { key: 'inventory', label: t('I/N'), width: '13%', render: (r) => <span className="ivs-mono">{r.inventory || '—'}</span> },
    { key: 'serial', label: t('S/N'), width: '13%', render: (r) => <span className="ivs-mono">{r.serial || '—'}</span> },
    { key: 'year', label: t('Yili'), width: '7%', render: (r) => r.year || '—' },
    {
      key: 'technics',
      label: t('Texnika'),
      width: '20%',
      render: (r) =>
        r.technics ? (
          <div className="aui-cell-text">
            <div className="aui-cell-primary">{r.technics_name}</div>
            <div className="aui-cell-secondary">{r.technics_employee_name || t('Biriktirilmagan#ombor')}</div>
          </div>
        ) : (
          <span className="ivs-muted">—</span>
        ),
    },
    { key: 'status', label: t('Holati'), render: (r) => <StatusTag status={r.status} label={r.status_display} /> },
  ]

  return (
    <Page
      icon="ri-usb-line"
      title="Qo'shimcha qurilmalar"
      subtitle="Uskunalarga biriktiriladigan monitor, klaviatura, UPS va boshqa qurilmalar."
      actions={
        allowed &&
        can(me, 'main.add_technics') && (
          <Button size="lg" icon="ri-add-line" onClick={() => setFormItem(null)}>
            {t("Qurilma qo'shish")}
          </Button>
        )
      }
    >
      {!allowed ? (
        <EmptyState icon="ri-lock-line" title="Ruxsat yo'q" description="Bu sahifa uchun ruxsatingiz yo'q (texnikani tahrirlash huquqi kerak)." />
      ) : (
        <>
          <FilterBar
            search={<SearchInput value={filters.search} onChange={(v) => setFilter('search', v)} placeholder="Nomi, I/N, S/N, yili..." />}
            summary={
              <span className="type-para-sm">
                {t('Qurilmalar: {n} ta', { n: list.data ? formatNumber(list.data.count) : '—' })}
              </span>
            }
          >
            <Select placeholder={t('Tashkilot')} options={refs.organizationOptions} value={n('organization')} onChange={(v) => setFilter('organization', v)} />
            <Select placeholder={t('Hudud')} options={toOptions(regions.data)} value={n('region')} onChange={(v) => setFilter('region', v)} />
            <Select placeholder={t('Holati')} options={statusOptions} searchable={false} value={filters.status || null} onChange={(v) => setFilter('status', v)} />
            <Select placeholder={t('Kategoriya')} options={categories} value={n('category')} onChange={(v) => setFilter('category', v)} />
          </FilterBar>

          <DataState
            isPending={list.isPending}
            isFetching={list.isFetching}
            error={list.error}
            empty={rows.length === 0}
            emptyText={hasFilters ? 'Filtrga mos qurilma topilmadi.' : "Hozircha qurilma yo'q."}
          >
            <DataTable
              rows={rows}
              columns={columns}
              getRowId={(r) => r.id}
              rowHeight={60}
              minWidth={920}
              rowActions={(r, e) => setMenu({ row: r, anchor: e.currentTarget as HTMLElement })}
              caption={t("Qo'shimcha qurilmalar ro'yxati")}
            />
            {pageCount > 1 && (
              <div className="ivs-pager">
                <Pagination pageCount={pageCount} page={page} onChange={setPage} />
              </div>
            )}
          </DataState>
        </>
      )}

      {menu && <ActionMenu anchor={menu.anchor} actions={actionsFor(menu.row)} onClose={closeMenu} />}
      {active?.dialog === 'detail' && (
        <Modal
          open
          onClose={() => setActive(null)}
          icon="ri-cpu-line"
          title="Qurilma tafsiloti"
          subtitle={active.row.name}
          width={640}
          footer={
            <>
              {can(me, 'main.change_technics') && (
                <Button variant="stroke" size="lg" icon="ri-pencil-line" onClick={() => setFormItem(active.row)}>
                  {t('Tahrirlash')}
                </Button>
              )}
              <Button size="lg" onClick={() => setActive(null)}>
                {t('Yopish')}
              </Button>
            </>
          }
        >
          <StructureDetail s={active.row} />
        </Modal>
      )}
      {active?.dialog === 'delete' && (
        <ConfirmDialog
          title="Qurilmani o'chirish"
          danger
          confirmLabel="O'chirish"
          loading={remove.isPending}
          message={
            <>
              <b>{active.row.name}</b>
              {[active.row.parametr, active.row.inventory && t('I/N: {v}', { v: active.row.inventory }), active.row.serial && t('S/N: {v}', { v: active.row.serial })]
                .filter(Boolean)
                .map((x) => (
                  <div key={x as string}>{x}</div>
                ))}
              <p>{t("Qurilmani o'chirasizmi? Texnikaga biriktirilgan bo'lsa, ajratiladi.")}</p>
              {remove.error && <p className="ivs-form-error">{errorText(remove.error)}</p>}
            </>
          }
          onConfirm={() => remove.mutate(active.row.id)}
          onClose={() => setActive(null)}
        />
      )}
      {formItem !== undefined && (
        <StructureForm
          item={formItem}
          onClose={() => {
            setFormItem(undefined)
            setActive(null)
          }}
        />
      )}
    </Page>
  )
}
