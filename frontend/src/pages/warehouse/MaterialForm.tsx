import FileUpload from '../../components/FileUpload'
import { useState } from 'react'
import type { FormEvent } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Button, Select, TextInput } from '../../ds'
import Modal from '../../components/Modal'
import { useToast } from '../../components/toast'
import { ApiError, api } from '../../api/client'
import { useT } from '../../i18n'
import type { Material } from './api'
import { useMaterialRefs } from './api'

interface Props {
  /** null — yangi material (egasi va tashkiloti — so'rov yuborgan xodim) */
  item: Material | null
  onClose: () => void
}

const num = (v: string | number | null) => (v == null ? null : Number(v))

/** "Material qo'shish" / "Materialni tahrirlash" (MaterialForm / material_update maydonlari, rasm bilan). */
export default function MaterialForm({ item, onClose }: Props) {
  const t = useT()
  const isEdit = item !== null
  const refs = useMaterialRefs()
  const qc = useQueryClient()
  const toast = useToast()
  const [form, setForm] = useState({
    category: item?.category ?? null,
    unit: item?.unit ?? null,
    name: item?.name ?? '',
    code: item?.code ?? '',
    number: item ? String(item.number) : '',
    price: item?.price ?? '',
    year: item?.year ?? '',
  })
  const [image, setImage] = useState<File | null>(null)
  const [errors, setErrors] = useState<Record<string, string>>({})
  const set = <K extends keyof typeof form>(k: K, v: (typeof form)[K]) => setForm((f) => ({ ...f, [k]: v }))

  const save = useMutation({
    mutationFn: () => {
      const fd = new FormData()
      for (const [k, v] of Object.entries(form)) fd.append(k, v == null ? '' : String(v))
      if (image) fd.append('image', image)
      return api(isEdit ? `/materials/${item.id}/` : '/materials/', { method: isEdit ? 'PATCH' : 'POST', body: fd })
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['warehouse'] })
      toast(isEdit ? 'Material tahrirlandi' : "Material qo'shildi")
      onClose()
    },
    onError: (e) => setErrors(e instanceof ApiError ? e.fieldErrors : {}),
  })

  const submit = (e: FormEvent) => {
    e.preventDefault()
    const missing: Record<string, string> = {}
    if (!isEdit && form.category == null) missing.category = t('Kategoriyani tanlang.')
    if (form.unit == null) missing.unit = t('Birligini tanlang.')
    if (!form.name.trim()) missing.name = t('Nomini kiriting.')
    if (!form.code.trim()) missing.code = t('Kodini kiriting.')
    if (form.number === '' || Number(form.number) < 0) missing.number = t('Sonini kiriting.')
    if (!isEdit && form.price === '') missing.price = t('Narxini kiriting.')
    setErrors(missing)
    if (!Object.keys(missing).length) save.mutate()
  }

  const text = (key: 'name' | 'code' | 'number' | 'price' | 'year', label: string, placeholder?: string, inputMode?: 'decimal' | 'numeric') => (
    <TextInput
      label={t(label)}
      placeholder={placeholder && t(placeholder)}
      inputMode={inputMode}
      value={form[key] ?? ''}
      onChange={(e) => {
        const v = e.target.value
        set(key, key === 'number' ? v.replace(/\D/g, '') : key === 'price' ? v.replace(/[^\d.,]/g, '').replace(',', '.') : v)
      }}
      error={!!errors[key]}
      hint={errors[key]}
    />
  )
  const formError = save.error && !Object.keys(errors).length ? save.error.message : null

  return (
    <Modal
      open
      onClose={onClose}
      icon="ri-archive-line"
      title={isEdit ? 'Materialni tahrirlash' : "Material qo'shish"}
      subtitle={isEdit ? 'Soni o\'zgarsa, kirim-chiqim jurnaliga yoziladi.' : '* belgili maydonlar majburiy.'}
      footer={
        <>
          <Button variant="stroke" size="lg" onClick={onClose}>
            {t('Yopish')}
          </Button>
          <Button size="lg" icon="ri-check-line" type="submit" form="material-form" loading={save.isPending}>
            {t('Saqlash')}
          </Button>
        </>
      }
    >
      <form id="material-form" onSubmit={submit} noValidate>
        {formError && (
          <p className="ivs-form-error type-para-sm" role="alert">
            {formError}
          </p>
        )}
        <div className="ivs-form-grid">
          <Select
            label={isEdit ? t('Kategoriya') : t('Kategoriya *')}
            placeholder={t('Tanlang...')}
            options={refs.categoryOptions}
            value={form.category}
            onChange={(v) => set('category', num(v))}
            error={!!errors.category}
            hint={errors.category}
          />
          <Select label={t('Birligi *')} placeholder={t('Tanlang...')} options={refs.unitOptions} value={form.unit} onChange={(v) => set('unit', num(v))} error={!!errors.unit} hint={errors.unit} />
          <div className="is-wide">{text('name', 'Nomi *', 'Masalan: UTP Cat6 kabel')}</div>
          {text('code', 'Kodi (1C) *', '100234')}
          {text('number', 'Soni *', '0', 'numeric')}
          {text('price', isEdit ? 'Narxi' : 'Narxi *', '0', 'decimal')}
          {text('year', 'Yili', '2025', 'numeric')}
          <div className="is-wide">
            <FileUpload
              label="Rasm"
              accept="image/jpeg,image/png"
              maxSizeMB={5}
              files={image ? [image] : []}
              onChange={(fs) => setImage(fs[0] ?? null)}
              error={errors.image || false}
              hint={isEdit && item.image ? 'Yangi rasm tanlansa, eskisi almashtiriladi.' : undefined}
            />
          </div>
        </div>
      </form>
    </Modal>
  )
}
