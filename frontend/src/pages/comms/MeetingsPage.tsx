import DatePicker from '../../components/DatePicker'
import EmptyState from '../../components/EmptyState'
import { useState } from 'react'
import type { FormEvent } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useLocation, useSearchParams } from 'react-router-dom'
import { Button, CellUser, DataTable, Icon, Pagination, StatusChip, TextInput, Textarea } from '../../ds'
import type { DataTableColumn } from '../../ds'
import Page from '../../layout/Page'
import PageTabs from '../../components/PageTabs'
import Modal from '../../components/Modal'
import ConfirmDialog from '../../components/ConfirmDialog'
import { useToast } from '../../components/toast'
import { api } from '../../api/client'
import { can, useMe } from '../../auth/me'
import { avatarColor, initials } from '../../lib/format'
import { useT } from '../../i18n'
import './comms.css'

interface Meeting {
  id: number
  title: string
  agenda: string
  start_at: string
  duration_minutes: number
  status: 'scheduled' | 'cancelled' | 'finished'
  ended_at: string | null
  organizer: { id: number; name: string }
  join_url: string
  password: string
  invitation: string
  is_organizer: boolean
  can_manage: boolean
  start_url?: string
}

const PAGE_SIZE = 20
const TABS = [
  { path: '/meetings', label: 'Rejalashtirilgan Zoomlar', icon: 'ri-calendar-schedule-line' },
  { path: '/meetings/past', label: "O'tgan va bekor qilinganlar", icon: 'ri-history-line' },
]

const pad = (n: number) => String(n).padStart(2, '0')
function fmtDateTime(d: Date): string {
  return `${pad(d.getDate())}.${pad(d.getMonth() + 1)}.${d.getFullYear()} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}
/** datetime-local qiymati (mahalliy vaqt) */
function localInput(d: Date): string {
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}
const endOf = (m: Meeting) => (m.ended_at ? new Date(m.ended_at) : new Date(new Date(m.start_at).getTime() + m.duration_minutes * 60000))

async function copyText(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text)
    return true
  } catch {
    const ta = document.createElement('textarea')
    ta.value = text
    document.body.appendChild(ta)
    ta.select()
    const ok = document.execCommand('copy')
    document.body.removeChild(ta)
    return ok
  }
}

function MeetingForm({ zoomEnabled, onClose }: { zoomEnabled: boolean; onClose: () => void }) {
  const t = useT()
  const qc = useQueryClient()
  const toast = useToast()
  const [form, setForm] = useState({ title: '', start_at: '', duration_minutes: '30', agenda: '' })
  const [error, setError] = useState<string | null>(null)
  const set = (k: keyof typeof form, v: string) => setForm((f) => ({ ...f, [k]: v }))
  // O'tgan vaqtni tanlab bo'lmasin
  const [minStart] = useState(() => localInput(new Date()))

  const save = useMutation({
    mutationFn: () =>
      api<Meeting>('/meetings/', {
        method: 'POST',
        body: JSON.stringify({ ...form, title: form.title.trim(), duration_minutes: Number(form.duration_minutes) }),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['meetings'] })
      toast('Uchrashuv yaratildi')
      onClose()
    },
    onError: (e) => setError(e.message),
  })

  const submit = (e: FormEvent) => {
    e.preventDefault()
    const d = Number(form.duration_minutes)
    if (!form.title.trim()) return setError(t('Mavzu kiritilmadi'))
    if (!form.start_at) return setError(t('Sana va vaqt kiritilmadi'))
    if (!(d >= 15 && d <= 480)) return setError(t("Davomiyligi 15–480 daqiqa orasida bo'lsin"))
    setError(null)
    save.mutate()
  }

  return (
    <Modal
      open
      onClose={onClose}
      icon="ri-video-add-line"
      title="Yangi Zoom"
      subtitle="Taklif matnini ishtirokchilarga o'zingiz yuborasiz (Nusxalash)."
      width={560}
      footer={
        <>
          <Button variant="stroke" size="lg" onClick={onClose}>
            {t('Bekor qilish')}
          </Button>
          <Button size="lg" icon="ri-video-on-line" type="submit" form="meeting-form" loading={save.isPending} disabled={!zoomEnabled}>
            {t('Yaratish va yuborish')}
          </Button>
        </>
      }
    >
      <form id="meeting-form" className="ivs-form-grid" onSubmit={submit}>
        <div className="is-wide">
          <TextInput label={t('Mavzu *')} maxLength={200} value={form.title} onChange={(e) => set('title', e.target.value)} />
        </div>
        <DatePicker label="Boshlanish vaqti *" withTime min={minStart} value={form.start_at} onChange={(v) => set('start_at', v)} />
        <TextInput
          label={t('Davomiyligi (daqiqada) *')}
          type="number"
          min={15}
          max={480}
          step={1}
          hint={t('15 dan 480 gacha')}
          value={form.duration_minutes}
          onChange={(e) => set('duration_minutes', e.target.value)}
        />
        <div className="is-wide">
          <Textarea label={t('Izoh (ixtiyoriy)')} rows={3} value={form.agenda} onChange={(e) => set('agenda', e.target.value)} />
        </div>
        {!zoomEnabled && (
          <div className="is-wide cm-warning type-para-sm">
            <Icon name="ri-error-warning-line" size={20} />
            {t("Zoom hali sozlanmagan. Administrator Zoom ma'lumotlarini kiritishi kerak.")}
          </div>
        )}
        {error && (
          <div className="is-wide cm-error type-para-sm" role="alert">
            {error}
          </div>
        )}
      </form>
    </Modal>
  )
}

/** Zoom uchrashuvlari (eski /chat/meetings/ — templates/chat/meetings.html). */
export default function MeetingsPage() {
  const t = useT()
  const me = useMe()
  const toast = useToast()
  const qc = useQueryClient()
  const { pathname } = useLocation()
  const past = pathname.startsWith('/meetings/past')
  const [params, setParams] = useSearchParams()
  const page = Math.max(1, Number(params.get('page') ?? 1) || 1)
  const [creating, setCreating] = useState(false)
  const [confirm, setConfirm] = useState<{ kind: 'finish' | 'cancel'; m: Meeting } | null>(null)

  const canAdd = can(me, 'chat.add_meeting')
  const canDelete = can(me, 'chat.delete_meeting')

  const config = useQuery({ queryKey: ['meetings', 'config'], queryFn: () => api<{ zoom_enabled: boolean }>('/spa/comms/meetings/config/') })
  const list = useQuery({
    queryKey: ['meetings', past ? 'past' : 'upcoming'],
    queryFn: () => api<{ results: Meeting[] }>('/meetings/', { query: { scope: past ? 'past' : 'upcoming' } }).then((d) => d.results),
    refetchInterval: 60000, // "boshlangan" holati va ro'yxat vaqt o'tishi bilan o'zgaradi
  })

  const action = useMutation({
    mutationFn: ({ kind, m }: { kind: 'finish' | 'cancel'; m: Meeting }) => api<Meeting>(`/meetings/${m.id}/${kind}/`, { method: 'POST' }),
    onSuccess: (_, v) => {
      setConfirm(null)
      qc.invalidateQueries({ queryKey: ['meetings'] })
      toast(v.kind === 'finish' ? "Uchrashuv tugatildi, vaqt bo'shadi" : 'Uchrashuv bekor qilindi')
    },
    onError: (e) => {
      setConfirm(null)
      toast(e.message, 'error')
    },
  })

  const rows = list.data ?? []
  const pageCount = Math.max(1, Math.ceil(rows.length / PAGE_SIZE))
  const shown = rows.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE)
  const start = (page - 1) * PAGE_SIZE
  const now = Date.now()
  const setPage = (p: number) =>
    setParams(
      (x) => {
        if (p > 1) x.set('page', String(p))
        else x.delete('page')
        return x
      },
      { replace: true },
    )

  const organizer: DataTableColumn<Meeting> = {
    key: 'organizer',
    label: t('Tashkilotchi'),
    width: '20%',
    render: (m) => <CellUser name={m.organizer.name} initials={initials(m.organizer.name)} color={avatarColor(m.organizer.id)} size={32} />,
  }
  const num: DataTableColumn<Meeting> = { key: 'n', label: t('T/r'), width: 56, render: (m) => start + shown.indexOf(m) + 1 }

  const upcomingColumns: DataTableColumn<Meeting>[] = [
    num,
    organizer,
    {
      key: 'title',
      label: t('Mavzu'),
      render: (m) => (
        <div className="aui-cell-text">
          <div className="aui-cell-primary">{m.title}</div>
          <div className="aui-cell-secondary">{m.agenda || '—'}</div>
        </div>
      ),
    },
    {
      key: 'start',
      label: t('Boshlanish vaqti'),
      width: 150,
      render: (m) =>
        new Date(m.start_at).getTime() <= now ? (
          <div className="aui-cell-text">
            <div className="aui-cell-primary">{fmtDateTime(new Date(m.start_at))}</div>
            <StatusChip status="active">{t('Davom etmoqda')}</StatusChip>
          </div>
        ) : (
          fmtDateTime(new Date(m.start_at))
        ),
    },
    { key: 'end', label: t('Tugash vaqti'), width: 140, render: (m) => fmtDateTime(endOf(m)) },
    { key: 'duration', label: t('Davomiyligi'), width: 110, render: (m) => t('{n} daqiqa', { n: m.duration_minutes }) },
    {
      key: 'actions',
      label: t('Amallar'),
      width: 170,
      render: (m) => {
        if (!m.is_organizer) return <span className="cm-muted">—</span>
        const running = new Date(m.start_at).getTime() <= now
        return (
          <div className="cm-actions">
            {m.start_url && (
              <Button size="sm" icon="ri-play-circle-line" title={t("Zoom'ni boshlash")} onClick={() => window.open(m.start_url, '_blank', 'noopener')}>
                {t('Boshlash')}
              </Button>
            )}
            <Button
              variant="ghost"
              size="sm"
              iconOnly
              icon="ri-file-copy-line"
              aria-label={t('Nusxalash')}
              title={t('Taklif matnini nusxalash')}
              onClick={async () => toast((await copyText(m.invitation || m.join_url)) ? 'Nusxalandi' : 'Nusxalab bo‘lmadi', 'info')}
            />
            {running && (
              <Button variant="ghost" size="sm" iconOnly icon="ri-stop-circle-line" aria-label={t('Tugatish')} title={t('Tugatish')} onClick={() => setConfirm({ kind: 'finish', m })} />
            )}
            {!running && canDelete && (
              <Button variant="ghost" size="sm" iconOnly icon="ri-delete-bin-line" aria-label={t("O'chirish")} title={t("O'chirish")} onClick={() => setConfirm({ kind: 'cancel', m })} />
            )}
          </div>
        )
      },
    },
  ]

  const pastColumns: DataTableColumn<Meeting>[] = [
    num,
    {
      key: 'title',
      label: t('Mavzu'),
      render: (m) => (
        <div className="aui-cell-text">
          <div className="aui-cell-primary">{m.title}</div>
          {m.agenda && <div className="aui-cell-secondary">{m.agenda}</div>}
        </div>
      ),
    },
    { key: 'time', label: t('Vaqt'), width: 160, render: (m) => fmtDateTime(new Date(m.start_at)) },
    organizer,
    {
      key: 'status',
      label: t('Holati'),
      width: 160,
      render: (m) =>
        m.status === 'cancelled' ? (
          <StatusChip status="failed">{t('Bekor qilingan')}</StatusChip>
        ) : m.status === 'finished' ? (
          <StatusChip status="completed">{t('Tugatilgan')}</StatusChip>
        ) : (
          <StatusChip status="absent">{t("O'tgan")}</StatusChip>
        ),
    },
  ]

  return (
    <Page
      icon="ri-video-chat-line"
      title="Zoom"
      subtitle="Zoom uchrashuvlarini rejalashtirish va boshqarish."
      actions={
        !past &&
        canAdd && (
          <Button size="lg" icon="ri-video-add-line" onClick={() => setCreating(true)}>
            {t('Yangi Zoom')}
          </Button>
        )
      }
    >
      <PageTabs tabs={TABS} label="Zoom uchrashuvlari" />

      {!past && canAdd && config.data && !config.data.zoom_enabled && (
        <div className="cm-warning type-para-sm" role="status">
          <Icon name="ri-error-warning-line" size={20} />
          {t("Zoom hali sozlanmagan. Administrator Zoom ma'lumotlarini kiritishi kerak.")}
        </div>
      )}

      {list.isError ? (
        <div className="ivs-empty" role="alert">
          {list.error.message}
        </div>
      ) : list.isPending ? (
        <div className="ivs-empty" aria-busy="true">
          {t('Yuklanmoqda…')}
        </div>
      ) : rows.length === 0 ? (
        <EmptyState icon="ri-video-chat-line" title={past ? "O'tgan yoki bekor qilingan Zoom yo'q" : "Rejalashtirilgan Zoom yo'q"} />
      ) : (
        <div className={list.isFetching ? 'ivs-loading' : undefined}>
          <DataTable
            rows={shown}
            columns={past ? pastColumns : upcomingColumns}
            getRowId={(m) => m.id}
            rowHeight={64}
            minWidth={past ? 720 : 1040}
            caption={t(past ? "O'tgan va bekor qilingan Zoomlar" : 'Rejalashtirilgan Zoomlar')}
          />
          {pageCount > 1 && (
            <div className="ivs-pager">
              <Pagination pageCount={pageCount} page={page} onChange={setPage} />
            </div>
          )}
        </div>
      )}

      {creating && <MeetingForm zoomEnabled={!!config.data?.zoom_enabled} onClose={() => setCreating(false)} />}
      {confirm && (
        <ConfirmDialog
          title={confirm.kind === 'finish' ? 'Zoomni tugatish' : "Zoomni o'chirish"}
          message={
            <>
              {confirm.kind === 'finish'
                ? t(`"{title}" tugatildimi? Zoom'da tugatiladi va vaqt keyingisi uchun bo'shaydi.`, { title: confirm.m.title })
                : t(`"{title}" Zoomini o'chirasizmi?`, { title: confirm.m.title })}
            </>
          }
          confirmLabel={confirm.kind === 'finish' ? 'Tugatish' : "O'chirish"}
          danger={confirm.kind === 'cancel'}
          loading={action.isPending}
          onConfirm={() => action.mutate(confirm)}
          onClose={() => setConfirm(null)}
        />
      )}
    </Page>
  )
}
