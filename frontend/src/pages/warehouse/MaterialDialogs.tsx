import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Button, Select, TextInput, Textarea } from '../../ds'
import Modal from '../../components/Modal'
import { useToast } from '../../components/toast'
import { api } from '../../api/client'
import { useT } from '../../i18n'
import type { BridgeResult } from '../technics/api'
import { SPA } from '../technics/api'
import { FormError } from '../technics/TechnicsDialogs'
import { money } from '../technics/util'
import type { Material } from './api'
import { useMaterialEmployees } from './api'

export type MaterialAction = 'give' | 'service' | 'basket'

/** Eski oynalardagi o'chirilgan maydonlar: Nomi, Mavjud soni, Narxi, Birligi, Code */
export function MaterialSummary({ m }: { m: Material }) {
  const t = useT()
  return (
    <div className="ivs-summary">
      <div className="type-label-sm">{m.name}</div>
      <div className="type-para-xs ivs-muted">
        {t('Mavjud: {n}', { n: m.number })} {m.unit_name || ''} · {t("Narxi: {sum} so'm", { sum: money(m.price) })}
        {m.code ? ` · ${t('Kod: {code}', { code: m.code })}` : ''}
      </div>
    </div>
  )
}

const TITLES: Record<MaterialAction, { title: string; icon: string; submit: string; done: string }> = {
  give: { title: 'Materialni biriktirish', icon: 'ri-attachment-2', submit: 'Biriktirish#ombor', done: 'Material biriktirildi' },
  service: { title: 'Materialni sarflash', icon: 'ri-indeterminate-circle-line', submit: 'Sarflash', done: 'Material muvaffaqiyatli sarflandi' },
  basket: { title: 'Savatga saqlash', icon: 'ri-shopping-basket-2-line', submit: 'Savatga saqlash', done: 'Material savatga saqlandi' },
}

/**
 * Bitta material bilan amal:
 *  give    — xodimga berish (material_attach → /api/v1/materials/give/),
 *  service — sarflash (material_service → /api/v1/materials/service/),
 *  basket  — savatga qo'yish (mat_post → spa/warehouse/materials/basket/).
 */
export function MaterialActionDialog({ m, action, onClose }: { m: Material; action: MaterialAction; onClose: () => void }) {
  const [employee, setEmployee] = useState<number | null>(null)
  const [count, setCount] = useState('')
  const [body, setBody] = useState('')
  const employees = useMaterialEmployees()
  const qc = useQueryClient()
  const toast = useToast()
  const t = useT()
  const meta = TITLES[action]
  const n = Number(count)

  const save = useMutation({
    mutationFn: () => {
      if (action === 'give')
        return api('/materials/give/', { method: 'POST', body: JSON.stringify({ employee_id: employee, items: [{ material_id: m.id, number: n }] }) })
      if (action === 'service') return api('/materials/service/', { method: 'POST', body: JSON.stringify({ material_id: m.id, give_number: n, body }) })
      return api<BridgeResult>(`${SPA}/materials/basket/`, { method: 'POST', body: JSON.stringify({ material_id: m.id, number: n }) })
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['warehouse'] })
      toast(meta.done)
      onClose()
    },
  })

  const tooMany = n > m.number
  const valid = n >= 1 && !tooMany && (action !== 'give' || employee != null)

  return (
    <Modal
      open
      onClose={onClose}
      icon={meta.icon}
      title={meta.title}
      width={520}
      footer={
        <>
          <Button variant="stroke" size="lg" onClick={onClose}>
            {t('Yopish')}
          </Button>
          <Button size="lg" icon="ri-check-line" type="submit" form="material-action" disabled={!valid} loading={save.isPending}>
            {t(meta.submit)}
          </Button>
        </>
      }
    >
      <MaterialSummary m={m} />
      <form
        id="material-action"
        className="ivs-stack"
        onSubmit={(e) => {
          e.preventDefault()
          if (valid) save.mutate()
        }}
      >
        <FormError error={save.error} />
        {action === 'give' && (
          <Select
            label={t('Xodim *')}
            placeholder={t('Tanlang...')}
            options={employees.options.filter((o) => o.value !== m.employee)}
            value={employee}
            onChange={(v) => setEmployee(v == null ? null : Number(v))}
          />
        )}
        <TextInput
          label={action === 'give' ? t('Beriladigan soni *') : t('Soni *')}
          inputMode="numeric"
          placeholder={`1 – ${m.number}`}
          value={count}
          onChange={(e) => setCount(e.target.value.replace(/\D/g, ''))}
          error={tooMany}
          hint={tooMany ? t("Mavjud sonidan ko'p (bor: {n})", { n: m.number }) : undefined}
        />
        {action === 'service' && <Textarea label={t('Izoh')} rows={3} value={body} onChange={(e) => setBody(e.target.value)} placeholder={t('Qayerga sarflandi...')} />}
      </form>
    </Modal>
  )
}
