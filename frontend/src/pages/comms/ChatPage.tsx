import { useEffect, useRef, useState } from 'react'
import EmptyState from '../../components/EmptyState'
import { useQuery } from '@tanstack/react-query'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { Icon } from '../../ds'
import Page from '../../layout/Page'
import { api } from '../../api/client'
import { useMe } from '../../auth/me'
import { useT } from '../../i18n'
import { chatKeys, useChatSocket } from './chatApi'
import type { Conversation } from './chatApi'
import ConversationList from './ConversationList'
import type { ChatTab } from './ConversationList'
import ChatThread from './ChatThread'
import ChatInfo from './ChatInfo'
import { themeColor, useAppearance } from './appearance'
import './comms.css'

/** Chat (eski /chat/ — templates/chat/chat.html + static/js/chat.js). /chat/:id — ochiq suhbat. */
export default function ChatPage() {
  const t = useT()
  const me = useMe()
  const myId = me.employee?.id ?? 0
  const { id } = useParams()
  const activeId = id ? Number(id) : null
  const navigate = useNavigate()
  const [params, setParams] = useSearchParams()
  const tab: ChatTab = params.get('tab') === 'group' ? 'group' : 'direct'
  const [infoOpen, setInfoOpen] = useState(false)
  const [appearance, setAppearance] = useAppearance()
  const live = useChatSocket()

  const convs = useQuery({
    queryKey: chatKeys.conversations,
    queryFn: () => api<{ results: Conversation[] }>('/chat/conversations/').then((d) => d.results),
    refetchInterval: 20000,
    enabled: !!me.employee,
  })
  const active = convs.data?.find((c) => c.id === activeId)

  // Boshqa turdagi suhbat ochilsa (masalan, guruh) mos yorliq tanlanadi — har suhbat uchun bir marta,
  // aks holda foydalanuvchi ochiq suhbat turib yorliqni almashtira olmaydi
  const syncedId = useRef<number | null>(null)
  useEffect(() => {
    if (!active || active.kind === 'saved' || syncedId.current === active.id) return
    syncedId.current = active.id
    const want: ChatTab = active.kind === 'group' ? 'group' : 'direct'
    if (want !== tab) setParams((p) => (want === 'group' ? p.set('tab', 'group') : p.delete('tab'), p), { replace: true })
  }, [active, tab, setParams])

  const open = (cid: number) => navigate({ pathname: `/chat/${cid}`, search: params.toString() })
  const close = () => {
    setInfoOpen(false)
    navigate({ pathname: '/chat', search: params.toString() })
  }

  if (!me.employee) {
    return (
      <Page icon="ri-chat-3-line" title="Chat">
        <EmptyState icon="ri-lock-line" title="Ruxsat yo'q" description="Chat faqat xodimlar uchun." />
      </Page>
    )
  }

  return (
    <Page icon="ri-chat-3-line" title="Chat" subtitle="Xodimlar bilan yozishmalar, guruhlar va saqlangan xabarlar.">
      <div
        className={`cm-chat${activeId ? ' has-active' : ''}${infoOpen && active ? ' has-info' : ''}`}
        style={{ '--cm-accent': themeColor(appearance.theme) } as React.CSSProperties}
        data-wallpaper={appearance.wallpaper}
      >
        <ConversationList
          conversations={convs.data}
          loading={convs.isPending}
          error={convs.error}
          activeId={activeId}
          tab={tab}
          onTab={(tb) => setParams((p) => (tb === 'group' ? p.set('tab', 'group') : p.delete('tab'), p), { replace: true })}
          onOpen={open}
        />
        <section className="cm-main" aria-label={t('Suhbat')}>
          {active ? (
            <ChatThread
              key={active.id}
              conv={active}
              myId={myId}
              live={live}
              onBack={close}
              infoOpen={infoOpen}
              onInfo={() => setInfoOpen((o) => !o)}
            />
          ) : (
            <div className="cm-empty">
              <Icon name="ri-chat-3-line" size={40} />
              {t(activeId && !convs.isPending ? 'Suhbat topilmadi' : 'Chapdan suhbat tanlang yoki yangisini boshlang')}
            </div>
          )}
        </section>
        {infoOpen && active && (
          <ChatInfo
            key={active.id}
            conv={active}
            myId={myId}
            appearance={appearance}
            onAppearance={setAppearance}
            onClose={() => setInfoOpen(false)}
            onLeft={close}
          />
        )}
      </div>
      <div className="cm-live type-para-xs" title={t(live ? 'Jonli ulanish (WebSocket)' : 'WebSocket ulanmagan — har 4 soniyada yangilanadi')}>
        <span className={`cm-live-dot${live ? ' is-on' : ''}`} />
        {t(live ? 'Jonli' : 'Davriy yangilanish')}
      </div>
    </Page>
  )
}
