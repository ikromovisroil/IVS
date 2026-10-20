import FileUpload from '../../components/FileUpload'

interface Props {
  label: string
  hint?: string
  error?: string
  accept: string
  multiple?: boolean
  files: File[]
  onChange: (files: File[]) => void
  /** Eski API bilan moslik uchun qoldirilgan; FileUpload o'z matnini ko'rsatadi */
  buttonLabel?: string
}

/** Hujjat fayli va ilovalari: umumiy FileUpload (asosiy PDF — 1 ta, ilovalar — 10 tagacha, har biri 10 MB gacha). */
export default function FilePicker({ label, hint, error, accept, multiple, files, onChange }: Props) {
  return (
    <FileUpload
      label={label}
      accept={accept}
      multiple={multiple}
      maxFiles={multiple ? 10 : undefined}
      maxSizeMB={10}
      files={files}
      onChange={onChange}
      hint={hint}
      error={error}
      compact={multiple}
    />
  )
}
