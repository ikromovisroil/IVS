import type { ReactNode } from 'react'
import EmptyState from './EmptyState'

interface DataStateProps {
  isPending: boolean
  isFetching?: boolean
  error: Error | null
  empty: boolean
  /** Bo'sh ro'yxat sarlavhasi */
  emptyText: ReactNode
  /** Bo'sh ro'yxat uchun izoh va keyingi qadam (ixtiyoriy) */
  emptyDescription?: ReactNode
  emptyAction?: ReactNode
  emptyIcon?: string
  children: ReactNode
}

/** Ro'yxat holatlari: xato / bo'sh / yuklanmoqda (eski ma'lumot xira ko'rinadi) / tayyor. */
export default function DataState({
  isPending,
  isFetching,
  error,
  empty,
  emptyText,
  emptyDescription,
  emptyAction,
  emptyIcon,
  children,
}: DataStateProps) {
  if (error) {
    return <EmptyState tone="error" title="Ma'lumotni yuklab bo'lmadi" description={error.message} />
  }
  if (isPending) {
    return (
      <div className="ivs-skeleton-rows" aria-busy="true" aria-label="Yuklanmoqda">
        {[0, 1, 2, 3, 4].map((i) => (
          <span key={i} />
        ))}
      </div>
    )
  }
  if (empty) return <EmptyState icon={emptyIcon} title={emptyText} description={emptyDescription} action={emptyAction} />
  return <div className={isFetching ? 'ivs-loading' : undefined}>{children}</div>
}
