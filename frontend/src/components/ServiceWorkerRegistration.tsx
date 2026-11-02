"use client";
import { useEffect } from "react";

export function ServiceWorkerRegistration() {
  useEffect(() => {
    if (typeof window === "undefined" || !("serviceWorker" in navigator)) return;
    navigator.serviceWorker
      .register("/sw.js", { scope: "/" })
      .then((reg) => {
        console.log("[SW] registered", reg.scope);
        reg.addEventListener("updatefound", () => {
          const worker = reg.installing;
          if (!worker) return;
          worker.addEventListener("statechange", () => {
            if (worker.state === "installed" && navigator.serviceWorker.controller) {
              // 新しい SW が待機中 → 次回リロードで有効
              console.log("[SW] new version available");
            }
          });
        });
      })
      .catch((err) => console.warn("[SW] registration failed", err));
  }, []);

  return null;
}
