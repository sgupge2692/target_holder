"use client";
import { useState } from "react";
import useSWR from "swr";
import { createCheckout, createPortal, getSubscription } from "@/lib/api";
import { useAuth } from "@/hooks/useAuth";
import { Check, X, CreditCard, ExternalLink, Zap, Crown, Shield, Lock } from "lucide-react";

// Free / Pro 機能比較
const FEATURE_ROWS = [
  { label: "シグナル閲覧",       free: "上位10件",       pro: "全件（数百銘柄）",   highlight: true },
  { label: "株価チャート",       free: "直近30日",       pro: "全期間",            highlight: false },
  { label: "シグナル履歴",       free: "直近5件",        pro: "全期間",            highlight: false },
  { label: "確率バー表示",       free: true,             pro: true,               highlight: false },
  { label: "ウォッチリスト",     free: "30件まで",       pro: "300件まで",         highlight: false },
  { label: "バックテスト閲覧",   free: true,             pro: true,               highlight: false },
  { label: "精度グラフ詳細",     free: false,            pro: true,               highlight: false },
  { label: "CSVエクスポート",    free: false,            pro: true,               highlight: true  },
  { label: "日次メールアラート", free: false,            pro: true,               highlight: true  },
  { label: "優先サポート",       free: false,            pro: true,               highlight: false },
] as const;

function FeatureValue({ val }: { val: boolean | string }) {
  if (val === true)  return <Check size={16} className="text-brand-500 mx-auto" />;
  if (val === false) return <X size={14} className="text-gray-300 dark:text-slate-600 mx-auto" />;
  return <span className="text-xs font-medium text-gray-600 dark:text-slate-300">{val}</span>;
}

export default function BillingPage() {
  const { user } = useAuth();
  const [loading, setLoading]       = useState(false);
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

  const isPro = user?.plan === "pro";

  return (
    <div className="max-w-2xl mx-auto space-y-8 pb-12">

      {/* ヘッダー */}
      <div className="text-center pt-2">
        <div className="inline-flex items-center gap-2 bg-brand-100 dark:bg-brand-900/30 text-brand-700 dark:text-brand-300 text-xs font-semibold px-3 py-1 rounded-full mb-4">
          <Crown size={12} />
          プランを選択
        </div>
        <h1 className="text-3xl font-black tracking-tight mb-2">AIシグナルを最大限に活用</h1>
        <p className="text-gray-500 dark:text-slate-400">全機能を無制限に使えるProプランで投資判断をレベルアップ</p>
      </div>

      {/* Pro ユーザーのサブスクリプション情報 */}
      {isPro && (
        <div className="rounded-2xl border border-brand-200 dark:border-brand-800 bg-gradient-to-r from-brand-50 to-emerald-50 dark:from-brand-900/20 dark:to-emerald-900/10 p-5">
          <div className="flex items-start justify-between gap-4 flex-wrap">
            <div>
              <p className="font-bold text-brand-700 dark:text-brand-300 flex items-center gap-2">
                <Crown size={15} className="fill-brand-500 text-brand-500" />
                Pro プラン ご利用中
              </p>
              {nextBillingDate && (
                <p className="text-sm text-gray-600 dark:text-slate-400 mt-1">
                  次回請求日: <span className="font-semibold">{nextBillingDate}</span>
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

      {/* 価格カード 2列 */}
      <div className="grid sm:grid-cols-2 gap-4">

        {/* FREE */}
        <div className={`rounded-2xl border p-6 flex flex-col ${
          !isPro && user?.plan === "free"
            ? "border-gray-300 dark:border-slate-600 bg-white dark:bg-slate-900 ring-2 ring-gray-200 dark:ring-slate-700"
            : "border-gray-200 dark:border-slate-700 bg-white dark:bg-slate-900"
        }`}>
          <div className="mb-4">
            <div className="flex items-center gap-2 mb-1">
              <Shield size={15} className="text-gray-400" />
              <span className="text-sm font-semibold text-gray-600 dark:text-slate-400">無料プラン</span>
              {!isPro && user?.plan === "free" && (
                <span className="ml-auto text-xs bg-gray-100 dark:bg-slate-800 text-gray-500 px-2 py-0.5 rounded-full">現在</span>
              )}
            </div>
            <div className="flex items-end gap-1">
              <span className="text-4xl font-black">¥0</span>
              <span className="text-gray-400 text-sm mb-1"> /月</span>
            </div>
          </div>
          <div className="flex-1" />
          <div className="mt-6 w-full text-center py-2.5 rounded-xl text-sm font-medium bg-gray-100 dark:bg-slate-800 text-gray-500 dark:text-slate-400">
            無料で利用中
          </div>
        </div>

        {/* PRO */}
        <div className="rounded-2xl border-2 border-brand-500 p-6 flex flex-col relative overflow-hidden bg-white dark:bg-slate-900 shadow-lg shadow-brand-500/10">
          {/* 背景グロウ */}
          <div className="absolute inset-0 bg-gradient-to-br from-brand-50/60 to-transparent dark:from-brand-900/20 pointer-events-none" />
          <div className="absolute top-3.5 right-3.5 z-10">
            <span className="bg-gradient-to-r from-brand-500 to-brand-600 text-white text-xs px-2.5 py-1 rounded-full font-bold shadow-sm">
              おすすめ
            </span>
          </div>
          <div className="relative z-10 mb-4">
            <div className="flex items-center gap-2 mb-1">
              <Crown size={15} className="text-brand-500" />
              <span className="text-sm font-bold text-brand-600 dark:text-brand-400">Proプラン</span>
            </div>
            <div className="flex items-end gap-1">
              <span className="text-4xl font-black">¥2,980</span>
              <span className="text-gray-400 text-sm mb-1"> /月</span>
            </div>
            <p className="text-xs text-gray-500 dark:text-slate-400 mt-1">いつでも解約可能</p>
          </div>
          <div className="relative z-10 flex-1" />
          <div className="relative z-10 mt-6">
            {isPro ? (
              <div className="w-full text-center py-2.5 rounded-xl text-sm font-bold bg-brand-100 dark:bg-brand-900/40 text-brand-700 dark:text-brand-400 border border-brand-200 dark:border-brand-800">
                ✓ 現在のプラン
              </div>
            ) : (
              <button
                onClick={checkout}
                disabled={loading}
                className="w-full flex items-center justify-center gap-2 bg-brand-600 hover:bg-brand-700 active:bg-brand-800 disabled:opacity-60 text-white py-3 rounded-xl font-bold transition-all shadow-md shadow-brand-500/20 hover:shadow-brand-500/30"
              >
                <Zap size={16} className="shrink-0" />
                {loading ? "処理中..." : "Pro にアップグレード"}
              </button>
            )}
          </div>
        </div>

      </div>

      {/* 機能比較テーブル */}
      <div className="rounded-2xl border border-gray-200 dark:border-slate-700 bg-white dark:bg-slate-900 overflow-hidden">
        <div className="px-5 py-3.5 bg-gray-50 dark:bg-slate-800/80 border-b border-gray-100 dark:border-slate-700">
          <p className="text-sm font-semibold text-gray-700 dark:text-slate-300">プラン比較</p>
        </div>
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-100 dark:border-slate-700">
              <th className="text-left px-5 py-3 text-xs text-gray-400 dark:text-slate-500 font-semibold uppercase tracking-wide w-1/2">機能</th>
              <th className="text-center px-4 py-3 text-xs text-gray-400 dark:text-slate-500 font-semibold uppercase tracking-wide">無料</th>
              <th className="text-center px-4 py-3 text-xs text-brand-600 dark:text-brand-400 font-semibold uppercase tracking-wide">Pro</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-50 dark:divide-slate-800">
            {FEATURE_ROWS.map((row) => (
              <tr key={row.label} className={row.highlight ? "bg-brand-50/30 dark:bg-brand-900/10" : ""}>
                <td className="px-5 py-3 text-gray-700 dark:text-slate-300 font-medium text-xs">{row.label}</td>
                <td className="px-4 py-3 text-center"><FeatureValue val={row.free} /></td>
                <td className="px-4 py-3 text-center"><FeatureValue val={row.pro} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* セキュリティ注記 */}
      <div className="flex items-center justify-center gap-4 text-xs text-gray-400 dark:text-slate-500">
        <span className="flex items-center gap-1"><Lock size={11} /> Stripe決済</span>
        <span>·</span>
        <span className="flex items-center gap-1"><CreditCard size={11} /> カード情報は保存不要</span>
        <span>·</span>
        <span>いつでも解約可能</span>
      </div>

    </div>
  );
}
