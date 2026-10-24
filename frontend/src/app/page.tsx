"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import useSWR from "swr";
import { getLatestSignals, getAccuracy, type Signal, type AccuracyRow } from "@/lib/api";
import { SignalBadge } from "@/components/SignalBadge";
import { StockSearch } from "@/components/StockSearch";
import { AccuracyChart } from "@/components/AccuracyChart";
import { useAuth } from "@/hooks/useAuth";
import { Lock } from "lucide-react";

type Tab = "ALL" | "UP" | "DOWN";

export default function HomePage() {
  const { user } = useAuth();
  const [tab, setTab] = useState<Tab>("ALL");

  const { data: signalData, isLoading: sigLoading } = useSWR(
    user ? ["signals", tab] : null,
    () => getLatestSignals(tab === "ALL" ? undefined : tab),
    { refreshInterval: 60_000 }
  );

  const { data: accData } = useSWR("accuracy", getAccuracy, { revalidateOnFocus: false });

  // 月別精度データを整形（/api/signals/accuracy はシグナル別集計のみなのでフロントでモック）
  const accuracyRows: AccuracyRow[] = accData?.accuracy ?? [];
  const upRow   = accuracyRows.find(r => r.signal === "UP");
  const downRow = accuracyRows.find(r => r.signal === "DOWN");

  return (
    <div className="space-y-8">
      {/* ヘッダー */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">AIシグナル一覧</h1>
          <p className="text-sm text-gray-500 dark:text-slate-400 mt-1">
            LightGBMによる翌日騰落予測シグナル（60%以上の確度のみ表示）
          </p>
        </div>
        <StockSearch />
      </div>

      {/* 精度サマリー */}
      {accuracyRows.length > 0 && (
        <div className="grid grid-cols-2 gap-4">
          {[upRow, downRow].map((row, i) => row && (
            <div key={i} className="rounded-xl border border-gray-200 dark:border-slate-700 bg-white dark:bg-slate-800 p-4">
              <div className="flex items-center gap-2 mb-2">
                <SignalBadge signal={row.signal as "UP" | "DOWN"} />
                <span className="text-xs text-gray-500 dark:text-slate-400">n={row.total}</span>
              </div>
              <p className="text-3xl font-bold">{row.accuracy_pct}%</p>
              <p className="text-xs text-gray-500 dark:text-slate-400 mt-1">
                平均リターン {(row.avg_return_pct ?? 0) > 0 ? "+" : ""}{row.avg_return_pct}%
              </p>
            </div>
          ))}
        </div>
      )}

      {/* シグナルテーブル */}
      {!user ? (
        <div className="rounded-xl border border-dashed border-gray-300 dark:border-slate-600 p-12 text-center">
          <Lock size={32} className="mx-auto mb-3 text-gray-400" />
          <p className="font-medium mb-2">ログインするとシグナルを閲覧できます</p>
          <Link
            href="/auth"
            className="inline-block mt-2 bg-brand-600 hover:bg-brand-700 text-white px-5 py-2 rounded-lg text-sm font-medium transition-colors"
          >
            無料で始める
          </Link>
        </div>
      ) : (
        <>
          {/* タブ */}
          <div className="flex gap-1 bg-gray-100 dark:bg-slate-800 p-1 rounded-lg w-fit">
            {(["ALL", "UP", "DOWN"] as Tab[]).map(t => (
              <button
                key={t}
                onClick={() => setTab(t)}
                className={`px-4 py-1.5 rounded-md text-sm font-medium transition-colors ${
                  tab === t
                    ? "bg-white dark:bg-slate-700 shadow-sm"
                    : "text-gray-500 hover:text-gray-700 dark:text-slate-400"
                }`}
              >
                {t}
              </button>
            ))}
          </div>

          {sigLoading ? (
            <div className="text-center py-12 text-gray-400">読み込み中...</div>
          ) : (
            <>
              {user.plan === "free" && (
                <div className="flex items-center justify-between rounded-lg bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-700 px-4 py-3 text-sm">
                  <span className="text-amber-800 dark:text-amber-300">
                    無料プランは上位 10 件まで。Pro プランで全件表示。
                  </span>
                  <Link
                    href="/billing"
                    className="ml-4 shrink-0 bg-amber-500 hover:bg-amber-600 text-white px-3 py-1 rounded-md font-medium transition-colors"
                  >
                    アップグレード
                  </Link>
                </div>
              )}

              <div className="overflow-x-auto rounded-xl border border-gray-200 dark:border-slate-700">
                <table className="w-full text-sm">
                  <thead className="bg-gray-50 dark:bg-slate-800 text-xs text-gray-500 dark:text-slate-400 uppercase tracking-wide">
                    <tr>
                      <th className="px-4 py-3 text-left">銘柄</th>
                      <th className="px-4 py-3 text-left">シグナル日</th>
                      <th className="px-4 py-3 text-center">シグナル</th>
                      <th className="px-4 py-3 text-right">確率</th>
                      <th className="px-4 py-3 text-right">実績リターン</th>
                      <th className="px-4 py-3 text-center">的中</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100 dark:divide-slate-700">
                    {(signalData?.signals ?? []).map((s: Signal) => (
                      <tr key={`${s.Code}-${s.Date}`} className="hover:bg-gray-50 dark:hover:bg-slate-800/60 transition-colors">
                        <td className="px-4 py-3">
                          <Link href={`/stocks/${s.Code}`} className="font-medium hover:text-brand-600 transition-colors">
                            {s.company_name ?? s.Code}
                          </Link>
                          <div className="text-xs text-gray-400">{s.Code}</div>
                        </td>
                        <td className="px-4 py-3 text-gray-500 dark:text-slate-400">{s.Date}</td>
                        <td className="px-4 py-3 text-center"><SignalBadge signal={s.signal} /></td>
                        <td className="px-4 py-3 text-right font-mono">
                          {(s.up_probability * 100).toFixed(1)}%
                        </td>
                        <td className="px-4 py-3 text-right font-mono">
                          {s.actual_return != null
                            ? <span className={s.actual_return >= 0 ? "text-emerald-600" : "text-red-500"}>
                                {s.actual_return >= 0 ? "+" : ""}{(s.actual_return * 100).toFixed(2)}%
                              </span>
                            : <span className="text-gray-300">—</span>
                          }
                        </td>
                        <td className="px-4 py-3 text-center">
                          {s.is_correct == null ? "—"
                            : s.is_correct ? "✅" : "❌"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {(signalData?.signals ?? []).length === 0 && (
                  <p className="text-center py-8 text-gray-400">シグナルなし</p>
                )}
              </div>
            </>
          )}
        </>
      )}
    </div>
  );
}
