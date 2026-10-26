import { useCallback, useEffect, useState } from 'react'
import { api } from '../api/client'

/**
 * Brauzer push (Web Push): service worker (/app/sw.js, Django beradi) + obuna.
 * Server: /api/v1/push/ (api/push_views.py). Yuborish: main.push_views.send_push_notification.
 */
const SW_URL = '/app/sw.js'
const SW_SCOPE = '/app/'

export type PushState = 'loading' | 'unsupported' | 'denied' | 'off' | 'on'

export const pushSupported = () =>
  typeof window !== 'undefined' && 'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window

/** VAPID kaliti (base64url) → PushManager kutadigan baytlar */
function keyBytes(base64Url: string): Uint8Array<ArrayBuffer> {
  const padded = (base64Url + '='.repeat((4 - (base64Url.length % 4)) % 4)).replace(/-/g, '+').replace(/_/g, '/')
  const raw = atob(padded)
  const out = new Uint8Array(new ArrayBuffer(raw.length))
  for (let i = 0; i < raw.length; i++) out[i] = raw.charCodeAt(i)
  return out
}

async function registration(): Promise<ServiceWorkerRegistration> {
  await navigator.serviceWorker.register(SW_URL, { scope: SW_SCOPE })
  return navigator.serviceWorker.ready
}

async function currentSubscription(): Promise<PushSubscription | null> {
  const reg = await navigator.serviceWorker.getRegistration(SW_SCOPE)
  return reg ? reg.pushManager.getSubscription() : null
}

/** Obunani serverga yozadi (xodimga bog'laydi) */
async function sendToServer(sub: PushSubscription) {
  const json = sub.toJSON()
  await api('/push/subscribe/', { method: 'POST', body: JSON.stringify({ endpoint: json.endpoint, keys: json.keys }) })
}

export async function enablePush(): Promise<PushState> {
  if (!pushSupported()) return 'unsupported'
  const permission = await Notification.requestPermission()
  if (permission !== 'granted') return permission === 'denied' ? 'denied' : 'off'
  const reg = await registration()
  let sub = await reg.pushManager.getSubscription()
  if (!sub) {
    const { public_key } = await api<{ public_key: string }>('/push/public-key/')
    sub = await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: keyBytes(public_key) })
  }
  await sendToServer(sub)
  return 'on'
}

export async function disablePush(): Promise<PushState> {
  const sub = await currentSubscription()
  if (sub) {
    await api('/push/unsubscribe/', { method: 'POST', body: JSON.stringify({ endpoint: sub.endpoint }) }).catch(() => undefined)
    await sub.unsubscribe()
  }
  return 'off'
}

async function readState(): Promise<PushState> {
  if (!pushSupported()) return 'unsupported'
  if (Notification.permission === 'denied') return 'denied'
  const sub = await currentSubscription()
  if (!sub) return 'off'
  // Brauzerda obuna bor, lekin serverda yo'q bo'lishi mumkin (boshqa xodim kirgan / o'chirilgan) — qayta bog'lanadi
  const status = await api<{ subscribed: boolean }>('/push/status/', { query: { endpoint: sub.endpoint } }).catch(() => null)
  if (status && !status.subscribed) await sendToServer(sub).catch(() => undefined)
  return 'on'
}

/** Sozlamalar paneli uchun: holat va yoqish/o'chirish */
export function usePush() {
  const [state, setState] = useState<PushState>('loading')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let alive = true
    readState().then(
      (s) => alive && setState(s),
      () => alive && setState('off'),
    )
    return () => {
      alive = false
    }
  }, [])

  const toggle = useCallback(async (on: boolean) => {
    setBusy(true)
    setError(null)
    try {
      setState(on ? await enablePush() : await disablePush())
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
      setState(await readState().catch(() => 'off' as PushState))
    } finally {
      setBusy(false)
    }
  }, [])

  return { state, busy, error, toggle }
}
