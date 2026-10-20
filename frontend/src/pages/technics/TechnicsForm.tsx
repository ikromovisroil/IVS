import { useState } from 'react'
import type { FormEvent } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Button, Select, Switch, TextInput } from '../../ds'
import Modal from '../../components/Modal'
import { useToast } from '../../components/toast'
import { ApiError, api } from '../../api/client'
import type { Technics, TechnicsInput, TechnicsStatus } from '../../api/types'
import { useT } from '../../i18n'
import { useTechnicsRefs } from './refs'
import { useStatusOptions } from './status'

interface Props {
  /** null — yangi uskuna, aks holda tahrirlanadigan uskuna */
  item: Technics | null
  onClose: () => void
}

const empty: TechnicsInput = {
  group: null,
  category: null,
  organization: null,
  name: '',
  parametr: '',
  inventory: '',
  serial: '',
  mac: '',
  ip: '',
  year: '',
  price: null,
  address: '',
  is_online: false,
}

function fromItem(t: Technics): TechnicsInput & { status: TechnicsStatus } {
  return {
    group: t.group,
    category: t.category,
    organization: t.organization,
    name: t.name,
    parametr: t.parametr ?? '',
    inventory: t.inventory ?? '',
    serial: t.serial ?? '',
    mac: t.mac ?? '',
    ip: t.ip ?? '',
    year: t.year ?? '',
    price: t.price,
    address: t.address ?? '',
    is_online: t.is_online,
    status: t.status,
  }
}

const num = (v: string | number | null) => (v == null ? null : Number(v))

export default function TechnicsForm({ item, onClose }: Props) {
  const t = useT()
  const statusOptions = useStatusOptions()
  const isEdit = item !== null
  const [form, setForm] = useState(() => (item ? fromItem(item) : { ...empty, status: 'free' as TechnicsStatus }))
  const [errors, setErrors] = useState<Record<string, string>>({})
  const refs = useTechnicsRefs()
  const qc = useQueryClient()
  const toast = useToast()

  const set = <K extends keyof typeof form>(key: K, value: (typeof form)[K]) => setForm((f) => ({ ...f, [key]: value }))

  const save = useMutation({
    mutationFn: () => {
      // Tahrirlashda guruh o'zgarmaydi (TechnicsUpdateSerializer), yaratishda holat avtomatik "Bo'sh"
      const { group, status, ...rest } = form
      const body = isEdit ? { ...rest, status } : { ...rest, group }
      return api<Technics>(isEdit ? `/technics/${item.id}/` : '/technics/', {
        method: isEdit ? 'PATCH' : 'POST',
        body: JSON.stringify({ ...body, price: form.price === '' ? null : form.price }),
      })
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['technics'] })
      toast(isEdit ? 'Uskuna tahrirlandi' : "Uskuna qo'shildi")
      onClose()
    },
    onError: (e) => setErrors(e instanceof ApiError ? e.fieldErrors : {}),
  })

  const submit = (e: FormEvent) => {
    e.preventDefault()
    const missing: Record<string, string> = {}
    if (!isEdit && form.group == null) missing.group = t('Turini tanlang.')
    if (form.category == null) missing.category = t('Kategoriyani tanlang.')
    if (form.organization == null) missing.organization = t('Tashkilotni tanlang.')
    if (!form.name.trim()) missing.name = t('Nomini kiriting.')
    setErrors(missing)
    if (!Object.keys(missing).length) save.mutate()
  }

  const text = (key: 'name' | 'parametr' | 'inventory' | 'serial' | 'mac' | 'ip' | 'year' | 'address', label: string, placeholder?: string, wide = false) => (
    <div className={wide ? 'is-wide' : undefined}>
      <TextInput
        label={t(label)}
        placeholder={placeholder && t(placeholder)}
        value={form[key]}
        onChange={(e) => set(key, e.target.value)}
        error={!!errors[key]}
        hint={errors[key]}
      />
    </div>
  )

  const formError = save.error && !Object.keys(errors).length ? save.error.message : null

  return (
    <Modal
      open
      onClose={onClose}
      icon="ri-computer-line"
      title={isEdit ? 'Uskunani tahrirlash' : "Uskuna qo'shish"}
      subtitle="* belgili maydonlar majburiy."
      footer={
        <>
          <Button variant="stroke" size="lg" onClick={onClose}>
            {t('Yopish')}
          </Button>
          <Button size="lg" icon="ri-check-line" type="submit" form="technics-form" loading={save.isPending}>
            {t('Saqlash')}
          </Button>
        </>
      }
    >
      <form id="technics-form" onSubmit={submit} noValidate>
        {formError && (
          <p className="ivs-form-error type-para-sm" role="alert">
            {formError}
          </p>
        )}
        <div className="ivs-form-grid">
          {isEdit ? (
            <Select
              label={t('Holati')}
              options={statusOptions}
              value={form.status}
              onChange={(v) => v && set('status', v as TechnicsStatus)}
              searchable={false}
              clearable={false}
            />
          ) : (
            <Select
              label={t('Turi *')}
              placeholder={t('Tanlang...')}
              options={refs.groupOptions}
              value={form.group}
              onChange={(v) => setForm((f) => ({ ...f, group: num(v), category: null }))}
              error={!!errors.group}
              hint={errors.group}
            />
          )}
          <Select
            label={t('Kategoriya *')}
            placeholder={t('Tanlang...')}
            options={refs.categoryOptions(isEdit ? item.group : form.group)}
            value={form.category}
            onChange={(v) => set('category', num(v))}
            error={!!errors.category}
            hint={errors.category}
          />
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
          {text('name', 'Nomi *', 'Masalan: Cisco Catalyst 2960-X')}
          {text('parametr', 'Parametr', 'Masalan: 24 port, PoE')}
          {text('inventory', 'Inventar', 'INV-000000')}
          {text('serial', 'Serial', 'Seriya raqami')}
          {text('mac', 'MAC', '00:00:00:00:00:00')}
          {text('ip', 'IP', '192.168.0.1')}
          {text('year', 'Yil', '2024')}
          <TextInput
            label={t('Narxi')}
            placeholder="0"
            inputMode="decimal"
            value={form.price ?? ''}
            onChange={(e) => set('price', e.target.value.replace(/[^\d.]/g, ''))}
            error={!!errors.price}
            hint={errors.price}
          />
          {text('address', 'Joylashuvi', 'Manzil yoki xona raqami', true)}
          <div className="is-wide ivs-form-note">
            <Switch
              label={t('Tarmoq qurilmasi')}
              sub={t("Qurilma tarmoqqa ulangan bo'lsa yoqing.")}
              checked={form.is_online}
              onChange={(checked) => set('is_online', checked)}
            />
          </div>
        </div>
      </form>
    </Modal>
  )
}
