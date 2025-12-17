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
    
    // Only cache API requests
    if (url.pathname.includes('/api/')) {
        event.respondWith(
            caches.open(CACHE_NAME).then((cache) => {
                return cache.match(event.request).then((cachedResponse) => {
                    // Check if cached response is still fresh
                    if (cachedResponse) {
                        const cachedTime = new Date(cachedResponse.headers.get('sw-cached-time'));
                        const now = new Date();
                        
                        if (now - cachedTime < CACHE_DURATION) {
                            console.log('Serving from cache:', url.pathname);
                            return cachedResponse;
                        }
                    }
                    
                    // Fetch fresh data
                    return fetch(event.request).then((response) => {
                        // Clone response and add timestamp
                        const responseToCache = response.clone();
                        const headers = new Headers(responseToCache.headers);
                        headers.append('sw-cached-time', new Date().toISOString());
                        
                        const newResponse = new Response(responseToCache.body, {
                            status: responseToCache.status,
                            statusText: responseToCache.statusText,
                            headers: headers
                        });
                        
                        cache.put(event.request, newResponse);
                        return response;
                    });
                });
            })
        );
    }
});
