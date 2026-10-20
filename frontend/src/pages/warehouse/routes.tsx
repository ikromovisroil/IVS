import type { AppRoute } from '../../routes'
import BasketPage from './BasketPage'
import ExtraDevicesPage from './ExtraDevicesPage'
import MaterialsPage from './MaterialsPage'
import MovementsPage from './MovementsPage'

// "Ombor": qo'shimcha qurilmalar (extra_tex) va materiallar (barn_mat, mat_arxiv, mat_info).
// Texnika sahifalari — pages/technics/routes.tsx.
export const routes: AppRoute[] = [
  { path: '/technics/extra', element: <ExtraDevicesPage /> },
  { path: '/materials', element: <MaterialsPage /> },
  { path: '/materials/basket', element: <BasketPage /> },
  { path: '/materials/movements', element: <MovementsPage /> },
]
