import { lazy } from 'react'
import type { AppRoute } from '../../routes'

// Sahifalar kerak bo'lganda yuklanadi (App.tsx dagi Suspense) — boshlang'ich JS kichrayadi
const DashboardPage = lazy(() => import('./DashboardPage'))

export const routes: AppRoute[] = [{ path: '/dashboard', element: <DashboardPage /> }]
