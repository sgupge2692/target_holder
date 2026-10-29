"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { useAuth } from "@/hooks/useAuth";
import { TrendingUp, Moon, Sun, Bookmark, Menu, X, BarChart2, Home, User } from "lucide-react";

function NavLink({ href, children, onClick }: { href: string; children: React.ReactNode; onClick?: () => void }) {
  const pathname = usePathname();
  const active = pathname === href || (href !== "/" && pathname.startsWith(href));
  return (
    <Link
      href={href}
      onClick={onClick}
      className={`transition-colors font-medium ${
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
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    const saved = localStorage.getItem("theme");
    const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    const isDark = saved ? saved === "dark" : prefersDark;
    setDark(isDark);
    document.documentElement.classList.toggle("dark", isDark);
  }, []);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 60);
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  // メニューを開いているときスクロール禁止
  useEffect(() => {
    document.body.style.overflow = menuOpen ? "hidden" : "";
    return () => { document.body.style.overflow = ""; };
  }, [menuOpen]);

  const toggleDark = () => {
    const next = !dark;
    setDark(next);
    localStorage.setItem("theme", next ? "dark" : "light");
    document.documentElement.classList.toggle("dark", next);
  };

  const close = () => setMenuOpen(false);

  return (
    <>
      <nav className={`sticky top-0 z-50 border-b transition-all duration-200 ${
        scrolled
          ? "border-gray-200 dark:border-slate-700 bg-white/95 dark:bg-slate-900/95 backdrop-blur-md shadow-sm"
          : "border-gray-200/80 dark:border-slate-700/80 bg-white dark:bg-slate-900"
      }`}>
        <div className="max-w-6xl mx-auto px-4 h-14 flex items-center justify-between">
          {/* ロゴ */}
          <Link href="/" onClick={close} className="flex items-center gap-2 font-bold text-lg text-brand-600 dark:text-brand-400 shrink-0">
            <TrendingUp size={20} />
            <span>Stock Intelligence</span>
          </Link>

          {/* デスクトップナビ */}
          <div className="hidden md:flex items-center gap-5 text-sm">
            {user ? (
              <>
                <NavLink href="/">シグナル</NavLink>
                <NavLink href="/backtest">バックテスト</NavLink>
                <NavLink href="/watchlist">
                  <span className="flex items-center gap-1">
                    <Bookmark size={13} />ウォッチ
                  </span>
                </NavLink>
                <NavLink href="/account">アカウント</NavLink>
              </>
            ) : (
              <>
                <NavLink href="/backtest">バックテスト</NavLink>
                <NavLink href="/#pricing">料金プラン</NavLink>
              </>
            )}

            <button onClick={toggleDark} className="p-1.5 rounded-md hover:bg-gray-100 dark:hover:bg-slate-800 transition-colors" aria-label="テーマ切替">
              {dark ? <Sun size={16} /> : <Moon size={16} />}
            </button>

            {!loading && (
              user ? (
                <div className="flex items-center gap-3">
                  <span className={`px-2 py-0.5 rounded-full text-xs font-semibold tracking-wide ${
                    user.plan === "pro"
                      ? "bg-brand-500 text-white"
                      : "bg-gray-200 dark:bg-slate-700 text-gray-600 dark:text-slate-300"
                  }`}>
                    {user.plan === "pro" ? "PRO" : "FREE"}
                  </span>
                  <button onClick={signOut} className="text-sm text-gray-500 hover:text-gray-800 dark:hover:text-slate-200 transition-colors">
                    ログアウト
                  </button>
                </div>
              ) : (
                <div className="flex items-center gap-2">
                  <Link href="/auth" className="text-sm text-gray-600 dark:text-slate-300 hover:text-brand-600 dark:hover:text-brand-400 transition-colors">
                    ログイン
                  </Link>
                  <Link href="/auth" className="bg-brand-600 hover:bg-brand-700 text-white px-4 py-1.5 rounded-lg text-sm font-semibold transition-colors">
                    無料で始める
                  </Link>
                </div>
              )
            )}
          </div>

          {/* モバイル右側 */}
          <div className="flex md:hidden items-center gap-2">
            <button onClick={toggleDark} className="p-1.5 rounded-md hover:bg-gray-100 dark:hover:bg-slate-800 transition-colors" aria-label="テーマ切替">
              {dark ? <Sun size={16} /> : <Moon size={16} />}
            </button>
            <button
              onClick={() => setMenuOpen(v => !v)}
              className="p-1.5 rounded-md hover:bg-gray-100 dark:hover:bg-slate-800 transition-colors"
              aria-label="メニュー"
            >
              {menuOpen ? <X size={20} /> : <Menu size={20} />}
            </button>
          </div>
        </div>
      </nav>

      {/* モバイルドロワー */}
      {menuOpen && (
        <div className="fixed inset-0 z-40 md:hidden" onClick={close}>
          <div className="absolute inset-0 bg-black/30 backdrop-blur-sm" />
          <div
            className="absolute top-14 left-0 right-0 bg-white dark:bg-slate-900 border-b border-gray-200 dark:border-slate-700 shadow-xl animate-fade-in"
            onClick={e => e.stopPropagation()}
          >
            <div className="px-4 py-5 space-y-1">
              {user ? (
                <>
                  {/* プランバッジ */}
                  <div className="flex items-center justify-between mb-4 pb-4 border-b border-gray-100 dark:border-slate-800">
                    <span className="text-sm text-gray-600 dark:text-slate-300">{user.email ?? "ユーザー"}</span>
                    <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${
                      user.plan === "pro"
                        ? "bg-brand-500 text-white"
                        : "bg-gray-200 dark:bg-slate-700 text-gray-600 dark:text-slate-300"
                    }`}>
                      {user.plan === "pro" ? "PRO" : "FREE"}
                    </span>
                  </div>

                  {[
                    { href: "/", icon: <Home size={17} />, label: "シグナル" },
                    { href: "/backtest", icon: <BarChart2 size={17} />, label: "バックテスト" },
                    { href: "/watchlist", icon: <Bookmark size={17} />, label: "ウォッチリスト" },
                    { href: "/account", icon: <User size={17} />, label: "アカウント" },
                  ].map(({ href, icon, label }) => (
                    <Link
                      key={href}
                      href={href}
                      onClick={close}
                      className="flex items-center gap-3 px-3 py-3 rounded-xl hover:bg-gray-50 dark:hover:bg-slate-800 text-gray-700 dark:text-slate-200 font-medium transition-colors"
                    >
                      <span className="text-gray-400 dark:text-slate-500">{icon}</span>
                      {label}
                    </Link>
                  ))}

                  <div className="pt-4 mt-2 border-t border-gray-100 dark:border-slate-800">
                    <button
                      onClick={() => { signOut(); close(); }}
                      className="w-full text-left px-3 py-3 text-sm text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-xl transition-colors"
                    >
                      ログアウト
                    </button>
                  </div>
                </>
              ) : (
                <div className="space-y-3 pb-2">
                  <Link href="/auth" onClick={close} className="block text-center w-full bg-brand-600 hover:bg-brand-700 text-white px-4 py-3 rounded-xl font-semibold transition-colors">
                    無料で始める
                  </Link>
                  <Link href="/auth" onClick={close} className="block text-center w-full border border-gray-200 dark:border-slate-700 px-4 py-3 rounded-xl font-medium text-gray-700 dark:text-slate-300 hover:bg-gray-50 dark:hover:bg-slate-800 transition-colors">
                    ログイン
                  </Link>
                  <Link href="/backtest" onClick={close} className="flex items-center gap-3 px-3 py-3 rounded-xl hover:bg-gray-50 dark:hover:bg-slate-800 text-gray-700 dark:text-slate-200 font-medium transition-colors">
                    <BarChart2 size={17} className="text-gray-400" />バックテスト
                  </Link>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </>
  );
}
