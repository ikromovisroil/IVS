import { useState } from 'react'
import type { ReactNode } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { Button, CellUser, DataTable, StatusChip, Switch } from '../../ds'
import type { DataTableColumn } from '../../ds'
import ConfirmDialog from '../../components/ConfirmDialog'
import { useToast } from '../../components/toast'
import { api } from '../../api/client'
import type { Page as ApiPage } from '../../api/client'
import { avatarColor, initials } from '../../lib/format'
import { useT } from '../../i18n'
import { useRefresh } from './api'
import MultiPicker from './MultiPicker'
import { CONSENT_STATUS, SIGN_STATUS, formatDateTime } from './status'
import type { Deed, DeedConsent, DeedPerson, PublicDeed, SignStatus } from './types'

interface SignerRow {
  key: 'sender' | 'receiver'
  n: number
  person: DeedPerson | null
  status: SignStatus
  date: string | null
  message: string | null
  canAdd: boolean
}

function Person({ p, name }: { p: DeedPerson | null; name?: string | null }) {
  const full = p?.full_name ?? name
  // Shaxs ko'rsatilmagan (masalan, tizim yaratgan talabnoma) — bo'sh avatar emas, oddiy chiziqcha
  if (!full) return <span className="type-para-sm">—</span>
  return <CellUser name={full} sub={p?.rank_name || undefined} initials={initials(full)} color={avatarColor(p?.id ?? full)} />
}

/** Holat belgisi, ostida (bo'lsa) sana va vaqt — alohida "Sana" ustuni joy olmasin. */
function StatusDate({ chip, date }: { chip: ReactNode; date: string | null | undefined }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-start', gap: 4 }}>
      {chip}
      {date && <span className="type-para-xs msg-note" style={{ whiteSpace: 'nowrap' }}>{formatDateTime(date)}</span>}
    </div>
  )
}

const note = (s: string | null | undefined) => (s ? <span className="msg-note msg-comment">{s}</span> : null)

/**
 * "Dalolatnoma holati" (contact*.html dagi holat oynasi va deed_status sahifasi): jo'natuvchi, imzolovchilar va
 * kelishuvchilar jadvallari. Yaratuvchi uchun — imzolovchiga kelishuvchi qo'shish ruxsati va kutilayotgan
 * kelishuvchini olib tashlash; ruxsati borlar uchun — kelishuvchi qo'shish.
 */
export default function DeedStatusPanel({ deed, readOnly = false }: { deed: Deed | PublicDeed; readOnly?: boolean }) {
  const full = !readOnly && 'can_manage_consents' in deed ? deed : null
  const manage = !!full?.can_manage_consents
  const canAdd = !!full?.can_add_consents
  const t = useT()
  const toast = useToast()
  const refresh = useRefresh()
  const [removing, setRemoving] = useState<DeedConsent | null>(null)

  const toggle = useMutation({
    mutationFn: ({ role, enabled }: { role: 'sender' | 'receiver'; enabled: boolean }) =>
      api(`/deeds/${deed.id}/signer-consent/${role}/`, { method: 'POST', body: JSON.stringify({ enabled }) }),
    onSuccess: () => refresh(),
    onError: (e) => toast(e.message, 'error'),
  })

  const remove = useMutation({
    mutationFn: (c: DeedConsent) => api(`/deed-consents/${c.id}/`, { method: 'DELETE' }),
    onSuccess: () => {
      toast('Kelishuvchi olib tashlandi')
      setRemoving(null)
      refresh()
    },
    onError: (e) => toast(e.message, 'error'),
  })

  const signers: SignerRow[] = [
    {
      key: 'sender',
      n: 1,
      person: deed.sender_info,
      status: deed.status_sender,
      date: deed.date_sender,
      message: deed.message_sender,
      canAdd: !!full?.sender_can_add_consent,
    },
  ]
  if (deed.receiver) {
    signers.push({
      key: 'receiver',
      n: 2,
      person: deed.receiver_info,
      status: deed.status_receiver,
      date: deed.date_receiver,
      message: deed.message_receiver,
      canAdd: !!full?.receiver_can_add_consent,
    })
  }

  const signerColumns: DataTableColumn<SignerRow>[] = [
    { key: 'n', label: t('T/R'), width: 56, render: (r) => r.n },
    { key: 'org', label: t('Tashkilot'), width: '32%', render: (r) => r.person?.organization_name || '—' },
    { key: 'fio', label: t('F.I.O'), width: '30%', render: (r) => <Person p={r.person} /> },
    {
      key: 'status',
      label: t('Holati / Sana'),
      width: 160,
      render: (r) => <StatusDate chip={<StatusChip status={SIGN_STATUS[r.status].chip}>{t(SIGN_STATUS[r.status].label)}</StatusChip>} date={r.status === 'viewed' ? null : r.date} />,
    },
    { key: 'msg', label: t('Izoh'), render: (r) => note(r.message) },
  ]
  if (manage) {
    signerColumns.push({
      key: 'can',
      label: t('Amallar'),
      width: 80,
      align: 'right',
      render: (r) => (
        <Switch
          aria-label={t("Yoqilsa, imzolovchi ham kelishuvchi qo'sha oladi")}
          title={t("Yoqilsa, imzolovchi ham kelishuvchi qo'sha oladi")}
          checked={r.canAdd}
          disabled={toggle.isPending}
          onChange={(checked) => toggle.mutate({ role: r.key, enabled: checked })}
        />
      ),
    })
  }

  const consentColumns: DataTableColumn<DeedConsent>[] = [
    { key: 'n', label: t('T/R'), width: 56, render: (r) => deed.consents.indexOf(r) + 1 },
    { key: 'org', label: t('Tashkilot'), width: '32%', render: (r) => r.employee_organization || '—' },
    {
      key: 'fio',
      label: t('F.I.O'),
      width: '30%',
      render: (r) => (
        <CellUser name={r.employee_name || '—'} sub={r.employee_rank || undefined} initials={initials(r.employee_name || '?')} color={avatarColor(r.employee ?? 0)} />
      ),
    },
    {
      key: 'status',
      label: t('Holati / Sana'),
      width: 160,
      render: (r) => <StatusDate chip={<StatusChip status={CONSENT_STATUS[r.status].chip}>{t(CONSENT_STATUS[r.status].label)}</StatusChip>} date={r.status === 'viewed' ? null : r.date_edit} />,
    },
    { key: 'msg', label: t('Izoh'), render: (r) => note(r.message) },
  ]
  if (manage) {
    consentColumns.push({
      key: 'rm',
      label: '',
      width: 56,
      align: 'right',
      render: (r) =>
        r.status === 'viewed' && (
          <Button variant="ghost" size="sm" icon="ri-delete-bin-line" iconOnly aria-label={t('Olib tashlash')} title={t('Olib tashlash')} onClick={() => setRemoving(r)} />
        ),
    })
  }

  const sender = deed.user_info
  return (
    <div className="msg-status">
      <section>
        <h3 className="type-label-md msg-section-title">{t("Jo'natuvchi")}</h3>
        <div className="msg-sender">
          <Person p={sender} />
          <div className="msg-kv">
            <span>{t('Tashkilot')}</span>
            <b>{sender?.organization_name || '—'}</b>
          </div>
          <div className="msg-kv">
            <span>{t('Sana')}</span>
            <b>{formatDateTime(deed.date_creat)}</b>
          </div>
          <div className="msg-kv">
            <span>{t('Izoh')}</span>
            <b>{deed.message_user || '—'}</b>
          </div>
        </div>
      </section>

      <section>
        <h3 className="type-label-md msg-section-title">{t('Imzolovchilar holati')}</h3>
        <DataTable rows={signers} columns={signerColumns} getRowId={(r) => r.key} rowHeight={60} minWidth={0} caption={t('Imzolovchilar holati')} />
      </section>

      {(deed.consents.length > 0 || canAdd) && (
        <section>
          <h3 className="type-label-md msg-section-title">{t('Kelishuvchilar holati')}</h3>
          {deed.consents.length > 0 ? (
            <DataTable rows={deed.consents} columns={consentColumns} getRowId={(r) => r.id} rowHeight={60} minWidth={0} caption={t('Kelishuvchilar holati')} />
          ) : (
            <p className="type-para-sm msg-muted">{t("Kelishuvchilar yo'q.")}</p>
          )}
          {canAdd && <AddConsents deedId={deed.id} />}
        </section>
      )}

      {removing && (
        <ConfirmDialog
          title="Kelishuvchini olib tashlaysizmi?"
          message={<>{removing.employee_name}</>}
          confirmLabel="Olib tashlash"
          danger
          loading={remove.isPending}
          onConfirm={() => remove.mutate(removing)}
          onClose={() => setRemoving(null)}
        />
      )}
    </div>
  )
}

interface Candidate {
  id: number
  full_name: string
  organization_name: string | null
  rank_name: string | null
}

/** "Kelishuvchi qo'shish" (deedconsent_add) — nomzodlar: /api/v1/deeds/{id}/consent-candidates/ */
function AddConsents({ deedId }: { deedId: number }) {
  const [ids, setIds] = useState<number[]>([])
  const t = useT()
  const toast = useToast()
  const refresh = useRefresh()

  const candidates = useQuery({
    queryKey: ['messages', 'candidates', deedId],
    queryFn: () => api<ApiPage<Candidate>>(`/deeds/${deedId}/consent-candidates/`, { query: { page_size: 100 } }),
  })

  const add = useMutation({
    mutationFn: () => api(`/deeds/${deedId}/consents/`, { method: 'POST', body: JSON.stringify({ employees: ids }) }),
    onSuccess: () => {
      toast(t("Kelishuvchi qo'shildi: {n} ta", { n: ids.length }))
      setIds([])
      refresh()
    },
    onError: (e) => toast(e.message, 'error'),
  })

  const options = (candidates.data?.results ?? []).map((c) => ({
    value: c.id,
    label: c.rank_name ? `${c.full_name} — ${c.rank_name}` : c.full_name,
  }))

  return (
    <div className="msg-add">
      <div className="msg-add-field">
        <MultiPicker label={t("Kelishuvchi qo'shish")} placeholder={t('Xodimni qidiring...')} options={options} value={ids} onChange={setIds} />
      </div>
      <Button size="lg" icon="ri-add-line" disabled={!ids.length} loading={add.isPending} onClick={() => add.mutate()}>
        {t("Qo'shish")}
      </Button>
    </div>
  )
}
