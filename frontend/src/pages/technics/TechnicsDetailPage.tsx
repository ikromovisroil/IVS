import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate, useParams } from 'react-router-dom'
import { Button, Widget } from '../../ds'
import Page from '../../layout/Page'
import ConfirmDialog from '../../components/ConfirmDialog'
import DataState from '../../components/DataState'
import { useToast } from '../../components/toast'
import { ApiError, api } from '../../api/client'
import { can, useMe } from '../../auth/me'
import { useT } from '../../i18n'
import type { TechnicsCard, TechnicsRow } from './api'
import { SPA } from './api'
import { AssignDialog, AttachDeviceDialog, DetachDeviceDialog } from './TechnicsDialogs'
import TechnicsDetail, { TechnicsCardView } from './TechnicsDetail'
import TechnicsForm from './TechnicsForm'
import './technics.css'

type Dialog = 'edit' | 'assign' | 'attach' | 'detach' | 'delete'

/**
 * /technics/:id — uskuna sahifasi. Ko'rish doirasidagi uskuna to'liq ma'lumot va amallar bilan,
 * aks holda (QR kod orqali kelganda) main/views.py:technics_detail dagi qisqa ma'lumot.
 */
export default function TechnicsDetailPage() {
  const t = useT()
  const { id } = useParams()
  const me = useMe()
  const navigate = useNavigate()
  const toast = useToast()
  const qc = useQueryClient()
  const [dialog, setDialog] = useState<Dialog | null>(null)
  const canView = can(me, 'main.view_technics')

  const full = useQuery({
    queryKey: ['technics', 'item', id],
    queryFn: () => api<TechnicsRow>(`${SPA}/technics/${id}/`),
    enabled: canView,
    retry: (n, e) => !(e instanceof ApiError && [403, 404].includes(e.status)) && n < 2,
  })
  const useCard = !canView || full.isError
  const card = useQuery({
    queryKey: ['technics', 'card', id],
    queryFn: () => api<TechnicsCard>(`${SPA}/technics/${id}/card/`),
    enabled: useCard,
  })

  const remove = useMutation({
    mutationFn: () => api(`/technics/${id}/`, { method: 'DELETE' }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['technics'] })
      toast("Uskuna muvaffaqiyatli o'chirildi")
      navigate('/technics')
    },
  })

  const item = full.data
  const close = () => setDialog(null)
  const title = item?.name ?? card.data?.name ?? 'Uskuna'

  return (
    <Page
      icon="ri-cpu-line"
      title={title}
      subtitle={item ? [item.group_name, item.category_name].filter(Boolean).join(' / ') : (card.data?.category_name ?? "Texnika ma'lumotlari")}
      actions={
        <Button variant="stroke" size="lg" icon="ri-arrow-left-line" onClick={() => (window.history.length > 1 ? navigate(-1) : navigate('/technics'))}>
          {t('Orqaga')}
        </Button>
      }
    >
      {item ? (
        <>
          {(can(me, 'main.change_technics') || can(me, 'main.delete_technics')) && (
            <div className="aui-toolbar">
              {can(me, 'main.change_technics') && (
                <>
                  <Button variant="stroke" icon="ri-pencil-line" onClick={() => setDialog('edit')}>
                    {t('Tahrirlash')}
                  </Button>
                  <Button variant="stroke" icon="ri-attachment-2" onClick={() => setDialog('assign')}>
                    {t('Biriktirish#ombor')}
                  </Button>
                  <Button variant="stroke" icon="ri-pushpin-line" onClick={() => setDialog('attach')}>
                    {t('Qurilmani biriktirish')}
                  </Button>
                  {item.extra_devices.length > 0 && (
                    <Button variant="stroke" icon="ri-close-circle-line" onClick={() => setDialog('detach')}>
                      {t('Qurilmani bekor qilish')}
                    </Button>
                  )}
                </>
              )}
              <span className="aui-toolbar-grow" />
              {can(me, 'main.delete_technics') && (
                <Button variant="error-lighter" icon="ri-delete-bin-line" onClick={() => setDialog('delete')}>
                  {t("O'chirish")}
                </Button>
              )}
            </div>
          )}
          <Widget icon="ri-cpu-line" title={t('Texnika tafsiloti')} className="ivs-detail-widget">
            <TechnicsDetail t={item} />
          </Widget>
        </>
      ) : useCard ? (
        <DataState isPending={card.isPending} error={card.error} empty={false} emptyText="">
          {card.data && (
            <Widget icon="ri-cpu-line" title={t("Texnika ma'lumotlari")} className="ivs-detail-widget">
              <TechnicsCardView c={card.data} />
            </Widget>
          )}
        </DataState>
      ) : (
        <DataState isPending empty={false} error={null} emptyText="">
          {null}
        </DataState>
      )}

      {item && dialog === 'edit' && <TechnicsForm item={item} onClose={close} />}
      {item && dialog === 'assign' && <AssignDialog t={item} onClose={close} />}
      {item && dialog === 'attach' && <AttachDeviceDialog t={item} me={me} onClose={close} />}
      {item && dialog === 'detach' && <DetachDeviceDialog t={item} onClose={close} />}
      {item && dialog === 'delete' && (
        <ConfirmDialog
          title="Texnikani o'chirish"
          danger
          confirmLabel="O'chirish"
          loading={remove.isPending}
          message={
            <>
              <b>{item.name}</b>
              <p>{t("Texnika o'chirilsinmi? Xodimga biriktirilgan bo'lsa, bo'shatiladi.")}</p>
              {remove.error && <p className="ivs-form-error">{remove.error.message}</p>}
            </>
          }
          onConfirm={() => remove.mutate()}
          onClose={close}
        />
      )}
    </Page>
  )
}
