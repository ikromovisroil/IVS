import { useCallback, useMemo } from 'react'
import { useSearchParams } from 'react-router-dom'

/**
 * Filtrlar va sahifa raqamini URL query'da saqlaydi (?search=..&page=2).
 * Filtr o'zgarsa sahifa 1 ga qaytadi. Bo'sh qiymat URL'dan o'chiriladi.
 */
export function useUrlFilters<K extends string>(keys: readonly K[]) {
  const [params, setParams] = useSearchParams()

  const filters = useMemo(
    () => Object.fromEntries(keys.map((k) => [k, params.get(k) ?? ''])) as Record<K, string>,
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [params, keys.join('|')],
  )

  const page = Math.max(1, Number(params.get('page')) || 1)
  const hasFilters = keys.some((k) => !!filters[k])

  const setFilter = useCallback(
    (key: K, value: string | number | null | undefined) =>
      setParams(
        (p) => {
          if (value == null || value === '') p.delete(key)
          else p.set(key, String(value))
          p.delete('page')
          return p
        },
        { replace: true },
      ),
    [setParams],
  )

  const setPage = useCallback(
    (n: number) =>
      setParams(
        (p) => {
          if (n <= 1) p.delete('page')
          else p.set('page', String(n))
          return p
        },
        { replace: true },
      ),
    [setParams],
  )

  return { filters, page, hasFilters, setFilter, setPage }
}
