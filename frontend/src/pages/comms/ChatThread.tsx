import { Fragment, useEffect, useLayoutEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { useInfiniteQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Button, Icon, Tag, TextInput, Textarea } from '../../ds'
import Modal from '../../components/Modal'
import ConfirmDialog from '../../components/ConfirmDialog'
import { useToast } from '../../components/toast'
import { api } from '../../api/client'
import { ATTACH_ACCEPT, ATTACH_MAX, MAX_BODY, chatKeys, convTitle, fmtDay, fmtTime, statusText } from './chatApi'
import { useT } from '../../i18n'
import type { ChatMessage, Conversation, MessagesPage } from './chatApi'
import { ConvAvatar } from './ConversationList'
import EmojiPicker from './EmojiPicker'

interface Props {
  conv: Conversation
  myId: number
  /** WebSocket ulangan bo'lsa davriy so'rov kerak emas */
  live: boolean
  onBack: () => void
  onInfo: () => void
  infoOpen: boolean
}

function Bubble({ m, mine, showSender, onEdit, onDelete }: { m: ChatMessage; mine: boolean; showSender: boolean; onEdit: () => void; onDelete: () => void }) {
  const t = useT()
  return (
    <div className={`cm-row ${mine ? 'is-mine' : 'is-theirs'}`}>
      {mine && !m.is_deleted && (
        <div className="cm-msg-actions">
          {!m.attachment_url && <Button variant="ghost" size="sm" iconOnly icon="ri-pencil-line" aria-label={t('Tahrirlash')} title={t('Tahrirlash')} onClick={onEdit} />}
          <Button variant="ghost" size="sm" iconOnly icon="ri-delete-bin-line" aria-label={t("O'chirish")} title={t("O'chirish")} onClick={onDelete} />
        </div>
      )}
      <div className="cm-bubble">
        {showSender && <div className="cm-bubble-sender">{m.is_ai ? t(m.sender_name) : m.sender_name}</div>}
        {m.attachment_url &&
          (m.is_image ? (
            <a href={m.attachment_url} target="_blank" rel="noopener noreferrer" className="cm-bubble-img">
              <img src={m.attachment_url} alt={m.attachment_name ?? t('Rasm')} loading="lazy" />
            </a>
          ) : (
            <a href={m.attachment_url} target="_blank" rel="noopener noreferrer" className="cm-bubble-file">
              <Icon name="ri-file-download-line" size={20} />
              <span>{m.attachment_name || t('Fayl')}</span>
            </a>
          ))}
        {m.body && <span className="cm-bubble-body">{m.body}</span>}
        <span className="cm-bubble-meta">
          {m.is_edited && !m.is_deleted && <span>{t('tahrirlangan')}</span>}
          <span>
            {m.is_ai ? 'AI · ' : ''}
            {fmtTime(m.date_creat)}
          </span>
          {mine && !m.is_ai && (
            <span title={t(m.read_at ? "O'qildi" : 'Yuborildi')} className="cm-tick">
              <Icon name={m.read_at ? 'ri-check-double-line' : 'ri-check-line'} size={14} />
            </span>
          )}
        </span>
      </div>
    </div>
  )
}

export default function ChatThread({ conv, myId, live, onBack, onInfo, infoOpen }: Props) {
  const t = useT()
  const qc = useQueryClient()
  const toast = useToast()
  const box = useRef<HTMLDivElement>(null)
  const composer = useRef<HTMLDivElement>(null)
  const inputEl = () => composer.current?.querySelector<HTMLInputElement>('input.aui-input') ?? null
  const fileInput = useRef<HTMLInputElement>(null)
  const [text, setText] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [editing, setEditing] = useState<ChatMessage | null>(null)
  const [editText, setEditText] = useState('')
  const [deleting, setDeleting] = useState<ChatMessage | null>(null)
  const stick = useRef(true) // pastda turgan bo'lsa yangi xabarda pastga suriladi
  const restore = useRef<number | null>(null) // eski xabarlar yuklanganda joy saqlanadi

  const messages = useInfiniteQuery({
    queryKey: chatKeys.messages(conv.id),
    queryFn: ({ pageParam }) => api<MessagesPage>(`/chat/conversations/${conv.id}/messages/`, { query: { page: pageParam } }),
    initialPageParam: 1,
    getNextPageParam: (last, pages) => (last.has_next_page ? pages.length + 1 : undefined),
    refetchInterval: live ? false : 4000,
  })

  // Ochilganda xabarlar "o'qildi" bo'ladi — ro'yxatdagi raqam yangilanadi
  const firstLoad = messages.dataUpdatedAt
  useEffect(() => {
    if (firstLoad) qc.invalidateQueries({ queryKey: chatKeys.conversations })
  }, [firstLoad, qc])

  // Sahifalar: 1 — eng yangilari; ekranda eskidan yangiga
  const seen = new Set<number>()
  const list = (messages.data?.pages ?? [])
    .slice()
    .reverse()
    .flatMap((p) => p.results)
    .filter((m) => !seen.has(m.id) && seen.add(m.id))

  const lastId = list.length ? list[list.length - 1].id : 0
  useLayoutEffect(() => {
    const el = box.current
    if (!el) return
    if (restore.current !== null) {
      el.scrollTop = el.scrollHeight - restore.current
      restore.current = null
    } else if (stick.current) {
      el.scrollTop = el.scrollHeight
    }
  }, [lastId, list.length])

  useEffect(() => {
    stick.current = true
    setText('')
    setFile(null)
    inputEl()?.focus()
  }, [conv.id])

  const loadOlder = () => {
    if (box.current) restore.current = box.current.scrollHeight - box.current.scrollTop
    messages.fetchNextPage()
  }

  const refresh = () => {
    qc.invalidateQueries({ queryKey: chatKeys.messages(conv.id) })
    qc.invalidateQueries({ queryKey: chatKeys.conversations })
  }

  const send = useMutation({
    mutationFn: ({ body, attachment }: { body: string; attachment: File | null }) => {
      const fd = new FormData()
      if (body) fd.append('body', body)
      if (attachment) fd.append('attachment', attachment)
      return api<{ message: ChatMessage }>(`/chat/conversations/${conv.id}/send/`, { method: 'POST', body: fd })
    },
    onSuccess: () => {
      stick.current = true
      refresh()
    },
    onError: (e, vars) => {
      toast(e.message, 'error')
      setText((cur) => cur || vars.body)
    },
  })

  const edit = useMutation({
    mutationFn: ({ id, body }: { id: number; body: string }) => api(`/chat/messages/${id}/edit/`, { method: 'POST', body: JSON.stringify({ body }) }),
    onSuccess: () => {
      setEditing(null)
      refresh()
    },
    onError: (e) => toast(e.message, 'error'),
  })

  const remove = useMutation({
    mutationFn: (id: number) => api(`/chat/messages/${id}/delete/`, { method: 'POST' }),
    onSuccess: () => {
      setDeleting(null)
      refresh()
    },
    onError: (e) => toast(e.message, 'error'),
  })

  const submit = (e: FormEvent) => {
    e.preventDefault()
    const body = text.trim()
    if (!body && !file) return
    if (body.length > MAX_BODY) return toast('Xabar juda uzun', 'error')
    send.mutate({ body, attachment: file })
    setText('')
    setFile(null)
    if (fileInput.current) fileInput.current.value = ''
  }

  const pickFile = (f: File | undefined) => {
    if (!f) return
    if (f.size > ATTACH_MAX) {
      toast('Fayl hajmi 15 MB dan oshmasin', 'error')
      if (fileInput.current) fileInput.current.value = ''
      return
    }
    setFile(f)
  }

  const insertEmoji = (emoji: string) => {
    const el = inputEl()
    const start = el?.selectionStart ?? text.length
    const end = el?.selectionEnd ?? text.length
    setText(text.slice(0, start) + emoji + text.slice(end))
    requestAnimationFrame(() => {
      el?.focus()
      el?.setSelectionRange(start + emoji.length, start + emoji.length)
    })
  }

  const hasStatus = conv.kind === 'direct' || conv.kind === 'group'

  return (
    <>
      <header className="cm-head">
        <Button className="cm-back" variant="ghost" size="sm" iconOnly icon="ri-arrow-left-line" aria-label={t('Orqaga')} onClick={onBack} />
        <ConvAvatar conv={conv} size={40} />
        <div className="cm-head-text">
          <div className="type-label-md cm-ellipsis">{convTitle(conv, t)}</div>
          {hasStatus && <div className={`type-para-xs ${conv.kind === 'direct' && conv.online ? 'cm-online' : 'cm-muted'}`}>{statusText(conv, t)}</div>}
        </div>
        {hasStatus && (
          <Button
            variant={infoOpen ? 'lighter' : 'ghost'}
            size="sm"
            iconOnly
            icon="ri-information-line"
            aria-label={t("Ma'lumot")}
            title={t("Ma'lumot")}
            aria-pressed={infoOpen}
            onClick={onInfo}
          />
        )}
      </header>

      <div
        ref={box}
        className="cm-messages"
        onScroll={(e) => {
          const el = e.currentTarget
          stick.current = el.scrollHeight - el.scrollTop - el.clientHeight < 80
        }}
      >
        {messages.hasNextPage && (
          <div className="cm-older">
            <Button variant="stroke" size="sm" icon="ri-history-line" loading={messages.isFetchingNextPage} onClick={loadOlder}>
              {t('Oldingi xabarlar')}
            </Button>
          </div>
        )}
        {messages.isError ? (
          <div className="cm-empty" role="alert">
            {messages.error.message}
          </div>
        ) : messages.isPending ? (
          <div className="cm-empty">{t('Yuklanmoqda…')}</div>
        ) : list.length === 0 ? (
          <div className="cm-empty">
            <Icon name="ri-chat-smile-2-line" size={32} />
            {t("Hozircha xabar yo'q. Birinchi bo'lib yozing!")}
          </div>
        ) : (
          list.map((m, i) => {
            const mine = !m.is_ai && m.sender_id === myId
            const newDay = i === 0 || fmtDay(list[i - 1].date_creat, t) !== fmtDay(m.date_creat, t)
            return (
              <Fragment key={m.id}>
                {newDay && (
                  <div className="cm-day">
                    <span>{fmtDay(m.date_creat, t)}</span>
                  </div>
                )}
                <Bubble
                  m={m}
                  mine={mine}
                  showSender={conv.kind === 'group' && !mine}
                  onEdit={() => {
                    setEditing(m)
                    setEditText(m.body)
                  }}
                  onDelete={() => setDeleting(m)}
                />
              </Fragment>
            )
          })
        )}
      </div>

      <form className="cm-composer" onSubmit={submit}>
        {file && (
          <div className="cm-attach">
            <Tag icon="ri-attachment-2" onRemove={() => {
              setFile(null)
              if (fileInput.current) fileInput.current.value = ''
            }}>
              {file.name}
            </Tag>
          </div>
        )}
        <div className="cm-composer-row">
          <input ref={fileInput} type="file" hidden accept={ATTACH_ACCEPT} onChange={(e) => pickFile(e.target.files?.[0])} />
          <Button type="button" variant="ghost" iconOnly icon="ri-attachment-2" aria-label={t('Fayl biriktirish')} title={t('Fayl biriktirish (jpg, png, pdf, word, excel — 15 MB gacha)')} onClick={() => fileInput.current?.click()} />
          <EmojiPicker onPick={insertEmoji} />
          <div ref={composer} className="cm-input">
            <TextInput
              placeholder={t('Xabar yozing...')}
              autoComplete="off"
              aria-label={t('Xabar')}
              maxLength={MAX_BODY}
              value={text}
              onChange={(e) => setText(e.target.value)}
            />
          </div>
          <Button type="submit" iconOnly icon="ri-send-plane-2-fill" aria-label={t('Yuborish')} disabled={!text.trim() && !file} loading={send.isPending} />
        </div>
      </form>

      {editing && (
        <Modal
          open
          onClose={() => setEditing(null)}
          icon="ri-pencil-line"
          title="Xabarni tahrirlash"
          width={520}
          footer={
            <>
              <Button variant="stroke" size="lg" onClick={() => setEditing(null)}>
                {t('Bekor qilish')}
              </Button>
              <Button size="lg" icon="ri-check-line" disabled={!editText.trim()} loading={edit.isPending} onClick={() => edit.mutate({ id: editing.id, body: editText.trim() })}>
                {t('Saqlash')}
              </Button>
            </>
          }
        >
          <Textarea rows={4} value={editText} maxLength={MAX_BODY} aria-label={t('Xabar matni')} onChange={(e) => setEditText(e.target.value)} />
        </Modal>
      )}
      {deleting && (
        <ConfirmDialog
          title="Xabarni o'chirish"
          message="Xabarni o'chirishni tasdiqlaysizmi? U ikkala tomonda ham ko'rinmay qoladi."
          confirmLabel="O'chirish"
          danger
          loading={remove.isPending}
          onConfirm={() => remove.mutate(deleting.id)}
          onClose={() => setDeleting(null)}
        />
      )}
    </>
  )
}
