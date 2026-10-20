import { createContext, useContext } from 'react'
import type { Me } from '../api/types'

export const MeContext = createContext<Me | null>(null)

export function useMe(): Me {
  const me = useContext(MeContext)
  if (!me) throw new Error('useMe() faqat RequireAuth ichida ishlaydi')
  return me
}

/** Django ruxsati: can(me, 'main.view_technics'). Superuser hamma narsaga ruxsatli. */
export function can(me: Me, perm: string): boolean {
  return me.is_superuser || me.permissions.includes(perm)
}

/** SSO orqali kirish (main/sso_views.py: sso_start_login). */
export const SSO_LOGIN_URL = '/sso/start/login/'
export const LOGOUT_URL = '/sso/logout/'
