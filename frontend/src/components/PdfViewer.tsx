import { Suspense, lazy, useEffect, useState } from 'react'
import { OPEN_PDF_EVENT } from '../lib/pdf'
import type { PdfRequest } from '../lib/pdf'

/**
 * PDF ni sahifaning o'zida ko'rsatish (brauzerning PDF ko'rgichiga bog'liq emas: ba'zi brauzerlar va ilova ichidagi
 * brauzerlar PDF'ni ochmasdan yuklab oladi). Ko'rsatish kutubxonasi (pdf.js) faqat kerak bo'lganda yuklanadi.
 *
 * Foydalanish: `openPdf(url, 'Sarlavha')` (lib/pdf.ts) — istalgan joydan; `PdfViewerHost` ilova ildizida bir marta qo'yilgan.
 */
const PdfViewerModal = lazy(() => import('./PdfViewerModal'))

export default function PdfViewerHost() {
  const [request, setRequest] = useState<PdfRequest | null>(null)

  useEffect(() => {
    const onOpen = (e: Event) => setRequest((e as CustomEvent<PdfRequest>).detail)
    window.addEventListener(OPEN_PDF_EVENT, onOpen)
    return () => window.removeEventListener(OPEN_PDF_EVENT, onOpen)
  }, [])

  if (!request) return null
  return (
    <Suspense fallback={null}>
      <PdfViewerModal url={request.url} title={request.title} onClose={() => setRequest(null)} />
    </Suspense>
  )
}
