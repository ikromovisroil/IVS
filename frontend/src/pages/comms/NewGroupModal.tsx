import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Avatar, Button, Checkbox, TextInput } from '../../ds'
import Modal from '../../components/Modal'
import SearchInput from '../../components/SearchInput'
import { api } from '../../api/client'
import { avatarColor, initials } from '../../lib/format'
import { useT } from '../../i18n'
import { chatKeys } from './chatApi'
import type { Contact } from './chatApi'

/** Yangi guruh: nomi + kamida 2 ta xodim (o'zingizdan tashqari). */
export default function NewGroupModal({ onClose, onCreated }: { onClose: () => void; onCreated: (id: number) => void }) {
  const t = useT()
  const qc = useQueryClient()
  const [name, setName] = useState('')
  const [q, setQ] = useState('')
  const [selected, setSelected] = useState<Map<number, string>>(new Map())
  const [error, setError] = useState<string | null>(null)

  const contacts = useQuery({
    queryKey: chatKeys.contacts(q),
    queryFn: () => api<{ results: Contact[] }>('/chat/contacts/', { query: { q } }).then((d) => d.results),
  })

  const create = useMutation({
    mutationFn: () =>
      api<{ conversation_id: number }>('/chat/groups/', { method: 'POST', body: JSON.stringify({ name: name.trim(), members: [...selected.keys()] }) }),
    onSuccess: async (r) => {
      await qc.invalidateQueries({ queryKey: chatKeys.conversations })
      onCreated(r.conversation_id)
    },
    onError: (e) => setError(e.message),
  })

  const toggle = (c: Contact) =>
    setSelected((m) => {
      const next = new Map(m)
      if (next.has(c.id)) next.delete(c.id)
      else next.set(c.id, c.name)
      return next
    })

  const submit = () => {
    if (!name.trim()) return setError(t('Guruh nomini kiriting'))
    if (selected.size < 2) return setError(t('Kamida 2 ta xodim tanlang'))
    setError(null)
    create.mutate()
  }

  return (
    <Modal
      open
      onClose={onClose}
      icon="ri-group-line"
      title="Yangi guruh"
      subtitle="O'zingizdan tashqari kamida 2 ta xodim tanlang."
      width={520}
      footer={
        <>
          <Button variant="stroke" size="lg" onClick={onClose}>
            {t('Bekor qilish')}
          </Button>
          <Button size="lg" icon="ri-check-line" loading={create.isPending} onClick={submit}>
            {t('Guruh yaratish')}
          </Button>
        </>
      }
    >
      <div className="cm-group-form">
        <TextInput label={t('Guruh nomi')} placeholder={t('Guruh nomi...')} value={name} maxLength={120} onChange={(e) => setName(e.target.value)} />
        <SearchInput value={q} onChange={setQ} placeholder="Xodim qidirish..." delay={250} style={{ width: '100%' }} />
        <div className="cm-group-list">
          {contacts.isPending ? (
            <div className="cm-hint">{t('Yuklanmoqda…')}</div>
          ) : contacts.data?.length ? (
            contacts.data.map((c) => (
              <label key={c.id} className="cm-group-row">
                <Checkbox checked={selected.has(c.id)} onChange={() => toggle(c)} aria-label={c.name} />
                <Avatar size={32} name={c.name} initials={initials(c.name)} color={avatarColor(c.id)} />
                <span className="type-para-sm">{c.name}</span>
              </label>
            ))
          ) : (
            <div className="cm-hint">{t('Xodim topilmadi')}</div>
          )}
        </div>
        <div className="type-label-sm cm-muted">{t('{n} ta xodim tanlandi', { n: selected.size })}</div>
        {error && (
          <div className="cm-error type-para-sm" role="alert">
            {error}
          </div>
        )}
      </div>
    </Modal>
  )
}
