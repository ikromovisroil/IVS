import { useNavigate } from 'react-router-dom'
import { Button } from '../../ds'
import BarnPage from './BarnPage'
import OrdersList from './OrdersList'
import { useT } from '../../i18n'

// Yuboruvchi — order_sender_barn / order_sender_arxiv_barn
/** Omborxona arizasi savat orqali yaratiladi — tugma materiallar ro'yxatiga olib boradi. */
function CreateButton() {
  const navigate = useNavigate()
  const t = useT()
  return (
    <Button icon="ri-add-line" onClick={() => navigate('/orders/barn/new')}>
      {t('Ariza yaratish')}
    </Button>
  )
}

export function SenderOrdersPage() {
  return (
    <BarnPage
      section="sender"
      actions={<CreateButton />}
    >
      <OrdersList role="barn_sender" mode="sender" columns={['receiver', 'user']} emptyText="Faol ariza yo'q" emptyDescription="«Material» bo'limidan materiallarni savatga qo'shing va ariza yuboring." />
    </BarnPage>
  )
}

export function SenderArchivePage() {
  return (
    <BarnPage section="sender" actions={<CreateButton />}>
      <OrdersList role="barn_sender_archive" mode="view" columns={['receiver', 'user', 'files']} emptyText="Tarixda ariza yo'q" />
    </BarnPage>
  )
}

// Omborxonachi — order_receiver_barn / order_receiver_activ_barn / order_receiver_arxiv_barn
export function ExecuteNewPage() {
  return (
    <BarnPage section="execute">
      <OrdersList role="barn_receiver_new" mode="review" columns={['sender']} actionLabel="Ko'rib chiqish" poll emptyText="Yangi ariza yo‘q" emptyDescription="Omborxonaga kelgan yangi arizalar shu yerda paydo bo‘ladi." />
    </BarnPage>
  )
}

export function ExecuteActivePage() {
  return (
    <BarnPage section="execute">
      <OrdersList role="barn_receiver_active" mode="finish" columns={['sender']} actionLabel="Bajarish" emptyText="Jarayondagi ariza yo‘q" emptyDescription="Qabul qilingan arizalar bajarilguncha shu yerda turadi." />
    </BarnPage>
  )
}

export function ExecuteArchivePage() {
  return (
    <BarnPage section="execute">
      <OrdersList role="barn_receiver_archive" mode="view" columns={['sender', 'files']} emptyText="Tarixda ariza yo'q" />
    </BarnPage>
  )
}

// Tasdiqlovchi — order_agrement / order_agrement_arxiv
export function ConfirmPage() {
  return (
    <BarnPage section="confirm">
      <OrdersList role="barn_agrement" mode="confirm" columns={['sender', 'receiver']} actionLabel="Ko'rib chiqish" emptyText="Tasdiqlashni kutayotgan ariza yo'q" emptyDescription="Omborxonachi tayyorlagan arizalar tasdiqlash uchun shu yerda paydo bo'ladi." />
    </BarnPage>
  )
}

export function ConfirmArchivePage() {
  return (
    <BarnPage section="confirm">
      <OrdersList role="barn_agrement_archive" mode="view" columns={['sender', 'receiver', 'files']} emptyText="Tarixda ariza yo'q" />
    </BarnPage>
  )
}
