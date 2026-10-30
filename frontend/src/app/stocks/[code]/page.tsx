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
import { ArrowLeft, Lock, Star, TrendingUp, TrendingDown, Crown } from "lucide-react";

/** 確率バー（ミニ版） */
function MiniProbBar({ prob }: { prob: number }) {
  const pct = Math.round(prob * 100);
  const color = prob >= 0.8 ? "bg-brand-500" : prob >= 0.7 ? "bg-emerald-400" : prob >= 0.6 ? "bg-amber-400" : "bg-gray-400";
  return (
    <div className="flex items-center gap-1.5 justify-end">
      <div className="prob-bar-track w-12">
        <div className={`prob-bar-fill ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className={`font-mono text-xs font-semibold w-[3rem] text-right ${prob >= 0.75 ? "text-brand-600 dark:text-brand-400" : "text-gray-600 dark:text-slate-400"}`}>
        {pct.toFixed(1)}%
      </span>
    </div>
  );
}

/** チャートのカスタムツールチップ */
function PriceTooltip({ active, payload, label }: { active?: boolean; payload?: { value: number }[]; label?: string }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-white dark:bg-slate-800 border border-gray-200 dark:border-slate-700 rounded-xl px-3 py-2 shadow-lg text-sm">
      <p className="text-xs text-gray-400 mb-0.5">{label}</p>
      <p className="font-mono font-bold text-brand-600 dark:text-brand-400">
        ¥{payload[0].value.toLocaleString()}
      </p>
    </div>
  );
}

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
      mutate("watchlist");
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : "エラーが発生しました");
    } finally {
      setWatchLd(false);
    }
  };

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

  // 直近2日の価格変化
  const latestPrice  = chartData.at(-1)?.price ?? null;
  const prevPrice    = chartData.at(-2)?.price ?? null;
  const priceChange  = latestPrice != null && prevPrice != null ? latestPrice - prevPrice : null;
  const changePct    = priceChange != null && prevPrice ? (priceChange / prevPrice) * 100 : null;
  const isUp         = priceChange != null && priceChange >= 0;

  return (
    <div className="space-y-5">
      {/* ヘッダー */}
      <div className="flex items-start gap-3">
        <Link href="/" className="mt-1 p-1.5 rounded-md hover:bg-gray-100 dark:hover:bg-slate-800 transition-colors shrink-0">
          <ArrowLeft size={18} />
        </Link>
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2 flex-wrap">
            <div>
              <h1 className="text-xl font-bold leading-tight">{stock?.company_name ?? code}</h1>
              <p className="text-sm text-gray-400 mt-0.5">{code} · {stock?.market_code}</p>
            </div>

            {/* 株価表示 */}
            {latestPrice && (
              <div className="text-right shrink-0">
                <div className="text-xl font-black font-mono tabular-nums">
                  ¥{latestPrice.toLocaleString()}
                </div>
                {changePct != null && (
                  <div className={`flex items-center justify-end gap-0.5 text-xs font-semibold ${isUp ? "text-emerald-600" : "text-red-500"}`}>
                    {isUp ? <TrendingUp size={12} /> : <TrendingDown size={12} />}
                    {isUp ? "+" : ""}{changePct.toFixed(2)}%
                  </div>
                )}
              </div>
            )}
          </div>

          {/* ウォッチ・Proバッジ */}
          <div className="flex items-center gap-2 mt-2">
            {user && (
              <button
                onClick={toggleWatch}
                disabled={watchLoading}
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
              <Link href="/billing" className="flex items-center gap-1 text-xs bg-gradient-to-r from-amber-100 to-orange-100 dark:from-amber-900/30 dark:to-orange-900/20 text-amber-700 dark:text-amber-300 border border-amber-200 dark:border-amber-700 px-3 py-1.5 rounded-full hover:from-amber-200 transition-colors">
                <Crown size={11} />
                Pro で全期間表示
              </Link>
            )}
          </div>
        </div>
      </div>

      {/* チャート */}
      <div className="bg-white dark:bg-slate-800 rounded-2xl border border-gray-200 dark:border-slate-700 p-5">
        <div className="flex items-center justify-between mb-4">
          <p className="text-sm font-semibold text-gray-700 dark:text-slate-300">株価チャート</p>
          {quotes?.plan === "free" && (
            <span className="text-xs text-amber-600 bg-amber-50 dark:bg-amber-900/20 px-2 py-0.5 rounded-full border border-amber-200 dark:border-amber-800">
              直近30日
            </span>
          )}
        </div>
        {!user ? (
          <div className="flex items-center justify-center h-40 gap-2 text-gray-400">
            <Lock size={16} /><span className="text-sm">ログインで閲覧可能</span>
          </div>
        ) : chartData.length > 0 ? (
          <ResponsiveContainer width="100%" height={240}>
            <AreaChart data={chartData} margin={{ top: 4, right: 8, left: -8, bottom: 4 }}>
              <defs>
                <linearGradient id="colorPrice" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%"  stopColor="#16a34a" stopOpacity={0.25} />
                  <stop offset="95%" stopColor="#16a34a" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(100,116,139,0.1)" />
              <XAxis dataKey="date" tick={{ fontSize: 10 }} interval="preserveStartEnd" />
              <YAxis domain={["auto", "auto"]} tick={{ fontSize: 10 }} tickFormatter={v => `¥${(v/1000).toFixed(0)}k`} />
              <Tooltip content={<PriceTooltip />} />
              <Area
                type="monotone"
                dataKey="price"
                stroke="#16a34a"
                fill="url(#colorPrice)"
                strokeWidth={2.5}
                dot={false}
                activeDot={{ r: 4, fill: "#16a34a" }}
              />
            </AreaChart>
          </ResponsiveContainer>
        ) : (
          <p className="text-center text-gray-400 py-12 text-sm">データなし</p>
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
        <div className="flex items-center justify-between mb-4">
          <p className="text-sm font-semibold text-gray-700 dark:text-slate-300">シグナル履歴</p>
          {history?.plan === "free" && (
            <span className="text-xs text-amber-600 bg-amber-50 dark:bg-amber-900/20 px-2 py-0.5 rounded-full border border-amber-200 dark:border-amber-800">
              直近5件
            </span>
          )}
        </div>
        {!user ? (
          <div className="flex items-center justify-center h-24 gap-2 text-gray-400">
            <Lock size={16} /><span className="text-sm">ログインで閲覧可能</span>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-xs text-gray-500 dark:text-slate-400 uppercase tracking-wide border-b border-gray-100 dark:border-slate-700">
                <tr>
                  <th className="pb-2.5 text-left">日付</th>
                  <th className="pb-2.5 text-center">シグナル</th>
                  <th className="pb-2.5 text-right">確率</th>
                  <th className="pb-2.5 text-right">実績</th>
                  <th className="pb-2.5 text-center">的中</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50 dark:divide-slate-700/60">
                {(history?.history ?? []).map((h, i) => (
                  <tr key={i} className="hover:bg-gray-50 dark:hover:bg-slate-700/30 transition-colors">
                    <td className="py-2.5 text-gray-500 dark:text-slate-400 tabular-nums text-xs">{h.Date}</td>
                    <td className="py-2.5 text-center"><SignalBadge signal={h.signal} /></td>
                    <td className="py-2.5">
                      <MiniProbBar prob={h.up_probability} />
                    </td>
                    <td className="py-2.5 text-right font-mono text-xs">
                      {h.actual_return != null
                        ? <span className={`font-semibold ${h.actual_return >= 0 ? "text-emerald-600" : "text-red-500"}`}>
                            {h.actual_return >= 0 ? "+" : ""}{(h.actual_return * 100).toFixed(2)}%
                          </span>
                        : <span className="text-gray-300 dark:text-slate-600">—</span>}
                    </td>
                    <td className="py-2.5 text-center text-base">
                      {h.is_correct == null
                        ? <span className="text-gray-300 dark:text-slate-600 text-xs">—</span>
                        : h.is_correct ? "✅" : "❌"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {(history?.history ?? []).length === 0 && (
              <p className="text-center text-gray-400 py-8 text-sm">履歴なし</p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
