import type { ReactNode } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ApiError, api } from '../api/client'
import type { Me } from '../api/types'
import LoginPage from '../pages/LoginPage'
import { MeContext } from './me'

/** /api/v1/me/ — sessiya bo'lmasa kirish sahifasini ko'rsatadi. */
export default function RequireAuth({ children }: { children: ReactNode }) {
  const me = useQuery({
    queryKey: ['me'],
    queryFn: () => api<Me>('/me/'),
    retry: (n, e) => !(e instanceof ApiError && (e.status === 401 || e.status === 403)) && n < 2,
    staleTime: 5 * 60 * 1000,
  })

  if (me.isPending) return <div className="ivs-boot" aria-busy="true" />
  if (me.isError) {
    if (me.error instanceof ApiError && (me.error.status === 401 || me.error.status === 403)) return <LoginPage />
    return (
      <div className="ivs-empty" role="alert">
        {me.error.message}
      </div>
    )
  }
  return <MeContext.Provider value={me.data}>{children}</MeContext.Provider>
}
