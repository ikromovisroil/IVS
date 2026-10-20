import type { AppRoute } from '../../routes'
import MyTechnicsPage from './MyTechnicsPage'
import TechnicsDetailPage from './TechnicsDetailPage'
import TechnicsPage from './TechnicsPage'

// /technics/extra — pages/warehouse/routes.tsx da (statik yo'l /technics/:id dan ustun turadi)
export const routes: AppRoute[] = [
  { path: '/technics', element: <TechnicsPage /> },
  { path: '/technics/mine', element: <MyTechnicsPage /> },
  { path: '/technics/:id', element: <TechnicsDetailPage /> },
]
