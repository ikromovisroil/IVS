import { lazy } from 'react'
import type { AppRoute } from '../../routes'

// Sahifalar kerak bo'lganda yuklanadi (App.tsx dagi Suspense) — boshlang'ich JS kichrayadi
const DeedPage = lazy(() => import('./DeedPage'))
const ExecuteActivePage = lazy(() => import('./ExecutePages').then((m) => ({ default: m.ExecuteActivePage })))
const ExecuteArchivePage = lazy(() => import('./ExecutePages').then((m) => ({ default: m.ExecuteArchivePage })))
const ExecuteNewPage = lazy(() => import('./ExecutePages').then((m) => ({ default: m.ExecuteNewPage })))
const OrdersIndex = lazy(() => import('./OrdersShell').then((m) => ({ default: m.OrdersIndex })))
const OnBehalfPage = lazy(() => import('./SentPages').then((m) => ({ default: m.OnBehalfPage })))
const SentArchivePage = lazy(() => import('./SentPages').then((m) => ({ default: m.SentArchivePage })))
const SentPage = lazy(() => import('./SentPages').then((m) => ({ default: m.SentPage })))

// ATM arizalari (main/order_views.py: order_sender* va order_receiver*).
// /orders/barn*, /orders/barn-execute*, /orders/confirm* — pages/orders-barn bo'limida.
export const routes: AppRoute[] = [
  { path: '/orders', element: <OrdersIndex /> },
  { path: '/orders/sent', element: <SentPage /> },
  { path: '/orders/sent/archive', element: <SentArchivePage /> },
  { path: '/orders/sent/on-behalf', element: <OnBehalfPage /> },
  { path: '/orders/execute', element: <ExecuteNewPage /> },
  { path: '/orders/execute/active', element: <ExecuteActivePage /> },
  { path: '/orders/execute/archive', element: <ExecuteArchivePage /> },
  { path: '/orders/execute/archive/:id/deed', element: <DeedPage /> },
]
