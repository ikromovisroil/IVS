import { useState } from 'react'
import type { FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { Button, DataTable, Select, TextInput, Textarea } from '../../ds'
import type { DataTableColumn } from '../../ds'
import DataState from '../../components/DataState'
import Modal from '../../components/Modal'
import { ApiError, api } from '../../api/client'
import { useMe } from '../../auth/me'
import { formatNumber } from '../../lib/format'
import { sectionAllowed } from './access'
import { SPA, materialGoals, useBarnMutation, useCart } from './api'
import BarnPage from './BarnPage'
import MaterialImage from './MaterialImage'
import type { CartItem } from './types'
import { useT } from '../../i18n'
import { useCtxT } from './i18n'

/** Savat — order_sender_basket_barn: sonlarni kiritish, o'chirish va "Ariza yaratish" (create_order_sender_from). */
export default function BasketPage() {
  const me = useMe()
  const t = useT()
  const ct = useCtxT()
  const allowed = sectionAllowed(me, 'sender')
  const cart = useCart(allowed)
  const items = cart.data ?? []
  // Faqat o'zgartirilgan sonlar saqlanadi; qolganlari savatdagi qiymat
  const [edited, setEdited] = useState<Record<number, string>>({})
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState('')

  const numberOf = (it: CartItem) => edited[it.id] ?? String(it.number)

  const remove = useBarnMutation((it: CartItem) => api(`${SPA}/cart/${it.id}/`, { method: 'DELETE' }), (it) => t("«{name}» savatdan o'chirildi", { name: it.name }))

  /** Sonlarni tekshiradi (kamida 1, butun son) va {item_id: son} qaytaradi. */
  const numbers = () => {
    const out: Record<string, number> = {}
    for (const it of items) {
      const n = Number(numberOf(it))
      if (!Number.isInteger(n) || n < 1) {
        setError(t("«{name}» uchun son kamida 1 bo'lishi kerak.", { name: it.name }))
        return null
      }
      out[it.id] = n
    }
    setError('')
    return out
  }

  const columns: DataTableColumn<CartItem>[] = [
    { key: 'n', label: t('T/r'), width: 64, render: (r) => items.indexOf(r) + 1 },
    { key: 'img', label: t('Rasm'), width: 72, render: (r) => <MaterialImage src={r.image} name={r.name} /> },
    {
      key: 'name',
      label: t('Nomi'),
      render: (r) => (
        <div className="aui-cell-text">
          <div className="aui-cell-primary">{r.name}</div>
          <div className="aui-cell-secondary">{t('Omborda: {n}', { n: formatNumber(r.stock) })}</div>
        </div>
      ),
    },
    { key: 'unit', label: t('Birligi'), width: 100, render: (r) => r.unit_name || '—' },
    {
      key: 'number',
      label: t('Soni'),
      width: 140,
      render: (r) => (
        <TextInput
          className="ob-number"
          type="number"
          inputMode="numeric"
          min={1}
          aria-label={t('{name}: soni', { name: r.name })}
          value={numberOf(r)}
          onChange={(e) => setEdited((s) => ({ ...s, [r.id]: e.target.value }))}
        />
      ),
    },
    {
      key: 'del',
      label: ct('Bekor qilish', 'savat'),
      width: 140,
      align: 'right',
      render: (r) => (
        <Button
          variant="error-lighter"
          size="sm"
          icon="ri-delete-bin-line"
          loading={remove.isPending && remove.variables?.id === r.id}
          onClick={() => remove.mutate(r)}
          aria-label={t("{name} — o'chirish", { name: r.name })}
        >
          {t("O'chirish")}
        </Button>
      ),
    },
  ]

  return (
    <BarnPage
      section="sender"
      tools={
        <Button
          icon="ri-add-line"
          disabled={!items.length}
          onClick={() => {
            if (numbers()) setCreating(true)
          }}
        >
          {t('Ariza yaratish')}
        </Button>
      }
    >
      <DataState
        isPending={cart.isPending}
        isFetching={cart.isFetching}
        error={cart.error}
        empty={items.length === 0}
        emptyText={
          <>
            <p>{t("Savat bo'sh — ariza yaratish uchun avval materiallarni savatga saqlang.")}</p>
            <BasketEmptyAction />
          </>
        }
      >
        <DataTable rows={items} columns={columns} getRowId={(r) => r.id} rowHeight={64} minWidth={760} caption={t('Savatdagi materiallar')} />
        {error && (
          <p className="ivs-form-error type-para-sm" role="alert">
            {error}
          </p>
        )}
      </DataState>
      {creating && <CreateOrderModal numbers={numbers} onClose={() => setCreating(false)} />}
    </BarnPage>
  )
}

function BasketEmptyAction() {
  const navigate = useNavigate()
  const t = useT()
  return (
    <Button variant="stroke" icon="ri-archive-line" onClick={() => navigate('/orders/barn/new')}>
      {t('Materiallarni tanlash')}
    </Button>
  )
}

function CreateOrderModal({ numbers, onClose }: { numbers: () => Record<string, number> | null; onClose: () => void }) {
  const me = useMe()
  const t = useT()
  const navigate = useNavigate()
  const goals = materialGoals(me)
  const [goal, setGoal] = useState<number | null>(goals.length === 1 ? goals[0].id : null)
  const [body, setBody] = useState('')
  const [errors, setErrors] = useState<Record<string, string>>({})

  const submit = useBarnMutation(
    (v: { goal: number; body: string; numbers: Record<string, number> }) =>
      api<{ id: number }>(`${SPA}/cart/submit/`, { method: 'POST', body: JSON.stringify(v) }),
    (_, d) => t('Ariza #{id} yuborildi', { id: d.id }),
    () => {
      onClose()
      navigate('/orders/barn')
    },
  )

  const onSubmit = (e: FormEvent) => {
    e.preventDefault()
    if (goal == null) {
      setErrors({ goal: 'Arizaning maqsadini tanlang.' })
      return
    }
    const n = numbers()
    if (!n) return onClose()
    setErrors({})
    submit.mutate(
      { goal, body: body.trim(), numbers: n },
      { onError: (err) => setErrors(err instanceof ApiError ? err.fieldErrors : {}) },
    )
  }

  return (
    <Modal
      open
      onClose={onClose}
      icon="ri-file-add-line"
      title="Ariza yaratish"
      subtitle="Savatdagi materiallar omborxonaga ariza sifatida yuboriladi."
      width={560}
      footer={
        <>
          <Button variant="stroke" size="lg" icon="ri-close-line" onClick={onClose}>
            {t('Bekor qilish')}
          </Button>
          <Button size="lg" icon="ri-send-plane-fill" type="submit" form="barn-create-order" loading={submit.isPending}>
            {t('Yuborish')}
          </Button>
        </>
      }
    >
      <form id="barn-create-order" onSubmit={onSubmit} noValidate>
        <div className="ivs-form-grid">
          <div className="is-wide">
            <Select
              label={t('Arizaning maqsadi *')}
              placeholder={t('Tanlang...')}
              options={goals.map((g) => ({ value: g.id, label: g.name }))}
              value={goal}
              onChange={(v) => setGoal(v == null ? null : Number(v))}
              error={!!errors.goal}
              hint={errors.goal ? t(errors.goal) : goals.length ? undefined : t('Tashkilotingiz uchun ariza turlari kiritilmagan.')}
            />
          </div>
          <div className="is-wide">
            <Textarea label={t("Qo'shimcha ma'lumot")} rows={4} value={body} onChange={(e) => setBody(e.target.value)} error={!!errors.body} hint={errors.body && t(errors.body)} />
          </div>
        </div>
        {(errors.numbers || errors.detail) && (
          <p className="ivs-form-error type-para-sm" role="alert">
            {t(errors.numbers || errors.detail)}
          </p>
        )}
      </form>
    </Modal>
  )
}
