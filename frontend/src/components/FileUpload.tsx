import { useEffect, useId, useMemo, useRef, useState } from 'react'
import type { DragEvent, ReactNode } from 'react'
import { Icon } from '../ds'
import { useT } from '../i18n'
import type { Vars } from '../i18n'
import './FileUpload.css'

interface FileUploadProps {
  label?: ReactNode
  /** Brauzer formati: ".pdf,.docx" yoki "image/jpeg,image/png" */
  accept?: string
  multiple?: boolean
  /** Bitta fayl hajmi chegarasi, MB */
  maxSizeMB?: number
  /** multiple bo'lganda nechta faylgacha */
  maxFiles?: number
  files: File[]
  onChange: (files: File[]) => void
  /** Hudud ichidagi qo'shimcha izoh (masalan, "PDF, 10 MB gacha") — berilmasa accept/maxSizeMB dan tuziladi */
  description?: ReactNode
  hint?: ReactNode
  error?: ReactNode | boolean
  disabled?: boolean
  compact?: boolean
}

const KB = 1024
const MB = KB * 1024

function formatSize(bytes: number): string {
  if (bytes < KB) return `${bytes} B`
  if (bytes < MB) return `${Math.round(bytes / KB)} KB`
  return `${(bytes / MB).toFixed(1).replace('.', ',')} MB`
}

function ext(name: string) {
  return name.split('.').pop()?.toLowerCase() ?? ''
}

/** Fayl turi bo'yicha belgi va rang (tokenlar) */
function kind(file: File): { icon: string; tone: string; label: string } {
  const e = ext(file.name)
  if (file.type.startsWith('image/')) return { icon: 'ri-image-line', tone: 'is-image', label: e.toUpperCase() || 'IMG' }
  if (e === 'pdf') return { icon: 'ri-file-pdf-2-line', tone: 'is-pdf', label: 'PDF' }
  if (e === 'doc' || e === 'docx') return { icon: 'ri-file-word-2-line', tone: 'is-doc', label: e.toUpperCase() }
  if (e === 'xls' || e === 'xlsx' || e === 'csv') return { icon: 'ri-file-excel-2-line', tone: 'is-xls', label: e.toUpperCase() }
  if (e === 'zip' || e === 'rar' || e === '7z') return { icon: 'ri-file-zip-line', tone: 'is-zip', label: e.toUpperCase() }
  return { icon: 'ri-file-line', tone: 'is-other', label: e.toUpperCase() || 'FILE' }
}

/** accept qoidasiga mosmi: kengaytma (.pdf), aniq tur (image/png) yoki guruh (image/*) */
function accepted(file: File, accept?: string) {
  if (!accept) return true
  const e = '.' + ext(file.name)
  return accept
    .split(',')
    .map((s) => s.trim().toLowerCase())
    .some((rule) => (rule.startsWith('.') ? rule === e : rule.endsWith('/*') ? file.type.startsWith(rule.slice(0, -1)) : rule === file.type))
}

function describeAccept(t: (s: string, v?: Vars) => string, accept?: string) {
  if (!accept) return ''
  return accept
    .split(',')
    .map((s) => s.trim())
    .map((s) => (s.startsWith('.') ? s.slice(1).toUpperCase() : s === 'image/*' ? t('Rasm') : s.split('/')[1]?.toUpperCase() ?? s))
    .filter((v, i, a) => a.indexOf(v) === i)
    .join(', ')
}

function Preview({ file }: { file: File }) {
  const url = useMemo(() => URL.createObjectURL(file), [file])
  useEffect(() => () => URL.revokeObjectURL(url), [url])
  return <img src={url} alt="" />
}

/** Fayl yuklash: sudrab tashlash yoki tanlash, tur/hajm tekshiruvi, tanlangan fayllar ro'yxati. */
export default function FileUpload({
  label,
  accept,
  multiple = false,
  maxSizeMB,
  maxFiles,
  files,
  onChange,
  description,
  hint,
  error,
  disabled,
  compact,
}: FileUploadProps) {
  const t = useT()
  const id = useId()
  const input = useRef<HTMLInputElement>(null)
  const [drag, setDrag] = useState(false)
  const [rejected, setRejected] = useState<string[]>([])

  const add = (picked: File[]) => {
    const bad: string[] = []
    const ok = picked.filter((f) => {
      if (!accepted(f, accept)) {
        bad.push(t('{name}: bu turdagi fayl qabul qilinmaydi', { name: f.name }))
        return false
      }
      if (maxSizeMB && f.size > maxSizeMB * MB) {
        bad.push(t('{name}: hajmi {size}, ruxsat {max} MB gacha', { name: f.name, size: formatSize(f.size), max: maxSizeMB }))
        return false
      }
      return true
    })
    let next = multiple ? [...files, ...ok.filter((f) => !files.some((x) => x.name === f.name && x.size === f.size))] : ok.slice(0, 1)
    if (multiple && maxFiles && next.length > maxFiles) {
      bad.push(t("Ko'pi bilan {n} ta fayl; ortiqchasi qo'shilmadi", { n: maxFiles }))
      next = next.slice(0, maxFiles)
    }
    setRejected(bad)
    if (ok.length) onChange(next)
  }

  const onDrop = (e: DragEvent) => {
    e.preventDefault()
    setDrag(false)
    if (!disabled) add(Array.from(e.dataTransfer.files))
  }

  const full = multiple && !!maxFiles && files.length >= maxFiles
  const info =
    description ??
    [describeAccept(t, accept), maxSizeMB ? t('{n} MB gacha', { n: maxSizeMB }) : '', multiple && maxFiles ? t('{n} tagacha', { n: maxFiles }) : ''].filter(Boolean).join(' · ')
  const errorText = typeof error === 'boolean' ? null : error

  return (
    <div className="aui-field ivs-fu">
      {label && (
        <label className="aui-field-label" htmlFor={id}>
          {typeof label === 'string' ? t(label) : label}
        </label>
      )}

      {!(!multiple && files.length) && !full && (
        <div
          className={`ivs-fu-zone${drag ? ' is-drag' : ''}${error ? ' is-error' : ''}${disabled ? ' is-disabled' : ''}${compact ? ' is-compact' : ''}`}
          onDragOver={(e) => {
            e.preventDefault()
            if (!disabled) setDrag(true)
          }}
          onDragLeave={() => setDrag(false)}
          onDrop={onDrop}
        >
          <span className="ivs-fu-icon" aria-hidden="true">
            <Icon name="ri-upload-cloud-2-line" size={compact ? 20 : 24} />
          </span>
          <div className="ivs-fu-text">
            <div className="ivs-fu-title">
              {drag ? (
                t('Faylni qo‘yib yuboring')
              ) : (
                <>
                  {t('Faylni shu yerga sudrab tashlang yoki')}{' '}
                  <button type="button" className="ivs-fu-browse" disabled={disabled} onClick={() => input.current?.click()}>
                    {t('kompyuterdan tanlang')}
                  </button>
                </>
              )}
            </div>
            {info && <div className="ivs-fu-desc">{info}</div>}
          </div>
          <input
            ref={input}
            id={id}
            type="file"
            className="ivs-fu-input"
            accept={accept}
            multiple={multiple}
            disabled={disabled}
            onChange={(e) => {
              add(Array.from(e.target.files ?? []))
              e.target.value = ''
            }}
          />
        </div>
      )}

      {files.length > 0 && (
        <ul className="ivs-fu-list" aria-label={t('Tanlangan fayllar')}>
          {files.map((f, i) => {
            const k = kind(f)
            return (
              <li key={`${f.name}-${f.size}-${i}`} className="ivs-fu-file">
                <span className={`ivs-fu-thumb ${k.tone}`}>{k.tone === 'is-image' ? <Preview file={f} /> : <Icon name={k.icon} size={20} />}</span>
                <span className="ivs-fu-meta">
                  <span className="ivs-fu-name" title={f.name}>
                    {f.name}
                  </span>
                  <span className="ivs-fu-size">
                    {k.label} · {formatSize(f.size)}
                  </span>
                </span>
                {!multiple && (
                  <button type="button" className="ivs-fu-act" onClick={() => input.current?.click()} disabled={disabled} aria-label={t('Boshqa fayl tanlash')}>
                    <Icon name="ri-refresh-line" size={18} />
                  </button>
                )}
                <button
                  type="button"
                  className="ivs-fu-act is-danger"
                  disabled={disabled}
                  aria-label={t('{name} — olib tashlash', { name: f.name })}
                  onClick={() => onChange(files.filter((_, j) => j !== i))}
                >
                  <Icon name="ri-delete-bin-6-line" size={18} />
                </button>
              </li>
            )
          })}
        </ul>
      )}

      {/* bitta fayl tanlangan bo'lsa ham "almashtirish" uchun input kerak */}
      {!multiple && files.length > 0 && (
        <input
          ref={input}
          type="file"
          className="ivs-fu-input"
          accept={accept}
          disabled={disabled}
          onChange={(e) => {
            add(Array.from(e.target.files ?? []))
            e.target.value = ''
          }}
        />
      )}

      {rejected.length > 0 && (
        <ul className="ivs-fu-rejected" role="alert">
          {rejected.map((r) => (
            <li key={r}>
              <Icon name="ri-error-warning-fill" size={14} />
              {r}
            </li>
          ))}
        </ul>
      )}
      {(errorText || hint) && <div className={`aui-field-hint${error ? ' is-error' : ''}`}>{typeof (errorText || hint) === 'string' ? t(String(errorText || hint)) : errorText || hint}</div>}
    </div>
  )
}
