import { useState } from 'react'
import { Button, Icon } from '../../ds'
import Modal from '../../components/Modal'
import { mediaPath } from './api'
import { useT } from '../../i18n'

/** Kichik rasm; bosilganda kattalashtirilgan ko'rinish (eski "Rasm" modali). Rasm bo'lmasa — "Rasm yo'q". */
export default function MaterialImage({ src, name }: { src: string | null; name: string }) {
  const t = useT()
  const [open, setOpen] = useState(false)
  const url = mediaPath(src)
  if (!url)
    return (
      <span className="ob-thumb-empty" title={t("Rasm yo'q")} aria-label={t("Rasm yo'q")}>
        <Icon name="ri-image-line" size={18} />
      </span>
    )
  return (
    <>
      <button type="button" className="ob-thumb" onClick={() => setOpen(true)} aria-label={t('{name} — rasmni kattalashtirish', { name })}>
        <img src={url} alt="" loading="lazy" />
      </button>
      {open && (
        <Modal
          open
          onClose={() => setOpen(false)}
          icon="ri-image-line"
          title="Rasm"
          subtitle={name}
          footer={
            <Button variant="stroke" size="lg" onClick={() => setOpen(false)}>
              {t('Yopish')}
            </Button>
          }
        >
          <img className="ob-preview" src={url} alt={name} />
        </Modal>
      )}
    </>
  )
}
