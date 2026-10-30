"use client";
import { useState } from "react";
import Link from "next/link";
import useSWR, { mutate } from "swr";
import { getWatchlist, removeFromWatchlist, type WatchlistItem } from "@/lib/api";
import { SignalBadge } from "@/components/SignalBadge";
import { useAuth } from "@/hooks/useAuth";
import { Bookmark, Trash2, TrendingUp, Search, Star, ArrowUpRight } from "lucide-react";

/** 確率バー（ミニ版） */
function MiniProbBar({ prob }: { prob: number }) {
  const pct = Math.round(prob * 100);
  const color = prob >= 0.8 ? "bg-brand-500" : prob >= 0.7 ? "bg-emerald-400" : prob >= 0.6 ? "bg-amber-400" : "bg-gray-400";
  return (
    <div className="flex items-center gap-1.5 justify-end">
      <div className="prob-bar-track w-14">
        <div className={`prob-bar-fill ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className={`font-mono text-xs font-semibold w-[3rem] text-right ${prob >= 0.75 ? "text-brand-600 dark:text-brand-400" : "text-gray-600 dark:text-slate-300"}`}>
        {pct.toFixed(1)}%
      </span>
    </div>
  );
}

function WatchlistRow({ item, onRemove }: { item: WatchlistItem; onRemove: () => void }) {
  const [removing, setRemoving] = useState(false);

  const handleRemove = async () => {
    setRemoving(true);
    try {
      await removeFromWatchlist(item.code);
      onRemove();
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : "削除に失敗しました");
      setRemoving(false);
    }
  };

  return (
    <tr className="hover:bg-gray-50 dark:hover:bg-slate-800/60 transition-colors group">
      <td className="px-4 py-3.5">
        <Link
          href={`/stocks/${item.code}`}
          className="font-semibold hover:text-brand-600 dark:hover:text-brand-400 transition-colors flex items-center gap-1 group/link"
        >
          {item.company_name ?? item.code}
          <ArrowUpRight size={12} className="opacity-0 group-hover/link:opacity-100 transition-opacity" />
        </Link>
        <div className="text-xs text-gray-400 mt-0.5">{item.code}</div>
      </td>
      <td className="px-4 py-3.5 text-right font-mono text-sm">
        {item.latest_price != null
          ? <span className="font-semibold">¥{item.latest_price.toLocaleString()}</span>
          : <span className="text-gray-300 dark:text-slate-600">—</span>}
      </td>
      <td className="px-4 py-3.5 text-center">
        {item.signal
          ? <SignalBadge signal={item.signal} />
          : <span className="text-gray-300 dark:text-slate-600 text-xs">なし</span>}
      </td>
      <td className="px-4 py-3.5">
        {item.up_probability != null
          ? <MiniProbBar prob={item.up_probability} />
          : <span className="text-gray-300 dark:text-slate-600 text-xs flex justify-end">—</span>}
      </td>
      <td className="px-4 py-3.5 text-xs text-gray-400 text-center tabular-nums">
        {item.signal_date ?? "—"}
      </td>
      <td className="px-4 py-3.5 text-center">
        <button
          onClick={handleRemove}
          disabled={removing}
          className="opacity-0 group-hover:opacity-100 p-1.5 rounded-md text-gray-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 transition-all disabled:opacity-30"
          title="ウォッチリストから削除"
        >
          <Trash2 size={14} />
        </button>
      </td>
    </tr>
  );
}

/** モバイル用カード */
function WatchlistCard({ item, onRemove }: { item: WatchlistItem; onRemove: () => void }) {
  const [removing, setRemoving] = useState(false);

  const handleRemove = async () => {
    setRemoving(true);
    try {
      await removeFromWatchlist(item.code);
      onRemove();
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : "削除に失敗しました");
      setRemoving(false);
    }
  };

  return (
    <div className="signal-card rounded-xl border border-gray-200 dark:border-slate-700 bg-white dark:bg-slate-800 p-4">
      <div className="flex items-start justify-between mb-2.5">
        <Link href={`/stocks/${item.code}`} className="font-semibold hover:text-brand-600 transition-colors">
          {item.company_name ?? item.code}
          <div className="text-xs text-gray-400 font-normal mt-0.5">{item.code}</div>
        </Link>
        <div className="flex items-center gap-2">
          {item.signal && <SignalBadge signal={item.signal} />}
          <button
            onClick={handleRemove}
            disabled={removing}
            className="p-1.5 rounded-md text-gray-300 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors disabled:opacity-30"
          >
            <Trash2 size={14} />
          </button>
        </div>
      </div>

      <div className="flex items-center justify-between gap-3">
        <div>
          <div className="text-xs text-gray-500 dark:text-slate-400 mb-0.5">最新株価</div>
          <div className="font-mono font-semibold text-sm">
            {item.latest_price != null ? `¥${item.latest_price.toLocaleString()}` : "—"}
          </div>
        </div>
        {item.up_probability != null && (
          <div className="flex-1 max-w-[140px]">
            <div className="text-xs text-gray-500 dark:text-slate-400 mb-1 text-right">上昇確率</div>
            <MiniProbBar prob={item.up_probability} />
          </div>
        )}
      </div>

      {item.signal_date && (
        <div className="mt-2 pt-2 border-t border-gray-100 dark:border-slate-700 text-xs text-gray-400 text-right">
          シグナル日: {item.signal_date}
        </div>
      )}
    </div>
  );
}

export default function WatchlistPage() {
  const { user } = useAuth();
  const { data, isLoading } = useSWR(
    user ? "watchlist" : null,
    getWatchlist,
    { revalidateOnFocus: true }
  );

  const handleRemove = () => {
    mutate("watchlist");
  };

  if (!user) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[50vh] gap-4 text-center">
        <Star className="w-12 h-12 text-gray-300" />
        <h1 className="text-xl font-bold">ウォッチリスト</h1>
        <p className="text-gray-500 text-sm">ログインすると銘柄をウォッチリストに登録できます</p>
        <Link
          href="/auth"
          className="bg-brand-600 hover:bg-brand-700 text-white px-6 py-2.5 rounded-lg font-medium text-sm transition-colors"
        >
          ログイン / 新規登録
        </Link>
      </div>
    );
  }

  const items = data?.watchlist ?? [];
  const maxItems = data?.plan === "pro" ? 300 : 30;
  const usagePct = Math.min((items.length / maxItems) * 100, 100);

  return (
    <div className="space-y-6">
      {/* ヘッダー */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-0.5">
            <Bookmark className="w-5 h-5 text-brand-500" />
            <h1 className="text-2xl font-bold">ウォッチリスト</h1>
            {items.length > 0 && (
              <span className="px-2 py-0.5 rounded-full bg-brand-100 dark:bg-brand-900/40 text-brand-700 dark:text-brand-300 text-xs font-bold">
                {items.length}件
              </span>
            )}
          </div>
          {/* 使用量バー */}
          <div className="flex items-center gap-2 mt-1.5">
            <div className="prob-bar-track w-28">
              <div
                className={`prob-bar-fill ${usagePct >= 90 ? "bg-red-400" : usagePct >= 70 ? "bg-amber-400" : "bg-brand-500"}`}
                style={{ width: `${usagePct}%` }}
              />
            </div>
            <span className="text-xs text-gray-500 dark:text-slate-400">
              {items.length} / {maxItems}
              {data?.plan === "free" && (
                <Link href="/billing" className="ml-1.5 text-brand-600 hover:underline">
                  Proで300件 →
                </Link>
              )}
            </span>
          </div>
        </div>
        <Link
          href="/"
          className="inline-flex items-center gap-2 text-sm text-gray-500 hover:text-brand-600 dark:hover:text-brand-400 transition-colors border border-gray-200 dark:border-slate-700 px-3 py-2 rounded-lg hover:border-brand-300"
        >
          <Search size={14} />
          シグナルから銘柄を探す
        </Link>
      </div>

      {isLoading ? (
        <div className="text-center py-16 text-gray-400">読み込み中...</div>
      ) : items.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 gap-4 text-center rounded-2xl border border-dashed border-gray-200 dark:border-slate-700">
          <TrendingUp className="w-12 h-12 text-gray-300" />
          <div>
            <p className="font-medium text-gray-600 dark:text-slate-400">ウォッチリストは空です</p>
            <p className="text-sm text-gray-400 mt-1">
              銘柄詳細ページから ★ ボタンで追加できます
            </p>
          </div>
          <Link
            href="/"
            className="bg-brand-600 hover:bg-brand-700 text-white px-5 py-2 rounded-lg text-sm font-medium transition-colors"
          >
            シグナル一覧を見る
          </Link>
        </div>
      ) : (
        <>
          {/* モバイル: カード */}
          <div className="md:hidden space-y-3">
            {items.map((item) => (
              <WatchlistCard key={item.code} item={item} onRemove={handleRemove} />
            ))}
          </div>

          {/* デスクトップ: テーブル */}
          <div className="hidden md:block overflow-x-auto rounded-xl border border-gray-200 dark:border-slate-700">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 dark:bg-slate-800/80 text-xs text-gray-500 dark:text-slate-400 uppercase tracking-wide">
                <tr>
                  <th className="px-4 py-3 text-left">銘柄</th>
                  <th className="px-4 py-3 text-right">最新株価</th>
                  <th className="px-4 py-3 text-center">シグナル</th>
                  <th className="px-4 py-3 text-right">確率</th>
                  <th className="px-4 py-3 text-center">シグナル日</th>
                  <th className="px-4 py-3 w-10" />
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 dark:divide-slate-700 bg-white dark:bg-slate-800/40">
                {items.map((item) => (
                  <WatchlistRow key={item.code} item={item} onRemove={handleRemove} />
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
