import { useState } from 'react'
import EmptyState from '../../components/EmptyState'
import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Button, DataTable, Pagination, Select, Textarea } from '../../ds'
import type { DataTableColumn } from '../../ds'
import Page from '../../layout/Page'
import ConfirmDialog from '../../components/ConfirmDialog'
import DataState from '../../components/DataState'
import Modal from '../../components/Modal'
import { useToast } from '../../components/toast'
import { ApiError, api } from '../../api/client'
import { can, useMe } from '../../auth/me'
import { useLang, useT } from '../../i18n'
import { formatNumber } from '../../lib/format'
import { useUrlFilters } from '../../lib/useUrlFilters'
import type { BridgeResult } from '../technics/api'
import { SPA } from '../technics/api'
import { FormError } from '../technics/TechnicsDialogs'
import { errorText, money } from '../technics/util'
import type { BasketRow } from './api'
import { MOVEMENT_STATUS, useReportEmployees } from './api'
import MaterialTabs from './MaterialTabs'
import '../technics/technics.css'
import './warehouse.css'

const PAGE_SIZE = 20

/** Biriktirishda ba'zi materiallar o'tmay qolishi mumkin — serverning barcha xabarlari ko'rsatiladi. */
function warnings(e: unknown): string[] {
  if (e instanceof ApiError && e.data && typeof e.data === 'object' && 'messages' in e.data) {
    return (e.data as BridgeResult).messages.map((m) => m.text)
  }
  return []
}

function AssignDialog({ onClose }: { onClose: () => void }) {
  const t = useT()
  const employees = useReportEmployees()
  const [employee, setEmployee] = useState<number | null>(null)
  const [body, setBody] = useState('')
  const qc = useQueryClient()
  const toast = useToast()
  const [notes, setNotes] = useState<string[]>([])
  const save = useMutation({
    mutationFn: () => api<BridgeResult>(`${SPA}/materials/basket/assign/`, { method: 'POST', body: JSON.stringify({ employee, body }) }),
    onSuccess: (r) => {
      qc.invalidateQueries({ queryKey: ['warehouse'] })
      const errors = r.messages.filter((m) => m.level !== 'success').map((m) => m.text)
      toast(r.detail)
      if (errors.length) setNotes(errors)
      else onClose()
    },
  })
  const list = notes.length ? notes : warnings(save.error)

  return (
    <Modal
      open
      onClose={onClose}
      icon="ri-user-shared-line"
      title="Xodimga biriktirish"
      subtitle="Savatdagi barcha materiallar tanlangan xodimga beriladi."
      width={520}
      footer={
        <>
          <Button variant="stroke" size="lg" onClick={onClose}>
            {t('Bekor qilish')}
          </Button>
          <Button size="lg" icon="ri-send-plane-fill" type="submit" form="basket-assign" disabled={!employee} loading={save.isPending}>
            {t('Yuborish')}
          </Button>
        </>
      }
    >
      <form
        id="basket-assign"
        className="ivs-stack"
        onSubmit={(e) => {
          e.preventDefault()
          if (employee) save.mutate()
        }}
      >
        {list.length ? (
          <ul className="ivs-notes" role="alert">
            {list.map((x) => (
              <li key={x}>{x}</li>
            ))}
          </ul>
        ) : (
          <FormError error={save.error} />
        )}
        <Select label={t('Xodimni tanlang *')} placeholder={t('Tanlang...')} options={employees.options} value={employee} onChange={(v) => setEmployee(v == null ? null : Number(v))} />
        <Textarea label={t("Qo'shimcha ma'lumot")} rows={4} placeholder="..." value={body} onChange={(e) => setBody(e.target.value)} />
      </form>
    </Modal>
  )
}

/** "Savat" (main/views.py:mat_arxiv) — berish uchun yig'ilgan materiallar. */
export default function BasketPage() {
  const t = useT()
  const { lang } = useLang()
  const me = useMe()
  const toast = useToast()
  const qc = useQueryClient()
  const { page, setPage } = useUrlFilters([])
  const [assign, setAssign] = useState(false)
  const [removing, setRemoving] = useState<BasketRow | null>(null)
  const allowed = can(me, 'main.all_material_employee')

  const list = useQuery({
    queryKey: ['warehouse', 'basket', page],
    queryFn: () => api<{ count: number; results: BasketRow[] }>(`${SPA}/materials/basket/`, { query: { page } }),
    placeholderData: keepPreviousData,
    enabled: allowed,
  })
  const remove = useMutation({
    mutationFn: (id: number) => api<BridgeResult>(`${SPA}/materials/basket/${id}/delete/`, { method: 'POST' }),
    onSuccess: (r) => {
      qc.invalidateQueries({ queryKey: ['warehouse'] })
      toast(r.detail || "Material savatdan o'chirildi")
      setRemoving(null)
    },
  })

  const rows = list.data?.results ?? []
  const pageCount = Math.max(1, Math.ceil((list.data?.count ?? 0) / PAGE_SIZE))

  const columns: DataTableColumn<BasketRow>[] = [
    { key: 'n', label: t('T/r'), width: '6%', render: (r) => (page - 1) * PAGE_SIZE + rows.indexOf(r) + 1 },
    {
      key: 'name',
      label: t('Material nomi'),
      width: '30%',
      render: (r) => (
        <div className="aui-cell-text">
          <div className="aui-cell-primary">{r.name}</div>
          <div className="aui-cell-secondary">
            {lang === 'ru' && MOVEMENT_STATUS[r.status] ? t(MOVEMENT_STATUS[r.status]) : r.status_display} ·{' '}
            {t('omborda {n}', { n: formatNumber(r.available) })} {r.unit_name || ''}
          </div>
        </div>
      ),
    },
    { key: 'price', label: t('Narxi'), width: '12%', align: 'right', render: (r) => money(r.price) },
    { key: 'sum', label: t('Umumiy narxi'), width: '14%', align: 'right', render: (r) => <b>{money(r.total_sum)}</b> },
    { key: 'number', label: t('Soni'), width: '8%', align: 'right', render: (r) => formatNumber(r.number) },
    { key: 'unit', label: t('Birligi'), width: '9%', render: (r) => r.unit_name || '' },
    { key: 'code', label: t('Kodi'), width: '11%', render: (r) => <span className="ivs-mono">{r.code || ''}</span> },
    {
      key: 'act',
      label: t('Amal'),
      align: 'right',
      render: (r) => <Button variant="ghost" size="sm" icon="ri-delete-bin-line" iconOnly aria-label={t("Savatdan o'chirish")} onClick={() => setRemoving(r)} />,
    },
  ]

  return (
    <Page
      icon="ri-shopping-basket-2-line"
      title="Materiallar savati"
      subtitle="Savatga yig'ilgan materiallarni bitta xodimga biriktirish."
      actions={
        allowed && (
          <Button size="lg" icon="ri-user-shared-line" disabled={!rows.length} onClick={() => setAssign(true)}>
            {t('Xodimga biriktirish')}
          </Button>
        )
      }
    >
      <MaterialTabs />
      {!allowed ? (
        <EmptyState icon="ri-lock-line" title="Ruxsat yo'q" description="Savat faqat barcha xodimlar materiallarini ko'rish huquqi bor xodimlar uchun." />
      ) : (
        <DataState isPending={list.isPending} isFetching={list.isFetching} error={list.error} empty={rows.length === 0} emptyText="Savat bo'sh. Materiallar ro'yxatidan o'z materialingizni savatga qo'shing.">
          <DataTable rows={rows} columns={columns} getRowId={(r) => r.id} rowHeight={60} minWidth={860} caption={t('Savatdagi materiallar')} />
          {pageCount > 1 && (
            <div className="ivs-pager">
              <Pagination pageCount={pageCount} page={page} onChange={setPage} />
            </div>
          )}
        </DataState>
      )}
      {assign && <AssignDialog onClose={() => setAssign(false)} />}
      {removing && (
        <ConfirmDialog
          title="Savatdan o'chirish"
          danger
          confirmLabel="O'chirish"
          loading={remove.isPending}
          message={
            <>
              <b>{removing.name}</b> — {removing.number} {removing.unit_name || ''}
              <p>{t("Ushbu materialni savatdan o'chirishni tasdiqlaysizmi?")}</p>
              {remove.error && <p className="ivs-form-error">{errorText(remove.error)}</p>}
            </>
          }
          onConfirm={() => remove.mutate(removing.id)}
          onClose={() => setRemoving(null)}
        />
      )}
    </Page>
  )
}
