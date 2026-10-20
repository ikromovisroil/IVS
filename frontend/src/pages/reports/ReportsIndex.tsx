import { Navigate } from 'react-router-dom'
import EmptyState from '../../components/EmptyState'
import Page from '../../layout/Page'
import { useT } from '../../i18n'
import { useReportsMeta } from './api'
import { REPORT_TABS } from './tabs'

/** /reports — foydalanuvchi ko'ra oladigan birinchi hisobotga yo'naltiradi. */
export default function ReportsIndex() {
  const t = useT()
  const meta = useReportsMeta()
  const first = REPORT_TABS.find((x) => meta.data?.reports[x.kind])
  if (first) return <Navigate to={first.path} replace />

  return (
    <Page icon="ri-bar-chart-box-line" title="Hisobotlar">
      {meta.isError ? (
        <div className="ivs-empty" role="alert">{t(meta.error.message)}</div>
      ) : meta.isPending ? (
        <div className="ivs-empty" aria-busy="true">{t('Yuklanmoqda…')}</div>
      ) : (
        <EmptyState icon="ri-lock-line" title="Ruxsat yo'q" description="Hisobotlar uchun ruxsatingiz yo'q." />
      )}
    </Page>
  )
}
