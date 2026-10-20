import type { AppRoute } from '../../routes'
import BasketPage from './BasketPage'
import {
  ConfirmArchivePage,
  ConfirmPage,
  ExecuteActivePage,
  ExecuteArchivePage,
  ExecuteNewPage,
  SenderArchivePage,
  SenderOrdersPage,
} from './ListPages'
import MaterialsPage from './MaterialsPage'

// Omborxona (material) arizalari — mijoz tashkiloti ichida. Eski sahifalar: main/order_views.py (order_*_barn, order_agrement*).
export const routes: AppRoute[] = [
  { path: '/orders/barn', element: <SenderOrdersPage /> }, // order_sender_barn
  { path: '/orders/barn/archive', element: <SenderArchivePage /> }, // order_sender_arxiv_barn
  { path: '/orders/barn/new', element: <MaterialsPage /> }, // order_sender_material_barn
  { path: '/orders/barn/basket', element: <BasketPage /> }, // order_sender_basket_barn
  { path: '/orders/barn-execute', element: <ExecuteNewPage /> }, // order_receiver_barn
  { path: '/orders/barn-execute/active', element: <ExecuteActivePage /> }, // order_receiver_activ_barn
  { path: '/orders/barn-execute/archive', element: <ExecuteArchivePage /> }, // order_receiver_arxiv_barn
  { path: '/orders/confirm', element: <ConfirmPage /> }, // order_agrement
  { path: '/orders/confirm/archive', element: <ConfirmArchivePage /> }, // order_agrement_arxiv
]
