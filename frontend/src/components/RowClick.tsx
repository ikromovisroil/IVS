import type { MouseEvent, ReactNode } from 'react'
import './RowClick.css'

interface RowClickProps<R> {
  /** DataTable'ga berilgan qatorlar (tartib bir xil, saralash yo'q) */
  rows: R[]
  onOpen: (row: R) => void
  children: ReactNode
}

/** Jadval qatori ustiga bosilganda ochish: qator ichidagi tugma/havola/maydonlar o'z ishini qiladi. */
export default function RowClick<R>({ rows, onOpen, children }: RowClickProps<R>) {
  const handle = (e: MouseEvent<HTMLDivElement>) => {
    const target = e.target as HTMLElement
    if (target.closest('button, a, input, select, textarea, label, [role="button"]')) return
    const tr = target.closest('tbody tr')
    if (!tr) return
    const row = rows[Array.from(tr.parentElement?.children ?? []).indexOf(tr)]
    if (row !== undefined) onOpen(row)
  }
  return (
    <div className="ivs-row-link" onClick={handle}>
      {children}
    </div>
  )
}
