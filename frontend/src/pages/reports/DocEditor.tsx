import { useLayoutEffect, useRef, useState } from 'react'
import { Button, Switch, Widget } from '../../ds'
import { useT } from '../../i18n'
import { useRichEdit } from '../../components/richText'
import type { DocApi } from './doc'

/** Hujjatni chop etish (TinyMCE "print" tugmasi o'rnida) — alohida iframe orqali, faqat hujjat matni. */
function printHtml(html: string, landscape: boolean) {
  const frame = document.createElement('iframe')
  frame.setAttribute('aria-hidden', 'true')
  Object.assign(frame.style, { position: 'fixed', width: '0', height: '0', border: '0', right: '0', bottom: '0' })
  document.body.appendChild(frame)
  const w = frame.contentWindow
  if (!w) return
  w.document.open()
  w.document.write(
    `<!doctype html><html><head><meta charset="utf-8"><title>Hujjat</title><style>
      @page { size: A4 ${landscape ? 'landscape' : 'portrait'}; margin: 15mm 10mm 25mm 15mm; }
      body { font-family: 'Times New Roman', serif; }
      table { border-collapse: collapse; width: 100%; table-layout: fixed; }
      tr { page-break-inside: avoid; } td { word-wrap: break-word; }
      table td, table th { border-width: 0.5pt !important; }
    </style></head><body>${html}</body></html>`,
  )
  w.document.close()
  w.focus()
  w.print()
  setTimeout(() => frame.remove(), 1000)
}

interface DocEditorProps {
  doc: DocApi
  /** Boshlang'ich HTML (bir marta yoziladi) */
  template: string
  landscape?: boolean
}

export default function DocEditor({ doc, template, landscape }: DocEditorProps) {
  const t = useT()
  const [editing, setEditing] = useState(false)
  const initial = useRef(template)

  // Shablon faqat birinchi chizishda yoziladi; keyingi o'zgarishlar sahifa tomonidan DOM ga yamaladi.
  useLayoutEffect(() => {
    if (doc.ref.current) doc.ref.current.innerHTML = initial.current
  }, [doc.ref])

  // TinyMCE (eski sahifalardagi muharrir) doim ko'rinadi; "Qo'lda tahrirlash" yoqilganda tahrirlanadi
  const { toolbar } = useRichEdit(doc.ref, editing)

  return (
    <Widget
      icon="ri-file-text-line"
      title={t('Hujjat matni')}
      action={<Switch label={t("Qo'lda tahrirlash")} checked={editing} onChange={setEditing} />}
      className="rep-doc-widget"
    >
      <div ref={toolbar} className="ivs-rich-toolbar" />
      <div className="rep-doc-toolbar" role="toolbar" aria-label={t('Matnni formatlash')}>
        <span className="aui-toolbar-grow" />
        <Button variant="ghost" size="sm" icon="ri-printer-line" onClick={() => printHtml(doc.html(), !!landscape)}>
          {t('Chop etish')}
        </Button>
      </div>
      <div className="rep-doc-scroll">
        <div
          ref={doc.ref}
          className={`rep-paper${landscape ? ' is-landscape' : ''}`}
          role="textbox"
          aria-multiline="true"
          aria-readonly={!editing}
          aria-label={t('Hujjat matni')}
          spellCheck={false}
        />
      </div>
    </Widget>
  )
}
