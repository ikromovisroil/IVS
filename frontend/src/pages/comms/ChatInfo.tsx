import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Avatar, Badge, Button, Icon } from '../../ds'
import ConfirmDialog from '../../components/ConfirmDialog'
import SearchInput from '../../components/SearchInput'
import { useToast } from '../../components/toast'
import { api } from '../../api/client'
import { avatarColor, initials } from '../../lib/format'
import { chatKeys, convTitle, statusText } from './chatApi'
import { useT } from '../../i18n'
import type { Contact, Conversation, MembersResponse } from './chatApi'
import { ConvAvatar } from './ConversationList'
import { THEMES, WALLPAPERS } from './appearance'
import type { Appearance } from './appearance'

interface Props {
  conv: Conversation
  myId: number
  appearance: Appearance
  onAppearance: (a: Appearance) => void
  onClose: () => void
  /** Suhbat yashirildi yoki guruhdan chiqildi */
  onLeft: () => void
}

type Confirm = { kind: 'hide' } | { kind: 'remove'; id: number; name: string; me: boolean }

/** O'ng panel: suhbat ma'lumoti, guruh a'zolari (admin/yaratuvchi amallari), fon va tema, chatni o'chirish. */
export default function ChatInfo({ conv, myId, appearance, onAppearance, onClose, onLeft }: Props) {
  const t = useT()
  const qc = useQueryClient()
  const toast = useToast()
  const isGroup = conv.kind === 'group'
  const [adding, setAdding] = useState(false)
  const [q, setQ] = useState('')
  const [confirm, setConfirm] = useState<Confirm | null>(null)

  const members = useQuery({
    queryKey: chatKeys.members(conv.id),
    queryFn: () => api<MembersResponse>(`/chat/conversations/${conv.id}/members/`),
    enabled: isGroup,
  })
  const memberIds = new Set(members.data?.results.map((m) => m.id))
  const contacts = useQuery({
    queryKey: chatKeys.contacts(q),
    queryFn: () => api<{ results: Contact[] }>('/chat/contacts/', { query: { q } }).then((d) => d.results),
    enabled: adding && !!q,
  })

  const refresh = () => {
    qc.invalidateQueries({ queryKey: chatKeys.members(conv.id) })
    qc.invalidateQueries({ queryKey: chatKeys.conversations })
  }
  const fail = (e: Error) => toast(e.message, 'error')

  const add = useMutation({
    mutationFn: (id: number) => api(`/chat/conversations/${conv.id}/members/add/`, { method: 'POST', body: JSON.stringify({ members: [id] }) }),
    onSuccess: () => {
      setQ('')
      refresh()
    },
    onError: fail,
  })
  const setAdmin = useMutation({
    mutationFn: ({ id, isAdmin }: { id: number; isAdmin: boolean }) =>
      api(`/chat/conversations/${conv.id}/members/${id}/admin/`, { method: 'POST', body: JSON.stringify({ is_admin: isAdmin }) }),
    onSuccess: refresh,
    onError: fail,
  })
  const remove = useMutation({
    mutationFn: (id: number) => api(`/chat/conversations/${conv.id}/members/${id}/remove/`, { method: 'POST' }),
    onSuccess: (_, id) => {
      setConfirm(null)
      refresh()
      if (id === myId) onLeft()
    },
    onError: fail,
  })
  const hide = useMutation({
    mutationFn: () => api(`/chat/conversations/${conv.id}/hide/`, { method: 'POST' }),
    onSuccess: () => {
      setConfirm(null)
      qc.invalidateQueries({ queryKey: chatKeys.conversations })
      onLeft()
    },
    onError: fail,
  })

  const amAdmin = !!members.data?.am_admin
  const amCreator = !!members.data?.am_creator

  return (
    <aside className="cm-info" aria-label={t("Suhbat ma'lumoti")}>
      <div className="cm-info-top">
        <Button variant="ghost" size="sm" iconOnly icon="ri-close-line" aria-label={t('Yopish')} onClick={onClose} />
      </div>
      <div className="cm-info-card">
        <ConvAvatar conv={conv} size={64} />
        <div className="type-label-lg">{convTitle(conv, t)}</div>
        <div className={`type-para-xs ${conv.kind === 'direct' && conv.online ? 'cm-online' : 'cm-muted'}`}>{statusText(conv, t)}</div>
      </div>

      {isGroup && (
        <section className="cm-info-section">
          <div className="cm-info-title">
            <Icon name="ri-group-line" size={16} /> {t("A'zolar")}
            {amAdmin && !adding && (
              <Button variant="ghost" size="sm" icon="ri-add-line" onClick={() => setAdding(true)}>
                {t("A'zo qo'shish")}
              </Button>
            )}
          </div>
          {adding && (
            <div className="cm-add">
              <SearchInput value={q} onChange={setQ} placeholder="A'zo qo'shish..." delay={250} style={{ width: '100%' }} />
              {q && (
                <div className="cm-results">
                  {(contacts.data ?? [])
                    .filter((c) => !memberIds.has(c.id))
                    .map((c) => (
                      <button key={c.id} type="button" className="cm-item" disabled={add.isPending} onClick={() => add.mutate(c.id)}>
                        <Avatar size={32} name={c.name} initials={initials(c.name)} color={avatarColor(c.id)} />
                        <span className="cm-item-title">{c.name}</span>
                        <Icon name="ri-user-add-line" size={18} className="cm-item-go" />
                      </button>
                    ))}
                  {contacts.data && contacts.data.filter((c) => !memberIds.has(c.id)).length === 0 && <div className="cm-hint">{t('Xodim topilmadi')}</div>}
                </div>
              )}
            </div>
          )}
          <div className="cm-members">
            {(members.data?.results ?? []).map((m) => {
              const canRemove = m.is_me || (!m.is_creator && (amCreator || (amAdmin && !m.is_admin)))
              return (
                <div key={m.id} className="cm-member">
                  <Avatar size={32} name={m.name} initials={initials(m.name)} color={avatarColor(m.id)} />
                  <span className="cm-member-name type-para-sm">
                    {m.name}
                    {m.is_me && <span className="cm-muted"> ({t('siz')})</span>}
                  </span>
                  {m.is_creator ? (
                    <Badge tone="purple" size="sm">
                      {t('yaratuvchi')}
                    </Badge>
                  ) : m.is_admin ? (
                    <Badge tone="primary" size="sm">
                      {t('admin')}
                    </Badge>
                  ) : null}
                  {amCreator && !m.is_creator && !m.is_me && (
                    <Button
                      variant="ghost"
                      size="sm"
                      iconOnly
                      icon={m.is_admin ? 'ri-star-fill' : 'ri-star-line'}
                      aria-label={t(m.is_admin ? 'Admindan tushirish' : 'Admin qilish')}
                      title={t(m.is_admin ? 'Admindan tushirish' : 'Admin qilish')}
                      onClick={() => setAdmin.mutate({ id: m.id, isAdmin: !m.is_admin })}
                    />
                  )}
                  {canRemove && (
                    <Button
                      variant="ghost"
                      size="sm"
                      iconOnly
                      icon={m.is_me ? 'ri-logout-box-r-line' : 'ri-close-line'}
                      aria-label={t(m.is_me ? 'Guruhdan chiqish' : 'Guruhdan chiqarish')}
                      title={t(m.is_me ? 'Guruhdan chiqish' : 'Guruhdan chiqarish')}
                      onClick={() => setConfirm({ kind: 'remove', id: m.id, name: m.name, me: m.is_me })}
                    />
                  )}
                </div>
              )
            })}
          </div>
        </section>
      )}

      <section className="cm-info-section">
        <div className="cm-info-title">
          <Icon name="ri-palette-line" size={16} /> {t('Fon tanlang')}
        </div>
        <div className="cm-swatches">
          {WALLPAPERS.map((w) => (
            <button
              key={w.value}
              type="button"
              className={`cm-wallpaper-swatch${appearance.wallpaper === w.value ? ' is-active' : ''}`}
              data-wallpaper={w.value}
              title={t(w.label)}
              aria-label={t(w.label)}
              aria-pressed={appearance.wallpaper === w.value}
              onClick={() => onAppearance({ ...appearance, wallpaper: w.value })}
            />
          ))}
        </div>
        <div className="cm-info-title">
          <Icon name="ri-brush-line" size={16} /> {t('Chat temasi')}
        </div>
        <div className="cm-themes">
          {THEMES.map((th) => (
            <Button
              key={th.value}
              variant={appearance.theme === th.value ? 'lighter' : 'stroke'}
              size="sm"
              icon={<span className="cm-theme-dot" style={{ background: th.color }} />}
              aria-pressed={appearance.theme === th.value}
              onClick={() => onAppearance({ ...appearance, theme: th.value })}
            >
              {t(th.label)}
            </Button>
          ))}
        </div>
      </section>

      <div className="cm-info-foot">
        <Button
          variant="error-lighter"
          icon="ri-logout-box-r-line"
          onClick={() => setConfirm(isGroup ? { kind: 'remove', id: myId, name: '', me: true } : { kind: 'hide' })}
          style={{ width: '100%' }}
        >
          {t(isGroup ? 'Guruhdan chiqish' : "Chatni o'chirish")}
        </Button>
      </div>

      {confirm?.kind === 'hide' && (
        <ConfirmDialog
          title="Chatni o'chirish"
          message="Suhbatni o'chirmoqchimisiz? Boshqalarga ta'sir qilmaydi."
          confirmLabel="O'chirish"
          danger
          loading={hide.isPending}
          onConfirm={() => hide.mutate()}
          onClose={() => setConfirm(null)}
        />
      )}
      {confirm?.kind === 'remove' && (
        <ConfirmDialog
          title={confirm.me ? 'Guruhdan chiqish' : "A'zoni chiqarish"}
          message={confirm.me ? 'Guruhdan chiqmoqchimisiz?' : <>{t('{name} guruhdan chiqarilsinmi?', { name: confirm.name })}</>}
          confirmLabel={confirm.me ? 'Chiqish' : 'Chiqarish'}
          danger
          loading={remove.isPending}
          onConfirm={() => remove.mutate(confirm.id)}
          onClose={() => setConfirm(null)}
        />
      )}
    </aside>
  )
}
