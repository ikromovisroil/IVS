import { lazy } from 'react'
import { Navigate } from 'react-router-dom'
import type { AppRoute } from '../../routes'

// Sahifalar kerak bo'lganda yuklanadi (App.tsx dagi Suspense) — boshlang'ich JS kichrayadi
const EmployeesStatsPage = lazy(() => import('./EmployeesStatsPage'))
const OrganizationsStatsPage = lazy(() => import('./OrganizationsStatsPage'))
const TechnicsStatsPage = lazy(() => import('./TechnicsStatsPage'))

// Eski sahifalar: /tex_status/, /emp_status/, /org_status/ (main/views.py). Ruxsat: main.status_employee (serverda).
export const routes: AppRoute[] = [
  { path: '/stats', element: <Navigate to="/stats/technics" replace /> },
  { path: '/stats/technics', element: <TechnicsStatsPage /> },
  { path: '/stats/employees', element: <EmployeesStatsPage /> },
  { path: '/stats/organizations', element: <OrganizationsStatsPage /> },
]
