import { Navigate } from 'react-router-dom'
import type { AppRoute } from '../../routes'
import DeedEditPage from './DeedEditPage'
import DeedListPage from './DeedListPage'
import DeedPage, { DeedCodeStatusPage } from './DeedPage'

// "Xabarlar" (templates/base.html): Imzolashga yuborish / Imzolash uchun / Kelishish uchun va arxivlari,
// hujjat sahifasi, tahrirlash (deed_edit) va kod bo'yicha holat (deed_status).
export const routes: AppRoute[] = [
  { path: '/messages', element: <Navigate to="/messages/send" replace /> },
  { path: '/messages/send', element: <DeedListPage key="send" box="send" /> },
  { path: '/messages/send/archive', element: <DeedListPage key="send_archive" box="send_archive" /> },
  { path: '/messages/sign', element: <DeedListPage key="sign" box="sign" /> },
  { path: '/messages/sign/archive', element: <DeedListPage key="sign_archive" box="sign_archive" /> },
  { path: '/messages/agree', element: <DeedListPage key="agree" box="agree" /> },
  { path: '/messages/agree/archive', element: <DeedListPage key="agree_archive" box="agree_archive" /> },
  { path: '/messages/deed/:id', element: <DeedPage /> },
  { path: '/messages/deed/:id/edit', element: <DeedEditPage /> },
  { path: '/messages/status/:code/:id', element: <DeedCodeStatusPage /> },
]
