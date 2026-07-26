// Service Worker — Web Push (M20): hiện popup thông báo desktop + điều hướng khi click.
// Không cache gì (chưa phải PWA đầy đủ), chỉ phục vụ push/notificationclick.

self.addEventListener('install', () => {
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(self.clients.claim());
});

self.addEventListener('push', (event) => {
  let payload = {};
  try {
    payload = event.data ? event.data.json() : {};
  } catch {
    payload = { title: 'Thông báo mới', body: event.data ? event.data.text() : '' };
  }

  const title = payload.title || 'Viện Sinh học — Thông báo mới';
  const options = {
    body: payload.body || '',
    icon: '/notification-icon-192.png', // logo RIBE
    badge: '/notification-badge-72.png',
    data: { url: '/notifications' },
    tag: payload.notification_id || undefined,
    // Định dạng gọn, dễ đọc trên desktop
    lang: 'vi',
    dir: 'ltr',
    requireInteraction: false,
    silent: false,
  };

  event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const targetUrl = event.notification.data?.url || '/notifications';

  event.waitUntil(
    (async () => {
      const clientsList = await self.clients.matchAll({ type: 'window', includeUncontrolled: true });
      for (const client of clientsList) {
        if ('focus' in client) {
          client.postMessage({ type: 'notification-click', url: targetUrl });
          return client.focus();
        }
      }
      if (self.clients.openWindow) {
        return self.clients.openWindow(targetUrl);
      }
    })(),
  );
});
