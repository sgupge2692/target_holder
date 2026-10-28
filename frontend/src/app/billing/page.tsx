"use client";
import { useState } from "react";
import useSWR from "swr";
import { createCheckout, createPortal, getSubscription } from "@/lib/api";
import { useAuth } from "@/hooks/useAuth";
import { Check, CreditCard, ExternalLink, Zap } from "lucide-react";

const FEATURES = {
  free: ["シグナル上位10件", "直近30日チャート", "直近5件の履歴", "ウォッチリスト30件"],
  pro:  ["シグナル全件（数百銘柄）", "全期間チャート", "全履歴閲覧", "精度グラフ", "CSV エクスポート", "ウォッチリスト300件", "優先サポート"],
};

export default function BillingPage() {
  const { user } = useAuth();
  const [loading, setLoading] = useState(false);
  const [portalLoading, setPortalLoading] = useState(false);

  const { data: sub } = useSWR(user?.plan === "pro" ? "subscription" : null, getSubscription);

  const checkout = async () => {
    if (!user) { window.location.href = "/auth"; return; }
    setLoading(true);
    try {
      const { url } = await createCheckout();
      window.location.href = url;
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : "エラーが発生しました");
      setLoading(false);
    }
  };

  const openPortal = async () => {
    setPortalLoading(true);
    try {
      const { url } = await createPortal();
      window.location.href = url;
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : "エラーが発生しました");
      setPortalLoading(false);
    }
  };

  const nextBillingDate = sub?.plan_expires_at
    ? new Date(sub.plan_expires_at).toLocaleDateString("ja-JP", {
        year: "numeric", month: "long", day: "numeric",
      })
    : null;

  return (
    <div className="max-w-3xl mx-auto space-y-8">
      <div className="text-center">
        <h1 className="text-3xl font-bold mb-2">プランを選択</h1>
        <p className="text-gray-500 dark:text-slate-400">全機能を使いたい方は Pro プランへ</p>
      </div>

      {/* Pro ユーザーのサブスクリプション情報 */}
      {user?.plan === "pro" && (
        <div className="rounded-2xl border border-brand-200 dark:border-brand-800 bg-brand-50 dark:bg-brand-900/20 p-5">
          <div className="flex items-start justify-between gap-4 flex-wrap">
            <div>
              <p className="font-semibold text-brand-700 dark:text-brand-300 flex items-center gap-2">
                <CreditCard size={16} />
                Pro プラン ご利用中
              </p>
              {nextBillingDate && (
                <p className="text-sm text-gray-600 dark:text-slate-400 mt-1">
                  次回請求日: <span className="font-medium">{nextBillingDate}</span>
                </p>
              )}
            </div>
            <button
              onClick={openPortal}
              disabled={portalLoading}
              className="flex items-center gap-1.5 text-sm px-4 py-2 rounded-lg border border-brand-300 dark:border-brand-700 text-brand-700 dark:text-brand-300 hover:bg-brand-100 dark:hover:bg-brand-900/40 transition-colors disabled:opacity-50"
            >
              <ExternalLink size={14} />
              {portalLoading ? "リダイレクト中..." : "プランの管理・解約"}
            </button>
          </div>
        </div>
      )}

      <div className="grid sm:grid-cols-2 gap-6">
        {/* FREE */}
        <div className="rounded-2xl border border-gray-200 dark:border-slate-700 p-6 bg-white dark:bg-slate-800">
          <p className="text-sm font-medium text-gray-500 mb-1">無料プラン</p>
          <p className="text-3xl font-bold mb-6">¥0<span className="text-base font-normal text-gray-400"> /月</span></p>
          <ul className="space-y-2 mb-8">
            {FEATURES.free.map(f => (
              <li key={f} className="flex items-center gap-2 text-sm">
                <Check size={14} className="text-brand-500 shrink-0" />{f}
              </li>
            ))}
          </ul>
          <div className={`w-full text-center py-2.5 rounded-lg text-sm font-medium ${
            user?.plan === "free"
              ? "border border-gray-300 dark:border-slate-600 text-gray-500"
              : "bg-gray-100 dark:bg-slate-700 text-gray-600 dark:text-slate-300"
          }`}>
            {user?.plan === "free" ? "現在のプラン" : "基本プラン"}
          </div>
        </div>

        {/* PRO */}
        <div className="rounded-2xl border-2 border-brand-500 p-6 bg-white dark:bg-slate-800 relative overflow-hidden">
          <div className="absolute top-3 right-3 bg-brand-500 text-white text-xs px-2 py-0.5 rounded-full font-medium">
            人気
          </div>
          <p className="text-sm font-medium text-brand-600 dark:text-brand-400 mb-1">Proプラン</p>
          <p className="text-3xl font-bold mb-6">¥2,980<span className="text-base font-normal text-gray-400"> /月</span></p>
          <ul className="space-y-2 mb-8">
            {FEATURES.pro.map(f => (
              <li key={f} className="flex items-center gap-2 text-sm">
                <Check size={14} className="text-brand-500 shrink-0" />{f}
              </li>
            ))}
          </ul>
          {user?.plan === "pro" ? (
            <div className="w-full text-center py-2.5 rounded-lg text-sm font-medium bg-brand-100 dark:bg-brand-900/30 text-brand-700 dark:text-brand-400 border border-brand-300 dark:border-brand-700">
              現在のプラン ✓
            </div>
          ) : (
            <button
              onClick={checkout}
              disabled={loading}
              className="w-full flex items-center justify-center gap-2 bg-brand-600 hover:bg-brand-700 disabled:opacity-60 text-white py-2.5 rounded-lg font-medium transition-colors"
            >
              <Zap size={16} />{loading ? "処理中..." : "Pro にアップグレード"}
            </button>
          )}
        </div>
      </div>

      <p className="text-center text-xs text-gray-400">
        決済はStripeを利用。解約はプラン管理ページからいつでも可能です。解約後も請求期間終了まで利用できます。
      </p>
    </div>
  );
}
