"use client";
import { useParams } from "next/navigation";
import { useState, useEffect } from "react";
import useSWR, { mutate } from "swr";
import Link from "next/link";
import {
  getStock, getQuotes, getSignalHistory, getSummary, generateSummary, regenerateSummary,
  getWatchlistStatus, addToWatchlist, removeFromWatchlist, type Summary,
} from "@/lib/api";
import { SignalBadge } from "@/components/SignalBadge";
import { SummaryCard } from "@/components/SummaryCard";
import { StockChart } from "@/components/StockChart";
import { useAuth } from "@/hooks/useAuth";
import { ArrowLeft, Lock, Star, TrendingUp, TrendingDown, Crown } from "lucide-react";

/** 確率バー（ミニ版） */
function MiniProbBar({ prob }: { prob: number }) {
  const pct = Math.round(prob * 100);
  const color = prob >= 0.8 ? "bg-teal-500" : prob >= 0.7 ? "bg-teal-400" : prob >= 0.6 ? "bg-amber-400" : "bg-slate-500";
  return (
    <div className="flex items-center gap-1.5 justify-end">
      <div className="prob-bar-track w-12">
        <div className={`prob-bar-fill ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className={`font-mono text-xs font-semibold w-[3rem] text-right ${prob >= 0.75 ? "text-teal-400" : "text-slate-400"}`}>
        {pct.toFixed(1)}%
      </span>
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

  const sortedQuotes = (quotes?.quotes ?? []).slice().sort((a, b) => a.Date < b.Date ? -1 : 1);

  // 直近2日の価格変化
  const latestPrice  = sortedQuotes.length > 0 ? Number(sortedQuotes.at(-1)!.AdjustmentClose) : null;
  const prevPrice    = sortedQuotes.length > 1 ? Number(sortedQuotes.at(-2)!.AdjustmentClose) : null;
  const priceChange  = latestPrice != null && prevPrice != null ? latestPrice - prevPrice : null;
  const changePct    = priceChange != null && prevPrice ? (priceChange / prevPrice) * 100 : null;
  const isUp         = priceChange != null && priceChange >= 0;

  // シグナル履歴をチャートマーカー用に変換
  const signalMarkers = (history?.history ?? [])
    .filter(h => h.signal === "UP" || h.signal === "DOWN")
    .map(h => ({
      date:   h.Date,
      signal: h.signal as "UP" | "DOWN",
      prob:   h.up_probability,
    }));

  return (
    <div className="space-y-5">
      {/* ヘッダー */}
      <div className="flex items-start gap-3">
        <Link href="/" className="mt-1 p-1.5 rounded hover:bg-slate-800/60 transition-colors shrink-0">
          <ArrowLeft size={18} />
        </Link>
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2 flex-wrap">
            <div>
              <h1 className="text-xl font-black tracking-tight leading-tight">{stock?.company_name ?? code}</h1>
              <p className="text-sm text-slate-500 mt-0.5 font-mono">{code} · {stock?.market_code}</p>
            </div>

            {/* 株価表示 */}
            {latestPrice && (
              <div className="text-right shrink-0">
                <div className="text-xl font-black font-mono tabular-nums text-white">
                  ¥{latestPrice.toLocaleString()}
                </div>
                {changePct != null && (
                  <div className={`flex items-center justify-end gap-0.5 text-xs font-semibold ${isUp ? "text-teal-400" : "text-red-400"}`}>
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
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-black tracking-wide border transition-all disabled:opacity-50 ${
                  watched
                    ? "bg-amber-900/30 text-amber-300 border-amber-700/40 hover:bg-amber-900/50"
                    : "bg-slate-800/60 text-slate-400 border-slate-700/60 hover:bg-slate-800"
                }`}
              >
                <Star size={12} className={watched ? "fill-amber-400 text-amber-400" : ""} />
                {watched ? "ウォッチ中" : "ウォッチ"}
              </button>
            )}
            {user && quotes?.plan === "free" && (
              <Link href="/billing" className="flex items-center gap-1 text-xs bg-teal-900/20 text-teal-400 border border-teal-700/40 px-3 py-1.5 rounded hover:bg-teal-900/40 transition-colors font-black tracking-wide">
                <Crown size={11} />
                Pro で全期間表示
              </Link>
            )}
          </div>
        </div>
      </div>

      {/* チャート */}
      <div className="bg-[#0c1424] rounded border border-slate-700/60 p-5">
        <p className="text-[10px] font-black tracking-widest uppercase text-slate-400 mb-4">株価チャート</p>
        {!user ? (
          <div className="flex items-center justify-center h-40 gap-2 text-slate-500">
            <Lock size={16} /><span className="text-sm">ログインで閲覧可能</span>
          </div>
        ) : sortedQuotes.length > 0 ? (
          <StockChart
            quotes={sortedQuotes}
            signals={signalMarkers}
            isPro={user.plan === "pro"}
          />
        ) : (
          <p className="text-center text-slate-500 py-12 text-sm">データなし</p>
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
      <div className="bg-[#0c1424] rounded border border-slate-700/60 p-5">
        <div className="flex items-center justify-between mb-4">
          <p className="text-[10px] font-black tracking-widest uppercase text-slate-400">シグナル履歴</p>
          {history?.plan === "free" && (
            <span className="text-[10px] font-black tracking-widest uppercase text-amber-500 bg-amber-900/20 px-2 py-0.5 rounded border border-amber-700/40">
              直近5件
            </span>
          )}
        </div>
        {!user ? (
          <div className="flex items-center justify-center h-24 gap-2 text-slate-500">
            <Lock size={16} /><span className="text-sm">ログインで閲覧可能</span>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-[10px] text-slate-500 uppercase tracking-widest font-black border-b border-slate-700/40">
                <tr>
                  <th className="pb-2.5 text-left">日付</th>
                  <th className="pb-2.5 text-center">シグナル</th>
                  <th className="pb-2.5 text-right">確率</th>
                  <th className="pb-2.5 text-right">実績</th>
                  <th className="pb-2.5 text-center">的中</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-700/30">
                {(history?.history ?? []).map((h, i) => (
                  <tr key={i} className="hover:bg-slate-800/30 transition-colors">
                    <td className="py-2.5 text-slate-500 tabular-nums text-xs font-mono">{h.Date}</td>
                    <td className="py-2.5 text-center"><SignalBadge signal={h.signal} /></td>
                    <td className="py-2.5">
                      <MiniProbBar prob={h.up_probability} />
                    </td>
                    <td className="py-2.5 text-right font-mono text-xs">
                      {h.actual_return != null
                        ? <span className={`font-semibold ${h.actual_return >= 0 ? "text-teal-400" : "text-red-400"}`}>
                            {h.actual_return >= 0 ? "+" : ""}{(h.actual_return * 100).toFixed(2)}%
                          </span>
                        : <span className="text-slate-700">—</span>}
                    </td>
                    <td className="py-2.5 text-center text-base">
                      {h.is_correct == null
                        ? <span className="text-slate-700 text-xs">—</span>
                        : h.is_correct ? "✅" : "❌"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {(history?.history ?? []).length === 0 && (
              <p className="text-center text-slate-500 py-8 text-sm">履歴なし</p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
