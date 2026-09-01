const CACHE_NAME = 'darussolah-public-v2';
const APP_SHELL = [
  './',
  './index.html',
  './darussolah-wal-jinan.html',
  './tpq-darul-jinan.html',
  './mdt-darussolah.html',
  './ra-darussolah.html',
  './rtq-darussolah.html',
  './darussolah-institution-site.css',
  './darussolah-institution-site.js',
  './darussolah-config.js',
  './manifest.webmanifest',
  './darussolah-logo-yayasan.jpeg'
];

self.addEventListener('install', event => {
  event.waitUntil(caches.open(CACHE_NAME).then(cache => cache.addAll(APP_SHELL)));
  self.skipWaiting();
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys => Promise.all(keys.filter(key => key !== CACHE_NAME).map(key => caches.delete(key))))
  );
  self.clients.claim();
});

self.addEventListener('fetch', event => {
  const request = event.request;
  const url = new URL(request.url);
  const publicPath = /\/(index|darussolah-wal-jinan|tpq-darul-jinan|mdt-darussolah|ra-darussolah|rtq-darussolah)\.html$/.test(url.pathname)
    || url.pathname === '/' || url.pathname.endsWith('/darussolah-institution-site.css')
    || url.pathname.endsWith('/darussolah-institution-site.js') || url.pathname.endsWith('/darussolah-config.js')
    || url.pathname.endsWith('/manifest.webmanifest') || url.pathname.endsWith('/darussolah-logo-yayasan.jpeg');
  if (request.method !== 'GET' || url.origin !== self.location.origin || !publicPath) return;

  event.respondWith(
    fetch(request)
      .then(response => {
        if (response.ok) {
          const copy = response.clone();
          caches.open(CACHE_NAME).then(cache => cache.put(request, copy));
        }
        return response;
      })
      .catch(() => caches.match(request).then(cached => cached || caches.match('./')))
  );
});
