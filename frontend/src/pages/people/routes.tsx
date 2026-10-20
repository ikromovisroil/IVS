import type { AppRoute } from '../../routes'
import EmployeesPage from './EmployeesPage'
import FilesPage from './FilesPage'
import NotificationsPage from './NotificationsPage'
import ProfilePage from './ProfilePage'

// Xodimlar (templates/main/employee.html), Profil (profil.html), Hujjatlar (files.html), Bildirishnomalar (core/notifications.html)
export const routes: AppRoute[] = [
  { path: '/employees', element: <EmployeesPage /> },
  { path: '/profile', element: <ProfilePage /> },
  { path: '/files', element: <FilesPage /> },
  { path: '/notifications', element: <NotificationsPage /> },
]
