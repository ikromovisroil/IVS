import EmptyState from '../components/EmptyState'
import Page from '../layout/Page'

/** Noma'lum manzil (eski interfeys olib tashlangan: hamma bo'lim yangi interfeysda). */
export default function LegacyPage() {
  return (
    <Page icon="ri-question-line" title="Sahifa topilmadi">
      <EmptyState icon="ri-compass-3-line" title="Bunday sahifa yo'q." />
    </Page>
  )
}
