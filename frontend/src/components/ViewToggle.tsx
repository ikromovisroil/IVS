import { Icon } from '../ds'
import type { ViewMode } from '../lib/useViewMode'
import { useT } from '../i18n'

/** Jadval / karta ko'rinishini almashtirish (ikki belgili tugma). */
export default function ViewToggle({ value, onChange }: { value: ViewMode; onChange: (mode: ViewMode) => void }) {
  const t = useT()
  const items: { mode: ViewMode; icon: string; label: string }[] = [
    { mode: 'cards', icon: 'ri-layout-grid-line', label: t('Karta ko‘rinishi') },
    { mode: 'table', icon: 'ri-list-unordered', label: t('Jadval ko‘rinishi') },
  ]
  return (
    <div className="aui-seg aui-seg-boxed ivs-viewtoggle" role="group" aria-label={t("Ko'rinish")}>
      {items.map((it) => (
        <button
          key={it.mode}
          type="button"
          className={`aui-seg-item${value === it.mode ? ' is-active' : ''}`}
          aria-pressed={value === it.mode}
          aria-label={it.label}
          title={it.label}
          onClick={() => onChange(it.mode)}
        >
          <Icon name={it.icon} size={18} />
        </button>
      ))}
    </div>
  )
}
