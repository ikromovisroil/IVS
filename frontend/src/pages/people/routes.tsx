import { lazy } from 'react'
import type { AppRoute } from '../../routes'

// Sahifalar kerak bo'lganda yuklanadi (App.tsx dagi Suspense) — boshlang'ich JS kichrayadi
const EmployeesPage = lazy(() => import('./EmployeesPage'))
const FilesPage = lazy(() => import('./FilesPage'))
const NotificationsPage = lazy(() => import('./NotificationsPage'))
const ProfilePage = lazy(() => import('./ProfilePage'))

// Xodimlar (templates/main/employee.html), Profil (profil.html), Hujjatlar (files.html), Bildirishnomalar (core/notifications.html)
export const routes: AppRoute[] = [
  { path: '/employees', element: <EmployeesPage /> },
  { path: '/profile', element: <ProfilePage /> },
  { path: '/files', element: <FilesPage /> },
  { path: '/notifications', element: <NotificationsPage /> },
]
