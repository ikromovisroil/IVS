import { useEffect, useId, useMemo, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { useT } from '../i18n'
import './CategoryTreeSelect.css'

export interface CategoryItem {
  id: number
  name: string
  parent: number | null
}

interface Props {
  items: CategoryItem[]
  value: number | null
  onChange: (value: number | null) => void
  placeholder?: string
  /** Forma ichida: sarlavha, yordam matni va xato holati (ds Select bilan bir xil) */
  label?: ReactNode
  hint?: ReactNode
  error?: boolean
}

/**
 * Kategoriya tanlash: ro'yxatda faqat asosiy kategoriyalar; ichki kategoriyasi borida "+" — bosilsa ichkilari
 * biroz o'ngda va pastda chiqadi. Asosiy kategoriya tanlansa uning ichkilari ham filtrga kiradi.
 */
export default function CategoryTreeSelect({ items, value, onChange, placeholder, label, hint, error }: Props) {
  const t = useT()
  const id = useId()
  const [open, setOpen] = useState(false)
  const [q, setQ] = useState('')
  const [expanded, setExpanded] = useState<Set<number>>(new Set())
  const ref = useRef<HTMLDivElement>(null)

  const { roots, children, byId } = useMemo(() => {
    const byId = new Map(items.map((i) => [i.id, i]))
    const children = new Map<number, CategoryItem[]>()
    for (const i of items) {
      if (i.parent != null && byId.has(i.parent)) children.set(i.parent, [...(children.get(i.parent) ?? []), i])
    }
    const roots = items.filter((i) => i.parent == null || !byId.has(i.parent))
    return { roots, children, byId }
  }, [items])

  useEffect(() => {
    if (!open) return
    const onDown = (e: MouseEvent) => !ref.current?.contains(e.target as Node) && setOpen(false)
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false)
    document.addEventListener('mousedown', onDown)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDown)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  const selected = value != null ? byId.get(value) : undefined
  const pick = (id: number | null) => {
    onChange(id)
    setOpen(false)
    setQ('')
  }
  const toggle = (id: number) =>
    setExpanded((s) => {
      const n = new Set(s)
      if (n.has(id)) n.delete(id)
      else n.add(id)
      return n
    })

  /** "Ota / Ichki / Eng ichki" */
  const pathOf = (c: CategoryItem) => {
    const names = [c.name]
    let cur = c.parent != null ? byId.get(c.parent) : undefined
    while (cur && names.length < 8) {
      names.unshift(cur.name)
      cur = cur.parent != null ? byId.get(cur.parent) : undefined
    }
    return names.join(' / ')
  }

  const term = q.trim().toLowerCase()
  const found = term ? items.filter((i) => i.name.toLowerCase().includes(term)) : []

  // Tanlangan kategoriyaning barcha ota-bobolari ochiq turadi
  const openByValue = useMemo(() => {
    const ids = new Set<number>()
    let cur = value != null ? byId.get(value) : undefined
    while (cur && cur.parent != null && !ids.has(cur.parent)) {
      ids.add(cur.parent)
      cur = byId.get(cur.parent)
    }
    return ids
  }, [value, byId])

  const row = (c: CategoryItem, child = false) => {
    const kids = children.get(c.id) ?? []
    const isOpen = expanded.has(c.id) || openByValue.has(c.id)
    return (
      <li key={c.id} className="ivs-cat-item" role="none">
        <div className={`aui-select-option ivs-cat-row${child ? ' is-child' : ''}${c.id === value ? ' is-selected' : ''}`} role="option" aria-selected={c.id === value}>
          <button type="button" className="ivs-cat-name" onClick={() => pick(c.id)}>
            {c.name}
          </button>
          {kids.length > 0 && (
            <button
              type="button"
              className="ivs-cat-toggle"
              aria-expanded={isOpen}
              aria-label={isOpen ? t('Yopish') : t("Ichki kategoriyalarni ko'rsatish")}
              onClick={() => toggle(c.id)}
            >
              <i className={isOpen ? 'ri-subtract-line' : 'ri-add-line'} aria-hidden="true" />
            </button>
          )}
        </div>
        {kids.length > 0 && isOpen && <ul className="ivs-cat-children">{kids.map((k) => row(k, true))}</ul>}
      </li>
    )
  }

  return (
    <div className="aui-field">
      {label ? (
        <label className="aui-field-label" htmlFor={id}>
          {label}
        </label>
      ) : null}
      <div ref={ref} className={`aui-select${open ? ' is-open' : ''}`}>
        <button id={id} type="button" className="aui-select-trigger" aria-haspopup="listbox" aria-expanded={open} onClick={() => setOpen((o) => !o)}>
          {selected ? <span className="aui-select-value">{selected.name}</span> : <span className="aui-select-placeholder">{placeholder ?? t('Kategoriya')}</span>}
          <i className={`aui-select-chevron ri-arrow-${open ? 'up' : 'down'}-s-line`} aria-hidden="true" />
        </button>

        {open && (
          <div className="aui-select-panel">
            <div className="aui-select-search">
              <i className="ri-search-line" aria-hidden="true" />
              <input autoFocus value={q} placeholder={t('Qidirish...')} aria-label={t('Qidirish...')} onChange={(e) => setQ(e.target.value)} />
            </div>
            <ul className="aui-select-list ivs-cat-list" role="listbox">
              {term ? (
                found.length === 0 ? (
                  <li className="aui-select-empty">{t('“{q}” bo‘yicha hech narsa topilmadi', { q })}</li>
                ) : (
                  found.map((c) => (
                    <li key={c.id} role="none">
                      <div className={`aui-select-option ivs-cat-row${c.id === value ? ' is-selected' : ''}`} role="option" aria-selected={c.id === value}>
                        <button type="button" className="ivs-cat-name" onClick={() => pick(c.id)}>
                          {pathOf(c)}
                        </button>
                      </div>
                    </li>
                  ))
                )
              ) : (
                roots.map((r) => row(r))
              )}
            </ul>
            {value != null && (
              <div className="aui-select-footer">
                <span />
                <button type="button" className="aui-select-clear" onClick={() => pick(null)}>
                  {t('Tozalash')}
                </button>
              </div>
            )}
          </div>
        )}
      </div>
      {hint ? <div className={`aui-field-hint${error ? ' is-error' : ''}`}>{hint}</div> : null}
    </div>
  )
}
