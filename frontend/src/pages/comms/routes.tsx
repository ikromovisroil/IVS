import { lazy } from 'react'
import { Navigate } from 'react-router-dom'
import type { AppRoute } from '../../routes'

// Sahifalar kerak bo'lganda yuklanadi (App.tsx dagi Suspense) — boshlang'ich JS kichrayadi
const ChatPage = lazy(() => import('./ChatPage'))
const MeetingsPage = lazy(() => import('./MeetingsPage'))

// Eski sahifalar: /chat/ (chat/views.py) va /chat/meetings/ (chat/meeting_views.py).
// Zoom ruxsati (chat.add_meeting yoki chat.view_meeting) serverda tekshiriladi; menyu bandi nav.ts da yashiriladi.
export const routes: AppRoute[] = [
  { path: '/chat', element: <ChatPage /> },
  { path: '/chat/:id', element: <ChatPage /> },
  // Zoom 1, Zoom 2, ... — har biri alohida host; eski manzillar Zoom 1 ga yo'naltiriladi
  { path: '/meetings', element: <Navigate to="/meetings/1" replace /> },
  { path: '/meetings/past', element: <Navigate to="/meetings/1/past" replace /> },
  { path: '/meetings/:host', element: <MeetingsPage /> },
  { path: '/meetings/:host/past', element: <MeetingsPage /> },
]
