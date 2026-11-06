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
  if (val === true)  return <Check size={16} className="text-teal-500 mx-auto" />;
  if (val === false) return <X size={14} className="text-slate-700 mx-auto" />;
  return <span className="text-xs font-medium text-slate-300">{val}</span>;
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
    <div className="max-w-2xl mx-auto space-y-6 pb-12">

      {/* ヘッダー */}
      <div className="text-center pt-2">
        <div className="inline-flex items-center gap-2 bg-teal-900/30 text-teal-400 text-[10px] font-black px-3 py-1 rounded tracking-widest uppercase mb-4">
          <Crown size={12} />
          プランを選択
        </div>
        <h1 className="text-3xl font-black tracking-tight mb-2">AIシグナルを最大限に活用</h1>
        <p className="text-slate-400 text-sm">全機能を無制限に使えるProプランで投資判断をレベルアップ</p>
      </div>

      {/* Pro ユーザーのサブスクリプション情報 */}
      {isPro && (
        <div className="rounded border border-teal-700/40 bg-teal-900/20 p-5">
          <div className="flex items-start justify-between gap-4 flex-wrap">
            <div>
              <p className="font-black text-teal-300 flex items-center gap-2 text-sm tracking-wide">
                <Crown size={15} className="fill-teal-500 text-teal-500" />
                Pro プラン ご利用中
              </p>
              {nextBillingDate && (
                <p className="text-sm text-slate-400 mt-1">
                  次回請求日: <span className="font-semibold text-slate-300">{nextBillingDate}</span>
                </p>
              )}
            </div>
            <button
              onClick={openPortal}
              disabled={portalLoading}
              className="flex items-center gap-1.5 text-sm px-4 py-2 rounded border border-teal-700/40 text-teal-400 hover:bg-teal-900/30 transition-colors disabled:opacity-50"
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
        <div className={`rounded border p-6 flex flex-col bg-[#0c1424] ${
          !isPro && user?.plan === "free"
            ? "border-slate-500/60 ring-1 ring-slate-500/30"
            : "border-slate-700/60"
        }`}>
          <div className="mb-4">
            <div className="flex items-center gap-2 mb-1">
              <Shield size={15} className="text-slate-500" />
              <span className="text-[10px] font-black tracking-widest uppercase text-slate-400">無料プラン</span>
              {!isPro && user?.plan === "free" && (
                <span className="ml-auto text-[10px] bg-slate-800 text-slate-500 px-2 py-0.5 rounded font-black tracking-widest uppercase">現在</span>
              )}
            </div>
            <div className="flex items-end gap-1">
              <span className="text-4xl font-black text-white">¥0</span>
              <span className="text-slate-500 text-sm mb-1"> /月</span>
            </div>
          </div>
          <div className="flex-1" />
          <div className="mt-6 w-full text-center py-2.5 rounded text-xs font-black tracking-widest uppercase bg-[#060b16] text-slate-500">
            無料で利用中
          </div>
        </div>

        {/* PRO */}
        <div className="rounded border-2 border-teal-500 p-6 flex flex-col relative overflow-hidden bg-[#0c1424] shadow-lg shadow-teal-500/10">
          <div className="absolute top-3.5 right-3.5 z-10">
            <span className="bg-teal-600 text-white text-[10px] px-2.5 py-1 rounded font-black tracking-widest uppercase shadow-sm">
              おすすめ
            </span>
          </div>
          <div className="relative z-10 mb-4">
            <div className="flex items-center gap-2 mb-1">
              <Crown size={15} className="text-teal-500" />
              <span className="text-[10px] font-black tracking-widest uppercase text-teal-400">Proプラン</span>
            </div>
            <div className="flex items-end gap-1">
              <span className="text-4xl font-black text-white">¥2,980</span>
              <span className="text-slate-500 text-sm mb-1"> /月</span>
            </div>
            <p className="text-xs text-slate-500 mt-1">いつでも解約可能</p>
          </div>
          <div className="relative z-10 flex-1" />
          <div className="relative z-10 mt-6">
            {isPro ? (
              <div className="w-full text-center py-2.5 rounded text-xs font-black tracking-widest uppercase bg-teal-900/30 text-teal-300 border border-teal-700/40">
                ✓ 現在のプラン
              </div>
            ) : (
              <button
                onClick={checkout}
                disabled={loading}
                className="w-full flex items-center justify-center gap-2 bg-teal-600 hover:bg-teal-500 active:bg-teal-700 disabled:opacity-60 text-white py-3 rounded font-black text-xs tracking-widest uppercase transition-all shadow-md shadow-teal-500/20"
              >
                <Zap size={16} className="shrink-0" />
                {loading ? "処理中..." : "Pro にアップグレード"}
              </button>
            )}
          </div>
        </div>

      </div>

      {/* 機能比較テーブル */}
      <div className="rounded border border-slate-700/60 bg-[#0c1424] overflow-hidden">
        <div className="px-5 py-3.5 bg-[#060b16] border-b border-slate-700/40">
          <p className="text-[10px] font-black tracking-widest uppercase text-slate-400">プラン比較</p>
        </div>
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-700/40">
              <th className="text-left px-5 py-3 text-[10px] text-slate-500 font-black uppercase tracking-widest w-1/2">機能</th>
              <th className="text-center px-4 py-3 text-[10px] text-slate-500 font-black uppercase tracking-widest">無料</th>
              <th className="text-center px-4 py-3 text-[10px] text-teal-500 font-black uppercase tracking-widest">Pro</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-700/30">
            {FEATURE_ROWS.map((row) => (
              <tr key={row.label} className={row.highlight ? "bg-teal-900/10" : ""}>
                <td className="px-5 py-3 text-slate-300 font-medium text-xs">{row.label}</td>
                <td className="px-4 py-3 text-center"><FeatureValue val={row.free} /></td>
                <td className="px-4 py-3 text-center"><FeatureValue val={row.pro} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* セキュリティ注記 */}
      <div className="flex items-center justify-center gap-4 text-xs text-slate-600">
        <span className="flex items-center gap-1"><Lock size={11} /> Stripe決済</span>
        <span>·</span>
        <span className="flex items-center gap-1"><CreditCard size={11} /> カード情報は保存不要</span>
        <span>·</span>
        <span>いつでも解約可能</span>
      </div>

    </div>
  );
}
