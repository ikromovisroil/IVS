import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { Button } from '../../ds'
import { useT } from '../../i18n'

export interface MenuAction {
  /** o'zbekcha matn — menyuda tarjima qilinadi */
  label: string
  icon: string
  danger?: boolean
  onClick: () => void
}

interface Props {
  /** Menyu ochilgan tugma (DataTable rowActions dagi event.currentTarget) */
  anchor: HTMLElement
  actions: MenuAction[]
  onClose: () => void
}

/** Jadval qatoridagi "..." menyusi (eski sahifadagi dropdown-menu): tugma ostida, ekran chetidan chiqmaydi. */
export default function ActionMenu({ anchor, actions, onClose }: Props) {
  const t = useT()
  const panel = useRef<HTMLDivElement>(null)
  const [pos, setPos] = useState({ top: 0, left: 0 })

  useLayoutEffect(() => {
    const r = anchor.getBoundingClientRect()
    const w = panel.current?.offsetWidth ?? 220
    const h = panel.current?.offsetHeight ?? 200
    const top = r.bottom + 4 + h > window.innerHeight ? Math.max(8, r.top - h - 4) : r.bottom + 4
    setPos({ top, left: Math.max(8, Math.min(r.right - w, window.innerWidth - w - 8)) })
  }, [anchor])

  useEffect(() => {
    const onDown = (e: MouseEvent) => {
      if (!panel.current?.contains(e.target as Node) && !anchor.contains(e.target as Node)) onClose()
    }
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    const onScroll = () => onClose()
    document.addEventListener('mousedown', onDown)
    document.addEventListener('keydown', onKey)
    window.addEventListener('resize', onScroll)
    panel.current?.querySelector('button')?.focus()
    return () => {
      document.removeEventListener('mousedown', onDown)
      document.removeEventListener('keydown', onKey)
      window.removeEventListener('resize', onScroll)
    }
  }, [anchor, onClose])

  return createPortal(
    <div ref={panel} className="ivs-menu" role="menu" style={{ top: pos.top, left: pos.left }}>
      {actions.map((a) => (
        <Button
          key={a.label}
          role="menuitem"
          variant="ghost"
          size="sm"
          icon={a.icon}
          className={a.danger ? 'ivs-menu-item is-danger' : 'ivs-menu-item'}
          onClick={() => {
            onClose()
            a.onClick()
          }}
        >
          {t(a.label)}
        </Button>
      ))}
    </div>,
    document.body,
  )
}
