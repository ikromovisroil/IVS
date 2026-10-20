// Bosh sahifa grafiklari: SVG, AlignUI tokenlari, sichqoncha va klaviatura bilan aniq qiymatli tooltip.
import { useEffect, useId, useRef, useState } from 'react'
import type { KeyboardEvent, PointerEvent, ReactNode } from 'react'
import { useT } from '../../i18n'
import { formatNumber } from '../../lib/format'

/* ---------- umumiy ---------- */

/** Konteyner kengligi (ResizeObserver). */
function useWidth<T extends HTMLElement>(): [React.RefObject<T | null>, number] {
  const ref = useRef<T>(null)
  const [w, setW] = useState(0)
  useEffect(() => {
    const el = ref.current
    if (!el) return
    const ro = new ResizeObserver(([e]) => setW(Math.round(e.contentRect.width)))
    ro.observe(el)
    setW(Math.round(el.getBoundingClientRect().width))
    return () => ro.disconnect()
  }, [])
  return [ref, w]
}

/** Grafik ustidagi tooltip: x — konteyner ichidagi markaz, chetdan chiqmaydi. */
export function Tip({ x, y, width, children }: { x: number; y: number; width: number; children: ReactNode }) {
  const half = 88
  const left = Math.min(Math.max(x, half), Math.max(half, width - half))
  return (
    <div className="ivs-tip" style={{ left, top: y }} role="status">
      {children}
    </div>
  )
}

export function TipRow({ color, label, value }: { color?: string; label: ReactNode; value: ReactNode }) {
  return (
    <div className="ivs-tip-row">
      {color && <span className="ivs-tip-dot" style={{ background: color }} />}
      <span className="ivs-tip-label">{label}</span>
      <span className="ivs-tip-value">{value}</span>
    </div>
  )
}

/** Har qanday elementga hover/focus tooltip (chiziqlar, kartochkalar uchun). */
export function HoverTip({ content, children, className }: { content: ReactNode; children: ReactNode; className?: string }) {
  const [open, setOpen] = useState(false)
  const [ref, width] = useWidth<HTMLDivElement>()
  return (
    <div
      ref={ref}
      className={`ivs-hovertip${className ? ' ' + className : ''}`}
      onPointerEnter={() => setOpen(true)}
      onPointerLeave={() => setOpen(false)}
      onFocus={() => setOpen(true)}
      onBlur={() => setOpen(false)}
    >
      {children}
      {open && (
        <Tip x={width / 2} y={0} width={width}>
          {content}
        </Tip>
      )}
    </div>
  )
}

function niceMax(v: number): number {
  if (v <= 4) return 4
  const p = Math.pow(10, Math.floor(Math.log10(v)))
  const n = v / p
  const step = n <= 1 ? 1 : n <= 2 ? 2 : n <= 4 ? 4 : n <= 5 ? 5 : 10
  return step * p
}

const pct = (v: number, total: number) => (total ? Math.round((v * 100) / total) : 0)

/* ---------- Arizalar dinamikasi: ikki chiziqli grafik ---------- */

export interface TrendSeries {
  key: string
  label: string
  color: string
  values: number[]
}

interface TrendChartProps {
  labels: string[] // har bir nuqta uchun tooltip sarlavhasi
  axisLabels: string[] // x o'qi (bo'sh satr — ko'rsatilmaydi)
  series: TrendSeries[]
  height?: number
  label: string
}

export function TrendChart({ labels, axisLabels, series, height = 220, label }: TrendChartProps) {
  const [ref, W] = useWidth<HTMLDivElement>()
  const [active, setActive] = useState<number | null>(null)
  const t = useT()
  const gid = useId().replace(/[^a-zA-Z0-9]/g, '')
  const n = labels.length
  const pad = { l: 36, r: 12, t: 12, b: 28 }
  const iw = Math.max(1, W - pad.l - pad.r)
  const ih = height - pad.t - pad.b
  const max = niceMax(Math.max(1, ...series.flatMap((s) => s.values)))
  const ticks = [0, 0.25, 0.5, 0.75, 1].map((f) => Math.round(max * f))
  const x = (i: number) => pad.l + (n <= 1 ? iw / 2 : (i * iw) / (n - 1))
  const y = (v: number) => pad.t + ih - (v / max) * ih

  const pickFromPointer = (e: PointerEvent<SVGRectElement>) => {
    const r = e.currentTarget.getBoundingClientRect()
    const i = Math.round(((e.clientX - r.left) / r.width) * (n - 1))
    setActive(Math.min(n - 1, Math.max(0, i)))
  }
  const onKey = (e: KeyboardEvent<HTMLDivElement>) => {
    if (e.key === 'ArrowRight') setActive((a) => Math.min(n - 1, (a ?? -1) + 1))
    else if (e.key === 'ArrowLeft') setActive((a) => Math.max(0, (a ?? n) - 1))
    else if (e.key === 'Home') setActive(0)
    else if (e.key === 'End') setActive(n - 1)
    else if (e.key === 'Escape') setActive(null)
    else return
    e.preventDefault()
  }

  return (
    <div
      ref={ref}
      className="ivs-chart"
      tabIndex={0}
      role="group"
      aria-label={`${label}. ${t("Qiymatlarni ko'rish uchun chap/o'ng strelkalarni bosing.")}`}
      onKeyDown={onKey}
      onBlur={() => setActive(null)}
    >
      {W > 0 && n > 0 && (
        <svg width={W} height={height} aria-hidden="true">
          <defs>
            {series.map((s) => (
              <linearGradient key={s.key} id={`${gid}-${s.key}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" style={{ stopColor: s.color, stopOpacity: 0.18 }} />
                <stop offset="100%" style={{ stopColor: s.color, stopOpacity: 0 }} />
              </linearGradient>
            ))}
          </defs>
          {ticks.map((t) => (
            <g key={t}>
              <line x1={pad.l} x2={W - pad.r} y1={y(t)} y2={y(t)} className="ivs-chart-grid" />
              <text x={pad.l - 8} y={y(t)} dy="0.32em" textAnchor="end" className="ivs-chart-axis">
                {formatNumber(t)}
              </text>
            </g>
          ))}
          {axisLabels.map((l, i) =>
            l ? (
              <text key={i} x={x(i)} y={height - 8} textAnchor={i === 0 ? 'start' : i === n - 1 ? 'end' : 'middle'} className="ivs-chart-axis">
                {l}
              </text>
            ) : null,
          )}
          {series.map((s) => {
            const pts = s.values.map((v, i) => `${x(i).toFixed(1)},${y(v).toFixed(1)}`)
            return (
              <g key={s.key}>
                <path d={`M${pts.join(' L')} L${x(n - 1)},${y(0)} L${x(0)},${y(0)} Z`} style={{ fill: `url(#${gid}-${s.key})` }} />
                <path d={`M${pts.join(' L')}`} className="ivs-chart-line" style={{ stroke: s.color }} />
              </g>
            )
          })}
          {active != null && (
            <g>
              <line x1={x(active)} x2={x(active)} y1={pad.t} y2={pad.t + ih} className="ivs-chart-cursor" />
              {series.map((s) => (
                <circle key={s.key} cx={x(active)} cy={y(s.values[active])} r={4.5} className="ivs-chart-point" style={{ stroke: s.color }} />
              ))}
            </g>
          )}
          <rect
            x={pad.l}
            y={pad.t}
            width={iw}
            height={ih}
            fill="transparent"
            onPointerMove={pickFromPointer}
            onPointerDown={pickFromPointer}
            onPointerLeave={() => setActive(null)}
          />
        </svg>
      )}
      {active != null && (
        <Tip x={x(active)} y={pad.t} width={W}>
          <div className="ivs-tip-title">{labels[active]}</div>
          {series.map((s) => (
            <TipRow key={s.key} color={s.color} label={s.label} value={formatNumber(s.values[active])} />
          ))}
        </Tip>
      )}
    </div>
  )
}

/* ---------- Kichik grafik (KPI) ---------- */

export function Sparkline({ values, labels, color }: { values: number[]; labels: string[]; color: string }) {
  const t = useT()
  const [ref, W] = useWidth<HTMLDivElement>()
  const [active, setActive] = useState<number | null>(null)
  const H = 44
  const n = values.length
  const max = Math.max(1, ...values)
  const x = (i: number) => 3 + (n <= 1 ? 0 : (i * (W - 6)) / (n - 1))
  const y = (v: number) => 4 + (H - 8) * (1 - v / max)
  const pts = values.map((v, i) => `${x(i).toFixed(1)},${y(v).toFixed(1)}`)

  const pick = (e: PointerEvent<SVGRectElement>) => {
    const r = e.currentTarget.getBoundingClientRect()
    setActive(Math.min(n - 1, Math.max(0, Math.round(((e.clientX - r.left) / r.width) * (n - 1)))))
  }

  return (
    <div ref={ref} className="ivs-spark">
      {W > 0 && n > 1 && (
        <svg width={W} height={H} aria-hidden="true">
          <path d={`M${pts.join(' L')}`} className="ivs-chart-line is-thin" style={{ stroke: color }} />
          {active != null && <circle cx={x(active)} cy={y(values[active])} r={3.5} className="ivs-chart-point" style={{ stroke: color }} />}
          <rect width={W} height={H} fill="transparent" onPointerMove={pick} onPointerLeave={() => setActive(null)} />
        </svg>
      )}
      {active != null && (
        <Tip x={x(active)} y={0} width={W}>
          <TipRow color={color} label={labels[active]} value={t('{n} ta#plain', { n: formatNumber(values[active]) })} />
        </Tip>
      )}
    </div>
  )
}

/* ---------- Donut (Arizalar holati) ---------- */

export interface Part {
  key: string
  label: string
  value: number
  color: string
}

interface DonutProps {
  parts: Part[]
  active: string | null
  onActive: (key: string | null) => void
  caption: string
  size?: number
  thickness?: number
}

export function Donut({ parts, active, onActive, caption, size = 196, thickness = 26 }: DonutProps) {
  const total = parts.reduce((a, p) => a + p.value, 0)
  const r = (size - thickness) / 2 - 4 // faol segment 6px qalinlashadi — chetdan chiqmasin
  const c = size / 2
  const visible = parts.filter((p) => p.value > 0)
  const gap = visible.length > 1 ? 0.012 : 0
  let acc = 0

  const arc = (a0: number, a1: number) => {
    const p = (a: number) => [c + r * Math.sin(a * 2 * Math.PI), c - r * Math.cos(a * 2 * Math.PI)]
    const [x0, y0] = p(a0)
    const [x1, y1] = p(a1)
    return `M${x0.toFixed(2)} ${y0.toFixed(2)} A${r} ${r} 0 ${a1 - a0 > 0.5 ? 1 : 0} 1 ${x1.toFixed(2)} ${y1.toFixed(2)}`
  }
  const cur = parts.find((p) => p.key === active)

  return (
    <div className="ivs-donut" style={{ width: size, height: size }}>
      <svg width={size} height={size} role="img" aria-label={`${caption}: ${parts.map((p) => `${p.label} ${p.value}`).join(', ')}`}>
        <circle cx={c} cy={c} r={r} className="ivs-donut-track" style={{ strokeWidth: thickness }} />
        {visible.map((p) => {
          const a0 = acc / total
          acc += p.value
          const a1 = acc / total
          const full = a1 - a0 >= 0.999
          const dim = active != null && active !== p.key
          return full ? (
            <circle
              key={p.key}
              cx={c}
              cy={c}
              r={r}
              className="ivs-donut-seg"
              style={{ stroke: p.color, strokeWidth: thickness, opacity: dim ? 0.3 : 1 }}
              onPointerEnter={() => onActive(p.key)}
              onPointerLeave={() => onActive(null)}
            />
          ) : (
            <path
              key={p.key}
              d={arc(a0 + gap / 2, a1 - gap / 2)}
              className="ivs-donut-seg"
              style={{ stroke: p.color, strokeWidth: active === p.key ? thickness + 6 : thickness, opacity: dim ? 0.3 : 1 }}
              onPointerEnter={() => onActive(p.key)}
              onPointerLeave={() => onActive(null)}
            />
          )
        })}
      </svg>
      <div className="ivs-donut-center" aria-live="polite">
        <span className="ivs-donut-caption">{cur ? cur.label : caption}</span>
        <span className="ivs-donut-value">{formatNumber(cur ? cur.value : total)}</span>
        {cur && <span className="ivs-donut-pct">{pct(cur.value, total)}%</span>}
      </div>
    </div>
  )
}

/* ---------- Bo'laklangan chiziq (Texnika holati) ---------- */

export function StackBar({ parts, active, onActive }: { parts: Part[]; active: string | null; onActive: (k: string | null) => void }) {
  const t = useT()
  const [ref, W] = useWidth<HTMLDivElement>()
  const total = parts.reduce((a, p) => a + p.value, 0)
  const cur = parts.find((p) => p.key === active)
  let left = 0
  const centers: Record<string, number> = {}
  for (const p of parts) {
    const w = total ? (p.value / total) * W : 0
    centers[p.key] = left + w / 2
    left += w
  }

  return (
    <div ref={ref} className="ivs-stackbar">
      <div className="ivs-stackbar-track" role="img" aria-label={parts.map((p) => `${p.label} ${p.value} (${pct(p.value, total)}%)`).join(', ')}>
        {parts
          .filter((p) => p.value > 0)
          .map((p) => (
            <span
              key={p.key}
              className={active && active !== p.key ? 'is-dim' : undefined}
              style={{ flexGrow: p.value, background: p.color }}
              onPointerEnter={() => onActive(p.key)}
              onPointerLeave={() => onActive(null)}
            />
          ))}
      </div>
      {cur && (
        <Tip x={centers[cur.key]} y={0} width={W}>
          <TipRow color={cur.color} label={cur.label} value={t('{n} ta · {p}%', { n: formatNumber(cur.value), p: pct(cur.value, total) })} />
        </Tip>
      )}
    </div>
  )
}

