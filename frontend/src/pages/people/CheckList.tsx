import { useState } from 'react'
import { Button, Checkbox, TextInput } from '../../ds'
import { useT } from '../../i18n'

interface Option {
  id: number
  name: string
  sub?: string | null
}

interface CheckListProps {
  label: string
  hint?: string
  options: Option[]
  selected: number[]
  onChange: (ids: number[]) => void
  disabled?: boolean
}

/** Bir nechtasini tanlash ro'yxati (saytdagi select2 multiple o'rniga): qidiruv + katakchalar. */
export default function CheckList({ label, hint, options, selected, onChange, disabled }: CheckListProps) {
  const t = useT()
  const [q, setQ] = useState('')
  const term = q.trim().toLowerCase()
  const shown = term ? options.filter((o) => `${o.name} ${o.sub ?? ''}`.toLowerCase().includes(term)) : options
  const set = new Set(selected)
  const toggle = (id: number, on: boolean) => onChange(on ? [...selected, id] : selected.filter((x) => x !== id))

  return (
    <section className={'ivs-people-checklist' + (disabled ? ' is-disabled' : '')}>
      <div className="ivs-people-checklist-head">
        <h3 className="type-label-md">{label}</h3>
        <span className="type-para-xs">
          {selected.length ? t('{n} ta tanlangan', { n: selected.length }) : t('Tanlanmagan')}
          {!disabled && selected.length > 0 && (
            <Button variant="ghost" size="sm" onClick={() => onChange([])}>
              {t('Tozalash')}
            </Button>
          )}
        </span>
      </div>
      {hint && <p className="type-para-xs ivs-people-note">{hint}</p>}
      {options.length > 8 && <TextInput placeholder={t('Qidirish...')} value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && e.preventDefault()} disabled={disabled} aria-label={t('{label}: qidirish', { label })} />}
      <div className="ivs-people-checklist-box" role="group" aria-label={label}>
        {shown.length === 0 ? (
          <p className="type-para-xs ivs-people-note">{t('Hech narsa topilmadi.')}</p>
        ) : (
          shown.map((o) => (
            <Checkbox key={o.id} label={o.name} sub={o.sub ?? undefined} checked={set.has(o.id)} disabled={disabled} onChange={(on) => toggle(o.id, on)} />
          ))
        )}
      </div>
    </section>
  )
}
