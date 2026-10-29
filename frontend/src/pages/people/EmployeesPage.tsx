import FilterBar from '../../components/FilterBar'
import { useState } from 'react'
import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Button, CellUser, DataTable, Pagination, Select, StatusChip } from '../../ds'
import type { DataTableColumn } from '../../ds'
import Page from '../../layout/Page'
import SearchInput from '../../components/SearchInput'
import DataState from '../../components/DataState'
import ConfirmDialog from '../../components/ConfirmDialog'
import { useToast } from '../../components/toast'
import { API, api, withQuery } from '../../api/client'
import type { Page as ApiPage } from '../../api/client'
import { can, useMe } from '../../auth/me'
import { useUrlFilters } from '../../lib/useUrlFilters'
import { avatarColor, formatNumber, initials } from '../../lib/format'
import { useT } from '../../i18n'
import { usePeopleRefs, useStructure } from './api'
import type { EmployeeRow } from './api'
import EmployeeForm from './EmployeeForm'
import EmployeePermissions from './EmployeePermissions'
import './people.css'

const PAGE_SIZE = 20
const FILTERS = ['organization', 'region', 'department', 'directorate', 'division', 'search'] as const

/** "Xodimlar" — templates/main/employee.html (main/views.py: employee, employee_create/update/delete/permission). */
export default function EmployeesPage() {
  const me = useMe()
  const t = useT()
  const toast = useToast()
  const qc = useQueryClient()
  const refs = usePeopleRefs()
  const { filters, page, hasFilters, setFilter, setPage } = useUrlFilters(FILTERS)
  // Departament faqat tashkilot VA hudud tanlangandan keyin chiqadi
  const structureReady = !!filters.organization && !!filters.region
  const structure = useStructure(filters.organization || null, filters.region || null, filters.department || null, filters.directorate || null)

  const [editing, setEditing] = useState<EmployeeRow | null | undefined>(undefined) // null — yangi xodim
  const [roles, setRoles] = useState<EmployeeRow | null>(null)
  const [removing, setRemoving] = useState<EmployeeRow | null>(null)

  const list = useQuery({
    queryKey: ['people', 'employees', filters, page],
    queryFn: () => api<ApiPage<EmployeeRow>>('/employees/', { query: { ...filters, page, page_size: PAGE_SIZE } }),
    placeholderData: keepPreviousData,
  })

  const remove = useMutation({
    mutationFn: (e: EmployeeRow) => api(`/employees/${e.id}/`, { method: 'DELETE' }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['people', 'employees'] })
      toast("Xodim o'chirildi (tizimga kira olmaydi; arizalari va hujjatlari saqlanadi)")
      setRemoving(null)
    },
    onError: (e) => {
      toast(e.message, 'error')
      setRemoving(null)
    },
  })

  const canAdd = can(me, 'main.add_employee')
  const canEdit = can(me, 'main.change_employee')
  const canDelete = can(me, 'main.delete_employee')
  const canRoles = can(me, 'main.permission_employee')

  // Yuqori daraja o'zgarsa pastdagilar tozalanadi (saytdagi filtr bilan bir xil)
  const setLevel = (key: (typeof FILTERS)[number], value: string | number | null) => {
    const order = ['organization', 'department', 'directorate', 'division'] as const
    setFilter(key, value)
    const start = key === 'region' ? 1 : order.indexOf(key as (typeof order)[number]) + 1
    if (start > 0) order.slice(start).forEach((k) => filters[k] && setFilter(k, null))
  }

  const rows = list.data?.results ?? []
  const total = list.data?.count
  const pageCount = Math.max(1, Math.ceil((total ?? 0) / PAGE_SIZE))

  const exportUrl = withQuery(`${API}/export/employees.xlsx`, {
    organization: filters.organization,
    region: filters.region,
    department: filters.department,
    directorate: filters.directorate,
    division: filters.division,
    name: filters.search,
  })

  // Qalin qism (son, ism) bilan jumla: tarjimadagi {n}/{name} o'rniga element qo'yiladi
  const countText = t('Xodimlar: {n} ta').split('{n}')
  const removeAsk = t("{name} xodimini o'chirmoqchimisiz?").split('{name}')

  const columns: DataTableColumn<EmployeeRow>[] = [
    { key: 'n', label: t('T/r'), width: 56, render: (r) => (page - 1) * PAGE_SIZE + rows.indexOf(r) + 1 },
    {
      key: 'full_name',
      label: t('F.I.O'),
      width: '28%',
      render: (r) => <CellUser name={r.full_name || '—'} sub={r.department_name || r.organization_name || undefined} initials={initials(r.full_name || '?')} color={avatarColor(r.id)} />,
    },
    { key: 'rank', label: t('Lavozimi'), width: '22%', render: (r) => <span className="ivs-people-wrap">{r.rank_name || ''}</span> },
    { key: 'pinfl', label: t('PINFL'), width: '14%', render: (r) => <span className="ivs-people-mono">{r.pinfl || ''}</span> },
    { key: 'phone', label: t('Telefon'), width: '14%', render: (r) => r.phone || '' },
    { key: 'status', label: t('Holati'), render: () => <StatusChip status="active">{t('Faol')}</StatusChip> },
    {
      key: 'actions',
      label: '',
      width: 132,
      align: 'right',
      render: (r) => (
        <div className="ivs-people-actions">
          {canRoles && <Button variant="ghost" size="sm" iconOnly icon="ri-shield-user-line" aria-label={t('Ruxsatlar')} title={t('Ruxsatlar')} onClick={() => setRoles(r)} />}
          {canEdit && <Button variant="ghost" size="sm" iconOnly icon="ri-pencil-line" aria-label={t('Tahrirlash')} title={t('Tahrirlash')} onClick={() => setEditing(r)} />}
          {canDelete && (
            <Button
              variant="ghost"
              size="sm"
              iconOnly
              icon="ri-delete-bin-line"
              aria-label={t("O'chirish")}
              title={t(r.id === me.employee?.id ? "O'zingizni o'chira olmaysiz" : "O'chirish")}
              disabled={r.id === me.employee?.id}
              onClick={() => setRemoving(r)}
            />
          )}
        </div>
      ),
    },
  ]

  return (
    <Page
      icon="ri-group-line"
      title="Xodimlar"
      subtitle="Tashkilot xodimlari, ularning lavozimi va tizimdagi ruxsatlari."
      actions={
        canAdd && (
          <Button size="lg" icon="ri-user-add-line" onClick={() => setEditing(null)}>
            {t("Xodim qo'shish")}
          </Button>
        )
      }
    >
      <FilterBar
        search={<SearchInput value={filters.search} onChange={(v) => setFilter('search', v)} placeholder="F.I.O yoki PINFL ..." />}
        summary={<>{countText[0]}<b>{total === undefined ? '—' : formatNumber(total)}</b>{countText[1]}</>}
        actions={
          <Button
            variant="stroke"
            icon="ri-file-excel-2-line"
            disabled={!filters.organization}
            onClick={() => window.location.assign(exportUrl)}
          >
            {t('Excel')}
          </Button>
        }
      >
        <Select placeholder={t('Tashkilot')} options={refs.organizationOptions} value={filters.organization ? Number(filters.organization) : null} onChange={(v) => setLevel('organization', v)} />
        <Select placeholder={t('Hududlar')} options={refs.regionOptions} value={filters.region ? Number(filters.region) : null} onChange={(v) => setLevel('region', v)} />
        <Select
          placeholder={t(structureReady ? 'Departament' : 'Avval tashkilot va hududni tanlang')}
          options={structureReady ? structure.departmentOptions : []}
          value={filters.department ? Number(filters.department) : null}
          onChange={(v) => setLevel('department', v)}
          disabled={!structureReady}
        />
        <Select placeholder={t('Boshqarma')} options={structure.directorateOptions} value={filters.directorate ? Number(filters.directorate) : null} onChange={(v) => setLevel('directorate', v)} disabled={!filters.department} />
        <Select placeholder={t("Bo'lim")} options={structure.divisionOptions} value={filters.division ? Number(filters.division) : null} onChange={(v) => setFilter('division', v)} disabled={!filters.directorate} />
      </FilterBar>

      <DataState
        isPending={list.isPending}
        isFetching={list.isFetching}
        error={list.error}
        empty={rows.length === 0}
        emptyText={hasFilters ? "Ma'lumot topilmadi." : "Hozircha xodim yo'q."}
      >
        <DataTable rows={rows} columns={columns} getRowId={(r) => r.id} rowHeight={64} minWidth={920} caption={t("Xodimlar ro'yxati")} />
        {pageCount > 1 && (
          <div className="ivs-pager">
            <Pagination pageCount={pageCount} page={page} onChange={setPage} />
          </div>
        )}
      </DataState>

      {editing !== undefined && <EmployeeForm item={editing} onClose={() => setEditing(undefined)} />}
      {roles && <EmployeePermissions employee={roles} onClose={() => setRoles(null)} />}
      {removing && (
        <ConfirmDialog
          danger
          title="O'chirishni tasdiqlang"
          confirmLabel="O'chirish"
          loading={remove.isPending}
          message={
            <>
              <p>
                {removeAsk[0]}
                <strong>{removing.full_name}</strong>
                {removeAsk[1]}
              </p>
              <p className="type-para-xs">
                {t(
                  "Xodim tizimga kira olmaydi va jadvaldan yo'qoladi; tashkilot, bo'lim, lavozim va hududi tozalanadi. Lekin xodim yozuvi bazadan o'chmaydi: uning arizalari, hujjatlari va materiallari saqlanadi.",
                )}
              </p>
            </>
          }
          onConfirm={() => remove.mutate(removing)}
          onClose={() => setRemoving(null)}
        />
      )}
    </Page>
  )
}
