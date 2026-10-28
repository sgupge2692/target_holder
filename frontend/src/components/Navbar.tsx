"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { useAuth } from "@/hooks/useAuth";
import { TrendingUp, Moon, Sun, Bookmark } from "lucide-react";

export function Navbar() {
  const { user, loading, signOut } = useAuth();
  const [dark, setDark] = useState(false);
  const [scrolled, setScrolled] = useState(false);

  // ダークモード初期化
  useEffect(() => {
    const saved = localStorage.getItem("theme");
    const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    const isDark = saved ? saved === "dark" : prefersDark;
    setDark(isDark);
    document.documentElement.classList.toggle("dark", isDark);
  }, []);

  // スクロール検知（LP ヒーロー通過後に背景を強調）
  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 60);
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  const toggleDark = () => {
    const next = !dark;
    setDark(next);
    localStorage.setItem("theme", next ? "dark" : "light");
    document.documentElement.classList.toggle("dark", next);
  };

  return (
    <nav className={`sticky top-0 z-50 border-b transition-shadow ${
      scrolled
        ? "border-gray-200 dark:border-slate-700 bg-white/95 dark:bg-slate-900/95 backdrop-blur shadow-sm"
        : "border-gray-200 dark:border-slate-700 bg-white dark:bg-slate-900"
    }`}>
      <div className="max-w-6xl mx-auto px-4 h-14 flex items-center justify-between">
        <Link href="/" className="flex items-center gap-2 font-bold text-lg text-brand-600 dark:text-brand-500">
          <TrendingUp size={20} />
          Stock Intelligence
        </Link>

        <div className="flex items-center gap-4 text-sm">
          {user ? (
            <>
              <Link href="/" className="hover:text-brand-600 dark:hover:text-brand-500 transition-colors">シグナル</Link>
              <Link href="/backtest" className="hidden sm:block hover:text-brand-600 dark:hover:text-brand-500 transition-colors">バックテスト</Link>
              <Link href="/watchlist" className="flex items-center gap-1 hover:text-brand-600 dark:hover:text-brand-500 transition-colors">
                <Bookmark size={14} />
                <span className="hidden sm:inline">ウォッチ</span>
              </Link>
              <Link href="/account" className="hover:text-brand-600 dark:hover:text-brand-500 transition-colors">アカウント</Link>
            </>
          ) : (
            <>
              <Link href="/backtest" className="hidden sm:block hover:text-brand-600 dark:hover:text-brand-500 transition-colors">バックテスト</Link>
              <Link href="/#pricing" className="hidden sm:block hover:text-brand-600 dark:hover:text-brand-500 transition-colors">料金プラン</Link>
            </>
          )}

          <button onClick={toggleDark} className="p-1.5 rounded-md hover:bg-gray-100 dark:hover:bg-slate-800 transition-colors">
            {dark ? <Sun size={16} /> : <Moon size={16} />}
          </button>

          {!loading && (
            user ? (
              <div className="flex items-center gap-3">
                <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                  user.plan === "pro"
                    ? "bg-brand-500 text-white"
                    : "bg-gray-200 dark:bg-slate-700 text-gray-600 dark:text-slate-300"
                }`}>
                  {user.plan === "pro" ? "PRO" : "FREE"}
                </span>
                <button
                  onClick={signOut}
                  className="text-gray-500 hover:text-gray-700 dark:hover:text-slate-200 transition-colors"
                >
                  ログアウト
                </button>
              </div>
            ) : (
              <div className="flex items-center gap-2">
                <Link
                  href="/auth"
                  className="text-gray-600 dark:text-slate-300 hover:text-brand-600 dark:hover:text-brand-400 transition-colors"
                >
                  ログイン
                </Link>
                <Link
                  href="/auth"
                  className="bg-brand-600 hover:bg-brand-700 text-white px-4 py-1.5 rounded-lg font-medium transition-colors"
                >
                  無料で始める
                </Link>
              </div>
            )
          )}
        </div>
      </div>
    </nav>
  );
}
