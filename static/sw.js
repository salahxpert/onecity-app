const CACHE_NAME = 'onecity-v1';
const urlsToCache = [
  '/',
  '/static/manifest.json',
  '/static/icon-192.png',
  '/static/icon-512.png',
  '/login',
  '/accounts',
  '/admin',
  '/collections',
  '/add-collection',
  '/client-ledgers',
  '/emi-track',
  '/employees-list',
  '/salary',
  '/conveyance',
  '/chq-register',
  '/car-requisition',
  '/deed-movement',
  '/token-money',
  '/courier',
  '/hotel-reservation',
  '/gift-ledger',
  '/mr-delivery',
  '/check-requisition',
  '/google-config',
  'https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css',
  'https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css',
  'https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap',
  'https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js'
];

// Install Event
self.addEventListener('install', function(event) {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(function(cache) {
        console.log('Opened cache');
        return cache.addAll(urlsToCache);
      })
      .catch(function(error) {
        console.log('Cache addAll error:', error);
      })
  );
  self.skipWaiting();
});

// Activate Event
self.addEventListener('activate', function(event) {
  event.waitUntil(
    caches.keys().then(function(cacheNames) {
      return Promise.all(
        cacheNames.map(function(cacheName) {
          if (cacheName !== CACHE_NAME) {
            console.log('Deleting old cache:', cacheName);
            return caches.delete(cacheName);
          }
        })
      );
    })
  );
  return self.clients.claim();
});

// Fetch Event
self.addEventListener('fetch', function(event) {
  event.respondWith(
    caches.match(event.request)
      .then(function(response) {
        if (response) {
          return response;
        }
        var fetchRequest = event.request.clone();
        return fetch(fetchRequest).then(
          function(response) {
            if (!response || response.status !== 200 || response.type !== 'basic') {
              return response;
            }
            var responseToCache = response.clone();
            caches.open(CACHE_NAME)
              .then(function(cache) {
                cache.put(event.request, responseToCache);
              });
            return response;
          }
        );
      })
  );
});

// ===== Periodic Sync =====
self.addEventListener('periodicsync', function(event) {
  if (event.tag === 'sync-data') {
    event.waitUntil(
      fetch('/api/db_stats')
        .then(function(response) {
          if (!response.ok) throw new Error('Network error');
          return response.json();
        })
        .then(function(data) {
          console.log('Periodic sync completed:', data);
          caches.open('onecity-v1')
            .then(function(cache) {
              cache.put('/api/db_stats', new Response(JSON.stringify(data)));
            });
        })
        .catch(function(error) {
          console.log('Periodic sync failed:', error);
        })
    );
  }
});

// ===== Background Sync =====
self.addEventListener('sync', function(event) {
  if (event.tag === 'sync-collection') {
    event.waitUntil(
      console.log('Background sync triggered for collections')
    );
  }
});