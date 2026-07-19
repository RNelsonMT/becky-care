// Becky's Care Service Worker v2
const CACHE = 'becky-care-v6';
const ASSETS = [
  '/becky-care/',
  '/becky-care/index.html',
  '/becky-care/manifest.json',
  '/becky-care/icon-192.png',
  '/becky-care/icon-512.png',
];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(ASSETS)));
  self.skipWaiting();
});

self.addEventListener('activate', e => {
  // Clear ALL old caches
  e.waitUntil(caches.keys().then(keys =>
    Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))
  ));
  self.clients.claim();
});

self.addEventListener('fetch', e => {
  const url = e.request.url;
  
  // Never intercept Firebase, Google APIs, or external requests
  if (url.includes('firestore.googleapis.com') ||
      url.includes('firebase') ||
      url.includes('googleapis.com') ||
      url.includes('gstatic.com') ||
      url.includes('medlineplus.gov') ||
      !url.startsWith(self.location.origin)) {
    return; // Let these go through normally
  }
  
  // For app files: network first, fall back to cache
  e.respondWith(
    fetch(e.request)
      .then(response => {
        // Update cache with fresh response
        const clone = response.clone();
        caches.open(CACHE).then(c => c.put(e.request, clone));
        return response;
      })
      .catch(() => caches.match(e.request))
  );
});
