"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { useAuth } from "@/hooks/useAuth";
import { Moon, Sun, BarChart2, Bookmark, User } from "lucide-react";

function NavLink({ href, children }: { href: string; children: React.ReactNode }) {
  const pathname = usePathname();
  const active = pathname === href || (href !== "/" && pathname.startsWith(href));
  return (
    <Link
      href={href}
      className={`transition-colors font-medium text-sm ${
        active
          ? "text-brand-600 dark:text-brand-400"
          : "text-gray-600 dark:text-slate-300 hover:text-brand-600 dark:hover:text-brand-400"
      }`}
    >
      {children}
    </Link>
  );
}

export function Navbar() {
  const { user, loading, signOut } = useAuth();
  const [dark, setDark] = useState(false);
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const saved = localStorage.getItem("theme");
    const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    const isDark = saved ? saved === "dark" : prefersDark;
    setDark(isDark);
    document.documentElement.classList.toggle("dark", isDark);
  }, []);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 30);
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
    <nav className={`sticky top-0 z-50 transition-all duration-200 ${
      scrolled
        ? "border-b border-gray-200 dark:border-slate-700 bg-white/95 dark:bg-slate-900/95 backdrop-blur-md shadow-sm"
        : "border-b border-transparent bg-white dark:bg-slate-900"
    }`}>
      <div className="max-w-6xl mx-auto px-4 h-14 flex items-center justify-between">

        {/* ロゴ */}
        <Link href="/" className="flex items-center gap-1.5 font-black text-xl tracking-tight text-emerald-600 dark:text-emerald-400 shrink-0">
          <span>かぶみ</span>
        </Link>

        {/* デスクトップナビ（md以上のみ） */}
        <div className="hidden md:flex items-center gap-5">
          {user ? (
            <>
              <NavLink href="/">シグナル</NavLink>
              <NavLink href="/backtest">バックテスト</NavLink>
              <NavLink href="/watchlist">
                <span className="flex items-center gap-1"><Bookmark size={13} />ウォッチ</span>
              </NavLink>
              <NavLink href="/account">
                <span className="flex items-center gap-1"><User size={13} />アカウント</span>
              </NavLink>
            </>
          ) : (
            <>
              <NavLink href="/backtest">
                <span className="flex items-center gap-1"><BarChart2 size={13} />バックテスト</span>
              </NavLink>
              <NavLink href="/#pricing">料金プラン</NavLink>
            </>
          )}
        </div>

        {/* 右側アクション */}
        <div className="flex items-center gap-2">
          {/* テーマ切替 */}
          <button
            onClick={toggleDark}
            className="p-2 rounded-xl hover:bg-gray-100 dark:hover:bg-slate-800 transition-colors"
            aria-label="テーマ切替"
          >
            {dark ? <Sun size={17} /> : <Moon size={17} />}
          </button>

          {!loading && (
            user ? (
              <div className="hidden md:flex items-center gap-3">
                <span className={`px-2.5 py-0.5 rounded-full text-xs font-bold tracking-wider ${
                  user.plan === "pro"
                    ? "bg-emerald-500 text-white"
                    : "bg-gray-200 dark:bg-slate-700 text-gray-600 dark:text-slate-300"
                }`}>
                  {user.plan === "pro" ? "PRO" : "FREE"}
                </span>
                <button
                  onClick={signOut}
                  className="text-xs text-gray-400 hover:text-gray-700 dark:hover:text-slate-200 transition-colors"
                >
                  ログアウト
                </button>
              </div>
            ) : (
              <div className="flex items-center gap-2">
                <Link
                  href="/auth"
                  className="hidden md:block text-sm text-gray-600 dark:text-slate-300 hover:text-emerald-600 transition-colors"
                >
                  ログイン
                </Link>
                <Link
                  href="/auth"
                  className="bg-emerald-600 hover:bg-emerald-700 text-white px-4 py-1.5 rounded-xl text-sm font-bold transition-colors"
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
