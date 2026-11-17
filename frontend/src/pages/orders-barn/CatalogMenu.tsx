import { useEffect, useRef, useState } from 'react'
import { Icon } from '../../ds'
import { useT } from '../../i18n'
import type { CatalogNode } from './types'

interface Props {
  tree: CatalogNode[]
  /** Tanlangan kategoriya (ota yoki ichki) */
  value: string
  onChange: (id: string) => void
}

/** "Katalog": chapda kategoriyalar, o'ngda tanlangan kategoriyaning ichki kategoriyalari (marketplace uslubida). */
export default function CatalogMenu({ tree, value, onChange }: Props) {
  const t = useT()
  const [open, setOpen] = useState(false)
  const [activeId, setActiveId] = useState<number | null>(null)
  const [pos, setPos] = useState<{ top: number; left: number; width: number; maxHeight: number } | null>(null)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const onDown = (e: MouseEvent) => {
      if (!ref.current?.contains(e.target as Node)) setOpen(false)
    }
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false)
    document.addEventListener('mousedown', onDown)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDown)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  if (!tree.length) return null

  const active = tree.find((n) => n.id === activeId) ?? tree[0]
  const pick = (id: number) => {
    onChange(id ? String(id) : '')
    setOpen(false)
  }

  return (
    <div className="ob-catalog" ref={ref}>
      <button
        type="button"
        className={`ob-catalog-btn${open ? ' is-open' : ''}${value ? ' is-selected' : ''}`}
        aria-expanded={open}
        onClick={(e) => {
          // Panel sahifa kontentining to'liq kengligida ochiladi (tugma ostida, ekrandan chiqmaydi)
          const r = e.currentTarget.getBoundingClientRect()
          const box = (e.currentTarget.closest('main') ?? document.body).getBoundingClientRect()
          const left = Math.max(16, box.left + 16)
          const width = Math.max(320, Math.min(window.innerWidth - left - 16, box.width - 32))
          setPos({ top: r.bottom + 8, left, width, maxHeight: Math.max(240, window.innerHeight - r.bottom - 24) })
          setOpen((o) => !o)
          setActiveId(null)
        }}
      >
        <Icon name="ri-stack-line" size={20} />
        {t('Katalog')}
      </button>


      {open && (
        <div className="ob-catalog-panel" role="dialog" aria-label={t('Katalog')} style={pos ?? undefined}>
          <ul className="ob-catalog-roots">
            {value && (
              <li>
                <button type="button" onClick={() => pick(0)}>
                  <span>{t('Barcha materiallar')}</span>
                  <Icon name="ri-close-line" size={18} />
                </button>
              </li>
            )}
            {tree.map((n) => (
              <li key={n.id}>
                <button
                  type="button"
                  className={n.id === active.id ? 'is-active' : ''}
                  onMouseEnter={() => setActiveId(n.id)}
                  onFocus={() => setActiveId(n.id)}
                  onClick={() => (n.children.length ? setActiveId(n.id) : n.selectable && pick(n.id))}
                >
                  <span>{n.name}</span>
                  <Icon name="ri-arrow-right-s-line" size={18} />
                </button>
              </li>
            ))}
          </ul>

          <div className="ob-catalog-sub">
            {active.selectable ? (
              <button type="button" className="ob-catalog-title" onClick={() => pick(active.id)}>
                {active.name}
                <Icon name="ri-arrow-right-s-line" size={20} />
              </button>
            ) : (
              <span className="ob-catalog-title is-static">{active.name}</span>
            )}
            {active.children.length > 0 ? (
              <CatalogChildren nodes={active.children} value={value} onPick={pick} />
            ) : (
              <p className="ob-catalog-empty">{t("Ichki kategoriyalar yo'q")}</p>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

/** Ichki kategoriyalar (ichma-ich): ichkisi borlari sarlavha, ularning ostida ichkilari biroz o'ngda. */
function CatalogChildren({ nodes, value, onPick, depth = 0 }: { nodes: CatalogNode[]; value: string; onPick: (id: number) => void; depth?: number }) {
  return (
    <ul className={`ob-catalog-children${depth ? ' is-nested' : ''}`}>
      {nodes.map((c) => (
        <li key={c.id} className={c.children.length ? 'has-kids' : ''}>
          {c.selectable ? (
            <button type="button" className={`${String(c.id) === value ? 'is-active' : ''}${c.children.length ? ' is-group' : ''}`} onClick={() => onPick(c.id)}>
              {c.name}
            </button>
          ) : (
            <span className="ob-catalog-group is-static">{c.name}</span>
          )}
          {c.children.length > 0 && <CatalogChildren nodes={c.children} value={value} onPick={onPick} depth={depth + 1} />}
        </li>
      ))}
    </ul>
  )
}
