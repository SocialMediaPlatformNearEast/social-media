const ASSET_VERSION = '88';
const STATIC_CACHE = `lvl-static-v${ASSET_VERSION}`;
const STATIC_ASSETS = [
  `/static/css/styles.css?v=${ASSET_VERSION}`,
  `/static/css/gender.css?v=${ASSET_VERSION}`,
  `/static/css/sections/auth.css?v=${ASSET_VERSION}`,
  `/static/css/sections/base.css?v=${ASSET_VERSION}`,
  `/static/css/sections/community-highlights.css?v=${ASSET_VERSION}`,
  `/static/css/sections/community-timeline.css?v=${ASSET_VERSION}`,
  `/static/css/sections/community.css?v=${ASSET_VERSION}`,
  `/static/css/sections/design-system.css?v=${ASSET_VERSION}`,
  `/static/css/sections/feed.css?v=${ASSET_VERSION}`,
  `/static/css/sections/feedback.css?v=${ASSET_VERSION}`,
  `/static/css/sections/hardening.css?v=${ASSET_VERSION}`,
  `/static/css/sections/home-reels.css?v=${ASSET_VERSION}`,
  `/static/css/sections/home.css?v=${ASSET_VERSION}`,
  `/static/css/sections/legacy-polish.css?v=${ASSET_VERSION}`,
  `/static/css/sections/message-discovery.css?v=${ASSET_VERSION}`,
  `/static/css/sections/messages.css?v=${ASSET_VERSION}`,
  `/static/css/sections/mobile-drawer.css?v=${ASSET_VERSION}`,
  `/static/css/sections/mobile-navigation.css?v=${ASSET_VERSION}`,
  `/static/css/sections/navigation.css?v=${ASSET_VERSION}`,
  `/static/css/sections/notification-badge.css?v=${ASSET_VERSION}`,
  `/static/css/sections/notifications.css?v=${ASSET_VERSION}`,
  `/static/css/sections/profile-mobile.css?v=${ASSET_VERSION}`,
  `/static/css/sections/profile.css?v=${ASSET_VERSION}`,
  `/static/css/sections/reels.css?v=${ASSET_VERSION}`,
  `/static/css/sections/rewards.css?v=${ASSET_VERSION}`,
  `/static/css/sections/search.css?v=${ASSET_VERSION}`,
  `/static/css/sections/settings.css?v=${ASSET_VERSION}`,
  `/static/css/sections/activity.css?v=${ASSET_VERSION}`,
  `/static/css/sections/streaks.css?v=${ASSET_VERSION}`,
  `/static/js/script.js?v=${ASSET_VERSION}`,
  `/static/manifest.json?v=${ASSET_VERSION}`,
  `/static/assets/default-male-avatar.svg?v=${ASSET_VERSION}`,
  `/static/assets/default-female-avatar.svg?v=${ASSET_VERSION}`,
  `/static/assets/icon.png?v=${ASSET_VERSION}`,
  `/static/assets/icon-192.png?v=${ASSET_VERSION}`,
  `/static/assets/icon-512.png?v=${ASSET_VERSION}`
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(STATIC_CACHE).then((cache) => cache.addAll(STATIC_ASSETS))
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(
      keys.filter((key) => key !== STATIC_CACHE).map((key) => caches.delete(key))
    ))
  );
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  const request = event.request;
  if (request.method !== 'GET') {
    return;
  }

  const url = new URL(request.url);
  if (url.origin !== self.location.origin) {
    return;
  }

  if (request.mode === 'navigate') {
    event.respondWith(fetch(request));
    return;
  }

  const isStaticAsset = url.pathname.startsWith('/static/');
  if (!isStaticAsset) {
    return;
  }

  event.respondWith(
    caches.match(request).then((cached) => {
      if (cached) {
        return cached;
      }
      return fetch(request).then((response) => {
        if (response.ok) {
          const copy = response.clone();
          caches.open(STATIC_CACHE).then((cache) => cache.put(request, copy));
        }
        return response;
      });
    })
  );
});
