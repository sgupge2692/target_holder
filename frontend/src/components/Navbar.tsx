"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { useAuth } from "@/hooks/useAuth";
import { Moon, Sun, BarChart2, Bookmark, User, ShieldCheck, Wallet, Menu, X } from "lucide-react";

function NavLink({ href, children, onClick }: { href: string; children: React.ReactNode; onClick?: () => void }) {
  const pathname = usePathname();
  const active = pathname === href || (href !== "/" && pathname.startsWith(href));
  return (
    <Link
      href={href}
      onClick={onClick}
      className={`relative py-1 text-sm font-medium transition-colors ${
        active
          ? "text-brand-600 dark:text-brand-400"
          : "text-surface-500 dark:text-surface-400 hover:text-surface-900 dark:hover:text-surface-100"
      }`}
    >
      {children}
      {active && (
        <span className="absolute -bottom-0.5 left-0 right-0 h-0.5 rounded-full bg-brand-500" />
      )}
    </Link>
  );
}

export function Navbar() {
  const { user, loading, signOut } = useAuth();
  const [dark, setDark] = useState(false);
  const [scrolled, setScrolled] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);

  useEffect(() => {
    const saved = localStorage.getItem("theme");
    const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    const isDark = saved ? saved === "dark" : prefersDark;
    setDark(isDark);
    document.documentElement.classList.toggle("dark", isDark);
  }, []);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 10);
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  // ドロワー開閉時に body スクロールをロック
  useEffect(() => {
    document.body.style.overflow = drawerOpen ? "hidden" : "";
    return () => { document.body.style.overflow = ""; };
  }, [drawerOpen]);

  const toggleDark = () => {
    const next = !dark;
    setDark(next);
    localStorage.setItem("theme", next ? "dark" : "light");
    document.documentElement.classList.toggle("dark", next);
  };

  const closeDrawer = () => setDrawerOpen(false);

  return (
    <>
      <nav className={`sticky top-0 z-50 transition-all duration-300 ${
        scrolled ? "navbar-glass shadow-sm" : "bg-transparent"
      }`}>
        <div className="max-w-6xl mx-auto px-4 h-14 flex items-center justify-between">

          {/* ロゴ */}
          <Link
            href="/"
            className="flex items-center gap-2 shrink-0 group"
          >
            <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-brand-500 to-brand-700 flex items-center justify-center shadow-sm group-hover:shadow-glow-green transition-shadow">
              <span className="text-white text-xs font-black leading-none">か</span>
            </div>
            <span className="font-black text-lg tracking-tight text-surface-900 dark:text-white">
              かぶみ
            </span>
          </Link>

          {/* デスクトップナビ（md以上のみ）*/}
          <div className="hidden md:flex items-center gap-6">
            {user ? (
              <>
                <NavLink href="/">シグナル</NavLink>
                <NavLink href="/backtest">バックテスト</NavLink>
                <NavLink href="/watchlist">
                  <span className="flex items-center gap-1"><Bookmark size={13} />ウォッチ</span>
                </NavLink>
                <NavLink href="/assets">
                  <span className="flex items-center gap-1"><Wallet size={13} />資産</span>
                </NavLink>
                <NavLink href="/account">
                  <span className="flex items-center gap-1"><User size={13} />アカウント</span>
                </NavLink>
                {user.is_admin && (
                  <NavLink href="/admin">
                    <span className="flex items-center gap-1"><ShieldCheck size={13} />管理</span>
                  </NavLink>
                )}
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
          <div className="flex items-center gap-1.5">
            {/* テーマトグル */}
            <button
              onClick={toggleDark}
              className="w-8 h-8 rounded-lg flex items-center justify-center text-surface-400 hover:text-surface-700 dark:hover:text-surface-200 hover:bg-surface-100 dark:hover:bg-surface-800 transition-colors"
              aria-label="テーマ切替"
            >
              {dark
                ? <Sun size={16} strokeWidth={1.8} />
                : <Moon size={16} strokeWidth={1.8} />
              }
            </button>

            {!loading && (
              user ? (
                <div className="hidden md:flex items-center gap-2.5">
                  <span className={`px-2.5 py-0.5 rounded-full text-xs font-bold tracking-wider uppercase ${
                    user.plan === "pro"
                      ? "bg-brand-500 text-white"
                      : "bg-surface-100 dark:bg-surface-800 text-surface-500 dark:text-surface-400"
                  }`}>
                    {user.plan}
                  </span>
                  <button
                    onClick={signOut}
                    className="text-xs text-surface-400 hover:text-surface-700 dark:hover:text-surface-200 transition-colors"
                  >
                    ログアウト
                  </button>
                </div>
              ) : (
                <div className="flex items-center gap-2">
                  <Link
                    href="/auth"
                    className="hidden md:block text-sm text-surface-500 dark:text-surface-400 hover:text-surface-800 dark:hover:text-surface-100 transition-colors"
                  >
                    ログイン
                  </Link>
                  <Link
                    href="/auth"
                    className="bg-brand-600 hover:bg-brand-700 text-white px-4 py-1.5 rounded-xl text-sm font-bold transition-colors shadow-sm"
                  >
                    無料で始める
                  </Link>
                </div>
              )
            )}

            {/* ハンバーガー（md未満のみ）*/}
            <button
              onClick={() => setDrawerOpen(o => !o)}
              className="md:hidden w-8 h-8 rounded-lg flex items-center justify-center text-surface-500 hover:text-surface-800 dark:hover:text-surface-200 hover:bg-surface-100 dark:hover:bg-surface-800 transition-colors"
              aria-label="メニューを開く"
            >
              {drawerOpen ? <X size={18} /> : <Menu size={18} />}
            </button>
          </div>

        </div>
      </nav>

      {/* ─── モバイルドロワー ─── */}
      {/* オーバーレイ */}
      <div
        className={`fixed inset-0 z-40 bg-black/40 backdrop-blur-sm transition-opacity md:hidden ${
          drawerOpen ? "opacity-100 pointer-events-auto" : "opacity-0 pointer-events-none"
        }`}
        onClick={closeDrawer}
      />

      {/* ドロワー本体 */}
      <div
        className={`fixed top-0 right-0 bottom-0 z-50 w-72 bg-white dark:bg-surface-900 shadow-2xl transition-transform duration-300 md:hidden ${
          drawerOpen ? "translate-x-0" : "translate-x-full"
        }`}
      >
        {/* ドロワーヘッダー */}
        <div className="flex items-center justify-between px-5 h-14 border-b border-surface-100 dark:border-surface-800">
          <span className="font-black text-lg text-surface-900 dark:text-white">メニュー</span>
          <button
            onClick={closeDrawer}
            className="w-8 h-8 rounded-lg flex items-center justify-center text-surface-400 hover:text-surface-700 dark:hover:text-surface-200 hover:bg-surface-100 dark:hover:bg-surface-800 transition-colors"
          >
            <X size={18} />
          </button>
        </div>

        {/* ナビリンク */}
        <nav className="px-4 py-4 space-y-1">
          {user ? (
            <>
              <DrawerLink href="/" icon={<BarChart2 size={16} />} label="シグナル" onClick={closeDrawer} />
              <DrawerLink href="/backtest" icon={<BarChart2 size={16} />} label="バックテスト" onClick={closeDrawer} />
              <DrawerLink href="/watchlist" icon={<Bookmark size={16} />} label="ウォッチリスト" onClick={closeDrawer} />
              <DrawerLink href="/assets" icon={<Wallet size={16} />} label="資産管理" onClick={closeDrawer} />
              <DrawerLink href="/account" icon={<User size={16} />} label="アカウント" onClick={closeDrawer} />
              {user.is_admin && (
                <DrawerLink href="/admin" icon={<ShieldCheck size={16} />} label="管理画面" onClick={closeDrawer} />
              )}
            </>
          ) : (
            <>
              <DrawerLink href="/backtest" icon={<BarChart2 size={16} />} label="バックテスト" onClick={closeDrawer} />
              <DrawerLink href="/#pricing" icon={null} label="料金プラン" onClick={closeDrawer} />
            </>
          )}
        </nav>

        {/* ドロワーフッター */}
        <div className="absolute bottom-0 left-0 right-0 p-4 border-t border-surface-100 dark:border-surface-800 space-y-3">
          {user ? (
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className={`px-2 py-0.5 rounded-full text-xs font-bold uppercase ${
                  user.plan === "pro"
                    ? "bg-brand-500 text-white"
                    : "bg-surface-100 dark:bg-surface-800 text-surface-500"
                }`}>
                  {user.plan}
                </span>
                <span className="text-xs text-surface-400 truncate max-w-[140px]">{user.email}</span>
              </div>
              <button
                onClick={() => { signOut(); closeDrawer(); }}
                className="text-xs text-red-400 hover:text-red-500 transition-colors"
              >
                ログアウト
              </button>
            </div>
          ) : (
            <Link
              href="/auth"
              onClick={closeDrawer}
              className="block w-full text-center bg-brand-600 hover:bg-brand-700 text-white py-2.5 rounded-xl text-sm font-bold transition-colors"
            >
              無料で始める
            </Link>
          )}
          <button
            onClick={toggleDark}
            className="flex items-center gap-2 w-full px-3 py-2 rounded-xl text-sm text-surface-500 hover:bg-surface-50 dark:hover:bg-surface-800 transition-colors"
          >
            {dark ? <Sun size={15} /> : <Moon size={15} />}
            {dark ? "ライトモード" : "ダークモード"}
          </button>
        </div>
      </div>
    </>
  );
}

function DrawerLink({
  href,
  icon,
  label,
  onClick,
}: {
  href: string;
  icon: React.ReactNode;
  label: string;
  onClick?: () => void;
}) {
  const pathname = usePathname();
  const active = pathname === href || (href !== "/" && pathname.startsWith(href));
  return (
    <Link
      href={href}
      onClick={onClick}
      className={`flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-colors ${
        active
          ? "bg-brand-50 dark:bg-brand-900/30 text-brand-600 dark:text-brand-400"
          : "text-surface-600 dark:text-surface-400 hover:bg-surface-50 dark:hover:bg-surface-800"
      }`}
    >
      {icon && <span className="text-current opacity-70">{icon}</span>}
      {label}
    </Link>
  );
}
