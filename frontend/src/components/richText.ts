import { useEffect, useRef } from 'react'
import type { RefObject } from 'react'
import './RichText.css'

/**
 * Hujjat matni uchun TinyMCE (eski sahifalardagi muharrir bilan bir xil). Kutubxona Django static'idan
 * (`/static/vendor/tinymce/`) birinchi marta kerak bo'lganda yuklanadi — bundle'ga kirmaydi.
 *
 * Inline rejimda ishlaydi: tahrirlanadigan element sahifadagi o'sha DOM tuguni bo'lib qoladi, shuning uchun
 * sahifalarning mavjud mantig'i (id bo'yicha matn yozish, `innerHTML` o'qish) o'zgarishsiz ishlayveradi.
 * Muharrir faqat "Qo'lda tahrirlash" yoqilganda ishga tushadi va o'chirilganda to'liq olib tashlanadi.
 */
const BASE = '/static/vendor/tinymce'

interface TinyEditor {
  getContent(): string
  remove(): void
  on(name: string, callback: () => void): void
  mode: { set(mode: 'design' | 'readonly'): void }
}
interface TinyMce {
  init(config: Record<string, unknown>): Promise<TinyEditor[]>
}
declare global {
  interface Window {
    tinymce?: TinyMce
  }
}

let loader: Promise<TinyMce> | null = null
function loadTinyMce(): Promise<TinyMce> {
  if (window.tinymce) return Promise.resolve(window.tinymce)
  if (!loader) {
    loader = new Promise<TinyMce>((resolve, reject) => {
      const script = document.createElement('script')
      script.src = `${BASE}/tinymce.min.js`
      script.async = true
      script.onload = () => (window.tinymce ? resolve(window.tinymce) : reject(new Error('TinyMCE topilmadi')))
      script.onerror = () => {
        loader = null                       // keyingi urinishda qayta yuklanadi
        script.remove()
        reject(new Error('TinyMCE yuklanmadi'))
      }
      document.head.appendChild(script)
    })
  }
  return loader
}

const active = new WeakMap<HTMLElement, TinyEditor>()

/** Elementning HTML matni: muharrir yoqilgan bo'lsa TinyMCE tozalagan (data-mce-* siz) variant. */
export function htmlOf(el: HTMLElement | null | undefined): string {
  if (!el) return ''
  const editor = active.get(el)
  return (editor ? editor.getContent() : el.innerHTML).trim()
}

const PLUGINS =
  'preview searchreplace autolink directionality code visualblocks visualchars fullscreen image link table charmap pagebreak nonbreaking anchor insertdatetime advlist lists wordcount help'
const TOOLBAR =
  'undo redo | bold italic underline strikethrough | fontfamily fontsize blocks | alignleft aligncenter alignright alignjustify | outdent indent | numlist bullist | forecolor backcolor removeformat | pagebreak | charmap | fullscreen preview | image link | ltr rtl'

/**
 * `target` elementida TinyMCE doim ishlaydi (uskunalar paneli har doim ko'rinadi); `editable` bo'lmaganda faqat o'qish
 * rejimi ("readonly"), bo'lganda tahrirlash. Qaytgan `toolbar` ref'ini sahifa muharrir ustida alohida `<div>` ga qo'yadi.
 * `ready` — element ichidagi matn joylangach `true` (muharrir shundan keyin ishga tushadi).
 */
export function useRichEdit(target: RefObject<HTMLElement | null>, editable: boolean, ready = true) {
  const toolbar = useRef<HTMLDivElement>(null)
  const editorRef = useRef<TinyEditor | null>(null)
  const fallbackRef = useRef(false)
  const editableRef = useRef(editable)

  // Tahrirlash yoqildi/o'chirildi: muharrir rejimi va "is-editing" belgisi (class'ni React emas, shu yerda boshqaramiz —
  // aks holda React className'ni qayta yozib TinyMCE belgilarini o'chirib yuboradi)
  useEffect(() => {
    editableRef.current = editable
    const el = target.current
    el?.classList.toggle('is-editing', editable)
    if (editorRef.current) editorRef.current.mode.set(editable ? 'design' : 'readonly')
    else if (fallbackRef.current && el) el.contentEditable = editable ? 'true' : 'false'
  }, [target, editable])

  useEffect(() => {
    const el = target.current
    if (!ready || !el) return
    let cancelled = false
    let editor: TinyEditor | undefined

    loadTinyMce()
      .then((tiny) => {
        if (cancelled) return undefined
        return tiny.init({
          target: el,
          inline: true,
          base_url: BASE,
          suffix: '.min',
          skin: document.documentElement.getAttribute('data-theme') === 'dark' ? 'oxide-dark' : 'oxide',
          plugins: PLUGINS,
          menubar: 'edit view insert format tools table help',
          toolbar: TOOLBAR,
          toolbar_mode: 'sliding',
          toolbar_persist: true,
          fixed_toolbar_container_target: toolbar.current ?? undefined,
          contextmenu: 'link image table',
          promotion: false,
          branding: false,
          image_advtab: true,
          noneditable_class: 'mceNonEditable',
          readonly: !editableRef.current,
          setup: (ed: TinyEditor) => {
            editor = ed
            active.set(el, ed)
            ed.on('init', () => {
              editorRef.current = ed
              ed.mode.set(editableRef.current ? 'design' : 'readonly')
            })
          },
        })
      })
      .then((list) => {
        if (cancelled && list?.[0]) {
          active.delete(el)
          list[0].remove()
        }
      })
      .catch(() => {
        // Kutubxona yuklanmasa ham matnni oddiy usulda tahrirlash mumkin bo'lsin
        if (!cancelled) {
          fallbackRef.current = true
          el.contentEditable = editableRef.current ? 'true' : 'false'
        }
      })

    return () => {
      cancelled = true
      editorRef.current = null
      if (editor) {
        active.delete(el)
        // TinyMCE o'chirilganda elementning class'ini ishga tushgandagi holatga qaytaradi: hozirgi class'lar saqlanadi,
        // mce-* belgilari olib tashlanadi.
        const classes = Array.from(el.classList).filter((c) => !c.startsWith('mce-'))
        editor.remove()
        el.className = classes.join(' ')
      }
      if (fallbackRef.current) {
        el.contentEditable = 'false'
        fallbackRef.current = false
      }
    }
  }, [target, ready])

  return { toolbar }
}
