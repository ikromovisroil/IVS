/* IVS: brauzer push (Web Push) service worker. Django uni /app/sw.js manzilidan beradi (config/spa.py). */

self.addEventListener('install', () => self.skipWaiting())
self.addEventListener('activate', (event) => event.waitUntil(self.clients.claim()))

self.addEventListener('push', (event) => {
  let data = {}
  try {
    data = event.data ? event.data.json() : {}
  } catch {
    data = { body: event.data ? event.data.text() : '' }
  }
  const options = {
    body: data.body || '',
    icon: data.icon || '/static/img/apple-touch-icon.png',
    badge: data.icon || '/static/img/apple-touch-icon.png',
    data: { url: data.url || '/app/' },
  }
  // Bir xil tag eski bildirishnomani jim almashtiradi — server har bir hodisaga yangi tag beradi
  if (data.tag) options.tag = data.tag
  event.waitUntil(self.registration.showNotification(data.title || 'IVS', options))
})

// Faqat shu saytning /app/ ostidagi manzillari ochiladi (boshqa manzil bo'lsa bosh sahifa)
function safeTarget(url) {
  try {
    const target = new URL(url || '/app/', self.location.origin)
    if (target.origin === self.location.origin && target.pathname.startsWith('/app/')) return target.href
  } catch {
    /* noto'g'ri manzil */
  }
  return new URL('/app/', self.location.origin).href
}

self.addEventListener('notificationclick', (event) => {
  event.notification.close()
  const target = safeTarget(event.notification.data && event.notification.data.url)
  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((windows) => {
      for (const client of windows) {
        if (client.url.startsWith(self.location.origin + '/app/') && 'focus' in client) {
          return client.focus().then(() => ('navigate' in client ? client.navigate(target) : undefined))
        }
      }
      return self.clients.openWindow(target)
    }),
  )
})
