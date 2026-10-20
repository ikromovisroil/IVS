import type { AppRoute } from '../../routes'
import ChatPage from './ChatPage'
import MeetingsPage from './MeetingsPage'

// Eski sahifalar: /chat/ (chat/views.py) va /chat/meetings/ (chat/meeting_views.py).
// Zoom ruxsati (chat.add_meeting yoki chat.view_meeting) serverda tekshiriladi; menyu bandi nav.ts da yashiriladi.
export const routes: AppRoute[] = [
  { path: '/chat', element: <ChatPage /> },
  { path: '/chat/:id', element: <ChatPage /> },
  { path: '/meetings', element: <MeetingsPage /> },
  { path: '/meetings/past', element: <MeetingsPage /> },
]
