import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Avatar, Badge, Button, Icon, SegmentedControl } from '../../ds'
import SearchInput from '../../components/SearchInput'
import { useToast } from '../../components/toast'
import { api } from '../../api/client'
import { avatarColor, initials } from '../../lib/format'
import { useT } from '../../i18n'
import { chatKeys, convTitle, fmtListTime } from './chatApi'
import type { Contact, Conversation } from './chatApi'
import NewGroupModal from './NewGroupModal'

export type ChatTab = 'direct' | 'group'

export function ConvAvatar({ conv, size = 40 }: { conv: Pick<Conversation, 'id' | 'kind' | 'title' | 'other_id' | 'online'>; size?: number }) {
  if (conv.kind === 'saved') {
    return (
      <span className="cm-avatar-icon" style={{ width: size, height: size }}>
        <Icon name="ri-bookmark-fill" size={size / 2} />
      </span>
    )
  }
  if (conv.kind === 'ai') {
    return (
      <span className="cm-avatar-icon is-ai" style={{ width: size, height: size }}>
        <Icon name="ri-robot-2-line" size={size / 2} />
      </span>
    )
  }
  return (
    <Avatar
      size={size}
      name={conv.title}
      initials={initials(conv.title)}
      color={avatarColor(conv.other_id ?? conv.id)}
      status={conv.kind === 'direct' ? (conv.online ? 'online' : 'offline') : undefined}
    />
  )
}

interface Props {
  conversations: Conversation[] | undefined
  loading: boolean
  error: Error | null
  activeId: number | null
  tab: ChatTab
  onTab: (tab: ChatTab) => void
  onOpen: (id: number) => void
}

/** Chap panel: Xodimlar / Guruhlar, xodim qidirish (yangi suhbat), Saqlangan xabarlar, suhbatlar ro'yxati. */
export default function ConversationList({ conversations, loading, error, activeId, tab, onTab, onOpen }: Props) {
  const t = useT()
  const qc = useQueryClient()
  const toast = useToast()
  const [q, setQ] = useState('')
  const [newGroup, setNewGroup] = useState(false)

  const contacts = useQuery({
    queryKey: chatKeys.contacts(q),
    queryFn: () => api<{ results: Contact[] }>('/chat/contacts/', { query: { q } }).then((d) => d.results),
    enabled: tab === 'direct' && !!q,
  })

  const open = useMutation({
    mutationFn: (target: number | 'saved') =>
      api<{ conversation_id: number }>('/chat/open/', { method: 'POST', body: JSON.stringify({ target }) }),
    onSuccess: async (r) => {
      setQ('')
      await qc.invalidateQueries({ queryKey: chatKeys.conversations })
      onOpen(r.conversation_id)
    },
    onError: (e) => toast(e.message, 'error'),
  })

  const all = conversations ?? []
  const saved = all.find((c) => c.kind === 'saved')
  const list = all.filter((c) => c.kind !== 'saved' && (tab === 'group' ? c.kind === 'group' : c.kind !== 'group'))
  const unread = (group: boolean) => all.filter((c) => (c.kind === 'group') === group).reduce((s, c) => s + (c.unread_count || 0), 0)

  return (
    <aside className="cm-side" aria-label={t('Suhbatlar')}>
      <div className="cm-side-head">
        <SegmentedControl
          className="is-fill"
          aria-label={t('Suhbat turi')}
          items={[
            { value: 'direct', label: t('Xodimlar'), icon: 'ri-user-line', count: unread(false) || undefined },
            { value: 'group', label: t('Guruhlar'), icon: 'ri-group-line', count: unread(true) || undefined },
          ]}
          value={tab}
          onChange={(v) => onTab(v as ChatTab)}
        />
        {tab === 'direct' ? (
          <SearchInput value={q} onChange={setQ} placeholder="Xodim qidirish (yangi suhbat)..." delay={250} style={{ width: '100%' }} />
        ) : (
          <Button variant="stroke" icon="ri-add-line" onClick={() => setNewGroup(true)} style={{ width: '100%' }}>
            {t('Yangi guruh')}
          </Button>
        )}
      </div>

      <div className="cm-side-scroll">
        {tab === 'direct' && q && (
          <div className="cm-results" aria-label={t('Qidiruv natijalari')}>
            {contacts.isPending ? (
              <div className="cm-hint">{t('Qidirilmoqda…')}</div>
            ) : contacts.data?.length ? (
              contacts.data.map((c) => (
                <button key={c.id} type="button" className="cm-item" disabled={open.isPending} onClick={() => open.mutate(c.id)}>
                  <Avatar size={32} name={c.name} initials={initials(c.name)} color={avatarColor(c.id)} />
                  <span className="cm-item-title">{c.name}</span>
                  <Icon name="ri-chat-new-line" size={18} className="cm-item-go" />
                </button>
              ))
            ) : (
              <div className="cm-hint">{t('Xodim topilmadi')}</div>
            )}
          </div>
        )}

        {tab === 'direct' && (
          <button
            type="button"
            className={`cm-item${saved && saved.id === activeId ? ' is-active' : ''}`}
            onClick={() => (saved ? onOpen(saved.id) : open.mutate('saved'))}
          >
            <ConvAvatar conv={{ id: 0, kind: 'saved', title: t('Saqlangan xabarlar'), other_id: null, online: false }} />
            <span className="cm-item-body">
              <span className="cm-item-title">{t('Saqlangan xabarlar')}</span>
              {saved?.last_message && <span className="cm-item-preview">{saved.last_message}</span>}
            </span>
          </button>
        )}

        {error ? (
          <div className="cm-hint" role="alert">
            {error.message}
          </div>
        ) : loading ? (
          <div className="cm-hint">{t('Yuklanmoqda…')}</div>
        ) : list.length === 0 ? (
          <div className="cm-hint">{t(tab === 'group' ? "Guruhlar yo'q" : "Suhbatlar yo'q. Yangi suhbat uchun xodimni qidiring.")}</div>
        ) : (
          list.map((c) => (
            <button key={c.id} type="button" className={`cm-item${c.id === activeId ? ' is-active' : ''}`} onClick={() => onOpen(c.id)}>
              <ConvAvatar conv={c} />
              <span className="cm-item-body">
                <span className="cm-item-row">
                  <span className="cm-item-title">{convTitle(c, t)}</span>
                  <span className="cm-item-time">{fmtListTime(c.last_message_at)}</span>
                </span>
                <span className="cm-item-row">
                  <span className="cm-item-preview">{c.last_message || (c.kind === 'group' ? t("{n} ta a'zo", { n: c.member_count }) : '')}</span>
                  {c.unread_count > 0 && (
                    <Badge tone="primary" size="sm">
                      {c.unread_count}
                    </Badge>
                  )}
                </span>
              </span>
            </button>
          ))
        )}
      </div>

      {newGroup && (
        <NewGroupModal
          onClose={() => setNewGroup(false)}
          onCreated={(id) => {
            setNewGroup(false)
            onTab('group')
            onOpen(id)
          }}
        />
      )}
    </aside>
  )
}
