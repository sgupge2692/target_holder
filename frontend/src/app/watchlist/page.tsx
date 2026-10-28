"use client";
import { useState } from "react";
import Link from "next/link";
import useSWR, { mutate } from "swr";
import { getWatchlist, removeFromWatchlist, type WatchlistItem } from "@/lib/api";
import { SignalBadge } from "@/components/SignalBadge";
import { useAuth } from "@/hooks/useAuth";
import { Bookmark, Trash2, TrendingUp, Search, Star } from "lucide-react";

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
      <td className="px-4 py-3">
        <Link
          href={`/stocks/${item.code}`}
          className="font-medium hover:text-brand-600 dark:hover:text-brand-400 transition-colors"
        >
          {item.company_name ?? item.code}
        </Link>
        <div className="text-xs text-gray-400 mt-0.5">{item.code}</div>
      </td>
      <td className="px-4 py-3 text-right font-mono text-sm">
        {item.latest_price != null
          ? `¥${item.latest_price.toLocaleString()}`
          : <span className="text-gray-300">—</span>}
      </td>
      <td className="px-4 py-3 text-center">
        {item.signal
          ? <SignalBadge signal={item.signal} />
          : <span className="text-gray-300 text-xs">なし</span>}
      </td>
      <td className="px-4 py-3 text-right font-mono text-sm">
        {item.up_probability != null
          ? `${(item.up_probability * 100).toFixed(1)}%`
          : <span className="text-gray-300">—</span>}
      </td>
      <td className="px-4 py-3 text-xs text-gray-400 text-center">
        {item.signal_date ?? "—"}
      </td>
      <td className="px-4 py-3 text-center">
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

  return (
    <div className="space-y-6">
      {/* ヘッダー */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Bookmark className="w-6 h-6 text-brand-500" />
            ウォッチリスト
          </h1>
          <p className="text-sm text-gray-500 dark:text-slate-400 mt-1">
            {items.length} / {maxItems} 件登録中
            {data?.plan === "free" && (
              <Link href="/billing" className="ml-2 text-brand-600 hover:underline text-xs">
                Proで300件まで →
              </Link>
            )}
          </p>
        </div>
        <Link
          href="/"
          className="inline-flex items-center gap-2 text-sm text-gray-500 hover:text-brand-600 dark:hover:text-brand-400 transition-colors"
        >
          <Search size={14} />
          銘柄を探す
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
        <div className="overflow-x-auto rounded-xl border border-gray-200 dark:border-slate-700">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 dark:bg-slate-800 text-xs text-gray-500 dark:text-slate-400 uppercase tracking-wide">
              <tr>
                <th className="px-4 py-3 text-left">銘柄</th>
                <th className="px-4 py-3 text-right">最新株価</th>
                <th className="px-4 py-3 text-center">最新シグナル</th>
                <th className="px-4 py-3 text-right">確率</th>
                <th className="px-4 py-3 text-center">シグナル日</th>
                <th className="px-4 py-3 w-10" />
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 dark:divide-slate-700">
              {items.map((item) => (
                <WatchlistRow key={item.code} item={item} onRemove={handleRemove} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
