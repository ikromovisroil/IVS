self.addEventListener('push', function (event) {
  let data = {};
  try {
    data = event.data ? event.data.json() : {};
  } catch (e) {
    data = { title: 'Bildirishnoma', body: event.data ? event.data.text() : '' };
  }

  const title = data.title || 'Bildirishnoma';
  const options = {
    body: data.body || '',
    icon: data.icon || '/static/img/apple-touch-icon.png',
    badge: '/static/img/apple-touch-icon.png',
    data: { url: data.url || '/' },
    // Backend'dan kelgan unikal tag ishlatiladi (masalan "order-new-123").
    // Agar backend tag yubormasa, fallback sifatida title ishlatiladi.
    tag: data.tag || title,
    // renotify: true — tag bir xil bo'lib qolgan holatlarda ham
    // foydalanuvchiga baribir ovozli/vibratsion signal bilan xabar
    // beriladi, notification JIM almashtirilmaydi.
    renotify: true,
  };

  event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener('notificationclick', function (event) {
  event.notification.close();
  const url = (event.notification.data && event.notification.data.url) || '/';

  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then(function (clientList) {
      for (const client of clientList) {
        if (client.url.includes(url) && 'focus' in client) {
          return client.focus();
        }
      }
      if (clients.openWindow) {
        return clients.openWindow(url);
      }
    })
  );
});