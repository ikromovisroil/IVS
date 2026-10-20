import { Children } from 'react'
import type { ReactNode } from 'react'
import { Icon } from '../ds'
import { useT } from '../i18n'
import './FilterBar.css'

interface FilterBarProps {
  /** Qidiruv maydoni (SearchInput) — chapda */
  search?: ReactNode
  /** O'ngdagi amallar (Excel, Qo'shish...) */
  actions?: ReactNode
  /** Natija soni ("Qurilmalar: 23 ta") — o'ngda, amallar yonida */
  summary?: ReactNode
  /** Nechta filtr tanlangan — 0 dan katta bo'lsa "Tozalash" ko'rinadi */
  activeCount?: number
  onReset?: () => void
  /**
   * inline — qidiruv, filtrlar va amallar bitta qatorda (filtrlar kam bo'lganda);
   * grid — yuqorida qidiruv/amallar, pastda teng kenglikdagi filtrlar setkasi.
   * Berilmasa: 4 tagacha filtr — inline, ko'proq — grid.
   */
  layout?: 'inline' | 'grid'
  /** Filtrlar (Select, DatePicker...) */
  children?: ReactNode
}

/** Ro'yxat sahifalarining filtrlar paneli (oq karta). */
export default function FilterBar({ search, actions, summary, activeCount = 0, onReset, layout, children }: FilterBarProps) {
  const t = useT()
  const count = Children.toArray(children).filter(Boolean).length
  const mode = layout ?? (count <= 4 ? 'inline' : 'grid')

  const tail = (
    <>
      <span className="ivs-fb-grow" />
      {summary && <div className="ivs-fb-summary">{summary}</div>}
      {onReset && activeCount > 0 && (
        <button type="button" className="ivs-fb-reset" onClick={onReset}>
          <Icon name="ri-filter-off-line" size={16} />
          {t('Tozalash')}
          <span className="ivs-fb-count">{activeCount}</span>
        </button>
      )}
      {actions && <div className="ivs-fb-actions">{actions}</div>}
    </>
  )

  if (mode === 'inline') {
    return (
      <section className="ivs-fb" aria-label={t('Filtrlar')}>
        <div className="ivs-fb-row">
          {search && <div className="ivs-fb-search">{search}</div>}
          {/* filtrlar qatorning bevosita elementlari — komponent qaytargan fragmentlar ham alohida element */}
          {children}
          {tail}
        </div>
      </section>
    )
  }

  return (
    <section className="ivs-fb" aria-label={t('Filtrlar')}>
      {(search || actions || summary || (onReset && activeCount > 0)) && (
        <div className="ivs-fb-row">
          {search && <div className="ivs-fb-search">{search}</div>}
          {tail}
        </div>
      )}
      {count > 0 && <div className="ivs-fb-grid">{children}</div>}
    </section>
  )
}
