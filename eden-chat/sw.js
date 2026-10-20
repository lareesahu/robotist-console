const CACHE = 'eden-chat-v1';
self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll([
    '/eden-chat-v2.html',
    '/eden-chat/avatars/sienna-sfw.webp',
    '/eden-chat/avatars/lynne-sfw.webp',
    '/eden-chat/avatars/dream.png',
    '/eden-chat/avatars/hope.png',
    '/eden-chat/avatars/lucian-sfw.webp',
    '/eden-chat/icon-192.png',
    '/eden-chat/icon-512.png'
  ])));
});
self.addEventListener('fetch', e => {
  e.respondWith(caches.match(e.request).then(r => r || fetch(e.request)));
});
