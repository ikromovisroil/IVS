import { lazy } from 'react'
import type { AppRoute } from '../../routes'

// Sahifalar kerak bo'lganda yuklanadi (App.tsx dagi Suspense) — boshlang'ich JS kichrayadi
const MyTechnicsPage = lazy(() => import('./MyTechnicsPage'))
const TechnicsDetailPage = lazy(() => import('./TechnicsDetailPage'))
const TechnicsPage = lazy(() => import('./TechnicsPage'))

// /technics/extra — pages/warehouse/routes.tsx da (statik yo'l /technics/:id dan ustun turadi)
export const routes: AppRoute[] = [
  { path: '/technics', element: <TechnicsPage /> },
  { path: '/technics/mine', element: <MyTechnicsPage /> },
  { path: '/technics/:id', element: <TechnicsDetailPage /> },
]
