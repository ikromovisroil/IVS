import { useNavigate } from 'react-router-dom'
import { Button } from '../../ds'
import Modal from '../../components/Modal'
import DataState from '../../components/DataState'
import { useT } from '../../i18n'
import { useDeed } from './api'
import DeedStatusPanel from './DeedStatusPanel'

/** "Dalolatnoma holati #KOD" oynasi (ro'yxatdagi "Holati" ustunini bosganda). */
export default function DeedStatusModal({ id, onClose }: { id: number; onClose: () => void }) {
  const deed = useDeed(id)
  const navigate = useNavigate()
  const t = useT()

  return (
    <Modal
      open
      onClose={onClose}
      icon="ri-file-text-line"
      title="Dalolatnoma holati"
      subtitle={deed.data ? `${t(deed.data.status_display)} #${deed.data.code ?? deed.data.id}` : undefined}
      width={1120}
      footer={
        <>
          <Button variant="stroke" size="lg" icon="ri-external-link-line" onClick={() => navigate(`/messages/deed/${id}`)}>
            {t('Batafsil')}
          </Button>
          <Button variant="stroke" size="lg" onClick={onClose}>
            {t('Yopish')}
          </Button>
        </>
      }
    >
      <DataState isPending={deed.isPending} isFetching={deed.isFetching} error={deed.error} empty={false} emptyText="">
        {deed.data && <DeedStatusPanel deed={deed.data} />}
      </DataState>
    </Modal>
  )
}
