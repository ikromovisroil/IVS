import { createContext, useContext } from 'react'

export type ToastTone = 'success' | 'error' | 'info'

export const ToastContext = createContext<(text: string, tone?: ToastTone) => void>(() => {})

/** toast("Saqlandi") — pastki o'ng burchakda 4 soniya ko'rinadi (ToastProvider.tsx). */
export function useToast() {
  return useContext(ToastContext)
}
