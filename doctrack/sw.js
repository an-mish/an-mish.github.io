const SHELL = 'doctrack-shell-v4';
const DATA = 'doctrack-data';
const FILES = ['./', 'index.html', 'manifest.webmanifest', 'icon.svg', 'icon-192.png', 'icon-512.png'];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(SHELL).then(c => c.addAll(FILES)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', e => {
  e.waitUntil(caches.keys()
    .then(keys => Promise.all(keys.filter(k => k !== SHELL && k !== DATA).map(k => caches.delete(k))))
    .then(() => self.clients.claim()));
});

// Network first so updates arrive; fall back to cache offline.
self.addEventListener('fetch', e => {
  if (e.request.method !== 'GET' || new URL(e.request.url).origin !== location.origin) return;
  e.respondWith(fetch(e.request)
    .then(res => {
      if (res.ok) { const copy = res.clone(); caches.open(SHELL).then(c => c.put(e.request, copy)); }
      return res;
    })
    .catch(() => caches.match(e.request, { ignoreSearch: true })));
});

// The page mirrors its list here, because a service worker cannot read localStorage.
self.addEventListener('message', e => {
  if (e.data?.type === 'docs') {
    e.waitUntil(caches.open(DATA).then(c => c.put('docs.json', new Response(JSON.stringify(e.data.docs)))));
  }
});

const DAY = 86400000;
const parseDate = s => { const [y, m, d] = s.split('-').map(Number); return new Date(y, m - 1, d); };
const fmtISO = d => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
function subtractLead(expires, value, unit) {
  const d = new Date(expires);
  if (unit === 'm') {
    const day = d.getDate();
    d.setDate(1); d.setMonth(d.getMonth() - value);
    d.setDate(Math.min(day, new Date(d.getFullYear(), d.getMonth() + 1, 0).getDate()));
  } else d.setDate(d.getDate() - value * (unit === 'w' ? 7 : 1));
  return d;
}

async function backgroundCheck() {
  const cache = await caches.open(DATA);
  const docsRes = await cache.match('docs.json');
  if (!docsRes) return;
  const docs = await docsRes.json();
  const sentRes = await cache.match('notified.json');
  const sent = sentRes ? await sentRes.json() : {};
  const n = new Date(), t = new Date(n.getFullYear(), n.getMonth(), n.getDate()), tISO = fmtISO(t);
  for (const d of docs) {
    const exp = parseDate(d.expires);
    const left = Math.round((exp - t) / DAY);
    if (t < subtractLead(exp, d.leadValue, d.leadUnit) || sent[d.id] === tISO) continue;
    const body = left < 0 ? `«${d.name}» истёк. Срочно обновите документ.`
      : left === 0 ? `«${d.name}» истекает сегодня!`
      : `Пора обновить «${d.name}»: осталось ${left} дн.`;
    await self.registration.showNotification('Обновите документ', { body, tag: d.id, icon: 'icon-192.png' });
    sent[d.id] = tISO;
  }
  await cache.put('notified.json', new Response(JSON.stringify(sent)));
}

self.addEventListener('periodicsync', e => {
  if (e.tag === 'doc-check') e.waitUntil(backgroundCheck());
});

self.addEventListener('notificationclick', e => {
  e.notification.close();
  e.waitUntil(self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then(list => {
    const win = list.find(c => c.url.includes('/doctrack/'));
    return win ? win.focus() : self.clients.openWindow('./');
  }));
});
