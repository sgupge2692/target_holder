"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { useAuth } from "@/hooks/useAuth";
import { Moon, Sun, BarChart2, Bookmark, User, ShieldCheck, Wallet, Menu, X, TrendingUp, FlaskConical } from "lucide-react";

function NavLink({ href, children, onClick }: { href: string; children: React.ReactNode; onClick?: () => void }) {
  const pathname = usePathname();
  const active = pathname === href || (href !== "/" && pathname.startsWith(href));
  return (
    <Link
      href={href}
      onClick={onClick}
      className={`relative py-1 text-sm font-semibold tracking-wide transition-colors ${
        active
          ? "text-teal-600 dark:text-teal-300"
          : "text-slate-500 dark:text-slate-400 hover:text-slate-800 dark:hover:text-slate-100"
      }`}
    >
      {children}
      {active && (
        <span className="absolute -bottom-0.5 left-0 right-0 h-0.5 rounded-full bg-teal-500 dark:bg-teal-400" />
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
        scrolled ? "navbar-glass" : "bg-transparent"
      }`}>
        <div className="max-w-6xl mx-auto px-4 h-14 flex items-center justify-between">

          {/* ── ロゴ ── */}
          <Link href="/" className="flex items-center gap-2 shrink-0 group">
            {/* チャート形ロゴマーク */}
            <div className="relative w-7 h-7 flex items-end gap-[3px] pb-0.5">
              <div className="w-[5px] rounded-t bg-teal-500/60 dark:bg-teal-400/50 group-hover:bg-teal-500 dark:group-hover:bg-teal-400 transition-colors" style={{height:'40%'}} />
              <div className="w-[5px] rounded-t bg-teal-500/80 dark:bg-teal-400/70 group-hover:bg-teal-500 dark:group-hover:bg-teal-400 transition-colors" style={{height:'65%'}} />
              <div className="w-[5px] rounded-t bg-teal-500 dark:bg-teal-400" style={{height:'100%'}} />
              <div className="w-[5px] rounded-t bg-teal-500/80 dark:bg-teal-400/70 group-hover:bg-teal-500 dark:group-hover:bg-teal-400 transition-colors" style={{height:'80%'}} />
            </div>
            <div className="flex flex-col leading-none">
              <span className="font-black text-base tracking-tight text-slate-900 dark:text-white">
                KABUMI
              </span>
              <span className="text-[9px] font-semibold tracking-[0.18em] text-teal-600 dark:text-teal-400 uppercase">
                Signal
              </span>
            </div>
          </Link>

          {/* ── デスクトップナビ ── */}
          <div className="hidden md:flex items-center gap-6">
            {user ? (
              <>
                <NavLink href="/">シグナル</NavLink>
                <NavLink href="/backtest">バックテスト</NavLink>
                <NavLink href="/watchlist">
                  <span className="flex items-center gap-1.5"><Bookmark size={12} />ウォッチ</span>
                </NavLink>
                <NavLink href="/assets">
                  <span className="flex items-center gap-1.5"><Wallet size={12} />資産</span>
                </NavLink>
                <NavLink href="/account">
                  <span className="flex items-center gap-1.5"><User size={12} />アカウント</span>
                </NavLink>
                {user.is_admin && (
                  <NavLink href="/admin">
                    <span className="flex items-center gap-1.5"><ShieldCheck size={12} />管理</span>
                  </NavLink>
                )}
              </>
            ) : (
              <>
                <NavLink href="/backtest">
                  <span className="flex items-center gap-1.5"><BarChart2 size={12} />バックテスト</span>
                </NavLink>
                <NavLink href="/#pricing">料金</NavLink>
              </>
            )}
          </div>

          {/* ── 右側アクション ── */}
          <div className="flex items-center gap-1.5">
            {/* テーマトグル */}
            <button
              onClick={toggleDark}
              className="w-8 h-8 rounded flex items-center justify-center text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800/60 transition-colors"
              aria-label="テーマ切替"
            >
              {dark
                ? <Sun size={15} strokeWidth={1.8} />
                : <Moon size={15} strokeWidth={1.8} />
              }
            </button>

            {!loading && (
              user ? (
                <div className="hidden md:flex items-center gap-2.5">
                  {/* プランバッジ */}
                  <span className={`px-2 py-0.5 rounded text-[10px] font-black tracking-[0.12em] uppercase ${
                    user.plan === "pro"
                      ? "bg-teal-500 text-white"
                      : "bg-slate-100 dark:bg-slate-800 text-slate-500 dark:text-slate-400"
                  }`}>
                    {user.plan}
                  </span>
                  <button
                    onClick={signOut}
                    className="text-xs text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 transition-colors"
                  >
                    ログアウト
                  </button>
                </div>
              ) : (
                <div className="flex items-center gap-2">
                  <Link
                    href="/auth"
                    className="hidden md:block text-sm text-slate-500 dark:text-slate-400 hover:text-slate-800 dark:hover:text-slate-100 transition-colors"
                  >
                    ログイン
                  </Link>
                  <Link
                    href="/auth"
                    className="bg-teal-600 hover:bg-teal-700 dark:bg-teal-500 dark:hover:bg-teal-600 text-white px-4 py-1.5 rounded text-sm font-bold transition-colors"
                  >
                    無料で始める
                  </Link>
                </div>
              )
            )}

            {/* ── ハンバーガーボタン（モバイル）── */}
            <button
              onClick={() => setDrawerOpen(o => !o)}
              className="md:hidden w-8 h-8 rounded flex items-center justify-center text-slate-500 hover:text-slate-800 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800/60 transition-colors"
              aria-label="メニュー"
            >
              {drawerOpen ? <X size={18} /> : <Menu size={18} />}
            </button>
          </div>
        </div>
      </nav>

      {/* ── モバイルドロワー ── */}
      <div
        className={`fixed inset-0 z-40 bg-black/50 backdrop-blur-sm transition-opacity md:hidden ${
          drawerOpen ? "opacity-100 pointer-events-auto" : "opacity-0 pointer-events-none"
        }`}
        onClick={closeDrawer}
      />

      <div
        className={`fixed top-0 right-0 bottom-0 z-50 w-72 bg-white dark:bg-[#0c1424] border-l border-slate-200 dark:border-[#1a2740] shadow-2xl transition-transform duration-300 md:hidden flex flex-col ${
          drawerOpen ? "translate-x-0" : "translate-x-full"
        }`}
      >
        {/* ドロワーヘッダー */}
        <div className="flex items-center justify-between px-5 h-14 border-b border-slate-100 dark:border-[#1a2740] shrink-0">
          <div className="flex items-center gap-2">
            <TrendingUp size={16} className="text-teal-500" />
            <span className="font-black text-sm tracking-[0.1em] uppercase text-slate-800 dark:text-white">Menu</span>
          </div>
          <button
            onClick={closeDrawer}
            className="w-8 h-8 rounded flex items-center justify-center text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 transition-colors"
          >
            <X size={18} />
          </button>
        </div>

        {/* ナビリンク */}
        <nav className="flex-1 px-3 py-4 space-y-0.5 overflow-y-auto">
          {user ? (
            <>
              <DrawerLink href="/" icon={<BarChart2 size={15} />} label="シグナル" onClick={closeDrawer} />
              <DrawerLink href="/backtest" icon={<BarChart2 size={15} />} label="バックテスト" onClick={closeDrawer} />
              <DrawerLink href="/paper" icon={<FlaskConical size={15} />} label="模擬売買" onClick={closeDrawer} />
              <DrawerLink href="/watchlist" icon={<Bookmark size={15} />} label="ウォッチリスト" onClick={closeDrawer} />
              <DrawerLink href="/assets" icon={<Wallet size={15} />} label="資産管理" onClick={closeDrawer} />
              <DrawerLink href="/account" icon={<User size={15} />} label="アカウント" onClick={closeDrawer} />
              {user.is_admin && (
                <DrawerLink href="/admin" icon={<ShieldCheck size={15} />} label="管理画面" onClick={closeDrawer} />
              )}
            </>
          ) : (
            <>
              <DrawerLink href="/backtest" icon={<BarChart2 size={15} />} label="バックテスト" onClick={closeDrawer} />
              <DrawerLink href="/#pricing" icon={null} label="料金プラン" onClick={closeDrawer} />
            </>
          )}
        </nav>

        {/* ドロワーフッター */}
        <div className="shrink-0 px-4 py-4 border-t border-slate-100 dark:border-[#1a2740] space-y-3">
          {user ? (
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className={`px-1.5 py-0.5 rounded text-[10px] font-black tracking-widest uppercase ${
                  user.plan === "pro"
                    ? "bg-teal-500 text-white"
                    : "bg-slate-100 dark:bg-slate-800 text-slate-500"
                }`}>
                  {user.plan}
                </span>
                <span className="text-xs text-slate-400 truncate max-w-[140px]">{user.email}</span>
              </div>
              <button
                onClick={() => { signOut(); closeDrawer(); }}
                className="text-xs text-red-400 hover:text-red-500 transition-colors font-semibold"
              >
                ログアウト
              </button>
            </div>
          ) : (
            <Link
              href="/auth"
              onClick={closeDrawer}
              className="block w-full text-center bg-teal-600 hover:bg-teal-700 text-white py-2.5 rounded text-sm font-bold transition-colors tracking-wide"
            >
              無料で始める
            </Link>
          )}
          <button
            onClick={toggleDark}
            className="flex items-center gap-2.5 w-full px-3 py-2 rounded text-sm text-slate-500 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-800/60 transition-colors"
          >
            {dark ? <Sun size={14} /> : <Moon size={14} />}
            <span className="text-xs font-semibold">{dark ? "ライトモード" : "ダークモード"}</span>
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
      className={`flex items-center gap-3 px-3 py-2.5 rounded text-sm font-semibold transition-colors ${
        active
          ? "bg-teal-50 dark:bg-teal-900/20 text-teal-700 dark:text-teal-300"
          : "text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-800/60"
      }`}
    >
      {icon && <span className="opacity-70">{icon}</span>}
      {label}
    </Link>
  );
}
