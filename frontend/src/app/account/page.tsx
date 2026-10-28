"use client";
import { useRouter } from "next/navigation";
import Link from "next/link";
import useSWR from "swr";
import { useAuth } from "@/hooks/useAuth";
import { createPortal, apiFetch, getSubscription } from "@/lib/api";
import { useState, useEffect } from "react";
import { Bell, BellOff } from "lucide-react";

interface NotifSettings {
  email_signal_alert: boolean;
  email_unsubscribed: boolean;
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

  // 通知設定を取得
  useEffect(() => {
    if (!user) return;
    apiFetch<NotifSettings>("/api/notifications/settings")
      .then(setNotif)
      .catch(() => {});
  }, [user]);

  if (loading) return <div className="text-center py-16 text-gray-400">読み込み中...</div>;
  if (!user) {
    router.push("/auth");
    return null;
  }

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
    <div className="max-w-lg mx-auto space-y-6">
      <h1 className="text-2xl font-bold">アカウント</h1>

      {/* ── プロフィール情報 ── */}
      <div className="bg-white dark:bg-slate-800 rounded-2xl border border-gray-200 dark:border-slate-700 divide-y divide-gray-100 dark:divide-slate-700">
        <div className="px-6 py-4 flex justify-between items-center">
          <span className="text-sm text-gray-500">メール</span>
          <span className="font-medium text-sm">{user.email}</span>
        </div>
        <div className="px-6 py-4 flex justify-between items-center">
          <span className="text-sm text-gray-500">プラン</span>
          <div className="text-right">
            <span className={`px-2.5 py-0.5 rounded-full text-xs font-semibold ${
              user.plan === "pro"
                ? "bg-brand-100 text-brand-700 dark:bg-brand-900/40 dark:text-brand-300"
                : "bg-gray-100 text-gray-600 dark:bg-slate-700 dark:text-slate-300"
            }`}>
              {user.plan === "pro" ? "Pro" : "無料"}
            </span>
            {nextBillingDate && (
              <p className="text-xs text-gray-400 dark:text-slate-500 mt-1">
                次回請求: {nextBillingDate}
              </p>
            )}
          </div>
        </div>
      </div>

      {/* ── 通知設定 ── */}
      {notif !== null && (
        <div className="bg-white dark:bg-slate-800 rounded-2xl border border-gray-200 dark:border-slate-700 overflow-hidden">
          <div className="px-6 py-4 border-b border-gray-100 dark:border-slate-700">
            <h2 className="text-sm font-semibold text-gray-700 dark:text-slate-300 flex items-center gap-2">
              <Bell className="w-4 h-4" />
              メール通知
            </h2>
          </div>
          <div className="px-6 py-4 flex justify-between items-center">
            <div>
              <p className="text-sm font-medium">日次シグナルアラート</p>
              <p className="text-xs text-gray-500 dark:text-slate-400 mt-0.5">
                {user.plan === "pro"
                  ? "毎日18:45頃にシグナルメールを送信"
                  : "Proプランで利用可能"}
              </p>
            </div>
            {user.plan === "pro" ? (
              <button
                onClick={toggleEmailAlert}
                disabled={notifLoading}
                className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 focus:outline-none disabled:opacity-50 ${
                  notif.email_signal_alert ? "bg-brand-600" : "bg-gray-200 dark:bg-slate-600"
                }`}
                role="switch"
                aria-checked={notif.email_signal_alert}
              >
                <span
                  className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${
                    notif.email_signal_alert ? "translate-x-5" : "translate-x-0"
                  }`}
                />
              </button>
            ) : (
              <span className="text-xs text-gray-400 dark:text-slate-500 flex items-center gap-1">
                <BellOff className="w-3 h-3" /> Pro限定
              </span>
            )}
          </div>
        </div>
      )}

      {/* ── アクション ── */}
      <div className="flex flex-col gap-3">
        {user.plan !== "pro" && (
          <Link
            href="/billing"
            className="w-full text-center bg-brand-600 hover:bg-brand-700 text-white py-2.5 rounded-lg font-medium transition-colors"
          >
            Pro プランにアップグレード
          </Link>
        )}
        {user.plan === "pro" && (
          <button
            onClick={openPortal}
            disabled={portalLoading}
            className="w-full border border-gray-300 dark:border-slate-600 hover:bg-gray-50 dark:hover:bg-slate-800 py-2.5 rounded-lg text-sm font-medium transition-colors disabled:opacity-60"
          >
            {portalLoading ? "処理中..." : "サブスクリプション管理（解約・カード変更）"}
          </button>
        )}
        <button
          onClick={signOut}
          className="w-full border border-red-200 dark:border-red-900 text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 py-2.5 rounded-lg text-sm font-medium transition-colors"
        >
          ログアウト
        </button>
      </div>
    </div>
  );
}
