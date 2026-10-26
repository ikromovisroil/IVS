import { useLayoutEffect, useRef, useState } from 'react'
import { Switch, Widget } from '../../ds'
import { useT } from '../../i18n'
import { useRichEdit } from '../../components/richText'
import type { DocApi } from './doc'

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
