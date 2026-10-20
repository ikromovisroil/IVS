import { useEffect, useState } from 'react'
import { Icon } from '../ds'
import { useT } from '../i18n'

interface SearchInputProps {
  value: string
  onChange: (value: string) => void
  placeholder: string
  /** Yozish tugagach shuncha ms kutib onChange chaqiriladi */
  delay?: number
  style?: React.CSSProperties
}

/** AlignUI SearchField ko'rinishi (.aui-search), lekin boshqariladigan va kechiktirilgan. */
export default function SearchInput({ value, onChange, placeholder, delay = 300, style }: SearchInputProps) {
  const t = useT()
  const [text, setText] = useState(value)

  useEffect(() => setText(value), [value])

  useEffect(() => {
    if (text === value) return
    const timer = setTimeout(() => onChange(text.trim()), delay)
    return () => clearTimeout(timer)
  }, [text, value, delay, onChange])

  return (
    <label className="aui-search is-lg" style={style}>
      <Icon name="search-2-line" size={20} />
      <input type="search" value={text} placeholder={t(placeholder)} aria-label={t(placeholder)} onChange={(e) => setText(e.target.value)} />
    </label>
  )
}
