import type { AppRoute } from '../../routes'
import DeedPage from './DeedPage'
import { ExecuteActivePage, ExecuteArchivePage, ExecuteNewPage } from './ExecutePages'
import { OrdersIndex } from './OrdersShell'
import { OnBehalfPage, SentArchivePage, SentPage } from './SentPages'

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
