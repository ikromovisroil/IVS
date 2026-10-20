import { useLocation } from 'react-router-dom'
import { Button } from '../ds'
import EmptyState from '../components/EmptyState'
import { useT } from '../i18n'
import Page from '../layout/Page'
import { findNav } from '../layout/nav'

// Ishlab chiqishda Django alohida portda; productionda bir domenda.
const LEGACY_ORIGIN = import.meta.env.DEV ? 'http://127.0.0.1:8000' : ''

/** Hali yangi interfeysga ko'chirilmagan bo'lim yoki noma'lum manzil. */
export default function LegacyPage() {
  const t = useT()
  const { pathname } = useLocation()
  const entry = findNav(pathname)

  return (
    <Page icon={entry?.icon ?? 'ri-question-line'} title={entry?.label ?? 'Sahifa topilmadi'}>
      {entry?.legacy ? (
        <EmptyState
          icon="ri-external-link-line"
          title="Bu bo'lim yangi interfeysga hali ko'chirilmagan."
          action={
            <Button variant="stroke" icon="ri-external-link-line" onClick={() => window.location.assign(LEGACY_ORIGIN + entry.legacy)}>
              {t('Eski interfeysda ochish')}
            </Button>
          }
        />
      ) : (
        <EmptyState icon="ri-compass-3-line" title="Bunday sahifa yo'q." />
      )}
    </Page>
  )
}
