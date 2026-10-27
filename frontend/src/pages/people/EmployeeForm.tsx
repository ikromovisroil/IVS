import { useState } from 'react'
import type { FormEvent } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Button, Radio, SegmentedControl, Select, TextInput } from '../../ds'
import Modal from '../../components/Modal'
import { useToast } from '../../components/toast'
import { ApiError, api } from '../../api/client'
import { can, useMe } from '../../auth/me'
import { useT } from '../../i18n'
import { usePeopleRefs, useStructure, toId } from './api'
import type { EmployeeRow } from './api'

interface Props {
  /** null — yangi xodim */
  item: EmployeeRow | null
  onClose: () => void
}

type Mode = 'manual' | 'gateway'
type TechnicsAction = 'with' | 'stay' | 'release'

const TECHNICS_ACTIONS: { value: TechnicsAction; label: string }[] = [
  { value: 'with', label: "Texnikalar bilan (xodim bilan birga ko'chsin)" },
  { value: 'stay', label: 'Texnikalar activ holda departamentda qolsin' },
  { value: 'release', label: "Texnikalar bo'shatilib skladga qaytarilsin" },
]

const PINFL_RE = /^\d{14}$/

/** Xodim qo'shish / tahrirlash oynasi (saytdagi "Xodim qo'shish" va "Xodimni tahrirlash" modallari). */
export default function EmployeeForm({ item, onClose }: Props) {
  const isEdit = item !== null
  const t = useT()
  const toast = useToast()
  const qc = useQueryClient()
  const me = useMe()
  const refs = usePeopleRefs()
  // Tahrirlashda tashkilotni faqat "Barcha tashkilotlar" huquqi bor xodim o'zgartira oladi (server ham tekshiradi)
  const canChangeOrg = can(me, 'main.all_organization')
  const [mode, setMode] = useState<Mode>('manual')
  const [form, setForm] = useState({
    pinfl: item?.pinfl ?? '',
    first_name: item?.first_name ?? '',
    last_name: item?.last_name ?? '',
    father_name: item?.father_name ?? '',
    organization: item?.organization ?? null,
    region: item?.region ?? null, // faqat departamentlarni saralash uchun (xodimning hududi bo'limdan olinadi)
    department: item?.department ?? null,
    directorate: item?.directorate ?? null,
    division: item?.division ?? null,
    rank: item?.rank ?? null,
    phone: item?.phone ?? '',
    technics_action: 'release' as TechnicsAction,
  })
  const [errors, setErrors] = useState<Record<string, string>>({})
  // Tahrirlashda departamentlar xodimning tashkiloti va hududi bo'yicha (saytdagidek)
  const structure = useStructure(form.organization, form.region, form.department, form.directorate)
  // Departament faqat tashkilot VA hudud tanlangandan keyin chiqadi (tahrirlashda ular xodimniki bilan oldindan to'ldirilgan)
  const structureReady = !!form.organization && !!form.region

  const set = <K extends keyof typeof form>(key: K, value: (typeof form)[K]) => setForm((f) => ({ ...f, [key]: value }))

  const done = (text: string) => {
    qc.invalidateQueries({ queryKey: ['people', 'employees'] })
    toast(text)
    onClose()
  }

  const save = useMutation({
    mutationFn: async () => {
      const body: Record<string, unknown> = {
        first_name: form.first_name.trim(),
        last_name: form.last_name.trim(),
        father_name: form.father_name.trim(),
        department: form.department,
        directorate: form.directorate,
        division: form.division,
        rank: form.rank,
        phone: form.phone.trim(),
      }
      if (isEdit) {
        if (form.pinfl.trim()) body.pinfl = form.pinfl.trim()
        body.technics_action = form.technics_action
        if (form.organization != null && form.organization !== item.organization) body.organization = form.organization
        return api<EmployeeRow>(`/employees/${item.id}/`, { method: 'PATCH', body: JSON.stringify(body) })
      }
      return api<EmployeeRow>('/employees/', {
        method: 'POST',
        body: JSON.stringify({ ...body, pinfl: form.pinfl.trim(), organization: form.organization }),
      })
    },
    onSuccess: (emp) => done(isEdit ? "Xodim ma'lumotlari yangilandi" : t("Xodim muvaffaqiyatli qo'shildi (login: {login})", { login: emp.username })),
    onError: (e) => setErrors(e instanceof ApiError ? e.fieldErrors : {}),
  })

  const gateway = useMutation({
    mutationFn: () => api<{ detail: string }>('/spa/people/employees/gateway-create/', { method: 'POST', body: JSON.stringify({ pinfl: form.pinfl.trim() }) }),
    onSuccess: (r) => {
      // Server: "<F.I.O> xodim yaratildi" — ism serverdan, qolgani tarjima qilinadi
      const m = /^(.*) xodim yaratildi$/.exec(r.detail)
      done(m ? t('{name} xodim yaratildi', { name: m[1] }) : r.detail)
    },
  })

  const submit = (e: FormEvent) => {
    e.preventDefault()
    const missing: Record<string, string> = {}
    const pinfl = form.pinfl.trim()
    if (mode === 'gateway' && !isEdit) {
      if (!PINFL_RE.test(pinfl)) missing.pinfl = t('PINFL 14 xonali raqamdan iborat bo‘lishi kerak.')
      setErrors(missing)
      if (!Object.keys(missing).length) gateway.mutate()
      return
    }
    if (pinfl && !PINFL_RE.test(pinfl)) missing.pinfl = t('PINFL 14 xonali raqamdan iborat bo‘lishi kerak.')
    if (!form.first_name.trim()) missing.first_name = t('Ismini kiriting.')
    if (!form.last_name.trim()) missing.last_name = t('Familiyasini kiriting.')
    if (!isEdit && form.organization == null) missing.organization = t('Tashkilotni tanlang.')
    if (form.region == null) missing.region = t('Hududni tanlang.')   // tashkilot va hudud majburiy (qo'shishda ham, tahrirlashda ham)
    setErrors(missing)
    if (!Object.keys(missing).length) save.mutate()
  }

  const text = (key: 'pinfl' | 'first_name' | 'last_name' | 'father_name' | 'phone', label: string, placeholder: string, extra?: { inputMode?: 'numeric' | 'tel'; maxLength?: number }) => (
    <TextInput
      label={t(label)}
      placeholder={t(placeholder)}
      value={form[key]}
      onChange={(e) => set(key, key === 'pinfl' ? e.target.value.replace(/\D/g, '') : e.target.value)}
      error={!!errors[key]}
      hint={errors[key]}
      {...extra}
    />
  )

  const pending = save.isPending || gateway.isPending
  const failed = mode === 'gateway' && !isEdit ? gateway.error : save.error
  const formError = failed && !Object.keys(errors).length ? failed.message : null
  // Server xatolari api/client.ts da tarjima qilingan; mijoz tekshiruvi xatolari — submit() da
  const fieldError = (k: string) => errors[k] ?? (k === 'department' ? errors.non_field_errors : undefined)

  return (
    <Modal
      open
      onClose={onClose}
      icon={isEdit ? 'ri-user-settings-line' : 'ri-user-add-line'}
      title={isEdit ? 'Xodimni tahrirlash' : "Xodim qo'shish"}
      subtitle={isEdit ? item.full_name : '* belgili maydonlar majburiy.'}
      footer={
        <>
          <Button variant="stroke" size="lg" onClick={onClose}>
            {t('Yopish')}
          </Button>
          <Button size="lg" icon="ri-check-line" type="submit" form="employee-form" loading={pending}>
            {t('Saqlash')}
          </Button>
        </>
      }
    >
      {!isEdit && (
        <div className="ivs-people-mode">
          <SegmentedControl
            className="is-fill"
            aria-label={t("Qo'shish usuli")}
            items={[
              { value: 'manual', label: t('Qo‘lda kiritish'), icon: 'ri-edit-line' },
              { value: 'gateway', label: t('PINFL orqali (Gateway)'), icon: 'ri-fingerprint-line' },
            ]}
            value={mode}
            onChange={(v) => {
              setMode(v as Mode)
              setErrors({})
            }}
          />
        </div>
      )}
      <form id="employee-form" onSubmit={submit} noValidate>
        {formError && (
          <p className="ivs-form-error type-para-sm" role="alert">
            {formError}
          </p>
        )}
        {mode === 'gateway' && !isEdit ? (
          <div className="ivs-form-grid">
            <div className="is-wide">{text('pinfl', 'PINFL *', '14 xonali PINFL', { inputMode: 'numeric', maxLength: 14 })}</div>
            <p className="is-wide ivs-form-note type-para-sm ivs-people-note">
              {t('F.I.O, tashkilot, departament va lavozim tashqi tizimdan (Gateway) PINFL bo‘yicha olinadi. Ish joyi tizimda topilmasa xodim qo‘shilmaydi.')}
            </p>
          </div>
        ) : (
          <div className="ivs-form-grid">
            {text('pinfl', 'PINFL', '14 xonali PINFL', { inputMode: 'numeric', maxLength: 14 })}
            {text('first_name', 'Ismi *', 'Ismi ...')}
            {text('last_name', 'Familiyasi *', 'Familiyasi ...')}
            {text('father_name', 'Otasini Ismi', 'Otasini Ismi ...')}
            <>
              <Select
                label={t('Tashkilot *')}
                placeholder={t('Tanlang...')}
                options={refs.organizationOptions}
                value={form.organization}
                disabled={isEdit && !canChangeOrg}
                onChange={(v) => setForm((f) => ({ ...f, organization: toId(v), department: null, directorate: null, division: null }))}
                error={!!errors.organization}
                hint={errors.organization}
              />
              <Select
                label={t('Hudud *')}
                placeholder={t('Tanlang...')}
                options={refs.regionOptions}
                value={form.region}
                onChange={(v) => setForm((f) => ({ ...f, region: toId(v), department: null, directorate: null, division: null }))}
                error={!!errors.region}
                hint={errors.region}
              />
            </>
            <Select
              label={t('Departament')}
              placeholder={t(structureReady ? 'Tanlang...' : 'Avval tashkilot va hududni tanlang')}
              options={structureReady ? structure.departmentOptions : []}
              value={form.department}
              onChange={(v) => setForm((f) => ({ ...f, department: toId(v), directorate: null, division: null }))}
              disabled={!structureReady}
              error={!!fieldError('department')}
              hint={fieldError('department')}
            />
            <Select
              label={t('Boshqarma')}
              placeholder={t('Tanlang...')}
              options={structure.directorateOptions}
              value={form.directorate}
              onChange={(v) => setForm((f) => ({ ...f, directorate: toId(v), division: null }))}
              disabled={!form.department}
              error={!!errors.directorate}
              hint={errors.directorate}
            />
            <Select
              label={t("Bo'lim")}
              placeholder={t('Tanlang...')}
              options={structure.divisionOptions}
              value={form.division}
              onChange={(v) => set('division', toId(v))}
              disabled={!form.directorate}
              error={!!errors.division}
              hint={errors.division}
            />
            <Select label={t('Lavozim')} placeholder={t('Tanlang...')} options={refs.rankOptions} value={form.rank} onChange={(v) => set('rank', toId(v))} />
            {text('phone', 'Telefon', '+998 90 123 45 67', { inputMode: 'tel' })}
            {isEdit && (
              <fieldset className="is-wide ivs-people-fieldset">
                <legend className="type-label-md">{t('Texnikalar')}</legend>
                {TECHNICS_ACTIONS.map((a) => (
                  <Radio
                    key={a.value}
                    name="technics_action"
                    value={a.value}
                    label={t(a.label)}
                    checked={form.technics_action === a.value}
                    onChange={() => set('technics_action', a.value)}
                  />
                ))}
                <p className="type-para-xs ivs-people-note">{t("Faqat tashkilot/departament/boshqarma/bo'lim haqiqatan o'zgargan holatda qo'llaniladi.")}</p>
              </fieldset>
            )}
          </div>
        )}
      </form>
    </Modal>
  )
}
