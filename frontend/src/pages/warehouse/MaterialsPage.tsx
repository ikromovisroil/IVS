import FilterBar from '../../components/FilterBar'
import { useCallback, useState } from 'react'
import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Avatar, Button, DataTable, Pagination, Select } from '../../ds'
import type { DataTableColumn } from '../../ds'
import Page from '../../layout/Page'
import ConfirmDialog from '../../components/ConfirmDialog'
import DataState from '../../components/DataState'
import Modal from '../../components/Modal'
import SearchInput from '../../components/SearchInput'
import { useToast } from '../../components/toast'
import { API, api, withQuery } from '../../api/client'
import type { Page as ApiPage } from '../../api/client'
import { can, useMe } from '../../auth/me'
import { useT } from '../../i18n'
import { formatNumber } from '../../lib/format'
import { useUrlFilters } from '../../lib/useUrlFilters'
import ActionMenu from '../technics/ActionMenu'
import type { MenuAction } from '../technics/ActionMenu'
import { SPA } from '../technics/api'
import { errorText, money } from '../technics/util'
import type { Material } from './api'
import { useMaterialEmployees, useMaterialRefs } from './api'
import type { MaterialAction } from './MaterialDialogs'
import { MaterialActionDialog, MaterialSummary } from './MaterialDialogs'
import MaterialForm from './MaterialForm'
import MaterialTabs from './MaterialTabs'
import '../technics/technics.css'
import './warehouse.css'

const PAGE_SIZE = 20
const FILTER_KEYS = ['employee', 'category', 'unit', 'search'] as const

/** "Materiallar" (main/views.py:barn_mat) — moddiy javobgarlar bo'yicha ombordagi materiallar. */
export default function MaterialsPage() {
  const t = useT()
  const me = useMe()
  const refs = useMaterialRefs()
  const employees = useMaterialEmployees()
  const toast = useToast()
  const qc = useQueryClient()
  const { filters, page, hasFilters, setFilter, setPage } = useUrlFilters(FILTER_KEYS)
  const [formItem, setFormItem] = useState<Material | null | undefined>(undefined)
  const [active, setActive] = useState<{ row: Material; dialog: MaterialAction | 'delete' | 'image' } | null>(null)
  const [menu, setMenu] = useState<{ row: Material; anchor: HTMLElement } | null>(null)
  const closeMenu = useCallback(() => setMenu(null), [])
  const close = () => setActive(null)

  const list = useQuery({
    queryKey: ['warehouse', 'materials', filters, page],
    queryFn: () => api<ApiPage<Material>>('/materials/', { query: { ...filters, page, page_size: PAGE_SIZE } }),
    placeholderData: keepPreviousData,
  })
  const summary = useQuery({
    queryKey: ['warehouse', 'materials-summary', filters],
    queryFn: () => api<{ count: number; total_sum: string }>(`${SPA}/materials/summary/`, { query: filters }),
  })
  const remove = useMutation({
    mutationFn: (id: number) => api(`/materials/${id}/`, { method: 'DELETE' }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['warehouse'] })
      toast("Material muvaffaqiyatli o'chirildi")
      close()
    },
  })

  const rows = list.data?.results ?? []
  const pageCount = Math.max(1, Math.ceil((list.data?.count ?? 0) / PAGE_SIZE))
  const myId = me.employee?.id
  // Savatga faqat o'z materialini (all_material_employee) qo'yish mumkin (saytdagidek)
  const canBasket = (m: Material) => can(me, 'main.all_material_employee') && m.employee === myId

  const actionsFor = (m: Material): MenuAction[] => {
    const open = (dialog: MaterialAction | 'delete') => () => setActive({ row: m, dialog })
    const out: MenuAction[] = []
    if (canBasket(m)) out.push({ label: 'Savatga saqlash', icon: 'ri-shopping-basket-2-line', onClick: open('basket') })
    if (can(me, 'main.change_material')) {
      out.push({ label: 'Tahrirlash', icon: 'ri-pencil-line', onClick: () => setFormItem(m) })
      out.push({ label: 'Biriktirish#ombor', icon: 'ri-attachment-2', onClick: open('give') })
    }
    if (can(me, 'main.material_service')) out.push({ label: 'Sarflash', icon: 'ri-indeterminate-circle-line', onClick: open('service') })
    if (can(me, 'main.delete_material')) out.push({ label: "O'chirish", icon: 'ri-delete-bin-line', danger: true, onClick: open('delete') })
    return out
  }

  const columns: DataTableColumn<Material>[] = [
    { key: 'n', label: t('T/r'), width: '5%', render: (r) => (page - 1) * PAGE_SIZE + rows.indexOf(r) + 1 },
    {
      key: 'image',
      label: t('Rasm'),
      width: '7%',
      render: (r) =>
        r.image ? (
          <a
            href={r.image}
            className="ivs-thumb"
            aria-label={t('{name} rasmi', { name: r.name })}
            onClick={(e) => {
              e.preventDefault()
              setActive({ row: r, dialog: 'image' })
            }}
          >
            <Avatar src={r.image} name={r.name} size={40} />
          </a>
        ) : (
          <span className="ivs-noimg" title={t("Rasm yo'q")}>
            <i className="ri-image-line" aria-hidden />
            <span className="aui-sr">{t("Rasm yo'q")}</span>
          </span>
        ),
    },
    {
      key: 'name',
      label: t('Material nomi'),
      width: '25%',
      render: (r) => (
        <div className="aui-cell-text">
          <div className="aui-cell-primary">
            {canBasket(r) ? (
              <a
                href="#"
                className="ivs-link"
                title={t('Savatga saqlash')}
                onClick={(e) => {
                  e.preventDefault()
                  setActive({ row: r, dialog: 'basket' })
                }}
              >
                {r.name}
              </a>
            ) : (
              r.name
            )}
          </div>
          <div className="aui-cell-secondary">{[r.category_name, r.employee_name].filter(Boolean).join(' · ') || '—'}</div>
        </div>
      ),
    },
    { key: 'price', label: t('Narxi'), width: '11%', align: 'right', render: (r) => money(r.price) },
    { key: 'sum', label: t('Umumiy narxi'), width: '13%', align: 'right', render: (r) => <b>{money(Number(r.price ?? 0) * r.number)}</b> },
    { key: 'number', label: t('Soni'), width: '8%', align: 'right', render: (r) => formatNumber(r.number) },
    { key: 'unit', label: t('Birligi'), width: '9%', render: (r) => r.unit_name || '—' },
    { key: 'code', label: t('Kodi'), render: (r) => <span className="ivs-mono">{r.code || '—'}</span> },
  ]

  const n = (k: (typeof FILTER_KEYS)[number]) => (filters[k] ? Number(filters[k]) : null)

  return (
    <Page
      icon="ri-archive-line"
      title="Materiallar"
      subtitle="Moddiy javobgar xodimlardagi materiallar, ularni berish, sarflash va savat."
      actions={
        can(me, 'main.add_material') && (
          <Button size="lg" icon="ri-add-line" onClick={() => setFormItem(null)}>
            {t("Material qo'shish")}
          </Button>
        )
      }
    >
      <MaterialTabs />

      <div className="aui-stats">
        <div>
          <div className="ivs-stat-label">{t('Materiallar')}</div>
          <div className="ivs-stat-value">
            {summary.data ? formatNumber(summary.data.count) : '—'}
            <small>{t('ta')}</small>
          </div>
        </div>
        <div>
          <div className="ivs-stat-label">{t('Umumiy narxi')}</div>
          <div className="ivs-stat-value">
            {summary.data ? money(summary.data.total_sum) : '—'}
            <small>{t("so'm")}</small>
          </div>
        </div>
      </div>

      <FilterBar
        search={<SearchInput value={filters.search} onChange={(v) => setFilter('search', v)} placeholder="Nomi, 1C kodi..." />}
        actions={
          <Button variant="stroke" icon="ri-file-excel-2-line" onClick={() => window.location.assign(withQuery(`${API}/export/materials.xlsx`, filters))}>
            {t('Excel')}
          </Button>
        }
      >
        <Select placeholder={t('Xodim')} options={employees.options} value={n('employee')} onChange={(v) => setFilter('employee', v)} />
        <Select placeholder={t('Kategoriya')} options={refs.categoryOptions} value={n('category')} onChange={(v) => setFilter('category', v)} />
        <Select placeholder={t('Birligi')} options={refs.unitOptions} value={n('unit')} onChange={(v) => setFilter('unit', v)} />
      </FilterBar>

      <DataState
        isPending={list.isPending}
        isFetching={list.isFetching}
        error={list.error}
        empty={rows.length === 0}
        emptyText={hasFilters ? 'Filtrga mos material topilmadi.' : "Ko'rish mumkin bo'lgan material yo'q."}
      >
        <DataTable
          rows={rows}
          columns={columns}
          getRowId={(r) => r.id}
          rowHeight={60}
          minWidth={940}
          rowActions={(r, e) => setMenu({ row: r, anchor: e.currentTarget as HTMLElement })}
          caption={t("Materiallar ro'yxati")}
        />
        {pageCount > 1 && (
          <div className="ivs-pager">
            <Pagination pageCount={pageCount} page={page} onChange={setPage} />
          </div>
        )}
      </DataState>

      {menu &&
        (() => {
          const actions = actionsFor(menu.row)
          return actions.length ? <ActionMenu anchor={menu.anchor} actions={actions} onClose={closeMenu} /> : null
        })()}
      {active && (active.dialog === 'give' || active.dialog === 'service' || active.dialog === 'basket') && (
        <MaterialActionDialog m={active.row} action={active.dialog} onClose={close} />
      )}
      {active?.dialog === 'image' && active.row.image && (
        <Modal
          open
          onClose={close}
          icon="ri-image-line"
          title="Rasm"
          subtitle={active.row.name}
          width={720}
          footer={
            <Button size="lg" onClick={close}>
              {t('Yopish')}
            </Button>
          }
        >
          <img className="ivs-preview" src={active.row.image} alt={active.row.name} />
        </Modal>
      )}
      {active?.dialog === 'delete' && (
        <ConfirmDialog
          title="Materialni o'chirish"
          danger
          confirmLabel="O'chirish"
          loading={remove.isPending}
          message={
            <>
              <MaterialSummary m={active.row} />
              <p>{t(`Materialni o'chirasizmi? Kirim-chiqim jurnaliga "O'chirildi" yozuvi qo'shiladi.`)}</p>
              {remove.error && <p className="ivs-form-error">{errorText(remove.error)}</p>}
            </>
          }
          onConfirm={() => remove.mutate(active.row.id)}
          onClose={close}
        />
      )}
      {formItem !== undefined && <MaterialForm item={formItem} onClose={() => setFormItem(undefined)} />}
    </Page>
  )
}
