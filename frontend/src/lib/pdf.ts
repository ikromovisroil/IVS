/**
 * PDF ni ochish.
 *  - Oddiy brauzerda (Chrome, Edge, Firefox, Safari: `navigator.pdfViewerEnabled`) — brauzerning o'z PDF ko'rgichida yangi
 *    tabda ochiladi (aniq, qidirish, chop etish va yuklab olish bilan).
 *  - PDF ko'rgichi yo'q yoki o'chirilgan brauzerda (telefon brauzerlari, ilova ichidagi Electron brauzerlari: ular
 *    `pdfViewerEnabled = true` desa ham PDF'ni yuklab oladi) sahifaning o'zidagi ko'rgich ochiladi
 *    (components/PdfViewer.tsx ilova ildizida eshitadi).
 */
export const OPEN_PDF_EVENT = 'ivs:open-pdf'

export interface PdfRequest {
  url: string
  title?: string
}

const embeddedBrowser = () => /\b(Electron|Claude)\//.test(navigator.userAgent)

export function openPdf(url: string, title?: string) {
  if (navigator.pdfViewerEnabled && !embeddedBrowser()) {
    window.open(url, '_blank', 'noopener')
    return
  }
  window.dispatchEvent(new CustomEvent<PdfRequest>(OPEN_PDF_EVENT, { detail: { url, title } }))
}
