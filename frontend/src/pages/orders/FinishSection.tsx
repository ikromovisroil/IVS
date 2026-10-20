import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Button, Select, TextInput } from '../../ds'
import { api, apiAll } from '../../api/client'
import { useT } from '../../i18n'
import { formatPrice } from './types'
import type { OrderDetail } from './types'
import type { FinishState, MaterialRow } from './hooks'
import { Section } from './OrderDetailModal'

interface AvailableMaterial {
  id: number
  name: string
  code: string | null
  number: number
  price: string | null
  unit_name: string | null
}

let seq = 0

interface Props {
  order: OrderDetail
  state: FinishState
  onChange: (s: FinishState) => void
}

/** order_receiver_activ.html: "Texnikani tanlang" va "Materiallar" bo'limlari. */
export default function FinishSection({ order, state, onChange }: Props) {
  const t = useT()
  const [warn, setWarn] = useState<string | null>(null)
  const technics = useQuery({
    queryKey: ['orders', 'sender-technics', order.id],
    queryFn: () => api<{ results: { id: number; text: string }[] }>(`/spa/orders/${order.id}/technics/`),
  })
  const materials = useQuery({
    queryKey: ['orders', 'available-materials'],
    queryFn: () => apiAll<AvailableMaterial>('/orders/available-materials/'),
  })

  // ajax_sender_technics: "nomi | inventar | serial | mac" — bo'sh qismlar olib tashlanadi
  const techOptions = (technics.data?.results ?? []).map((t) => ({
    value: t.id,
    label: t.text.split('|').map((x) => x.trim()).filter(Boolean).join(' | '),
  }))
  const matOptions = (materials.data ?? []).map((m) => ({
    value: m.id,
    label: t('Nomi: {name} | Code: {code} | Soni: {n} | Narxi: {price}', { name: m.name, code: m.code || '—', n: m.number, price: formatPrice(m.price) }),
  }))

  const setRow = (key: number, patch: Partial<MaterialRow>) =>
    onChange({ ...state, rows: state.rows.map((r) => (r.key === key ? { ...r, ...patch } : r)) })

  const addRow = () => {
    if (state.technics == null) {
      setWarn("Material qo'shish uchun avval texnikani tanlang")
      return
    }
    setWarn(null)
    onChange({ ...state, rows: [...state.rows, { key: ++seq, material: null, number: '1' }] })
  }

  const setTechnics = (v: number | null) => {
    onChange({ ...state, technics: v })
    setWarn(v == null && state.rows.length ? 'Materiallar bilan ishlash uchun texnika tanlanishi kerak' : null)
  }

  return (
    <>
      <Section title="Texnikani tanlang">
        <Select
          placeholder={t(technics.isPending ? 'Yuklanmoqda...' : 'Tanlang...')}
          options={techOptions}
          value={state.technics}
          onChange={(v) => setTechnics(v == null ? null : Number(v))}
          error={!!warn}
          hint={warn ? t(warn) : technics.isError ? t('Xatolik yuz berdi') : undefined}
        />
      </Section>
      <Section
        title="Materiallar"
        extra={
          <Button variant="success" size="sm" icon="ri-add-line" disabled={state.technics == null} onClick={addRow}>
            {t("Material qo'shish")}
          </Button>
        }
      >
        {state.rows.length === 0 ? (
          <p className="type-para-sm ivs-orders-muted">
            {t(matOptions.length || materials.isPending ? 'Material berilmasa, faqat texnikani tanlab yakunlang.' : "Sizga biriktirilgan omborda material yo'q.")}
          </p>
        ) : (
          <div className="ivs-orders-matrows">
            {state.rows.map((r) => (
              <div key={r.key} className="ivs-orders-matrow">
                <Select
                  placeholder={t('Tanlang...')}
                  options={matOptions}
                  value={r.material}
                  onChange={(v) => setRow(r.key, { material: v == null ? null : Number(v) })}
                />
                <TextInput
                  aria-label={t('Soni')}
                  inputMode="numeric"
                  value={r.number}
                  onChange={(e) => setRow(r.key, { number: e.target.value.replace(/\D/g, '') })}
                />
                <Button
                  variant="error-lighter"
                  iconOnly
                  icon="ri-delete-bin-line"
                  aria-label={t("Qatorni o'chirish")}
                  onClick={() => onChange({ ...state, rows: state.rows.filter((x) => x.key !== r.key) })}
                />
              </div>
            ))}
          </div>
        )}
      </Section>
    </>
  )
}
