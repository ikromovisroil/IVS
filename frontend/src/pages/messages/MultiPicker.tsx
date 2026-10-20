import { Select, Tag } from '../../ds'
import type { SelectOption } from '../../ds'
import { useT } from '../../i18n'

interface Props {
  label: string
  placeholder: string
  options: SelectOption[]
  value: number[]
  onChange: (ids: number[]) => void
  error?: string
  hint?: string
  disabled?: boolean
}

/** Bir nechta xodim tanlash (eski select2 multiple): Select'dan tanlanadi, tanlanganlar Tag bo'lib chiqadi. */
export default function MultiPicker({ label, placeholder, options, value, onChange, error, hint, disabled }: Props) {
  const t = useT()
  const free = options.filter((o) => !value.includes(Number(o.value)))
  const byId = new Map(options.map((o) => [Number(o.value), o.label]))

  return (
    <div className="msg-picker">
      <Select
        label={label}
        placeholder={free.length ? placeholder : options.length ? t('Hammasi tanlangan') : placeholder}
        options={free}
        value={null}
        disabled={disabled || !free.length}
        onChange={(v) => v != null && onChange([...value, Number(v)])}
        error={!!error}
        hint={error || hint}
      />
      {value.length > 0 && (
        <div className="msg-tags">
          {value.map((id) => (
            <Tag key={id} onRemove={() => onChange(value.filter((x) => x !== id))}>
              {byId.get(id) ?? `#${id}`}
            </Tag>
          ))}
        </div>
      )}
    </div>
  )
}
