import { lazy } from 'react'
import type { AppRoute } from '../../routes'

// Sahifalar kerak bo'lganda yuklanadi (App.tsx dagi Suspense) — boshlang'ich JS kichrayadi
const BasketPage = lazy(() => import('./BasketPage'))
const ExtraDevicesPage = lazy(() => import('./ExtraDevicesPage'))
const MaterialsPage = lazy(() => import('./MaterialsPage'))
const MovementsPage = lazy(() => import('./MovementsPage'))

// "Ombor": qo'shimcha qurilmalar (extra_tex) va materiallar (barn_mat, mat_arxiv, mat_info).
// Texnika sahifalari — pages/technics/routes.tsx.
export const routes: AppRoute[] = [
  { path: '/technics/extra', element: <ExtraDevicesPage /> },
  { path: '/materials', element: <MaterialsPage /> },
  { path: '/materials/basket', element: <BasketPage /> },
  { path: '/materials/movements', element: <MovementsPage /> },
]
