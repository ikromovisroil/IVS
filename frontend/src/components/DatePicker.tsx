import { useCallback, useEffect, useId, useLayoutEffect, useRef, useState } from 'react'
import type { KeyboardEvent, ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { Icon } from '../ds'
import { useLang, useT } from '../i18n'
import { MONTHS, MONTHS_TITLE, MONTHS_SHORT, WEEKDAYS_MIN } from '../i18n/format'
import './DatePicker.css'


/* ---------- sana yordamchilari (mahalliy vaqt, ISO "YYYY-MM-DD") ---------- */

const pad = (n: number) => String(n).padStart(2, '0')
const toIso = (d: Date) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
function parseIso(s: string | undefined | null): Date | null {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(s ?? '')
  return m ? new Date(+m[1], +m[2] - 1, +m[3]) : null
}
const sameDay = (a: Date | null, b: Date | null) => !!a && !!b && toIso(a) === toIso(b)
const addDays = (d: Date, n: number) => new Date(d.getFullYear(), d.getMonth(), d.getDate() + n)
const addMonths = (d: Date, n: number) => {
  const r = new Date(d.getFullYear(), d.getMonth() + n, 1)
  r.setDate(Math.min(d.getDate(), new Date(r.getFullYear(), r.getMonth() + 1, 0).getDate()))
  return r
}

/** "20.10.2026" / "20.10.2026, 14:30" */
function formatDisplay(value: string, withTime: boolean): string {
  const d = parseIso(value)
  if (!d) return ''
  const date = `${pad(d.getDate())}.${pad(d.getMonth() + 1)}.${d.getFullYear()}`
  const time = withTime ? /T(\d{2}:\d{2})/.exec(value)?.[1] : null
  return time ? `${date}, ${time}` : date
}

interface DatePickerProps {
  label?: ReactNode
  /** "YYYY-MM-DD" yoki withTime bo'lsa "YYYY-MM-DDTHH:mm"; bo'sh — "" */
  value: string
  onChange: (value: string) => void
  /** Sana bilan birga vaqt (datetime-local o'rniga) */
  withTime?: boolean
  min?: string
  max?: string
  placeholder?: string
  required?: boolean
  disabled?: boolean
  hint?: ReactNode
  error?: boolean
  className?: string
}

type View = 'days' | 'months' | 'years'

/** Kalendar: input ko'rinishidagi tugma + ochiladigan oy jadvali. */
export default function DatePicker({
  label,
  value,
  onChange,
  withTime = false,
  min,
  max,
  placeholder,
  required,
  disabled,
  hint,
  error,
  className,
}: DatePickerProps) {
  const t = useT()
  const { lang } = useLang()
  const id = useId()
  const trigger = useRef<HTMLButtonElement>(null)
  const panel = useRef<HTMLDivElement>(null)
  const [open, setOpen] = useState(false)
  const [view, setView] = useState<View>('days')
  const selected = parseIso(value)
  const today = new Date()
  const [focus, setFocus] = useState<Date>(selected ?? today)
  const [pos, setPos] = useState<{ top: number; left: number; up: boolean }>({ top: 0, left: 0, up: false })
  const minD = parseIso(min)
  const maxD = parseIso(max)
  const time = /T(\d{2}:\d{2})/.exec(value)?.[1] ?? '09:00'

  const disabledDay = useCallback(
    (d: Date) => (!!minD && toIso(d) < toIso(minD)) || (!!maxD && toIso(d) > toIso(maxD)),
    [minD, maxD],
  )

  const place = useCallback(() => {
    const r = trigger.current?.getBoundingClientRect()
    if (!r) return
    const h = panel.current?.offsetHeight ?? 360
    const w = panel.current?.offsetWidth ?? 300
    const up = r.bottom + h + 8 > window.innerHeight && r.top - h - 8 > 0
    const left = Math.min(Math.max(8, r.left), window.innerWidth - w - 8)
    setPos({ top: up ? r.top - h - 6 : r.bottom + 6, left, up })
  }, [])

  const openPanel = () => {
    if (disabled) return
    setFocus(selected ?? (minD && disabledDay(today) ? minD : today))
    setView('days')
    setOpen(true)
  }
  const close = useCallback((refocus = true) => {
    setOpen(false)
    if (refocus) trigger.current?.focus()
  }, [])

  useLayoutEffect(() => {
    if (open) place()
  }, [open, view, place])

  useEffect(() => {
    if (!open) return
    const onDown = (e: MouseEvent) => {
      const t = e.target as Node
      if (!panel.current?.contains(t) && !trigger.current?.contains(t)) close(false)
    }
    const onMove = () => place()
    document.addEventListener('mousedown', onDown)
    window.addEventListener('resize', onMove)
    window.addEventListener('scroll', onMove, true)
    return () => {
      document.removeEventListener('mousedown', onDown)
      window.removeEventListener('resize', onMove)
      window.removeEventListener('scroll', onMove, true)
    }
  }, [open, place, close])

  // fokusni tanlangan kunga o'tkazish (klaviatura)
  useEffect(() => {
    if (open && view === 'days') panel.current?.querySelector<HTMLButtonElement>(`[data-day="${toIso(focus)}"]`)?.focus()
  }, [open, view, focus])

  const commit = (d: Date, keepOpen = false) => {
    if (disabledDay(d)) return
    onChange(withTime ? `${toIso(d)}T${time}` : toIso(d))
    if (!keepOpen && !withTime) close()
  }

  const onGridKey = (e: KeyboardEvent<HTMLDivElement>) => {
    const moves: Record<string, () => Date> = {
      ArrowLeft: () => addDays(focus, -1),
      ArrowRight: () => addDays(focus, 1),
      ArrowUp: () => addDays(focus, -7),
      ArrowDown: () => addDays(focus, 7),
      PageUp: () => addMonths(focus, -1),
      PageDown: () => addMonths(focus, 1),
      Home: () => addDays(focus, -((focus.getDay() + 6) % 7)),
      End: () => addDays(focus, 6 - ((focus.getDay() + 6) % 7)),
    }
    if (moves[e.key]) {
      e.preventDefault()
      setFocus(moves[e.key]())
    } else if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault()
      commit(focus)
    }
  }

  const onPanelKey = (e: KeyboardEvent<HTMLDivElement>) => {
    if (e.key === 'Escape') {
      e.stopPropagation() // modal oynani yopib yubormasin
      close()
    }
  }

  // oy jadvali: dushanbadan boshlanadigan 6 hafta
  const first = new Date(focus.getFullYear(), focus.getMonth(), 1)
  const start = addDays(first, -((first.getDay() + 6) % 7))
  const days = Array.from({ length: 42 }, (_, i) => addDays(start, i))
  const yearStart = focus.getFullYear() - (focus.getFullYear() % 12)

  const step = (dir: 1 | -1) => {
    if (view === 'days') setFocus(addMonths(focus, dir))
    else if (view === 'months') setFocus(new Date(focus.getFullYear() + dir, focus.getMonth(), 1))
    else setFocus(new Date(focus.getFullYear() + dir * 12, focus.getMonth(), 1))
  }

  const display = formatDisplay(value, withTime)

  return (
    <div className={`aui-field ivs-dp${className ? ' ' + className : ''}`}>
      {label && (
        <label className="aui-field-label" htmlFor={id}>
          {typeof label === 'string' ? t(label) : label}
          {required && typeof label === 'string' && !label.includes('*') ? ' *' : ''}
        </label>
      )}
      <div className={`ivs-dp-field${error ? ' is-error' : ''}${open ? ' is-open' : ''}${disabled ? ' is-disabled' : ''}`}>
        <button
          ref={trigger}
          id={id}
          type="button"
          className="ivs-dp-trigger"
          aria-haspopup="dialog"
          aria-expanded={open}
          disabled={disabled}
          onClick={() => (open ? close() : openPanel())}
          onKeyDown={(e) => {
            if (e.key === 'ArrowDown' && !open) {
              e.preventDefault()
              openPanel()
            }
          }}
        >
          <Icon name="ri-calendar-line" size={18} />
          <span className={display ? 'ivs-dp-value' : 'ivs-dp-placeholder'}>{display || (placeholder ? t(placeholder) : t(withTime ? 'Sana va vaqtni tanlang' : 'Sanani tanlang'))}</span>
        </button>
        {value && !required && !disabled && (
          <button type="button" className="ivs-dp-clear" aria-label={t('Sanani tozalash')} onClick={() => onChange('')}>
            <Icon name="ri-close-circle-fill" size={16} />
          </button>
        )}
      </div>
      {hint && <div className={`aui-field-hint${error ? ' is-error' : ''}`}>{typeof hint === 'string' ? t(hint) : hint}</div>}

      {open &&
        createPortal(
          <div
            ref={panel}
            className={`ivs-dp-panel${pos.up ? ' is-up' : ''}`}
            style={{ top: pos.top, left: pos.left }}
            role="dialog"
            aria-modal="false"
            aria-label={t('Sanani tanlash')}
            onKeyDown={onPanelKey}
          >
            <div className="ivs-dp-head">
              <button type="button" className="ivs-dp-nav" aria-label={t('Oldingi')} onClick={() => step(-1)}>
                <Icon name="ri-arrow-left-s-line" size={20} />
              </button>
              <button
                type="button"
                className="ivs-dp-title"
                onClick={() => setView(view === 'days' ? 'months' : view === 'months' ? 'years' : 'days')}
                aria-live="polite"
              >
                {view === 'days' && `${MONTHS_TITLE[lang][focus.getMonth()]} ${focus.getFullYear()}`}
                {view === 'months' && focus.getFullYear()}
                {view === 'years' && `${yearStart} – ${yearStart + 11}`}
                <Icon name="ri-arrow-down-s-line" size={16} />
              </button>
              <button type="button" className="ivs-dp-nav" aria-label={t('Keyingi')} onClick={() => step(1)}>
                <Icon name="ri-arrow-right-s-line" size={20} />
              </button>
            </div>

            {view === 'days' && (
              <div className="ivs-dp-grid" role="grid" onKeyDown={onGridKey}>
                {WEEKDAYS_MIN[lang].map((w, i) => (
                  <span key={w} className={`ivs-dp-wd${i > 4 ? ' is-weekend' : ''}`} role="columnheader">
                    {w}
                  </span>
                ))}
                {days.map((d) => {
                  const out = d.getMonth() !== focus.getMonth()
                  const sel = sameDay(d, selected)
                  const off = disabledDay(d)
                  return (
                    <button
                      key={toIso(d)}
                      type="button"
                      role="gridcell"
                      data-day={toIso(d)}
                      tabIndex={sameDay(d, focus) ? 0 : -1}
                      aria-selected={sel}
                      aria-disabled={off || undefined}
                      aria-label={`${d.getDate()} ${MONTHS[lang][d.getMonth()]} ${d.getFullYear()}`}
                      className={[
                        'ivs-dp-day',
                        out && 'is-out',
                        sel && 'is-selected',
                        sameDay(d, today) && 'is-today',
                        off && 'is-disabled',
                      ]
                        .filter(Boolean)
                        .join(' ')}
                      onClick={() => {
                        setFocus(d)
                        commit(d)
                      }}
                    >
                      {d.getDate()}
                    </button>
                  )
                })}
              </div>
            )}

            {view === 'months' && (
              <div className="ivs-dp-cells">
                {MONTHS_SHORT[lang].map((m, i) => (
                  <button
                    key={m}
                    type="button"
                    className={`ivs-dp-cell${selected && selected.getFullYear() === focus.getFullYear() && selected.getMonth() === i ? ' is-selected' : ''}`}
                    onClick={() => {
                      setFocus(new Date(focus.getFullYear(), i, 1))
                      setView('days')
                    }}
                  >
                    {m}
                  </button>
                ))}
              </div>
            )}

            {view === 'years' && (
              <div className="ivs-dp-cells">
                {Array.from({ length: 12 }, (_, i) => yearStart + i).map((y) => (
                  <button
                    key={y}
                    type="button"
                    className={`ivs-dp-cell${selected?.getFullYear() === y ? ' is-selected' : ''}${today.getFullYear() === y ? ' is-today' : ''}`}
                    onClick={() => {
                      setFocus(new Date(y, focus.getMonth(), 1))
                      setView('months')
                    }}
                  >
                    {y}
                  </button>
                ))}
              </div>
            )}

            {withTime && (
              <div className="ivs-dp-time">
                <Icon name="ri-time-line" size={18} />
                <span>{t('Vaqt')}</span>
                <input
                  type="time"
                  className="aui-input"
                  value={time}
                  aria-label={t('Vaqt')}
                  onChange={(e) => e.target.value && onChange(`${toIso(selected ?? focus)}T${e.target.value}`)}
                />
              </div>
            )}

            <div className="ivs-dp-foot">
              <button
                type="button"
                className="ivs-dp-link"
                disabled={disabledDay(today)}
                onClick={() => {
                  setFocus(today)
                  setView('days')
                  commit(today, withTime)
                }}
              >
                {t('Bugun')}
              </button>
              {withTime ? (
                <button type="button" className="ivs-dp-done" onClick={() => close()}>
                  {t('Tayyor')}
                </button>
              ) : (
                !required &&
                value && (
                  <button
                    type="button"
                    className="ivs-dp-link is-muted"
                    onClick={() => {
                      onChange('')
                      close()
                    }}
                  >
                    {t('Tozalash')}
                  </button>
                )
              )}
            </div>
          </div>,
          document.body,
        )}
    </div>
  )
}
