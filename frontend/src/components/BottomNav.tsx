"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Home, BarChart2, Bookmark, User, FlaskConical } from "lucide-react";
import { useAuth } from "@/hooks/useAuth";

const NAV_ITEMS = [
  { href: "/",          icon: Home,         label: "シグナル"   },
  { href: "/backtest",  icon: BarChart2,    label: "実績"       },
  { href: "/paper",     icon: FlaskConical, label: "模擬売買"   },
  { href: "/watchlist", icon: Bookmark,     label: "ウォッチ"   },
  { href: "/account",   icon: User,         label: "アカウント" },
];

export function BottomNav() {
  const pathname = usePathname();
  const { user } = useAuth();

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
              <Icon
                size={20}
                strokeWidth={active ? 2.5 : 1.8}
                className="transition-transform duration-150"
                style={active ? { transform: "scale(1.1)" } : {}}
              />
              <span>{label}</span>
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
