// Chat: mavjud /api/v1/chat/... (api/chat_views.py) + WebSocket /ws/chat/ (chat/consumers.py).
import { useEffect, useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import type { Vars } from '../../i18n'

export type ConversationKind = 'direct' | 'group' | 'saved' | 'ai'

export interface Conversation {
  id: number
  kind: ConversationKind
  title: string
  other_id: number | null
  member_count: number | null
  is_admin: boolean | null
  last_message: string
  last_message_at: string | null
  unread_count: number
  online: boolean
  last_seen: string | null
}

export interface ChatMessage {
  id: number
  conversation_id: number
  sender_id: number | null
  sender_name: string
  is_ai: boolean
  body: string
  attachment_url: string | null
  attachment_name: string | null
  is_image: boolean
  is_edited: boolean
  is_deleted: boolean
  read_at: string | null
  date_creat: string
}

export interface MessagesPage {
  results: ChatMessage[]
  has_next_page: boolean
}

export interface Member {
  id: number
  name: string
  is_admin: boolean
  is_creator: boolean
  is_me: boolean
}

export interface MembersResponse {
  results: Member[]
  am_admin: boolean
  am_creator: boolean
}

export interface Contact {
  id: number
  name: string
}

export const chatKeys = {
  conversations: ['chat', 'conversations'] as const,
  messages: (id: number) => ['chat', 'messages', id] as const,
  members: (id: number) => ['chat', 'members', id] as const,
  contacts: (q: string) => ['chat', 'contacts', q] as const,
}

/** chat/validators.py: jpg/png/pdf/word/excel, 15 MB gacha */
export const ATTACH_ACCEPT = '.jpg,.jpeg,.png,.pdf,.doc,.docx,.xls,.xlsx'
export const ATTACH_MAX = 15 * 1024 * 1024
export const MAX_BODY = 4000

export function fmtTime(iso: string | null): string {
  if (!iso) return ''
  return new Date(iso).toLocaleTimeString('uz-UZ', { hour: '2-digit', minute: '2-digit' })
}

/** Suhbatlar ro'yxatidagi vaqt: bugun — soat, aks holda sana. */
export function fmtListTime(iso: string | null): string {
  if (!iso) return ''
  const d = new Date(iso)
  const now = new Date()
  if (d.toDateString() === now.toDateString()) return fmtTime(iso)
  const dd = String(d.getDate()).padStart(2, '0')
  const mm = String(d.getMonth() + 1).padStart(2, '0')
  return d.getFullYear() === now.getFullYear() ? `${dd}.${mm}` : `${dd}.${mm}.${d.getFullYear()}`
}

/** Tarjima funksiyasi (useT() natijasi) — yordamchilar hook emas, shuning uchun parametr sifatida beriladi. */
export type TFn = (text: string, vars?: Vars) => string

export function fmtDay(iso: string, t: TFn): string {
  const d = new Date(iso)
  const now = new Date()
  const yesterday = new Date(now)
  yesterday.setDate(now.getDate() - 1)
  if (d.toDateString() === now.toDateString()) return t('Bugun')
  if (d.toDateString() === yesterday.toDateString()) return t('Kecha')
  return `${String(d.getDate()).padStart(2, '0')}.${String(d.getMonth() + 1).padStart(2, '0')}.${d.getFullYear()}`
}

export function fmtLastSeen(iso: string | null, t: TFn): string {
  if (!iso) return t('hech qachon kirmagan')
  const d = new Date(iso)
  const diffMin = Math.round((Date.now() - d.getTime()) / 60000)
  if (diffMin < 1) return t('hozirgina')
  if (diffMin < 60) return t('{n} daqiqa oldin', { n: diffMin })
  if (diffMin < 24 * 60) return t('{n} soat oldin', { n: Math.floor(diffMin / 60) })
  return `${fmtDay(iso, t)} ${fmtTime(iso)}`
}

/** Server "Saqlangan xabarlar" / "AI Yordamchi" nomlarini o'zbekcha beradi — ular tarjima qilinadi; boshqalari (ism, guruh nomi) — yo'q. */
export function convTitle(c: Pick<Conversation, 'kind' | 'title'>, t: TFn): string {
  return c.kind === 'saved' || c.kind === 'ai' ? t(c.title) : c.title
}

export function statusText(c: Conversation, t: TFn): string {
  if (c.kind === 'group') return t("{n} ta a'zo", { n: c.member_count ?? 0 })
  if (c.kind === 'direct') return c.online ? t('Onlayn') : t('Oxirgi faollik: {when}', { when: fmtLastSeen(c.last_seen, t) })
  return ''
}

type WsEvent =
  | { type: 'message' | 'edit' | 'delete'; message: ChatMessage }
  | { type: 'read'; conversation_id: number; reader_id: number; message_ids: number[] }
  | { type: 'group_update'; conversation_id: number }

/**
 * Jonli yangilanishlar: WebSocket /ws/chat/ (sessiya cookie bilan autentifikatsiya, Vite /ws ni proksilaydi).
 * Har 20 soniyada ping ("onlayn" holati). Hodisa kelganda tegishli so'rovlar yangilanadi.
 * Ulanish bo'lmasa `false` qaytadi — sahifa zaxira sifatida davriy so'rovga o'tadi (eski chat.js dagi kabi).
 */
export function useChatSocket(): boolean {
  const qc = useQueryClient()
  const [connected, setConnected] = useState(false)
  const retry = useRef(0)

  useEffect(() => {
    let ws: WebSocket | null = null
    let ping: ReturnType<typeof setInterval> | undefined
    let reconnect: ReturnType<typeof setTimeout> | undefined
    let closed = false

    const connect = () => {
      const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      ws = new WebSocket(`${proto}//${window.location.host}/ws/chat/`)
      ws.onopen = () => {
        retry.current = 0
        setConnected(true)
        ping = setInterval(() => ws?.readyState === WebSocket.OPEN && ws.send(JSON.stringify({ type: 'ping' })), 20000)
      }
      ws.onmessage = (evt) => {
        let data: WsEvent
        try {
          data = JSON.parse(evt.data)
        } catch {
          return
        }
        const convId = 'message' in data ? data.message.conversation_id : data.conversation_id
        if (data.type !== 'read') qc.invalidateQueries({ queryKey: chatKeys.conversations })
        qc.invalidateQueries({ queryKey: chatKeys.messages(convId) })
        if (data.type === 'group_update') qc.invalidateQueries({ queryKey: chatKeys.members(convId) })
      }
      ws.onclose = () => {
        clearInterval(ping)
        setConnected(false)
        if (closed) return
        // 4401/4403 — sessiya yo'q yoki xodim emas: qayta urinish foydasiz
        retry.current += 1
        reconnect = setTimeout(connect, Math.min(30000, 2000 * retry.current))
      }
    }
    connect()
    return () => {
      closed = true
      clearInterval(ping)
      clearTimeout(reconnect)
      ws?.close()
    }
  }, [qc])

  return connected
}
