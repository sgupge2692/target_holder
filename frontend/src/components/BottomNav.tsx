"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Home, BarChart2, Bookmark, User } from "lucide-react";
import { useAuth } from "@/hooks/useAuth";

const NAV_ITEMS = [
  { href: "/",         icon: Home,      label: "シグナル" },
  { href: "/backtest", icon: BarChart2, label: "実績"     },
  { href: "/watchlist",icon: Bookmark,  label: "ウォッチ"  },
  { href: "/account",  icon: User,      label: "アカウント" },
];

export function BottomNav() {
  const pathname = usePathname();
  const { user } = useAuth();

  // 未ログインやauth画面では非表示
  if (!user) return null;

  return (
    <nav className="bottom-nav md:hidden">
      <div className="flex">
        {NAV_ITEMS.map(({ href, icon: Icon, label }) => {
          const active = pathname === href || (href !== "/" && pathname.startsWith(href));
          return (
            <Link
              key={href}
              href={href}
              className={`bottom-nav-item ${active ? "active" : ""}`}
            >
              <Icon size={22} strokeWidth={active ? 2.5 : 1.8} />
              <span>{label}</span>
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
