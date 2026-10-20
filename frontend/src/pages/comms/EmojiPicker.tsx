import { useEffect, useRef, useState } from 'react'
import { Button } from '../../ds'
import { useT } from '../../i18n'

// Eski chat.js dagi to'plam (guruhlar bo'yicha)
const EMOJIS = [
  '😀', '😃', '😄', '😁', '😆', '😅', '🤣', '😂', '🙂', '🙃', '😉', '😊', '😇', '🥰', '😍', '🤩', '😘', '😗', '😚', '😙',
  '😋', '😛', '😜', '🤪', '😝', '🤑', '🤗', '🤭', '🤫', '🤔', '🤐', '🤨', '😐', '😑', '😶', '😏', '😒', '🙄', '😬', '🤥',
  '😌', '😔', '😪', '🤤', '😴', '😷', '🤒', '🤕', '🤢', '🤮', '🥵', '🥶', '🥴', '😵', '🤯', '🤠', '🥳', '😎', '🤓', '🧐',
  '😕', '😟', '🙁', '☹️', '😮', '😯', '😲', '😳', '🥺', '😦', '😧', '😨', '😰', '😥', '😢', '😭', '😱', '😖', '😣', '😞',
  '😓', '😩', '😫', '🥱', '😤', '😡', '😠', '🤬', '😈', '👿',
  '👋', '🤚', '🖐️', '✋', '🖖', '👌', '🤌', '🤏', '✌️', '🤞', '🤟', '🤘', '🤙', '👈', '👉', '👆', '👇', '☝️', '👍',
  '👎', '✊', '👊', '🤛', '🤜', '👏', '🙌', '👐', '🤲', '🙏', '💪', '🦾', '🫶', '🤝', '💅', '🧠',
  '❤️', '🧡', '💛', '💚', '💙', '💜', '🖤', '🤍', '🤎', '💔', '❣️', '💕', '💞', '💓', '💗', '💖', '💘', '💝', '💯', '✅',
  '❌', '❗', '❓', '⚠️', '🔥', '✨', '🎉', '🎊', '🎈', '🎁', '🏆', '🥇', '⭐', '🌟', '💤', '💢', '💬',
  '🧑', '👨', '👩', '🧓', '👴', '👵', '👶', '🧑‍💻', '👨‍💼', '👩‍💼', '🕵️', '👮', '🧑‍⚕️', '👨‍🏫', '👩‍🏫', '🧑‍🔧',
  '🐶', '🐱', '🐭', '🐹', '🐰', '🦊', '🐻', '🐼', '🐨', '🐯', '🦁', '🐮', '🐷', '🐸', '🐵', '🐔', '🐧', '🐦', '🦄', '🐝',
  '🌸', '🌼', '🌻', '🌈', '☀️', '⛅', '☁️', '🌧️', '❄️', '🌙',
  '🍏', '🍎', '🍊', '🍋', '🍌', '🍉', '🍇', '🍓', '🍒', '🍑', '🍕', '🍔', '🍟', '🌭', '🥪', '🌮', '🍣', '🍜', '🍦', '🍩',
  '🍪', '🎂', '☕', '🍵', '🥤', '🍺', '🍷',
  '⚽', '🏀', '🏈', '⚾', '🎾', '🏐', '🏓', '🎯', '🎮', '🎲', '🎸', '🎹', '🎤', '🎧', '🚴', '🏃', '🧘',
  '🚗', '🚕', '🚌', '🚀', '✈️', '🚲', '⛵', '🚦', '🗺️', '🏠',
  '💻', '📱', '⌚', '📷', '💡', '🔋', '📎', '📌', '📅', '📞', '✉️', '📩', '📝', '📚', '🔑', '🔒', '🔓', '💰', '💳', '🎓',
]

/** Smayliklar paneli: tanlangani kursor joyiga qo'yiladi; tashqariga bosilsa yopiladi. */
export default function EmojiPicker({ onPick }: { onPick: (emoji: string) => void }) {
  const t = useT()
  const [open, setOpen] = useState(false)
  const wrap = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const close = (e: MouseEvent) => {
      if (!wrap.current?.contains(e.target as Node)) setOpen(false)
    }
    const esc = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false)
    document.addEventListener('mousedown', close)
    document.addEventListener('keydown', esc)
    return () => {
      document.removeEventListener('mousedown', close)
      document.removeEventListener('keydown', esc)
    }
  }, [open])

  return (
    <div className="cm-emoji" ref={wrap}>
      <Button type="button" variant={open ? 'lighter' : 'ghost'} iconOnly icon="ri-emotion-line" aria-label={t('Smaylik')} title={t('Smaylik')} aria-expanded={open} onClick={() => setOpen((o) => !o)} />
      {open && (
        <div className="cm-emoji-panel" role="dialog" aria-label={t('Smayliklar')}>
          {EMOJIS.map((e) => (
            <button key={e} type="button" className="cm-emoji-item" onClick={() => onPick(e)}>
              {e}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
