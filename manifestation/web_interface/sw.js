/* Service worker de OmniaMentis: solo hace instalable la app y guarda la CÁSCARA (pantalla) para que abra sin red.
 * NUNCA guarda nada de la API ni datos de la persona: solo atiende GET del mismo origen a archivos estáticos.
 * El chat y los módulos siguen necesitando conexión con el servidor. */
const CACHE = 'omnia-shell-v2';
const SHELL = ['./omnia_dashboard.html', './manifest.webmanifest', './icons/icon-192.png', './icons/icon-512.png'];
const STATIC_EXT = /\.(html|js|css|png|svg|webmanifest|ico)$/i;

self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(SHELL)).then(() => self.skipWaiting()));
});
self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== CACHE).map(k => caches.delete(k))))
    .then(() => self.clients.claim()));
});
self.addEventListener('fetch', e => {
  const req = e.request, url = new URL(req.url);
  if (req.method !== 'GET' || url.origin !== self.location.origin) return;       // API en otro origen: no se toca
  const nav = req.mode === 'navigate';                                           // abrir la app (p. ej. /app/)
  if (url.pathname.includes('/api/') || (!nav && !STATIC_EXT.test(url.pathname))) return;  // ni API ni nada dinámico
  e.respondWith(
    fetch(req).then(res => {                                                     // red primero: siempre la versión nueva
      if (res.ok) { const copy = res.clone(); caches.open(CACHE).then(c => c.put(req, copy)); }
      return res;
    }).catch(() => caches.match(req).then(r => r || (req.mode === 'navigate' ? caches.match('./omnia_dashboard.html') : Response.error())))
  );
});
