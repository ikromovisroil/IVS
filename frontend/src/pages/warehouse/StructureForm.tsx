import { useState } from 'react'
import type { FormEvent } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Button, Select, TextInput } from '../../ds'
import Modal from '../../components/Modal'
import { useToast } from '../../components/toast'
import { ApiError, api } from '../../api/client'
import type { TechnicsStatus } from '../../api/types'
import { useT } from '../../i18n'
import { useTechnicsRefs } from '../technics/refs'
import { useStatusOptions } from '../technics/status'
import type { Structure } from './api'
import { useStructureCategories } from './api'

interface Props {
  /** null — yangi qurilma */
  item: Structure | null
  onClose: () => void
}

type Text = 'name' | 'parametr' | 'inventory' | 'serial' | 'year' | 'price'
const num = (v: string | number | null) => (v == null ? null : Number(v))

/** "Qurilma qo'shish" / "Qurilmani tahrirlash" (ExtraTechnicsForm / extra_tex_update maydonlari). */
export default function StructureForm({ item, onClose }: Props) {
  const t = useT()
  const statusOptions = useStatusOptions()
  const isEdit = item !== null
  const refs = useTechnicsRefs()
  const categories = useStructureCategories()
  const qc = useQueryClient()
  const toast = useToast()
  const [form, setForm] = useState({
    organization: item?.organization ?? null,
    category: item?.category ?? null,
    status: (item?.status ?? 'free') as TechnicsStatus,
    name: item?.name ?? '',
    parametr: item?.parametr ?? '',
    inventory: item?.inventory ?? '',
    serial: item?.serial ?? '',
    year: item?.year ?? '',
    price: item?.price ?? '',
  })
  const [errors, setErrors] = useState<Record<string, string>>({})
  const set = <K extends keyof typeof form>(k: K, v: (typeof form)[K]) => setForm((f) => ({ ...f, [k]: v }))

  const save = useMutation({
    mutationFn: () => {
      const { status, ...rest } = form
      const body = { ...rest, price: form.price === '' ? null : form.price, ...(isEdit ? { status } : {}) }
      return api(isEdit ? `/structures/${item.id}/` : '/structures/', { method: isEdit ? 'PATCH' : 'POST', body: JSON.stringify(body) })
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['warehouse'] })
      qc.invalidateQueries({ queryKey: ['technics'] })
      toast(isEdit ? 'Qurilma tahrirlandi' : "Qurilma qo'shildi")
      onClose()
    },
    onError: (e) => setErrors(e instanceof ApiError ? e.fieldErrors : {}),
  })

  const submit = (e: FormEvent) => {
    e.preventDefault()
    const missing: Record<string, string> = {}
    if (form.organization == null) missing.organization = t('Tashkilotni tanlang.')
    if (form.category == null) missing.category = t('Kategoriyani tanlang.')
    if (!form.name.trim()) missing.name = t('Nomini kiriting.')
    setErrors(missing)
    if (!Object.keys(missing).length) save.mutate()
  }

  const text = (key: Text, label: string, placeholder?: string, inputMode?: 'decimal' | 'numeric') => (
    <TextInput
      label={t(label)}
      placeholder={placeholder && t(placeholder)}
      inputMode={inputMode}
      value={form[key] ?? ''}
      onChange={(e) => set(key, key === 'price' ? e.target.value.replace(/[^\d.,]/g, '').replace(',', '.') : e.target.value)}
      error={!!errors[key]}
      hint={errors[key]}
    />
  )
  const formError = save.error && !Object.keys(errors).length ? save.error.message : null

  return (
    <Modal
      open
      onClose={onClose}
      icon="ri-usb-line"
      title={isEdit ? 'Qurilmani tahrirlash' : "Qurilma qo'shish"}
      subtitle="* belgili maydonlar majburiy."
      footer={
        <>
          <Button variant="stroke" size="lg" onClick={onClose}>
            {t('Yopish')}
          </Button>
          <Button size="lg" icon="ri-check-line" type="submit" form="structure-form" loading={save.isPending}>
            {t('Saqlash')}
          </Button>
        </>
      }
    >
      <form id="structure-form" onSubmit={submit} noValidate>
        {formError && (
          <p className="ivs-form-error type-para-sm" role="alert">
            {formError}
          </p>
        )}
        <div className="ivs-form-grid">
          <div className="is-wide">
            <Select
              label={t('Tashkilot *')}
              placeholder={t('Tanlang...')}
              options={refs.organizationOptions}
              value={form.organization}
              onChange={(v) => set('organization', num(v))}
              error={!!errors.organization}
              hint={errors.organization}
            />
          </div>
          <Select
            label={t('Kategoriya *')}
            placeholder={t('Tanlang...')}
            options={categories}
            value={form.category}
            onChange={(v) => set('category', num(v))}
            error={!!errors.category}
            hint={errors.category}
          />
          {isEdit ? (
            <Select label={t('Holati')} options={statusOptions} value={form.status} searchable={false} clearable={false} onChange={(v) => v && set('status', v as TechnicsStatus)} />
          ) : (
            text('name', 'Nomi *', 'Masalan: Dell P2422H')
          )}
          {isEdit && text('name', 'Nomi *')}
          {text('parametr', 'Parametr', 'Masalan: 24", IPS')}
          {text('inventory', 'Inventar', 'INV-000000')}
          {text('serial', 'Serial', 'Seriya raqami')}
          {text('year', 'Yili', '2024', 'numeric')}
          {text('price', 'Narxi', '0', 'decimal')}
        </div>
      </form>
    </Modal>
  )
}
