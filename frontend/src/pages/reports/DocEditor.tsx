import { useLayoutEffect, useRef, useState } from 'react'
import { Button, Switch, Widget } from '../../ds'
import { useT } from '../../i18n'
import type { DocApi } from './doc'

const TOOLS: { cmd: string; icon: string; label: string }[] = [
  { cmd: 'undo', icon: 'ri-arrow-go-back-line', label: 'Bekor qilish' },
  { cmd: 'redo', icon: 'ri-arrow-go-forward-line', label: 'Qaytarish' },
  { cmd: 'bold', icon: 'ri-bold', label: 'Qalin' },
  { cmd: 'italic', icon: 'ri-italic', label: 'Kursiv' },
  { cmd: 'underline', icon: 'ri-underline', label: 'Tagiga chizilgan' },
  { cmd: 'strikeThrough', icon: 'ri-strikethrough', label: 'Ustidan chizilgan' },
  { cmd: 'justifyLeft', icon: 'ri-align-left', label: 'Chapga' },
  { cmd: 'justifyCenter', icon: 'ri-align-center', label: 'Markazga' },
  { cmd: 'justifyRight', icon: 'ri-align-right', label: "O'ngga" },
  { cmd: 'justifyFull', icon: 'ri-align-justify', label: 'Ikki tomonga' },
  { cmd: 'insertOrderedList', icon: 'ri-list-ordered', label: "Raqamli ro'yxat" },
  { cmd: 'insertUnorderedList', icon: 'ri-list-unordered', label: "Ro'yxat" },
  { cmd: 'removeFormat', icon: 'ri-format-clear', label: 'Formatni tozalash' },
]

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

  const exec = (cmd: string) => {
    doc.ref.current?.focus()
    document.execCommand(cmd)
  }

  return (
    <Widget
      icon="ri-file-text-line"
      title={t('Hujjat matni')}
      action={<Switch label={t("Qo'lda tahrirlash")} checked={editing} onChange={setEditing} />}
      className="rep-doc-widget"
    >
      <div className="rep-doc-toolbar" role="toolbar" aria-label={t('Matnni formatlash')}>
        {TOOLS.map((tool) => (
          <Button
            key={tool.cmd}
            variant="ghost"
            size="sm"
            icon={tool.icon}
            iconOnly
            aria-label={t(tool.label)}
            title={t(tool.label)}
            disabled={!editing}
            onMouseDown={(e) => e.preventDefault()}
            onClick={() => exec(tool.cmd)}
          />
        ))}
        <span className="aui-toolbar-grow" />
        <Button variant="ghost" size="sm" icon="ri-printer-line" onClick={() => printHtml(doc.html(), !!landscape)}>
          {t('Chop etish')}
        </Button>
      </div>
      <div className="rep-doc-scroll">
        <div
          ref={doc.ref}
          className={`rep-paper${landscape ? ' is-landscape' : ''}${editing ? ' is-editing' : ''}`}
          contentEditable={editing}
          suppressContentEditableWarning
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
