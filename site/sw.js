// Finantsabi service worker: rakenduse kest vahemälus, andmed võrgust (vahemälu tagavaraks).
const CACHE = 'finantsabi-v1';
const SHELL = ['./', 'index.html', 'manifest.webmanifest', 'icon-192.png', 'icon-512.png', 'apple-touch-icon.png'];
self.addEventListener('install', e => { e.waitUntil(caches.open(CACHE).then(c => c.addAll(SHELL)).then(() => self.skipWaiting())); });
self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== CACHE).map(k => caches.delete(k)))).then(() => self.clients.claim()));
});
self.addEventListener('fetch', e => {
  const url = new URL(e.request.url);
  if (e.request.method !== 'GET' || url.origin !== location.origin) return;
  if (url.pathname.endsWith('data.enc')) {
    // võrk enne, vahemälu kui võrku pole
    e.respondWith(fetch(e.request).then(r => { const c = r.clone(); caches.open(CACHE).then(x => x.put('data.enc', c)); return r; })
      .catch(() => caches.match('data.enc')));
    return;
  }
  // kest: võrk enne (et uuendused jõuaks kohe kohale), vahemälu offline jaoks
  e.respondWith(fetch(e.request).then(r => { const c = r.clone(); caches.open(CACHE).then(x => x.put(e.request, c)); return r; })
    .catch(() => caches.match(e.request).then(r => r || caches.match('index.html'))));
});
