"use client";
import { useRouter } from "next/navigation";
import Link from "next/link";
import useSWR from "swr";
import { useAuth } from "@/hooks/useAuth";
import { createPortal, apiFetch, getSubscription } from "@/lib/api";
import { useState, useEffect } from "react";
import { Bell, BellOff, CreditCard, LogOut, User, Crown, Shield, ChevronRight } from "lucide-react";

interface NotifSettings {
  email_signal_alert: boolean;
  email_unsubscribed: boolean;
}

function Toggle({ checked, onChange, disabled }: { checked: boolean; onChange: () => void; disabled?: boolean }) {
  return (
    <button
      onClick={onChange}
      disabled={disabled}
      role="switch"
      aria-checked={checked}
      className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 focus:outline-none disabled:opacity-50 ${
        checked ? "bg-teal-600" : "bg-slate-700"
      }`}
    >
      <span className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${
        checked ? "translate-x-5" : "translate-x-0"
      }`} />
    </button>
  );
}

export default function AccountPage() {
  const { user, loading, signOut } = useAuth();
  const [portalLoading, setPortalLoading] = useState(false);
  const [notif, setNotif] = useState<NotifSettings | null>(null);
  const [notifLoading, setNotifLoading] = useState(false);
  const router = useRouter();

  const { data: sub } = useSWR(user?.plan === "pro" ? "subscription" : null, getSubscription);
  const nextBillingDate = sub?.plan_expires_at
    ? new Date(sub.plan_expires_at).toLocaleDateString("ja-JP", { year: "numeric", month: "long", day: "numeric" })
    : null;

  useEffect(() => {
    if (!user) return;
    apiFetch<NotifSettings>("/api/notifications/settings").then(setNotif).catch(() => {});
  }, [user]);

  if (loading) return (
    <div className="max-w-lg mx-auto pt-12 space-y-4">
      {[...Array(3)].map((_, i) => <div key={i} className="skeleton h-20 rounded" />)}
    </div>
  );

  if (!user) { router.push("/auth"); return null; }

  const isPro = user.plan === "pro";
  const initials = (user.email ?? "U").slice(0, 2).toUpperCase();

  const openPortal = async () => {
    setPortalLoading(true);
    try {
      const { url } = await createPortal();
      window.location.href = url;
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : "エラー");
      setPortalLoading(false);
    }
  };

  const toggleEmailAlert = async () => {
    if (!notif) return;
    setNotifLoading(true);
    try {
      const updated = await apiFetch<NotifSettings>("/api/notifications/settings", {
        method: "PATCH",
        body: JSON.stringify({ email_signal_alert: !notif.email_signal_alert }),
      });
      setNotif(updated);
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : "設定変更に失敗しました");
    } finally {
      setNotifLoading(false);
    }
  };

  return (
    <div className="max-w-lg mx-auto space-y-4 pb-10">

      {/* プロフィールヘッダー */}
      <div className={`rounded border p-5 relative overflow-hidden ${
        isPro
          ? "border-teal-700/50 bg-gradient-to-br from-teal-900/60 to-[#0c1424]"
          : "border-slate-700/60 bg-[#0c1424]"
      }`}>
        <div className="absolute -right-6 -top-6 w-28 h-28 rounded-full bg-white/[0.03]" />
        <div className="relative z-10 flex items-center gap-4">
          <div className={`w-12 h-12 rounded flex items-center justify-center text-lg font-black flex-shrink-0 ${
            isPro ? "bg-teal-700/50 text-teal-200" : "bg-slate-700/50 text-slate-300"
          }`}>
            {initials}
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-0.5">
              <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-black tracking-widest uppercase ${
                isPro ? "bg-teal-900/60 text-teal-300 border border-teal-700/40" : "bg-slate-800 text-slate-400 border border-slate-700/40"
              }`}>
                {isPro ? <Crown size={9} /> : <User size={9} />}
                {isPro ? "Pro" : "Free"}
              </span>
            </div>
            <p className="text-slate-200 text-sm truncate font-medium">{user.email}</p>
            {nextBillingDate && <p className="text-slate-500 text-xs mt-0.5">次回請求: {nextBillingDate}</p>}
          </div>
        </div>
      </div>

      {/* プラン・課金 */}
      <div className="rounded border border-slate-700/60 bg-[#0c1424] overflow-hidden">
        <div className="px-5 py-3 border-b border-slate-700/40 flex items-center gap-2">
          <Shield size={13} className="text-slate-500" />
          <span className="text-[10px] font-black tracking-widest uppercase text-slate-400">プラン・課金</span>
        </div>
        {!isPro ? (
          <div className="px-5 py-4">
            <p className="text-sm text-slate-400 mb-3">
              無料プランは上位10件のシグナルのみ。Pro にアップグレードすると全件・ICT分析・メールアラートが使えます。
            </p>
            <Link
              href="/billing"
              className="flex items-center justify-between w-full bg-teal-600 hover:bg-teal-500 text-white px-4 py-3 rounded font-black text-xs tracking-widest uppercase transition-colors"
            >
              <span className="flex items-center gap-2"><Crown size={13} />Pro にアップグレード</span>
              <ChevronRight size={15} />
            </Link>
          </div>
        ) : (
          <button
            onClick={openPortal}
            disabled={portalLoading}
            className="w-full px-5 py-4 flex items-center justify-between hover:bg-slate-800/40 transition-colors disabled:opacity-60"
          >
            <span className="flex items-center gap-3 text-sm text-slate-300">
              <CreditCard size={15} className="text-slate-500" />
              <span>
                <span className="font-medium">サブスクリプション管理</span>
                <span className="block text-xs text-slate-500 mt-0.5">解約・カード変更はこちら</span>
              </span>
            </span>
            <ChevronRight size={14} className="text-slate-500" />
          </button>
        )}
      </div>

      {/* 通知設定 */}
      <div className="rounded border border-slate-700/60 bg-[#0c1424] overflow-hidden">
        <div className="px-5 py-3 border-b border-slate-700/40 flex items-center gap-2">
          <Bell size={13} className="text-slate-500" />
          <span className="text-[10px] font-black tracking-widest uppercase text-slate-400">通知設定</span>
        </div>
        <div className="px-5 py-4 flex justify-between items-center">
          <div>
            <p className="text-sm font-medium text-slate-200">日次シグナルアラート</p>
            <p className="text-xs text-slate-500 mt-0.5">
              {isPro
                ? "毎日18:45頃にシグナルメールを送信"
                : <span className="flex items-center gap-1"><BellOff size={10} /> Proプランで利用可能</span>}
            </p>
          </div>
          {isPro && notif !== null ? (
            <Toggle checked={notif.email_signal_alert} onChange={toggleEmailAlert} disabled={notifLoading} />
          ) : (
            <span className="text-xs text-slate-700">—</span>
          )}
        </div>
      </div>

      {/* ログアウト */}
      <button
        onClick={signOut}
        className="w-full flex items-center justify-center gap-2 border border-red-900/40 text-red-500 hover:bg-red-900/10 py-3 rounded text-sm font-black tracking-widest uppercase transition-colors"
      >
        <LogOut size={14} />
        ログアウト
      </button>

    </div>
  );
}
