import { lazy } from 'react'
import type { AppRoute } from '../../routes'

// Sahifalar kerak bo'lganda yuklanadi (App.tsx dagi Suspense) — boshlang'ich JS kichrayadi
const AktReport = lazy(() => import('./AktReport'))
const DocumentReport = lazy(() => import('./DocumentReport'))
const ReestrReport = lazy(() => import('./ReestrReport'))
const ReportsIndex = lazy(() => import('./ReportsIndex'))
const ServiceReport = lazy(() => import('./ServiceReport'))
const SvodReport = lazy(() => import('./SvodReport'))
import './reports.css'

// Eski: /document/, /svod/, /reestr/, /akt/, /service/ (main/urls.py)
export const routes: AppRoute[] = [
  { path: '/reports', element: <ReportsIndex /> },
  { path: '/reports/document', element: <DocumentReport /> },
  { path: '/reports/svod', element: <SvodReport /> },
  { path: '/reports/reestr', element: <ReestrReport /> },
  { path: '/reports/akt', element: <AktReport /> },
  { path: '/reports/service', element: <ServiceReport /> },
]
