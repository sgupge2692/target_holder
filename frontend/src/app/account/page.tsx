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

/** トグルスイッチ */
function Toggle({ checked, onChange, disabled }: { checked: boolean; onChange: () => void; disabled?: boolean }) {
  return (
    <button
      onClick={onChange}
      disabled={disabled}
      role="switch"
      aria-checked={checked}
      className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 focus:outline-none disabled:opacity-50 ${
        checked ? "bg-brand-600" : "bg-gray-200 dark:bg-slate-600"
      }`}
    >
      <span
        className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${
          checked ? "translate-x-5" : "translate-x-0"
        }`}
      />
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
    ? new Date(sub.plan_expires_at).toLocaleDateString("ja-JP", {
        year: "numeric", month: "long", day: "numeric",
      })
    : null;

  useEffect(() => {
    if (!user) return;
    apiFetch<NotifSettings>("/api/notifications/settings")
      .then(setNotif)
      .catch(() => {});
  }, [user]);

  if (loading) return (
    <div className="max-w-lg mx-auto pt-12 space-y-4">
      {[...Array(3)].map((_, i) => (
        <div key={i} className="skeleton h-24 rounded-2xl" />
      ))}
    </div>
  );

  if (!user) {
    router.push("/auth");
    return null;
  }

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
    <div className="max-w-lg mx-auto space-y-5 pb-10">

      {/* ── プロフィールヘッダー ── */}
      <div className={`rounded-2xl p-6 text-white relative overflow-hidden ${
        isPro
          ? "bg-gradient-to-br from-brand-600 to-brand-800"
          : "bg-gradient-to-br from-slate-600 to-slate-800 dark:from-slate-700 dark:to-slate-900"
      }`}>
        {/* 背景装飾 */}
        <div className="absolute -right-8 -top-8 w-32 h-32 rounded-full bg-white/10" />
        <div className="absolute -right-2 -bottom-6 w-20 h-20 rounded-full bg-white/5" />
        <div className="relative z-10 flex items-center gap-4">
          {/* アバター */}
          <div className={`w-14 h-14 rounded-2xl flex items-center justify-center text-xl font-bold flex-shrink-0 ${
            isPro ? "bg-white/20 text-white" : "bg-white/15 text-white"
          }`}>
            {initials}
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-0.5">
              <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-bold ${
                isPro ? "bg-white/25 text-white" : "bg-white/15 text-white/80"
              }`}>
                {isPro ? <Crown size={11} /> : <User size={11} />}
                {isPro ? "Pro" : "Free"}
              </span>
            </div>
            <p className="text-white/90 text-sm truncate font-medium">{user.email}</p>
            {nextBillingDate && (
              <p className="text-white/60 text-xs mt-0.5">次回請求: {nextBillingDate}</p>
            )}
          </div>
        </div>
      </div>

      {/* ── プラン情報 ── */}
      <div className="rounded-2xl border border-gray-200 dark:border-slate-700 bg-white dark:bg-slate-900 overflow-hidden">
        <div className="px-5 py-3.5 border-b border-gray-100 dark:border-slate-800 flex items-center gap-2">
          <Shield size={15} className="text-gray-400" />
          <span className="text-sm font-semibold text-gray-700 dark:text-slate-300">プラン・課金</span>
        </div>

        {!isPro ? (
          <div className="px-5 py-4">
            <p className="text-sm text-gray-600 dark:text-slate-400 mb-3">
              無料プランは上位10件のシグナルのみ表示。Proにアップグレードすると全件・メールアラートが使えます。
            </p>
            <Link
              href="/billing"
              className="flex items-center justify-between w-full bg-brand-600 hover:bg-brand-700 text-white px-4 py-3 rounded-xl font-semibold text-sm transition-colors"
            >
              <span className="flex items-center gap-2">
                <Crown size={15} />
                Pro プランにアップグレード
              </span>
              <ChevronRight size={16} />
            </Link>
          </div>
        ) : (
          <button
            onClick={openPortal}
            disabled={portalLoading}
            className="w-full px-5 py-4 flex items-center justify-between hover:bg-gray-50 dark:hover:bg-slate-800 transition-colors disabled:opacity-60"
          >
            <span className="flex items-center gap-3 text-sm text-gray-700 dark:text-slate-300">
              <CreditCard size={16} className="text-gray-400" />
              <span>
                <span className="font-medium">サブスクリプション管理</span>
                <span className="block text-xs text-gray-400 dark:text-slate-500 mt-0.5">解約・カード変更はこちら</span>
              </span>
            </span>
            <ChevronRight size={15} className="text-gray-400" />
          </button>
        )}
      </div>

      {/* ── 通知設定 ── */}
      <div className="rounded-2xl border border-gray-200 dark:border-slate-700 bg-white dark:bg-slate-900 overflow-hidden">
        <div className="px-5 py-3.5 border-b border-gray-100 dark:border-slate-800 flex items-center gap-2">
          <Bell size={15} className="text-gray-400" />
          <span className="text-sm font-semibold text-gray-700 dark:text-slate-300">通知設定</span>
        </div>
        <div className="px-5 py-4 flex justify-between items-center">
          <div>
            <p className="text-sm font-medium text-gray-800 dark:text-slate-200">日次シグナルアラート</p>
            <p className="text-xs text-gray-500 dark:text-slate-400 mt-0.5">
              {isPro
                ? "毎日18:45頃にシグナルメールを送信します"
                : <span className="flex items-center gap-1"><BellOff size={11} /> Proプランで利用可能</span>}
            </p>
          </div>
          {isPro && notif !== null ? (
            <Toggle
              checked={notif.email_signal_alert}
              onChange={toggleEmailAlert}
              disabled={notifLoading}
            />
          ) : (
            <span className="text-xs text-gray-300 dark:text-slate-600">—</span>
          )}
        </div>
      </div>

      {/* ── ログアウト ── */}
      <button
        onClick={signOut}
        className="w-full flex items-center justify-center gap-2 border border-red-200 dark:border-red-900/50 text-red-500 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/10 py-3 rounded-xl text-sm font-medium transition-colors"
      >
        <LogOut size={15} />
        ログアウト
      </button>

    </div>
  );
}
