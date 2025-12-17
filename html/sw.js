// Service Worker for caching API responses and static assets
const CACHE_NAME = 'oddsmagnet-v1';
const CACHE_DURATION = 5 * 60 * 1000; // 5 minutes

self.addEventListener('install', (event) => {
    console.log('Service Worker installing...');
    self.skipWaiting();
});

self.addEventListener('activate', (event) => {
    console.log('Service Worker activating...');
    event.waitUntil(
        caches.keys().then((cacheNames) => {
            return Promise.all(
                cacheNames.map((cacheName) => {
                    if (cacheName !== CACHE_NAME) {
                        return caches.delete(cacheName);
                    }
                })
            );
        })
    );
    return self.clients.claim();
});

self.addEventListener('fetch', (event) => {
    const url = new URL(event.request.url);
    
    // DO NOT cache API requests - we need real-time data!
    // WebSocket provides real-time updates, HTTP uses ETag validation
    // Caching API responses blocks real-time updates and shows stale data
    
    if (url.pathname.includes('/api/') || url.pathname.includes('/om/')) {
        // Just pass through - no caching for real-time data
        // ETag validation handles efficiency
        return; // Let browser handle it normally
    }
    
    // For static assets (HTML, CSS, JS, images), cache aggressively
    if (url.pathname.match(/\.(html|css|js|png|jpg|svg|woff2)$/)) {
        event.respondWith(
            caches.open(CACHE_NAME).then((cache) => {
                return cache.match(event.request).then((cachedResponse) => {
                    if (cachedResponse) {
                        return cachedResponse;
                    }
                    
                    return fetch(event.request).then((response) => {
                        cache.put(event.request, response.clone());
                        return response;
                    });
                });
            })
        );
    }
});
