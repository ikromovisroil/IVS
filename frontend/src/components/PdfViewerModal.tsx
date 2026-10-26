import { useEffect, useRef, useState } from 'react'
import { getDocument, GlobalWorkerOptions } from 'pdfjs-dist'
import type { PDFDocumentProxy } from 'pdfjs-dist'
import workerSrc from 'pdfjs-dist/build/pdf.worker.min.mjs?url'
import { Button } from '../ds'
import { useT } from '../i18n'
import Modal from './Modal'
import './PdfViewer.css'

GlobalWorkerOptions.workerSrc = workerSrc

/** Dev serverda fayl manzili boshqa port (127.0.0.1:8000) bo'lishi mumkin: /media/ yo'li shu saytdan (proksi orqali) olinadi */
function sameOrigin(url: string): string {
  try {
    const u = new URL(url, window.location.href)
    return u.pathname.startsWith('/media/') ? u.pathname + u.search : u.href
  } catch {
    return url
  }
}

interface Props {
  url: string
  title?: string
  onClose: () => void
}

export default function PdfViewerModal({ url, title, onClose }: Props) {
  const t = useT()
  const href = sameOrigin(url)
  const holder = useRef<HTMLDivElement>(null)
  const [state, setState] = useState<'loading' | 'ready' | 'error'>('loading')
  const [pages, setPages] = useState(0)

  useEffect(() => {
    let cancelled = false
    let doc: PDFDocumentProxy | null = null
    const box = holder.current
    if (!box) return
    box.innerHTML = ''

    const task = getDocument({ url: href })
    task.promise
      .then(async (pdf) => {
        doc = pdf
        if (cancelled) return pdf.destroy()
        setPages(pdf.numPages)
        // Aniq (xira bo'lmasligi uchun) chizish: ekran zichligidan qat'i nazar kamida 2x, eni 2400 pikselgacha
        const cssWidth = Math.max(320, box.clientWidth || 880)
        const targetWidth = Math.min(cssWidth * Math.max(window.devicePixelRatio || 1, 2), 2400)
        for (let n = 1; n <= pdf.numPages; n++) {
          const page = await pdf.getPage(n)
          if (cancelled) return
          const base = page.getViewport({ scale: 1 })
          const viewport = page.getViewport({ scale: targetWidth / base.width })
          const canvas = document.createElement('canvas')
          canvas.className = 'ivs-pdf-page'
          canvas.width = Math.floor(viewport.width)
          canvas.height = Math.floor(viewport.height)
          box.appendChild(canvas)
          const ctx = canvas.getContext('2d')
          if (!ctx) continue
          await page.render({ canvasContext: ctx, viewport }).promise
          if (n === 1) setState('ready')
        }
      })
      .catch(() => {
        if (!cancelled) setState('error')
      })

    return () => {
      cancelled = true
      task.destroy()
      doc?.destroy()
    }
  }, [href])

  return (
    <Modal
      open
      onClose={onClose}
      title={title || 'Hujjat'}
      subtitle={pages > 1 ? t('{n} sahifa', { n: pages }) : undefined}
      icon="ri-file-pdf-2-line"
      width={960}
      footer={
        <>
          <a className="ivs-pdf-link" href={href} target="_blank" rel="noopener noreferrer">
            <Button variant="stroke" size="md" icon="ri-external-link-line" tabIndex={-1}>
              {t('Yangi tabda ochish')}
            </Button>
          </a>
          <a className="ivs-pdf-link" href={href} download>
            <Button size="md" icon="ri-download-2-line" tabIndex={-1}>
              {t('Yuklab olish')}
            </Button>
          </a>
        </>
      }
    >
      <div className="ivs-pdf">
        {state === 'loading' && <p className="ivs-pdf-note type-para-sm">{t('PDF yuklanmoqda…')}</p>}
        {state === 'error' && <p className="ivs-pdf-note is-error type-para-sm">{t("PDF'ni ochib bo'lmadi. Yuklab olib ko'ring.")}</p>}
        <div ref={holder} className="ivs-pdf-pages" />
      </div>
    </Modal>
  )
}
