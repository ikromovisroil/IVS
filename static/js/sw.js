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
    tag: title,
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