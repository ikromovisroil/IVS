import FilterBar from '../../components/FilterBar'
import { useCallback, useMemo, useState } from 'react'
import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { Badge, Button, CellUser, DataTable, Pagination, Select } from '../../ds'
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
import { avatarColor, initials } from '../../lib/format'
import { useUrlFilters } from '../../lib/useUrlFilters'
import ActionMenu from './ActionMenu'
import type { MenuAction } from './ActionMenu'
import type { TechnicsRow, TechnicsStats } from './api'
import { SPA, toOptions, useOrgTree, useRegions } from './api'
import { AssignDialog, AttachDeviceDialog, DetachDeviceDialog } from './TechnicsDialogs'
import { errorText } from './util'
import TechnicsDetail, { StatusTag } from './TechnicsDetail'
import TechnicsForm from './TechnicsForm'
import TechnicsTabs from './TechnicsTabs'
import { useTechnicsRefs } from './refs'
import { useStatusOptions } from './status'
import StatsStrip from './StatsStrip'
import './technics.css'

const PAGE_SIZE = 20
const FILTER_KEYS = ['search', 'group', 'category', 'status', 'organization', 'region', 'department', 'directorate', 'division'] as const

type Dialog = 'detail' | 'edit' | 'assign' | 'attach' | 'detach' | 'delete'

/** Har bir uskunaning qo'shimcha qurilmalari ustun ichida alohida qatorlarda (eski jadvaldagidek). */
function DeviceLines({ r, field }: { r: TechnicsRow; field: 'name' | 'inventory' | 'serial' }) {
  if (!r.extra_devices.length) return null
  return (
    <div className="ivs-device-lines">
      {r.extra_devices.map((d) => (
        <div key={d.id}>{field === 'name' ? `${d.category_name ?? ''}${d.category_name ? ' / ' : ''}${d.name}` : d[field] || '—'}</div>
      ))}
    </div>
  )
}

export default function TechnicsPage() {
  const t = useT()
  const statusOptions = useStatusOptions()
  const me = useMe()
  const refs = useTechnicsRefs()
  const regions = useRegions()
  const navigate = useNavigate()
  const toast = useToast()
  const qc = useQueryClient()
  const { filters, page, hasFilters, setFilter, setPage } = useUrlFilters(FILTER_KEYS)
  const [, setParams] = useSearchParams()
  // Bir nechta filtrni bir vaqtda o'zgartirish (yuqori daraja tanlansa, quyi darajalar tozalanadi)
  const setFilters = (patch: Partial<Record<(typeof FILTER_KEYS)[number], string | number | null>>) =>
    setParams(
      (p) => {
        for (const [k, v] of Object.entries(patch)) {
          if (v == null || v === '') p.delete(k)
          else p.set(k, String(v))
        }
        p.delete('page')
        return p
      },
      { replace: true },
    )
  const n = (k: (typeof FILTER_KEYS)[number]) => (filters[k] ? Number(filters[k]) : null)
  const tree = useOrgTree({ organization: n('organization'), region: n('region'), department: n('department'), directorate: n('directorate') })

  const [formItem, setFormItem] = useState<TechnicsRow | null | undefined>(undefined) // undefined — forma yopiq
  const [active, setActive] = useState<{ row: TechnicsRow; dialog: Dialog } | null>(null)
  const [menu, setMenu] = useState<{ row: TechnicsRow; anchor: HTMLElement } | null>(null)

  // Biriktirish/tahrirlashdan keyin oyna yangi ma'lumot bilan qolishi uchun qator ro'yxatdan qayta olinadi
  const list = useQuery({
    queryKey: ['technics', 'list', filters, page],
    queryFn: () => api<ApiPage<TechnicsRow>>(`${SPA}/technics/`, { query: { ...filters, page, page_size: PAGE_SIZE } }),
    placeholderData: keepPreviousData,
  })
  const stats = useQuery({
    queryKey: ['technics', 'stats', filters],
    queryFn: () => api<TechnicsStats>(`${SPA}/technics/stats/`, { query: filters }),
  })

  const canAdd = can(me, 'main.add_technics')
  const canEdit = can(me, 'main.change_technics')
  const canDelete = can(me, 'main.delete_technics')
  const rows = useMemo(() => list.data?.results ?? [], [list.data])
  const pageCount = Math.max(1, Math.ceil((list.data?.count ?? 0) / PAGE_SIZE))
  const current = active ? (rows.find((r) => r.id === active.row.id) ?? active.row) : null
  const close = useCallback(() => setActive(null), [])
  const closeMenu = useCallback(() => setMenu(null), [])

  const remove = useMutation({
    mutationFn: (id: number) => api(`/technics/${id}/`, { method: 'DELETE' }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['technics'] })
      qc.invalidateQueries({ queryKey: ['warehouse'] })
      toast("Uskuna muvaffaqiyatli o'chirildi")
      setActive(null)
    },
  })

  // Eski jadval: xodim bo'yicha guruhlanadi, T/r va F.I.O guruhning birinchi qatorida
  const groups = useMemo(() => {
    const first = new Map<number, number>()
    let g = 0
    rows.forEach((r, i) => {
      if (i === 0 || (rows[i - 1].employee ?? 0) !== (r.employee ?? 0)) first.set(r.id, ++g)
    })
    return first
  }, [rows])

  const actionsFor = (r: TechnicsRow): MenuAction[] => {
    const open = (dialog: Dialog) => () => setActive({ row: r, dialog })
    const out: MenuAction[] = [{ label: 'Tafsilot', icon: 'ri-information-line', onClick: open('detail') }]
    if (canEdit) {
      out.push(
        { label: 'Tahrirlash', icon: 'ri-pencil-line', onClick: () => setFormItem(r) },
        { label: 'Biriktirish#ombor', icon: 'ri-attachment-2', onClick: open('assign') },
        { label: 'Qurilmani biriktirish', icon: 'ri-pushpin-line', onClick: open('attach') },
      )
      if (r.extra_devices.length) out.push({ label: 'Qurilmani bekor qilish', icon: 'ri-close-circle-line', onClick: open('detach') })
    }
    out.push({ label: 'Alohida sahifada', icon: 'ri-external-link-line', onClick: () => navigate(`/technics/${r.id}`) })
    if (canDelete) out.push({ label: "O'chirish", icon: 'ri-delete-bin-line', danger: true, onClick: open('delete') })
    return out
  }

  const columns: DataTableColumn<TechnicsRow>[] = [
    { key: 'n', label: t('T/r'), width: '5%', render: (r) => (groups.has(r.id) ? (page - 1) * PAGE_SIZE + (groups.get(r.id) ?? 0) : '') },
    {
      key: 'employee_name',
      label: t('F.I.O'),
      width: '21%',
      render: (r) =>
        !groups.has(r.id) ? null : r.employee_name ? (
          <CellUser name={r.employee_name} sub={r.employee_rank ? `"${r.employee_rank}"` : r.department_name || undefined} initials={initials(r.employee_name)} color={avatarColor(r.employee ?? 0)} />
        ) : (
          <CellUser name={t('Biriktirilmagan#ombor')} sub={r.department_name || r.directorate_name || r.division_name || t('Omborxonada')} initials="—" color="gray" />
        ),
    },
    {
      key: 'name',
      label: t('Texnika nomi'),
      width: '25%',
      render: (r) => (
        <div className="aui-cell-text">
          <div className="aui-cell-primary">
            <Link
              to={`/technics/${r.id}`}
              className="ivs-link"
              onClick={(e) => {
                if (e.metaKey || e.ctrlKey || e.shiftKey) return
                e.preventDefault()
                setActive({ row: r, dialog: 'detail' })
              }}
            >
              {r.name}
            </Link>
            {r.is_online && (
              <Badge tone="sky" size="sm" icon="ri-router-line" className="ivs-inline-badge">
                {t('tarmoq')}
              </Badge>
            )}
          </div>
          <div className="aui-cell-secondary">{r.parametr || r.category_name}</div>
          <DeviceLines r={r} field="name" />
        </div>
      ),
    },
    {
      key: 'inventory',
      label: t('I/R'),
      width: '12%',
      render: (r) => (
        <div className="ivs-mono">
          {r.inventory || '—'}
          <DeviceLines r={r} field="inventory" />
        </div>
      ),
    },
    {
      key: 'serial',
      label: t('S/R'),
      width: '13%',
      render: (r) => (
        <div className="ivs-mono">
          {r.serial || '—'}
          <DeviceLines r={r} field="serial" />
        </div>
      ),
    },
    { key: 'address', label: t('Joylashuvi'), width: '12%', render: (r) => <span className="type-para-xs">{r.address || '—'}</span> },
    { key: 'status', label: t('Holati'), render: (r) => <StatusTag status={r.status} label={r.status_display} /> },
  ]

  // /api/v1/export/technics.xlsx — ro'yxat bilan bir xil doira va filtrlar (qidiruv u yerda F.I.O bo'yicha emas)
  const exportUrl = withQuery(`${API}/export/technics.xlsx`, filters)

  // Departament faqat tashkilot VA hudud tanlangandan keyin chiqadi
  const structureReady = !!n('organization') && !!n('region')
  const selectFilter = (key: (typeof FILTER_KEYS)[number], reset: (typeof FILTER_KEYS)[number][] = []) => (v: string | number | null) =>
    setFilters({ [key]: v, ...Object.fromEntries(reset.map((k) => [k, null])) })

  return (
    <Page
      icon="ri-computer-line"
      title="Texnika va uskunalar"
      subtitle="Tashkilotlardagi barcha uskunalar ro'yxati va holati."
      actions={
        canAdd && (
          <Button size="lg" icon="ri-add-line" onClick={() => setFormItem(null)}>
            {t("Uskuna qo'shish")}
          </Button>
        )
      }
    >
      <TechnicsTabs />

      <StatsStrip stats={stats.data} totalLabel="Jami uskunalar" />

      <FilterBar
        search={<SearchInput value={filters.search} onChange={(v) => setFilter('search', v)} placeholder="F.I.O, nomi, I/R, S/R, MAC, IP..." />}
        activeCount={FILTER_KEYS.filter((k) => filters[k]).length}
        onReset={() => setFilters(Object.fromEntries(FILTER_KEYS.map((k) => [k, null])))}
        actions={
          <Button variant="stroke" icon="ri-file-excel-2-line" onClick={() => window.location.assign(exportUrl)}>
            {t('Excel')}
          </Button>
        }
      >
        <Select placeholder={t('Turi')} options={refs.groupOptions} value={n('group')} onChange={selectFilter('group', ['category'])} />
        <Select placeholder={t('Kategoriya')} options={refs.categoryOptions(n('group'))} value={n('category')} onChange={selectFilter('category')} />
        <Select placeholder={t('Holati')} options={statusOptions} searchable={false} value={filters.status || null} onChange={selectFilter('status')} />
        <Select placeholder={t('Tashkilot')} options={refs.organizationOptions} value={n('organization')} onChange={selectFilter('organization', ['department', 'directorate', 'division'])} />
        <Select placeholder={t('Hudud')} options={toOptions(regions.data)} value={n('region')} onChange={selectFilter('region', ['department', 'directorate', 'division'])} />
        <Select
          placeholder={t(structureReady ? 'Departament' : 'Avval tashkilot va hududni tanlang')}
          options={structureReady ? tree.departments : []}
          value={n('department')}
          disabled={!structureReady}
          onChange={selectFilter('department', ['directorate', 'division'])}
        />
        <Select placeholder={t('Boshqarma')} options={tree.directorates} value={n('directorate')} disabled={!n('department')} onChange={selectFilter('directorate', ['division'])} />
        <Select placeholder={t("Bo'lim")} options={tree.divisions} value={n('division')} disabled={!n('directorate')} onChange={selectFilter('division')} />
      </FilterBar>

      <DataState
        isPending={list.isPending}
        isFetching={list.isFetching}
        error={list.error}
        empty={rows.length === 0}
        emptyText={hasFilters ? 'Filtrga mos uskuna topilmadi.' : "Hozircha uskuna yo'q."}
      >
        <DataTable
          rows={rows}
          columns={columns}
          getRowId={(r) => r.id}
          rowHeight={64}
          minWidth={1040}
          rowActions={(r, e) => setMenu({ row: r, anchor: e.currentTarget as HTMLElement })}
          caption={t("Texnika va uskunalar ro'yxati")}
        />
        {pageCount > 1 && (
          <div className="ivs-pager">
            <Pagination pageCount={pageCount} page={page} onChange={setPage} />
          </div>
        )}
      </DataState>

      {menu && <ActionMenu anchor={menu.anchor} actions={actionsFor(menu.row)} onClose={closeMenu} />}

      {current && active?.dialog === 'detail' && (
        <Modal
          open
          onClose={close}
          icon="ri-cpu-line"
          title="Texnika tafsiloti"
          subtitle={current.name}
          footer={
            <>
              {canEdit && (
                <>
                  <Button variant="stroke" size="lg" icon="ri-attachment-2" onClick={() => setActive({ row: current, dialog: 'assign' })}>
                    {t('Biriktirish#ombor')}
                  </Button>
                  <Button variant="stroke" size="lg" icon="ri-pencil-line" onClick={() => setFormItem(current)}>
                    {t('Tahrirlash')}
                  </Button>
                </>
              )}
              <Button size="lg" onClick={close}>
                {t('Yopish')}
              </Button>
            </>
          }
        >
          <TechnicsDetail t={current} />
        </Modal>
      )}
      {current && active?.dialog === 'assign' && <AssignDialog t={current} onClose={close} />}
      {current && active?.dialog === 'attach' && <AttachDeviceDialog t={current} me={me} onClose={close} />}
      {current && active?.dialog === 'detach' && <DetachDeviceDialog t={current} onClose={close} />}
      {current && active?.dialog === 'delete' && (
        <ConfirmDialog
          title="Texnikani o'chirish"
          danger
          confirmLabel="O'chirish"
          loading={remove.isPending}
          message={
            <>
              <b>{current.name}</b>
              {[current.parametr, current.inventory && t('I/R: {v}', { v: current.inventory }), current.serial && t('S/R: {v}', { v: current.serial })].filter(Boolean).map((x) => (
                <div key={x as string}>{x}</div>
              ))}
              <p>{t("Texnika o'chirilsinmi? Xodimga biriktirilgan bo'lsa, bo'shatiladi.")}</p>
              {remove.error && <p className="ivs-form-error">{errorText(remove.error)}</p>}
            </>
          }
          onConfirm={() => remove.mutate(current.id)}
          onClose={close}
        />
      )}
      {formItem !== undefined && (
        <TechnicsForm
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
