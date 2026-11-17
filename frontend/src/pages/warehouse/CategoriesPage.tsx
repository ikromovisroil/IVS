import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Button, DataTable, Select, TextInput } from '../../ds'
import type { DataTableColumn } from '../../ds'
import ConfirmDialog from '../../components/ConfirmDialog'
import DataState from '../../components/DataState'
import Modal from '../../components/Modal'
import { useToast } from '../../components/toast'
import { api } from '../../api/client'
import { useT } from '../../i18n'
import Page from '../../layout/Page'
import { SPA } from '../technics/api'
import { FormError } from '../technics/TechnicsDialogs'
import { errorText } from '../technics/util'
import MaterialTabs from './MaterialTabs'
import '../technics/technics.css'
import './warehouse.css'

interface CategoryRow {
  id: number
  name: string
  parent: number | null
  materials: number
  children: number
  editable: boolean
}

interface CategoriesResponse {
  max_depth: number
  can_add: boolean
  can_change: boolean
  can_delete: boolean
  results: CategoryRow[]
}

interface Node extends CategoryRow {
  depth: number
  kids: Node[]
}

/** Tekis ro'yxatdan daraxt (nom bo'yicha tartibda). */
function buildTree(rows: CategoryRow[]): Node[] {
  const byId = new Map<number, Node>(rows.map((r) => [r.id, { ...r, depth: 0, kids: [] }]))
  const roots: Node[] = []
  for (const n of byId.values()) {
    const parent = n.parent != null ? byId.get(n.parent) : undefined
    if (parent) parent.kids.push(n)
    else roots.push(n)
  }
  const setDepth = (n: Node, d: number) => {
    n.depth = d
    n.kids.forEach((k) => setDepth(k, d + 1))
  }
  roots.forEach((r) => setDepth(r, 0))
  return roots
}

const height = (n: Node): number => (n.kids.length ? 1 + Math.max(...n.kids.map(height)) : 0)

function descendants(n: Node): Set<number> {
  const out = new Set<number>()
  const walk = (x: Node) => x.kids.forEach((k) => (out.add(k.id), walk(k)))
  walk(n)
  return out
}

/** "Kategoriyalar" tabi: kategoriyalar daraxti — ko'rish, qo'shish (ichki kategoriya ham), tahrirlash, o'chirish. */
export default function CategoriesPage() {
  const t = useT()
  const qc = useQueryClient()
  const toast = useToast()
  const list = useQuery({ queryKey: ['warehouse', 'categories'], queryFn: () => api<CategoriesResponse>(`${SPA}/materials/categories/`) })
  const data = list.data
  const tree = useMemo(() => buildTree(data?.results ?? []), [data])
  const maxDepth = data?.max_depth ?? 3

  const [expanded, setExpanded] = useState<Set<number>>(new Set())
  const [form, setForm] = useState<{ item: Node | null; parent: number | null } | null>(null)
  const [removing, setRemoving] = useState<Node | null>(null)

  const flat = useMemo(() => {
    const out: Node[] = []
    const walk = (n: Node) => {
      out.push(n)
      if (expanded.has(n.id)) n.kids.forEach(walk)
    }
    tree.forEach(walk)
    return out
  }, [tree, expanded])

  const allIds = useMemo(() => (data?.results ?? []).filter((r) => r.children > 0).map((r) => r.id), [data])
  const toggle = (id: number) =>
    setExpanded((s) => {
      const n = new Set(s)
      if (n.has(id)) n.delete(id)
      else n.add(id)
      return n
    })

  const remove = useMutation({
    mutationFn: (id: number) => api(`${SPA}/materials/categories/${id}/`, { method: 'DELETE' }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['warehouse'] })
      qc.invalidateQueries({ queryKey: ['orders-barn'] })
      toast(t("Kategoriya o'chirildi"))
      setRemoving(null)
    },
  })

  const columns: DataTableColumn<Node>[] = [
    {
      key: 'name',
      label: t('Kategoriya'),
      render: (r) => (
        <div className="ivs-cat-cell" style={{ paddingLeft: r.depth * 28 }}>
          {r.kids.length > 0 ? (
            <button
              type="button"
              className="ivs-cat-toggle"
              aria-expanded={expanded.has(r.id)}
              aria-label={expanded.has(r.id) ? t('Yopish') : t("Ichki kategoriyalarni ko'rsatish")}
              onClick={() => toggle(r.id)}
            >
              <i className={expanded.has(r.id) ? 'ri-subtract-line' : 'ri-add-line'} aria-hidden="true" />
            </button>
          ) : (
            <span className="ivs-cat-dot" aria-hidden="true" />
          )}
          <span className={r.depth === 0 ? 'aui-cell-primary' : ''}>{r.name}</span>
          {!r.editable && <span className="ivs-muted">{t('(umumiy)')}</span>}
        </div>
      ),
    },
    { key: 'kids', label: t('Ichki'), width: 100, align: 'right', render: (r) => r.children || '' },
    { key: 'materials', label: t('Materiallar'), width: 120, align: 'right', render: (r) => r.materials || '' },
    {
      key: 'actions',
      label: '',
      width: 150,
      align: 'right',
      render: (r) =>
        r.editable ? (
          <div className="ivs-cat-actions">
            {data?.can_add && r.depth + 1 < maxDepth && (
              <Button variant="ghost" size="sm" iconOnly icon="ri-add-circle-line" aria-label={t("Ichki kategoriya qo'shish")} title={t("Ichki kategoriya qo'shish")} onClick={() => setForm({ item: null, parent: r.id })} />
            )}
            {data?.can_change && (
              <Button variant="ghost" size="sm" iconOnly icon="ri-edit-line" aria-label={t('Tahrirlash')} title={t('Tahrirlash')} onClick={() => setForm({ item: r, parent: r.parent })} />
            )}
            {data?.can_delete && (
              <Button variant="ghost" size="sm" iconOnly icon="ri-delete-bin-line" aria-label={t("O'chirish")} title={t("O'chirish")} onClick={() => setRemoving(r)} />
            )}
          </div>
        ) : null,
    },
  ]

  return (
    <Page
      icon="ri-archive-line"
      title="Materiallar"
      subtitle="Moddiy javobgar xodimlardagi materiallar, ularni berish, sarflash va savat."
      actions={
        data?.can_add && (
          <Button size="lg" icon="ri-add-line" onClick={() => setForm({ item: null, parent: null })}>
            {t("Kategoriya qo'shish")}
          </Button>
        )
      }
    >
      <MaterialTabs />

      <DataState
        isPending={list.isPending}
        isFetching={list.isFetching}
        error={list.error}
        empty={tree.length === 0}
        emptyText="Kategoriya yo'q"
        emptyDescription={data?.can_add ? "«Kategoriya qo'shish» tugmasi bilan birinchi kategoriyani yarating." : undefined}
      >
        <div className="ivs-cat-bar">
          <Button variant="stroke" size="sm" icon={expanded.size ? 'ri-contract-up-down-line' : 'ri-expand-up-down-line'} onClick={() => setExpanded(expanded.size ? new Set() : new Set(allIds))}>
            {expanded.size ? t('Hammasini yopish') : t('Hammasini ochish')}
          </Button>
        </div>
        <DataTable rows={flat} columns={columns} getRowId={(r) => r.id} rowHeight={56} minWidth={560} caption={t('Material kategoriyalari')} />
      </DataState>

      {form && <CategoryForm tree={tree} maxDepth={maxDepth} item={form.item} parent={form.parent} onClose={() => setForm(null)} />}
      {removing && (
        <ConfirmDialog
          title="Kategoriyani o'chirish"
          danger
          confirmLabel="O'chirish"
          loading={remove.isPending}
          message={
            <>
              <p>{t('«{name}» kategoriyasini o‘chirasizmi?', { name: removing.name })}</p>
              {remove.error && <p className="ivs-form-error">{errorText(remove.error)}</p>}
            </>
          }
          onConfirm={() => remove.mutate(removing.id)}
          onClose={() => {
            remove.reset()
            setRemoving(null)
          }}
        />
      )}
    </Page>
  )
}

/** Qo'shish / tahrirlash oynasi: nomi + ota kategoriya (daraja chegarasi va o'z avlodi hisobga olinadi). */
function CategoryForm({ tree, maxDepth, item, parent, onClose }: { tree: Node[]; maxDepth: number; item: Node | null; parent: number | null; onClose: () => void }) {
  const t = useT()
  const qc = useQueryClient()
  const toast = useToast()
  const [name, setName] = useState(item?.name ?? '')
  const [parentId, setParentId] = useState<number | null>(parent)

  const options = useMemo(() => {
    const exclude = item ? new Set([item.id, ...descendants(item)]) : new Set<number>()
    const below = item ? height(item) : 0
    const out: { value: number; label: string }[] = []
    const walk = (n: Node, path: string[]) => {
      const here = [...path, n.name]
      // ota darajasi + 1 + ostidagi darajalar chegaradan oshmasin
      if (!exclude.has(n.id) && n.depth + 1 + 1 + below <= maxDepth) out.push({ value: n.id, label: here.join(' / ') })
      n.kids.forEach((k) => walk(k, here))
    }
    tree.forEach((r) => walk(r, []))
    return out
  }, [tree, item, maxDepth])

  const save = useMutation({
    mutationFn: () => {
      const body = JSON.stringify({ name: name.trim(), parent: parentId })
      return item
        ? api(`${SPA}/materials/categories/${item.id}/`, { method: 'PATCH', body })
        : api(`${SPA}/materials/categories/`, { method: 'POST', body })
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['warehouse'] })
      qc.invalidateQueries({ queryKey: ['orders-barn'] })
      toast(item ? t('Kategoriya saqlandi') : t("Kategoriya qo'shildi"))
      onClose()
    },
  })

  const valid = name.trim().length > 0

  return (
    <Modal
      open
      onClose={onClose}
      icon="ri-folder-3-line"
      title={item ? 'Kategoriyani tahrirlash' : item === null && parent ? "Ichki kategoriya qo'shish" : "Kategoriya qo'shish"}
      width={780}
      footer={
        <>
          <Button variant="stroke" size="lg" onClick={onClose}>
            {t('Yopish')}
          </Button>
          <Button size="lg" icon="ri-check-line" type="submit" form="category-form" disabled={!valid} loading={save.isPending}>
            {t('Saqlash')}
          </Button>
        </>
      }
    >
      <form
        id="category-form"
        className="ivs-stack"
        onSubmit={(e) => {
          e.preventDefault()
          if (valid) save.mutate()
        }}
      >
        <FormError error={save.error} />
        <TextInput label={t('Nomi *')} autoFocus maxLength={200} value={name} onChange={(e) => setName(e.target.value)} />
        <Select
          label={t('Ota kategoriya')}
          placeholder={t('Yo‘q (asosiy kategoriya)')}
          options={options}
          value={parentId}
          onChange={(v) => setParentId(v == null ? null : Number(v))}
        />
      </form>
    </Modal>
  )
}
