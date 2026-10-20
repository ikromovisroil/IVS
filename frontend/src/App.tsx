import { Suspense } from 'react'
import { MutationCache, QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import RequireAuth from './auth/RequireAuth'
import { useMe } from './auth/me'
import SettingsProvider from './components/SettingsProvider'
import ToastProvider from './components/ToastProvider'
import LegacyPage from './pages/LegacyPage'
import { visibleNav } from './layout/nav'
import { BASENAME } from './routes'
import type { AppRoute } from './routes'
import { routes as comms } from './pages/comms/routes'
import { routes as dashboard } from './pages/dashboard/routes'
import { routes as messages } from './pages/messages/routes'
import { routes as orders } from './pages/orders/routes'
import { routes as ordersBarn } from './pages/orders-barn/routes'
import { routes as people } from './pages/people/routes'
import { routes as reports } from './pages/reports/routes'
import { routes as stats } from './pages/stats/routes'
import { routes as technics } from './pages/technics/routes'
import { routes as warehouse } from './pages/warehouse/routes'

const queryClient: QueryClient = new QueryClient({
  defaultOptions: { queries: { refetchOnWindowFocus: false } },
  // Har qanday o'zgarishdan keyin (qabul qilish, imzolash, o'qildi...) yon menyudagi sonlar darhol yangilansin
  mutationCache: new MutationCache({ onSuccess: () => queryClient.invalidateQueries({ queryKey: ['badges'] }) }),
})

const ROUTES: AppRoute[] = [...dashboard, ...orders, ...ordersBarn, ...messages, ...technics, ...warehouse, ...people, ...reports, ...stats, ...comms]

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <SettingsProvider>
        <ToastProvider>
          <BrowserRouter basename={BASENAME}>
            <RequireAuth>
              {/* Bo'lim sahifalari lazy yuklanadi; navigatsiyada router startTransition ishlatadi — eski sahifa ko'rinib turadi */}
              <Suspense fallback={<div className="ivs-boot" aria-busy="true" />}>
              <Routes>
                <Route path="/" element={<Home />} />
                {ROUTES.map((r) => (
                  <Route key={r.path} path={r.path} element={r.element} />
                ))}
                <Route path="*" element={<LegacyPage />} />
              </Routes>
              </Suspense>
            </RequireAuth>
          </BrowserRouter>
        </ToastProvider>
      </SettingsProvider>
    </QueryClientProvider>
  )
}

/** Bosh sahifa: admin — umumiy dashboard, qolganlar — Arizalar */
function Home() {
  const me = useMe()
  // Admin — umumiy dashboard; boshqa rollar — o'z menyusining birinchi bandi
  const first = visibleNav(me)[0]?.items[0]?.path
  return <Navigate to={first ?? '/profile'} replace />
}
