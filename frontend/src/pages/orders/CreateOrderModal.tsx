import { useState } from 'react'
import type { FormEvent } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Button, Select, Textarea } from '../../ds'
import Modal from '../../components/Modal'
import { useToast } from '../../components/toast'
import { ApiError, api } from '../../api/client'
import type { Named } from '../../api/types'
import { useT } from '../../i18n'

interface Props {
  /** true — boshqa xodim nomidan ("Ariza berish", 'add_order') */
  onBehalf?: boolean
  onClose: () => void
}

/** order_sender.html / order_sender_user.html dagi "Ariza Yaratish" oynasi. */
export default function CreateOrderModal({ onBehalf = false, onClose }: Props) {
  const t = useT()
  const qc = useQueryClient()
  const toast = useToast()
  const [goal, setGoal] = useState<number | null>(null)
  const [organization, setOrganization] = useState<number | null>(null)
  const [employee, setEmployee] = useState<number | null>(null)
  const [body, setBody] = useState('')
  const [errors, setErrors] = useState<Record<string, string>>({})

  const goals = useQuery({ queryKey: ['orders', 'goals'], queryFn: () => api<Named[]>('/spa/orders/goals/'), staleTime: 300_000 })
  const orgs = useQuery({
    queryKey: ['orders', 'organizations'],
    queryFn: () => api<Named[]>('/spa/orders/organizations/'),
    enabled: onBehalf,
    staleTime: 300_000,
  })
  const employees = useQuery({
    queryKey: ['orders', 'org-employees', organization],
    queryFn: () => api<{ results: { id: number; text: string }[] }>(`/spa/orders/organizations/${organization}/employees/`),
    enabled: onBehalf && organization != null,
  })

  const save = useMutation({
    mutationFn: () =>
      api('/orders/', {
        method: 'POST',
        body: JSON.stringify({ goal, message_sender: body.trim() || null, ...(onBehalf ? { sender: employee } : {}) }),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['orders'] })
      toast(onBehalf ? 'Ariza yuborildi' : 'Ariza yaratildi')
      onClose()
    },
    onError: (e) => setErrors(e instanceof ApiError ? e.fieldErrors : {}),
  })

  const submit = (e: FormEvent) => {
    e.preventDefault()
    if (save.isPending) return
    const missing: Record<string, string> = {}
    if (onBehalf && organization == null) missing.organization = 'Tashkilotni tanlang.'
    if (onBehalf && employee == null) missing.sender = 'Xodimni tanlang.'
    if (goal == null) missing.goal = 'Ariza turi tanlanmadi.'
    setErrors(missing)
    if (!Object.keys(missing).length) save.mutate()
  }

  const formError = save.error && !Object.keys(errors).length ? save.error.message : null
  const empOptions = (employees.data?.results ?? []).map((e) => ({ value: e.id, label: e.text }))

  return (
    <Modal
      open
      onClose={onClose}
      icon="ri-send-plane-line"
      title="Ariza yaratish"
      subtitle={onBehalf ? 'Xodim nomidan ATMga ariza yuborish.' : 'ATM (Axborot texnologiyalari markazi)ga ariza yuborish.'}
      width={560}
      footer={
        <>
          <Button variant="stroke" size="lg" icon="ri-close-line" onClick={onClose}>
            {t('Bekor qilish')}
          </Button>
          <Button size="lg" icon="ri-send-plane-fill" type="submit" form="order-create-form" loading={save.isPending}>
            {t('Yuborish')}
          </Button>
        </>
      }
    >
      <form id="order-create-form" onSubmit={submit} noValidate>
        {formError && (
          <p className="ivs-form-error type-para-sm" role="alert">
            {t(formError)}
          </p>
        )}
        <div className="ivs-form-grid">
          {onBehalf && (
            <>
              <div className="is-wide">
                <Select
                  label={t('Tashkilot *')}
                  placeholder={t('Tanlang...')}
                  options={(orgs.data ?? []).map((o) => ({ value: o.id, label: o.name }))}
                  value={organization}
                  onChange={(v) => {
                    setOrganization(v == null ? null : Number(v))
                    setEmployee(null)
                  }}
                  error={!!errors.organization}
                  hint={errors.organization && t(errors.organization)}
                />
              </div>
              <div className="is-wide">
                <Select
                  label={t('Xodim *')}
                  placeholder={t(organization == null ? 'Avval tashkilotni tanlang' : employees.isFetching ? 'Yuklanmoqda...' : 'Tanlang...')}
                  options={empOptions}
                  value={employee}
                  onChange={(v) => setEmployee(v == null ? null : Number(v))}
                  disabled={organization == null}
                  error={!!errors.sender}
                  hint={errors.sender && t(errors.sender)}
                />
              </div>
            </>
          )}
          <div className="is-wide">
            <Select
              label={t('Arizaning maqsadi *')}
              placeholder={t('Tanlang...')}
              options={(goals.data ?? []).map((g) => ({ value: g.id, label: g.name }))}
              value={goal}
              onChange={(v) => setGoal(v == null ? null : Number(v))}
              error={!!errors.goal}
              hint={errors.goal && t(errors.goal)}
            />
          </div>
          <div className="is-wide">
            <Textarea
              label={t("Qo'shimcha ma'lumot")}
              rows={4}
              placeholder={t("IP, telefon va qo'shimcha ma'lumot yozing")}
              value={body}
              onChange={(e) => setBody(e.target.value)}
              error={!!errors.message_sender}
              hint={errors.message_sender && t(errors.message_sender)}
            />
          </div>
        </div>
      </form>
    </Modal>
  )
}
