"use client";
import { useParams } from "next/navigation";
import { useState, useEffect } from "react";
import useSWR, { mutate } from "swr";
import Link from "next/link";
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from "recharts";
import {
  getStock, getQuotes, getSignalHistory, getSummary, generateSummary, regenerateSummary,
  getWatchlistStatus, addToWatchlist, removeFromWatchlist, type Summary,
} from "@/lib/api";
import { SignalBadge } from "@/components/SignalBadge";
import { SummaryCard } from "@/components/SummaryCard";
import { useAuth } from "@/hooks/useAuth";
import { ArrowLeft, Lock, Star } from "lucide-react";

export default function StockPage() {
  const { code } = useParams<{ code: string }>();
  const { user } = useAuth();

  const [summary, setSummary]      = useState<Summary | null>(null);
  const [sumLoading, setSumLoad]   = useState(false);
  const [watchLoading, setWatchLd] = useState(false);

  const { data: stock }   = useSWR(`stock:${code}`,   () => getStock(code));
  const { data: quotes }  = useSWR(user ? `quotes:${code}` : null, () => getQuotes(code));
  const { data: history } = useSWR(user ? `hist:${code}` : null, () => getSignalHistory(code));
  const { data: watchStatus, mutate: mutateWatch } = useSWR(
    user ? `watch:${code}` : null,
    () => getWatchlistStatus(code),
  );
  const watched = watchStatus?.watched ?? false;

  const toggleWatch = async () => {
    if (!user) return;
    setWatchLd(true);
    try {
      if (watched) {
        await removeFromWatchlist(code);
      } else {
        await addToWatchlist(code);
      }
      mutateWatch();
      mutate("watchlist");  // ウォッチリストページのキャッシュも更新
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : "エラーが発生しました");
    } finally {
      setWatchLd(false);
    }
  };

  // 要約を初回ロード（404 は無視）
  useEffect(() => {
    if (!user) return;
    getSummary(code).then(setSummary).catch(() => {});
  }, [code, user]);

  const handleGenerate = async (text: string, yearLabel: string) => {
    setSumLoad(true);
    try { setSummary(await generateSummary(code, text, yearLabel)); }
    catch (e: unknown) { alert(e instanceof Error ? e.message : "エラー"); }
    finally { setSumLoad(false); }
  };

  const handleRegenerate = async (text: string, yearLabel: string) => {
    setSumLoad(true);
    try { setSummary(await regenerateSummary(code, text, yearLabel)); }
    catch (e: unknown) { alert(e instanceof Error ? e.message : "エラー"); }
    finally { setSumLoad(false); }
  };

  const chartData = (quotes?.quotes ?? [])
    .slice().reverse()
    .map(q => ({ date: q.Date, price: Number(q.AdjustmentClose) }));

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Link href="/" className="p-1.5 rounded-md hover:bg-gray-100 dark:hover:bg-slate-800 transition-colors">
          <ArrowLeft size={18} />
        </Link>
        <div>
          <h1 className="text-xl font-bold">{stock?.company_name ?? code}</h1>
          <p className="text-sm text-gray-400">{code} · {stock?.market_code}</p>
        </div>
        <div className="ml-auto flex items-center gap-2">
          {user && (
            <button
              onClick={toggleWatch}
              disabled={watchLoading}
              title={watched ? "ウォッチリストから削除" : "ウォッチリストに追加"}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium border transition-all disabled:opacity-50 ${
                watched
                  ? "bg-amber-100 dark:bg-amber-900/30 text-amber-600 dark:text-amber-300 border-amber-300 dark:border-amber-700 hover:bg-amber-200"
                  : "bg-gray-100 dark:bg-slate-800 text-gray-500 dark:text-slate-400 border-gray-200 dark:border-slate-700 hover:bg-gray-200 dark:hover:bg-slate-700"
              }`}
            >
              <Star size={12} className={watched ? "fill-amber-500 text-amber-500" : ""} />
              {watched ? "ウォッチ中" : "ウォッチ"}
            </button>
          )}
          {user && quotes?.plan === "free" && (
            <Link href="/billing" className="text-xs bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300 border border-amber-200 dark:border-amber-700 px-3 py-1 rounded-full hover:bg-amber-200 transition-colors">
              Pro で全期間表示
            </Link>
          )}
        </div>
      </div>

      {/* チャート */}
      <div className="bg-white dark:bg-slate-800 rounded-2xl border border-gray-200 dark:border-slate-700 p-5">
        <p className="text-sm font-medium mb-4 text-gray-500 dark:text-slate-400">
          株価チャート（調整後終値）
          {quotes?.plan === "free" && <span className="ml-2 text-amber-500 text-xs">直近30日</span>}
        </p>
        {!user ? (
          <div className="flex items-center justify-center h-40 gap-2 text-gray-400">
            <Lock size={16} /><span className="text-sm">ログインで閲覧可能</span>
          </div>
        ) : chartData.length > 0 ? (
          <ResponsiveContainer width="100%" height={240}>
            <AreaChart data={chartData}>
              <defs>
                <linearGradient id="colorPrice" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%"  stopColor="#22c55e" stopOpacity={0.2} />
                  <stop offset="95%" stopColor="#22c55e" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(100,116,139,0.15)" />
              <XAxis dataKey="date" tick={{ fontSize: 10 }} interval="preserveStartEnd" />
              <YAxis domain={["auto", "auto"]} tick={{ fontSize: 10 }} />
              <Tooltip formatter={(v: number) => `¥${v.toLocaleString()}`} />
              <Area type="monotone" dataKey="price" stroke="#22c55e" fill="url(#colorPrice)" strokeWidth={2} dot={false} />
            </AreaChart>
          </ResponsiveContainer>
        ) : (
          <p className="text-center text-gray-400 py-12">データなし</p>
        )}
      </div>

      {/* 四季報 LLM 要約 */}
      {user && (
        <SummaryCard
          code={code}
          isPro={user.plan === "pro"}
          summary={summary}
          loading={sumLoading}
          onGenerate={handleGenerate}
          onRegenerate={handleRegenerate}
        />
      )}

      {/* シグナル履歴 */}
      <div className="bg-white dark:bg-slate-800 rounded-2xl border border-gray-200 dark:border-slate-700 p-5">
        <p className="text-sm font-medium mb-4 text-gray-500 dark:text-slate-400">
          シグナル履歴
          {history?.plan === "free" && <span className="ml-2 text-amber-500 text-xs">直近5件</span>}
        </p>
        {!user ? (
          <div className="flex items-center justify-center h-24 gap-2 text-gray-400">
            <Lock size={16} /><span className="text-sm">ログインで閲覧可能</span>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-xs text-gray-500 dark:text-slate-400 uppercase">
                <tr>
                  <th className="pb-2 text-left">日付</th>
                  <th className="pb-2 text-center">シグナル</th>
                  <th className="pb-2 text-right">確率</th>
                  <th className="pb-2 text-right">実績リターン</th>
                  <th className="pb-2 text-center">的中</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50 dark:divide-slate-700">
                {(history?.history ?? []).map((h, i) => (
                  <tr key={i}>
                    <td className="py-2 text-gray-500">{h.Date}</td>
                    <td className="py-2 text-center"><SignalBadge signal={h.signal} /></td>
                    <td className="py-2 text-right font-mono">{(h.up_probability * 100).toFixed(1)}%</td>
                    <td className="py-2 text-right font-mono">
                      {h.actual_return != null
                        ? <span className={h.actual_return >= 0 ? "text-emerald-600" : "text-red-500"}>
                            {h.actual_return >= 0 ? "+" : ""}{(h.actual_return * 100).toFixed(2)}%
                          </span>
                        : "—"}
                    </td>
                    <td className="py-2 text-center">
                      {h.is_correct == null ? "—" : h.is_correct ? "✅" : "❌"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {(history?.history ?? []).length === 0 && (
              <p className="text-center text-gray-400 py-8">履歴なし</p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
