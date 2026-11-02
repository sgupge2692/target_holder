"use client";
import { useEffect, useState } from "react";
import { X, Download, Smartphone } from "lucide-react";

interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
}

export function PwaInstallBanner() {
  const [deferredPrompt, setDeferredPrompt] = useState<BeforeInstallPromptEvent | null>(null);
  const [show, setShow]       = useState(false);
  const [isIos, setIsIos]     = useState(false);
  const [dismissed, setDismissed] = useState(false);
  const [installed, setInstalled] = useState(false);

  useEffect(() => {
    // すでにインストール済み / 非表示設定ならスキップ
    try {
      if (localStorage.getItem("pwa-dismissed")) { setDismissed(true); return; }
    } catch {}

    // インストール済みかどうか (standalone モード)
    if (window.matchMedia("(display-mode: standalone)").matches) {
      setInstalled(true);
      return;
    }

    // iOS Safari 判定
    const ua = navigator.userAgent;
    const isIosDev = /iphone|ipad|ipod/i.test(ua) && !(window as { MSStream?: unknown }).MSStream;
    if (isIosDev) {
      setIsIos(true);
      // iOS は beforeinstallprompt が来ないので、初回のみ案内を表示
      setTimeout(() => setShow(true), 3000);
      return;
    }

    // Android / Chrome: beforeinstallprompt を待つ
    const handler = (e: Event) => {
      e.preventDefault();
      setDeferredPrompt(e as BeforeInstallPromptEvent);
      setTimeout(() => setShow(true), 2000);
    };
    window.addEventListener("beforeinstallprompt", handler);
    return () => window.removeEventListener("beforeinstallprompt", handler);
  }, []);

  const handleInstall = async () => {
    if (!deferredPrompt) return;
    await deferredPrompt.prompt();
    const { outcome } = await deferredPrompt.userChoice;
    if (outcome === "accepted") setInstalled(true);
    setShow(false);
  };

  const handleDismiss = () => {
    setShow(false);
    try { localStorage.setItem("pwa-dismissed", "1"); } catch {}
  };

  if (!show || dismissed || installed) return null;

  return (
    <div
      className="fixed bottom-20 md:bottom-6 left-4 right-4 md:left-auto md:right-6 md:w-80 z-50 animate-slide-up"
    >
      <div className="bg-white dark:bg-surface-900 border border-surface-200 dark:border-surface-700 rounded-2xl shadow-xl p-4 flex items-start gap-3">
        {/* アイコン */}
        <div className="w-10 h-10 rounded-xl bg-brand-600 flex items-center justify-center shrink-0 shadow-sm">
          <span className="text-white text-lg font-black leading-none">か</span>
        </div>

        <div className="flex-1 min-w-0">
          <p className="text-sm font-bold text-surface-900 dark:text-white leading-tight">
            ホーム画面に追加
          </p>
          {isIos ? (
            <p className="text-xs text-surface-400 dark:text-surface-500 mt-1 leading-relaxed">
              Safari の <span className="font-semibold">共有</span> → <span className="font-semibold">ホーム画面に追加</span> でインストールできます
            </p>
          ) : (
            <p className="text-xs text-surface-400 dark:text-surface-500 mt-1 leading-relaxed">
              アプリとしてインストールするとオフラインでも使えます
            </p>
          )}

          {!isIos && deferredPrompt && (
            <button
              onClick={handleInstall}
              className="mt-2.5 flex items-center gap-1.5 bg-brand-600 hover:bg-brand-700 active:scale-95 text-white text-xs font-bold px-3 py-1.5 rounded-lg transition-all"
            >
              <Download size={12} />
              インストール
            </button>
          )}
          {isIos && (
            <div className="mt-2 flex items-center gap-1.5 text-xs text-brand-600 dark:text-brand-400 font-medium">
              <Smartphone size={12} />
              Safari で開いて追加できます
            </div>
          )}
        </div>

        <button
          onClick={handleDismiss}
          className="p-1 rounded-lg text-surface-300 dark:text-surface-600 hover:text-surface-500 dark:hover:text-surface-400 hover:bg-surface-100 dark:hover:bg-surface-800 transition-colors shrink-0"
          aria-label="閉じる"
        >
          <X size={14} />
        </button>
      </div>
    </div>
  );
}
