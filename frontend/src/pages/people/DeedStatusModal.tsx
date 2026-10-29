import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Badge, Button, DataTable, Switch } from '../../ds'
import type { BadgeProps, DataTableColumn } from '../../ds'
import DateTimeStack from '../../components/DateTimeStack'
import Modal from '../../components/Modal'
import { useToast } from '../../components/toast'
import { api } from '../../api/client'
import { useT } from '../../i18n'
import { formatDateTime } from './api'
import type { DeedPerson, DeedRow, SignStatus } from './api'

const SIGN: Record<SignStatus, { tone: BadgeProps['tone']; label: string }> = {
  viewed: { tone: 'warning', label: 'Kutilmoqda#hujjat' },
  approved: { tone: 'success', label: 'Tasdiqlandi#hujjat' },
  rejected: { tone: 'error', label: 'Rad etildi#hujjat' },
}

interface PartyRow {
  n: number
  person: DeedPerson | null
  status?: SignStatus | null
  statusLabel?: string
  date: string | null
  message: string | null
}

// F.I.O ostida lavozim — joy tejash uchun bitta ustunda ikki qator
const base: DataTableColumn<PartyRow>[] = [
  { key: 'n', label: 'T/R', width: 52, render: (r) => r.n },
  { key: 'org', label: 'Tashkilot', width: '32%', render: (r) => <span className="ivs-people-wrap">{r.person?.organization_name || ''}</span> },
  {
    key: 'fio',
    label: 'F.I.O',
    width: '30%',
    render: (r) => (
      <span className="ivs-people-wrap" style={{ display: 'block' }}>
        {r.person?.full_name || ''}
        {r.person?.rank_name && <span style={{ display: 'block', color: 'var(--text-sub-600)' }}>{r.person.rank_name}</span>}
      </span>
    ),
  },
]
const dateCol: DataTableColumn<PartyRow> = {
  key: 'date',
  label: 'Sana',
  width: 110,
  render: (r) => (r.date ? <DateTimeStack text={formatDateTime(r.date)} /> : null),
}
const msgCol: DataTableColumn<PartyRow> = {
  key: 'msg',
  label: 'Izoh',
  render: (r) => <span className="ivs-people-wrap ivs-people-note ivs-people-comment">{r.message}</span>,
}

function Table({ rows, withStatus, caption }: { rows: PartyRow[]; withStatus?: boolean; caption: string }) {
  const t = useT()
  const tr = (cols: DataTableColumn<PartyRow>[]) => cols.map((c) => ({ ...c, label: t(String(c.label)) }))
  // Holati va sana bitta ustunda: tepada belgi, ostida sana va vaqt (joy tejaladi)
  const statusColT: DataTableColumn<PartyRow> = {
    key: 'status',
    label: t('Holati / Sana'),
    width: 160,
    render: (r) =>
      r.status ? (
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-start', gap: 4 }}>
          <Badge tone={SIGN[r.status].tone} size="sm">
            {t(r.statusLabel ?? SIGN[r.status].label)}
          </Badge>
          {r.date && <span className="type-para-xs ivs-people-note" style={{ whiteSpace: 'nowrap' }}>{formatDateTime(r.date)}</span>}
        </div>
      ) : (
        null
      ),
  }
  const columns = withStatus ? [...tr(base), statusColT, ...tr([msgCol])] : [...tr(base), ...tr([dateCol, msgCol])]
  return <DataTable rows={rows} columns={columns} getRowId={(r) => r.n} rowHeight={52} minWidth={720} caption={t(caption)} />
}

/** "Dalolatnoma holati #kod" oynasi (saytdagi files.html → modalcondition). */
export default function DeedStatusModal({ deed, canToggle, onClose }: { deed: DeedRow; canToggle: boolean; onClose: () => void }) {
  const t = useT()
  const toast = useToast()
  const qc = useQueryClient()
  const toggle = useMutation({
    mutationFn: () => api<{ success: boolean; user_edit: boolean; error?: string }>(`/spa/people/files/${deed.id}/toggle-user-edit/`, { method: 'POST' }),
    onSuccess: (r) => {
      if (!r.success) return toast(r.error || 'Xatolik yuz berdi', 'error')
      qc.invalidateQueries({ queryKey: ['people', 'files'] })
      toast(r.user_edit ? 'Tahrirlash ruxsati yoqildi' : "Tahrirlash ruxsati o'chirildi")
    },
    onError: (e) => toast(e.message || "Server bilan bog'lanishda xatolik", 'error'),
  })

  const signers: PartyRow[] = [{ n: 1, person: deed.sender, status: deed.status_sender, date: deed.date_sender, message: deed.message_sender }]
  if (deed.receiver) signers.push({ n: 2, person: deed.receiver, status: deed.status_receiver, date: deed.date_receiver, message: deed.message_receiver })
  const consents: PartyRow[] = deed.consents.map((c, i) => ({
    n: i + 1,
    person: c.employee,
    status: c.status,
    statusLabel: c.status === 'approved' ? 'Kelishildi' : undefined,
    date: c.date_edit,
    message: c.message,
  }))

  return (
    <Modal
      open
      onClose={onClose}
      icon="ri-file-text-line"
      title={t('Dalolatnoma holati #{code}', { code: deed.code ?? deed.id })}
      subtitle={`${deed.status_display} · ${formatDateTime(deed.date_creat)}`}
      width={1120}
      footer={
        <Button variant="stroke" size="lg" onClick={onClose}>
          {t('Yopish')}
        </Button>
      }
    >
      <div className="ivs-people-sections">
        <section>
          <h3 className="type-label-md">{t("Jo'natuvchi")}</h3>
          <Table caption="Jo'natuvchi" rows={[{ n: 1, person: deed.user, date: deed.date_creat, message: deed.message_user }]} />
        </section>

        {canToggle && (
          <div className="ivs-form-note">
            <Switch
              label={t('Tahrirlash ruxsati')}
              sub={t("Yoqilsa hujjat yaratuvchisi uni (javob berilmagan bo'lsa) tahrirlay oladi.")}
              checked={deed.user_edit}
              disabled={toggle.isPending}
              onChange={() => toggle.mutate()}
            />
          </div>
        )}

        <section>
          <h3 className="type-label-md">{t('Imzolovchilar holati')}</h3>
          <Table caption="Imzolovchilar holati" rows={signers} withStatus />
        </section>

        {consents.length > 0 && (
          <section>
            <h3 className="type-label-md">{t('Kelishuvchilar holati')}</h3>
            <Table caption="Kelishuvchilar holati" rows={consents} withStatus />
          </section>
        )}
      </div>
    </Modal>
  )
}
