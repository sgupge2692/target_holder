// かぶみ Service Worker
const CACHE_NAME = "kabumi-v1";
const STATIC_ASSETS = [
  "/",
  "/backtest",
  "/manifest.json",
  "/icon-192.png",
  "/icon-512.png",
];

// インストール: 静的アセットをキャッシュ
self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(STATIC_ASSETS))
  );
  self.skipWaiting();
});

// アクティベート: 古いキャッシュを削除
self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

// フェッチ戦略:
// - API (/api/*): Network Only（常に最新データ）
// - 静的アセット: Cache First
// - ページ: Network First → キャッシュフォールバック
self.addEventListener("fetch", (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // API は常にネットワーク
  if (url.pathname.startsWith("/api/")) return;

  // 静的ファイル (画像・JS・CSS) は Cache First
  if (
    request.destination === "image" ||
    request.destination === "script" ||
    request.destination === "style" ||
    request.destination === "font"
  ) {
    event.respondWith(
      caches.match(request).then(
        (cached) => cached ?? fetch(request).then((res) => {
          const clone = res.clone();
          caches.open(CACHE_NAME).then((c) => c.put(request, clone));
          return res;
        })
      )
    );
    return;
  }

  // HTML ページは Network First
  if (request.mode === "navigate") {
    event.respondWith(
      fetch(request)
        .then((res) => {
          const clone = res.clone();
          caches.open(CACHE_NAME).then((c) => c.put(request, clone));
          return res;
        })
        .catch(() => caches.match(request).then((c) => c ?? caches.match("/")))
    );
  }
});

// プッシュ通知 (将来拡張用)
self.addEventListener("push", (event) => {
  if (!event.data) return;
  const data = event.data.json();
  event.waitUntil(
    self.registration.showNotification(data.title ?? "かぶみ", {
      body:  data.body  ?? "新しいシグナルが届きました",
      icon:  "/icon-192.png",
      badge: "/icon-192.png",
      tag:   "kabumi-signal",
      data:  { url: data.url ?? "/" },
    })
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const url = event.notification.data?.url ?? "/";
  event.waitUntil(clients.openWindow(url));
});
