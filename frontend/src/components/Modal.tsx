import { useEffect, useId, useRef } from 'react'
import type { ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { Button, Icon } from '../ds'
import { useT, useTMaybe } from '../i18n'
import './Modal.css'

interface ModalProps {
  open: boolean
  onClose: () => void
  title: string
  subtitle?: string
  icon?: string
  /** Pastki qatordagi tugmalar */
  footer?: ReactNode
  width?: number
  children: ReactNode
}

/** "Uskuna qo'shish" maketidagi dialog: overlay-gray fon, 20px radius, sarlavha / kontent / tugmalar. */
export default function Modal({ open, onClose, title, subtitle, icon, footer, width = 720, children }: ModalProps) {
  const t = useT()
  const tMaybe = useTMaybe()
  const titleId = useId()
  const panel = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const back = document.activeElement as HTMLElement | null
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKey)
    panel.current?.querySelector<HTMLElement>('input, textarea, button:not(.ivs-modal-close)')?.focus()
    return () => {
      document.removeEventListener('keydown', onKey)
      back?.focus()
    }
  }, [open, onClose])

  if (!open) return null
  return createPortal(
    <div className="ivs-modal-overlay" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div ref={panel} className="ivs-modal" role="dialog" aria-modal="true" aria-labelledby={titleId} style={{ width }}>
        <div className="ivs-modal-head">
          {icon && (
            <div className="ivs-modal-icon">
              <Icon name={icon} size={20} />
            </div>
          )}
          <div className="ivs-modal-titles">
            <h2 id={titleId} className="type-label-md">
              {tMaybe(title)}
            </h2>
            {subtitle && <p className="type-para-xs">{tMaybe(subtitle)}</p>}
          </div>
          <Button className="ivs-modal-close" variant="ghost" size="sm" icon="ri-close-line" iconOnly aria-label={t('Yopish')} onClick={onClose} />
        </div>
        <div className="ivs-modal-body">{children}</div>
        {footer && <div className="ivs-modal-foot">{footer}</div>}
      </div>
    </div>,
    document.body,
  )
}
