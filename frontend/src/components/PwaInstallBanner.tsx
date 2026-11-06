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
    try {
      if (localStorage.getItem("pwa-dismissed")) { setDismissed(true); return; }
    } catch {}

    if (window.matchMedia("(display-mode: standalone)").matches) {
      setInstalled(true);
      return;
    }

    const ua = navigator.userAgent;
    const isIosDev = /iphone|ipad|ipod/i.test(ua) && !(window as { MSStream?: unknown }).MSStream;
    if (isIosDev) {
      setIsIos(true);
      setTimeout(() => setShow(true), 3000);
      return;
    }

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
    <div className="fixed bottom-20 md:bottom-6 left-4 right-4 md:left-auto md:right-6 md:w-80 z-50 animate-slide-up">
      <div className="bg-[#0c1424] border border-slate-700/60 rounded shadow-xl shadow-black/40 p-4 flex items-start gap-3">
        {/* アイコン */}
        <div className="w-10 h-10 rounded bg-teal-600 flex items-center justify-center shrink-0">
          <span className="text-white text-lg font-black leading-none">か</span>
        </div>

        <div className="flex-1 min-w-0">
          <p className="text-sm font-black text-white leading-tight tracking-tight">
            ホーム画面に追加
          </p>
          {isIos ? (
            <p className="text-xs text-slate-500 mt-1 leading-relaxed">
              Safari の <span className="font-semibold text-slate-400">共有</span> → <span className="font-semibold text-slate-400">ホーム画面に追加</span> でインストールできます
            </p>
          ) : (
            <p className="text-xs text-slate-500 mt-1 leading-relaxed">
              アプリとしてインストールするとオフラインでも使えます
            </p>
          )}

          {!isIos && deferredPrompt && (
            <button
              onClick={handleInstall}
              className="mt-2.5 flex items-center gap-1.5 bg-teal-600 hover:bg-teal-500 active:scale-95 text-white text-xs font-black px-3 py-1.5 rounded tracking-widest uppercase transition-all"
            >
              <Download size={12} />
              インストール
            </button>
          )}
          {isIos && (
            <div className="mt-2 flex items-center gap-1.5 text-xs text-teal-500 font-semibold">
              <Smartphone size={12} />
              Safari で開いて追加できます
            </div>
          )}
        </div>

        <button
          onClick={handleDismiss}
          className="p-1 rounded text-slate-600 hover:text-slate-400 hover:bg-slate-800/60 transition-colors shrink-0"
          aria-label="閉じる"
        >
          <X size={14} />
        </button>
      </div>
    </div>
  );
}
