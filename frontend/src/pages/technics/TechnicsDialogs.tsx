import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Button, Select, TextInput } from '../../ds'
import Modal from '../../components/Modal'
import { useToast } from '../../components/toast'
import { api, apiAll } from '../../api/client'
import type { Me } from '../../api/types'
import { useT } from '../../i18n'
import type { BridgeResult, TechnicsRow } from './api'
import { SPA, useOrgEmployees, useOrgTree } from './api'
import { errorText } from './util'

type Id = number | null
const num = (v: string | number | null) => (v == null ? null : Number(v))

export function FormError({ error }: { error: unknown }) {
  const text = errorText(error)
  return text ? (
    <p className="ivs-form-error type-para-sm" role="alert">
      {text}
    </p>
  ) : null
}

/** Uskunaning qisqa ma'lumoti (eski oynalardagi o'chirilgan maydonlar: Nomi, Parametr, Inventory, Serial) */
export function TechnicsSummary({ t: item }: { t: TechnicsRow }) {
  const t = useT()
  return (
    <div className="ivs-summary">
      <div className="type-label-sm">{item.name}</div>
      <div className="type-para-xs ivs-muted">
        {[item.parametr, item.inventory && t('I/R: {v}', { v: item.inventory }), item.serial && t('S/R: {v}', { v: item.serial })].filter(Boolean).join(' · ') || ''}
      </div>
    </div>
  )
}

function useDone(message: string, onClose: () => void) {
  const qc = useQueryClient()
  const toast = useToast()
  return () => {
    qc.invalidateQueries({ queryKey: ['technics'] })
    qc.invalidateQueries({ queryKey: ['warehouse'] })
    toast(message)
    onClose()
  }
}

/** "Uskunani biriktirish": xodimga YOKI departament/boshqarma/bo'limga; hech biri tanlanmasa — bo'shatiladi. */
export function AssignDialog({ t: item, onClose }: { t: TechnicsRow; onClose: () => void }) {
  const t = useT()
  const [employee, setEmployee] = useState<Id>(item.employee)
  const [department, setDepartment] = useState<Id>(item.department)
  const [directorate, setDirectorate] = useState<Id>(item.directorate)
  const [division, setDivision] = useState<Id>(item.division)
  const employees = useOrgEmployees(item.organization, item.region)
  const tree = useOrgTree({ organization: item.organization, region: item.region, department, directorate })

  const body = employee ? { employee } : department || directorate || division ? { department, directorate, division } : {}
  const message = employee ? 'Uskuna xodimga biriktirildi' : 'department' in body ? "Uskuna strukturaga biriktirildi" : "Uskuna bo'shatildi"
  const done = useDone(message, onClose)
  const save = useMutation({
    mutationFn: () => api(`/technics/${item.id}/assign/`, { method: 'POST', body: JSON.stringify(body) }),
    onSuccess: done,
  })
  const freeDone = useDone("Uskuna bo'shatildi", onClose)
  const free = useMutation({ mutationFn: () => api(`/technics/${item.id}/unassign/`, { method: 'POST' }), onSuccess: freeDone })

  return (
    <Modal
      open
      onClose={onClose}
      icon="ri-attachment-2"
      title="Uskunani biriktirish"
      subtitle="Xodimni yoki tuzilmani tanlang. Hech narsa tanlanmasa uskuna bo'shatiladi."
      width={640}
      footer={
        <>
          {(item.employee || item.department || item.directorate || item.division) && (
            <Button variant="error-lighter" size="lg" icon="ri-link-unlink" loading={free.isPending} onClick={() => free.mutate()}>
              {t("Bo'shatish")}
            </Button>
          )}
          <span className="aui-toolbar-grow" />
          <Button variant="stroke" size="lg" onClick={onClose}>
            {t('Yopish')}
          </Button>
          <Button size="lg" icon="ri-check-line" loading={save.isPending} onClick={() => save.mutate()}>
            {t('Biriktirish#ombor')}
          </Button>
        </>
      }
    >
      <TechnicsSummary t={item} />
      <FormError error={save.error || free.error} />
      <div className="ivs-form-grid">
        <div className="is-wide">
          <Select
            label={t('Xodim')}
            placeholder={employees.isPending && item.organization ? t('Yuklanmoqda…') : t('Tanlang...')}
            options={employees.data ?? []}
            value={employee}
            onChange={(v) => {
              setEmployee(num(v))
              if (v != null) {
                setDepartment(null)
                setDirectorate(null)
                setDivision(null)
              }
            }}
          />
        </div>
        <div className="is-wide ivs-form-divider type-para-xs">{t('yoki tuzilmaga')}</div>
        <Select
          label={t('Departament')}
          placeholder={t('Tanlang...')}
          options={tree.departments}
          value={department}
          disabled={!!employee}
          onChange={(v) => {
            setDepartment(num(v))
            setDirectorate(null)
            setDivision(null)
          }}
        />
        <Select
          label={t('Boshqarma')}
          placeholder={t('Tanlang...')}
          options={tree.directorates}
          value={directorate}
          disabled={!!employee || !department}
          onChange={(v) => {
            setDirectorate(num(v))
            setDivision(null)
          }}
        />
        <div className="is-wide">
          <Select label={t("Bo'lim")} placeholder={t('Tanlang...')} options={tree.divisions} value={division} disabled={!!employee || !directorate} onChange={(v) => setDivision(num(v))} />
        </div>
      </div>
    </Modal>
  )
}

interface FreeStructure {
  id: number
  name: string
  inventory: string | null
  serial: string | null
  category_name: string | null
}

/** "Qurilmani biriktirish": tashkilotdagi bo'sh qo'shimcha qurilmalardan biri. */
export function AttachDeviceDialog({ t: item, me, onClose }: { t: TechnicsRow; me: Me; onClose: () => void }) {
  const t = useT()
  const [device, setDevice] = useState<Id>(null)
  const region = (me.employee as { region?: number | null } | null)?.region ?? null
  const free = useQuery({
    queryKey: ['warehouse', 'structures', 'free', item.organization, region],
    queryFn: () => apiAll<FreeStructure>('/structures/', { organization: item.organization, status: 'free', region }),
    enabled: !!item.organization,
  })
  const done = useDone("Qo'shimcha qurilma biriktirildi", onClose)
  const save = useMutation({
    mutationFn: () => api(`/structures/${device}/assign/`, { method: 'POST', body: JSON.stringify({ technics: item.id }) }),
    onSuccess: done,
  })
  const options = (free.data ?? []).map((s) => ({
    value: s.id,
    label: [s.category_name ? `${s.category_name} / ${s.name}` : s.name, s.inventory, s.serial].filter(Boolean).join(' | '),
  }))

  return (
    <Modal
      open
      onClose={onClose}
      icon="ri-pushpin-line"
      title="Qurilmani biriktirish"
      width={760}
      footer={
        <>
          <Button variant="stroke" size="lg" onClick={onClose}>
            {t('Yopish')}
          </Button>
          <Button size="lg" icon="ri-check-line" disabled={!device} loading={save.isPending} onClick={() => save.mutate()}>
            {t('Biriktirish#ombor')}
          </Button>
        </>
      }
    >
      <TechnicsSummary t={item} />
      <FormError error={save.error || free.error} />
      <Select
        label={t('Qurilmalar *')}
        placeholder={free.isPending ? t('Yuklanmoqda…') : options.length ? t('Tanlang...') : t("Bo'sh qurilma yo'q")}
        options={options}
        value={device}
        onChange={(v) => setDevice(num(v))}
      />
    </Modal>
  )
}

/** "Qurilmani bekor qilish": uskunaga biriktirilgan qurilmani ajratish. */
export function DetachDeviceDialog({ t: item, onClose }: { t: TechnicsRow; onClose: () => void }) {
  const t = useT()
  const [device, setDevice] = useState<Id>(item.extra_devices.length === 1 ? item.extra_devices[0].id : null)
  const done = useDone("Qo'shimcha qurilma bekor qilindi", onClose)
  const save = useMutation({
    mutationFn: () => api(`/structures/${device}/unassign/`, { method: 'POST', body: JSON.stringify({ technics: item.id }) }),
    onSuccess: done,
  })
  const options = item.extra_devices.map((s) => ({ value: s.id, label: [s.name, s.inventory, s.serial].filter(Boolean).join(' | ') }))

  return (
    <Modal
      open
      onClose={onClose}
      icon="ri-close-circle-line"
      title="Qurilmani bekor qilish"
      width={760}
      footer={
        <>
          <Button variant="stroke" size="lg" onClick={onClose}>
            {t('Yopish')}
          </Button>
          <Button size="lg" variant="error" icon="ri-link-unlink" disabled={!device} loading={save.isPending} onClick={() => save.mutate()}>
            {t('Bekor qilish')}
          </Button>
        </>
      }
    >
      <TechnicsSummary t={item} />
      <FormError error={save.error} />
      <Select
        label={t('Qurilmalar *')}
        placeholder={options.length ? t('Tanlang...') : t("Biriktirilgan qurilma yo'q")}
        options={options}
        value={device}
        onChange={(v) => setDevice(num(v))}
      />
    </Modal>
  )
}

/** "Xodim qo'shish" — PINFL bo'yicha (Gateway'dan ma'lumot olinadi, main/views.py:employe_create). */
export function EmployeePinflDialog({ onClose }: { onClose: () => void }) {
  const t = useT()
  const [pinfl, setPinfl] = useState('')
  const toast = useToast()
  const qc = useQueryClient()
  const save = useMutation({
    mutationFn: () => api<BridgeResult>(`${SPA}/employees/pinfl/`, { method: 'POST', body: JSON.stringify({ pinfl }) }),
    onSuccess: (r) => {
      qc.invalidateQueries({ queryKey: ['technics', 'employees'] })
      toast(r.detail || 'Xodim yaratildi')
      onClose()
    },
  })

  return (
    <Modal
      open
      onClose={onClose}
      icon="ri-user-add-line"
      title="Xodim qo'shish"
      subtitle="Xodim ma'lumotlari va ish joyi tashqi tizimdan (Gateway) olinadi."
      width={480}
      footer={
        <>
          <Button variant="stroke" size="lg" onClick={onClose}>
            {t('Yopish')}
          </Button>
          <Button size="lg" icon="ri-check-line" type="submit" form="pinfl-form" disabled={!pinfl.trim()} loading={save.isPending}>
            {t('Saqlash')}
          </Button>
        </>
      }
    >
      <form
        id="pinfl-form"
        onSubmit={(e) => {
          e.preventDefault()
          if (pinfl.trim()) save.mutate()
        }}
      >
        <FormError error={save.error} />
        <TextInput label={t('PINFL *')} placeholder={t('PINFL kiriting')} inputMode="numeric" maxLength={20} value={pinfl} onChange={(e) => setPinfl(e.target.value.replace(/\D/g, ''))} />
      </form>
    </Modal>
  )
}
