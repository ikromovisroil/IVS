import type { ReactNode } from 'react'
import { Icon } from '../ds'
import { useTMaybe } from '../i18n'
import './EmptyState.css'

interface EmptyStateProps {
  /** RemixIcon nomi; standart — bo'sh quti */
  icon?: string
  title: ReactNode
  description?: ReactNode
  /** Tugma(lar): <Button size="md">...</Button> */
  action?: ReactNode
  /** error — xato holati (qizil belgi, role=alert) */
  tone?: 'default' | 'error'
  /** compact — kartochka/vidjet ichida */
  size?: 'default' | 'compact'
}

/**
 * Bo'sh holat: ro'yxat bo'sh, filtrga mos natija yo'q, xato yoki ruxsat yo'q.
 * Sarlavha — nima bo'ldi; tavsif — nima qilish mumkin; action — keyingi qadam.
 */
export default function EmptyState({ icon, title, description, action, tone = 'default', size = 'default' }: EmptyStateProps) {
  const t = useTMaybe()
  const name = icon ?? (tone === 'error' ? 'ri-error-warning-line' : 'ri-inbox-2-line')
  return (
    <div className={`ivs-es is-${tone} is-${size}`} role={tone === 'error' ? 'alert' : 'status'}>
      <div className="ivs-es-art" aria-hidden="true">
        <span className="ivs-es-ring is-outer" />
        <span className="ivs-es-ring is-inner" />
        <span className="ivs-es-icon">
          <Icon name={name} size={size === 'compact' ? 20 : 24} />
        </span>
      </div>
      <div className="ivs-es-text">
        <div className="ivs-es-title">{typeof title === 'string' ? t(title) : title}</div>
        {description && <div className="ivs-es-desc">{typeof description === 'string' ? t(description) : description}</div>}
      </div>
      {action && <div className="ivs-es-action">{action}</div>}
    </div>
  )
}
