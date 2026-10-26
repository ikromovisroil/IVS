import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Button, Checkbox } from '../../ds'
import Modal from '../../components/Modal'
import ConfirmDialog from '../../components/ConfirmDialog'
import { useToast } from '../../components/toast'
import { api } from '../../api/client'
import { useT } from '../../i18n'
import CheckList from './CheckList'
import type { EmployeeRow, PermItem, PermState } from './api'

interface Catalog {
  dependent: Record<string, string[]>
  super_permissions: string[]
}

// Saytdagi "ruxsatlar" oynasidagi bo'limlar tartibi
const GROUP_ORDER = ['Ariza', 'Hujjatlar', "Ko'rish doirasi", 'Texnika', 'Material', 'Zoom', 'Xodimlar', 'Maxsus rollar', 'Hisobotlar']

interface Draft {
  perms: Record<string, boolean>
  goals: number[]
  categories: number[]
  contracts: number[]
  material_categories: number[]
}

/** Xodim ruxsatlari (rollar) — saytdagi "{F.I.O} — ruxsatlar" oynasi; api/roles.py qoidalari. */
export default function EmployeePermissions({ employee, onClose }: { employee: EmployeeRow; onClose: () => void }) {
  const t = useT()
  const state = useQuery({
    queryKey: ['people', 'permissions', employee.id],
    queryFn: () => api<PermState>(`/employees/${employee.id}/permissions/`),
    gcTime: 0,
  })
  const catalog = useQuery({ queryKey: ['people', 'perm-catalog'], queryFn: () => api<Catalog>('/permissions/catalog/'), staleTime: Infinity })

  return (
    <Modal
      open
      onClose={onClose}
      icon="ri-shield-user-line"
      title={t('{name} — ruxsatlar', { name: employee.full_name })}
      subtitle={employee.rank_name ?? undefined}
      width={880}
      footer={
        <>
          <Button variant="stroke" size="lg" icon="ri-close-line" onClick={onClose}>
            {t('Yopish')}
          </Button>
          <Button size="lg" icon="ri-checkbox-circle-line" type="submit" form="perm-form" disabled={!state.data || !catalog.data}>
            {t('Yakunlash')}
          </Button>
        </>
      }
    >
      {state.error || catalog.error ? (
        <div className="ivs-empty" role="alert">
          {(state.error ?? catalog.error)?.message}
        </div>
      ) : !state.data || !catalog.data ? (
        <div className="ivs-empty" aria-busy="true">
          {t('Yuklanmoqda…')}
        </div>
      ) : (
        <PermissionsForm employee={employee} state={state.data} catalog={catalog.data} onClose={onClose} />
      )}
    </Modal>
  )
}

function PermissionsForm({ employee, state, catalog, onClose }: { employee: EmployeeRow; state: PermState; catalog: Catalog; onClose: () => void }) {
  const t = useT()
  const toast = useToast()
  const qc = useQueryClient()
  const [confirm, setConfirm] = useState(false)
  const [draft, setDraft] = useState<Draft>(() => ({
    perms: Object.fromEntries(state.permissions.map((p) => [p.key, p.granted])),
    goals: state.goals.selected,
    categories: state.categories.selected,
    contracts: state.contracts.selected,
    material_categories: state.material_categories.selected,
  }))

  const supers = new Set(catalog.super_permissions)
  const masterOf: Record<string, string> = {}
  for (const [master, subs] of Object.entries(catalog.dependent)) subs.forEach((s) => (masterOf[s] = master))

  const isWorker = state.employee.organization_type === 'worker'
  // Ko'rinadigan katakchalar: o'zgartirish mumkin bo'lganlar; berishga haqi yo'q SUPER ruxsat — faqat bor bo'lsa (o'chirilgan holda)
  const visible = (p: PermItem) => p.editable || (supers.has(p.key) && p.granted)
  const groups = GROUP_ORDER.map((g) => ({ title: g, items: state.permissions.filter((p) => p.group === g && visible(p)) })).filter((g) => g.items.length)

  const on = (key: string) => !!draft.perms[key]

  const toggle = (key: string, value: boolean) =>
    setDraft((d) => {
      const perms = { ...d.perms, [key]: value }
      if (!value) (catalog.dependent[key] ?? []).forEach((s) => (perms[s] = false)) // "ko'rish" o'chsa bog'liqlari ham
      return {
        ...d,
        perms,
        goals: perms.change_order ? d.goals : [],
        categories: perms.view_technics ? d.categories : [],
        contracts: perms.report_employee ? d.contracts : [],
      }
    })

  const save = useMutation({
    mutationFn: () => {
      const permissions = Object.fromEntries(state.permissions.filter((p) => p.editable).map((p) => [p.key, on(p.key)]))
      const body: Record<string, unknown> = { permissions, goals: draft.goals, categories: draft.categories }
      if (isWorker) body.contracts = draft.contracts
      else body.material_categories = draft.material_categories
      return api<PermState>(`/employees/${employee.id}/permissions/`, { method: 'PUT', body: JSON.stringify(body) })
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['people', 'permissions', employee.id] })
      toast('Xodim ruxsatlari muvaffaqiyatli yangilandi')
      onClose()
    },
    onError: (e) => {
      setConfirm(false)
      toast(e.message, 'error')
    },
  })

  return (
    <form
      id="perm-form"
      onSubmit={(e) => {
        e.preventDefault()
        setConfirm(true)
      }}
    >
      <div className="ivs-people-perm-groups">
        {groups.map((g) => (
          <section key={g.title} className="ivs-people-perm-group">
            <h3 className="type-label-md">{t(g.title)}</h3>
            {g.items.map((p) => {
              const master = masterOf[p.key]
              const blocked = !p.editable || (master !== undefined && !on(master))
              return <Checkbox key={p.key} label={t(`${p.label}#ruxsat`)} checked={on(p.key)} disabled={blocked} onChange={(v) => toggle(p.key, v)} />
            })}
          </section>
        ))}
      </div>

      <div className="ivs-people-lists">
        <CheckList
          label={t('Ariza kategoriyasi')}
          hint={t('"Ariza bajarish" belgilanganda yoqiladi.')}
          options={state.goals.options}
          selected={draft.goals}
          onChange={(ids) => setDraft((d) => ({ ...d, goals: ids }))}
          disabled={!on('change_order')}
        />
        <CheckList
          label={t('Texnika kategoriyasi')}
          hint={t('"Texnikalarni ko\'rish" belgilanganda yoqiladi. Xodim faqat tanlangan kategoriyalardagi texnikalarni ko\'radi.')}
          options={state.categories.options.map((c) => ({ id: c.id, name: c.name, sub: c.group }))}
          selected={draft.categories}
          onChange={(ids) => setDraft((d) => ({ ...d, categories: ids }))}
          disabled={!on('view_technics')}
        />
        {isWorker ? (
          <CheckList
            label={t('Shartnomalar (hisobotlar va Dalolatnoma uchun)')}
            hint={t('"Hisobotlarni ko\'rish" belgilanganda yoqiladi. Dalolatnoma tanlangan shartnomalar asosida shakllanadi. Hech narsa tanlanmasa - barcha shartnomalar.')}
            options={state.contracts.options}
            selected={draft.contracts}
            onChange={(ids) => setDraft((d) => ({ ...d, contracts: ids }))}
            disabled={!on('report_employee')}
          />
        ) : (
          <CheckList
            label={t('Ruxsat etilgan material kategoriyasi')}
            options={state.material_categories.options}
            selected={draft.material_categories}
            onChange={(ids) => setDraft((d) => ({ ...d, material_categories: ids }))}
          />
        )}
      </div>


      {confirm && (
        <ConfirmDialog
          title="Yakunlashni tasdiqlang?"
          message={<>{t('{name} ruxsatlari saqlanadi.', { name: employee.full_name })}</>}
          confirmLabel="Yakunlash"
          loading={save.isPending}
          onConfirm={() => save.mutate()}
          onClose={() => setConfirm(false)}
        />
      )}
    </form>
  )
}
