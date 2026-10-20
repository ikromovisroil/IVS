import type { AppRoute } from '../../routes'
import AktReport from './AktReport'
import DocumentReport from './DocumentReport'
import ReestrReport from './ReestrReport'
import ReportsIndex from './ReportsIndex'
import ServiceReport from './ServiceReport'
import SvodReport from './SvodReport'
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
