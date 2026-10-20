import type { ReactNode } from 'react'
import { Icon } from '../ds'
import { useTMaybe } from '../i18n'
import './PublicPage.css'

interface PublicPageProps {
  icon: string
  title: string
  subtitle?: string
  actions?: ReactNode
  children: ReactNode
}

/** Kirishsiz ochiladigan sahifalar qobig'i (masalan, PDF dagi QR havolasi): yon menyusiz, faqat brend va sarlavha. */
export default function PublicPage({ icon, title, subtitle, actions, children }: PublicPageProps) {
  const t = useTMaybe()
  return (
    <div className="ivs-public">
      <header className="ivs-public-brand">
        <span className="ivs-public-logo" aria-hidden="true">
          <Icon name="ri-server-fill" size={20} />
        </span>
        <span>
          <span className="type-label-md">IVS</span>
          <span className="type-para-xs ivs-public-muted">{t('Texnik xizmat platformasi')}</span>
        </span>
      </header>
      <main className="ivs-public-main">
        <div className="ivs-public-head">
          <span className="ivs-public-icon" aria-hidden="true">
            <Icon name={icon} size={22} />
          </span>
          <div className="ivs-public-titles">
            <h1 className="type-label-lg">{t(title)}</h1>
            {subtitle && <p className="type-para-sm ivs-public-muted">{t(subtitle)}</p>}
          </div>
          {actions}
        </div>
        {children}
      </main>
    </div>
  )
}
