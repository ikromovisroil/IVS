import { useCallback, useState } from 'react'
import type { ReactNode } from 'react'
import { Icon } from '../ds'
import { useTMaybe } from '../i18n'
import { ToastContext } from './toast'
import type { ToastTone } from './toast'

interface Toast {
  id: number
  tone: ToastTone
  text: string
}

const ICONS: Record<ToastTone, string> = {
  success: 'ri-checkbox-circle-fill',
  error: 'ri-error-warning-fill',
  info: 'ri-information-fill',
}

let seq = 0

export default function ToastProvider({ children }: { children: ReactNode }) {
  const t = useTMaybe()
  const [items, setItems] = useState<Toast[]>([])

  const show = useCallback((text: string, tone: ToastTone = 'success') => {
    const id = ++seq
    setItems((xs) => [...xs, { id, tone, text }])
    setTimeout(() => setItems((xs) => xs.filter((x) => x.id !== id)), 4000)
  }, [])

  return (
    <ToastContext.Provider value={show}>
      {children}
      <div className="ivs-toasts" role="status" aria-live="polite">
        {items.map((it) => (
          <div key={it.id} className={`ivs-toast is-${it.tone}`}>
            <Icon name={ICONS[it.tone]} size={20} />
            <span>{t(it.text)}</span>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}
