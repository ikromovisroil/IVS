import type { ReactNode } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useLocation } from 'react-router-dom'
import { ApiError, api } from '../api/client'
import type { Me } from '../api/types'
import LoginPage from '../pages/LoginPage'
import { MeContext } from './me'

/** Kirishsiz ham ochiladigan sahifalar (backend'dagi AllowAny endpointlar bilan): PDF QR havolasidagi hujjat holati */
const PUBLIC_PATHS = [/^\/messages\/status\/[^/]+\/\d+\/?$/]

/** /api/v1/me/ — sessiya bo'lmasa kirish sahifasini ko'rsatadi (ommaviy sahifalar foydalanuvchisiz ochiladi). */
export default function RequireAuth({ children }: { children: ReactNode }) {
  const { pathname } = useLocation()
  const isPublic = PUBLIC_PATHS.some((re) => re.test(pathname))
  const me = useQuery({
    queryKey: ['me'],
    queryFn: () => api<Me>('/me/'),
    retry: (n, e) => !(e instanceof ApiError && (e.status === 401 || e.status === 403)) && n < 2,
    staleTime: 5 * 60 * 1000,
  })

  if (me.isPending) return <div className="ivs-boot" aria-busy="true" />
  if (me.isError) {
    if (me.error instanceof ApiError && (me.error.status === 401 || me.error.status === 403)) return isPublic ? <>{children}</> : <LoginPage />
    return (
      <div className="ivs-empty" role="alert">
        {me.error.message}
      </div>
    )
  }
  return <MeContext.Provider value={me.data}>{children}</MeContext.Provider>
}
