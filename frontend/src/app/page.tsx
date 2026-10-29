"use client";
import { useState } from "react";
import Link from "next/link";
import useSWR from "swr";
import { getLatestSignals, getAccuracy, downloadSignalsCsv, type Signal, type AccuracyRow } from "@/lib/api";
import { SignalBadge } from "@/components/SignalBadge";
import { StockSearch } from "@/components/StockSearch";
import { LandingPage } from "@/components/LandingPage";
import { SignalRowSkeleton, SignalCardSkeleton, StatCardSkeleton } from "@/components/Skeleton";
import { useAuth } from "@/hooks/useAuth";
import { useToast } from "@/components/Toast";
import {
  ChevronDown, ChevronRight, Download, Lightbulb,
  SlidersHorizontal, TrendingUp, TrendingDown,
} from "lucide-react";

type Tab = "ALL" | "UP" | "DOWN";

/** 確率を色クラスに変換 */
function probColor(prob: number): string {
  if (prob >= 0.8)  return "bg-brand-500";
  if (prob >= 0.7)  return "bg-emerald-400";
  if (prob >= 0.6)  return "bg-amber-400";
  return "bg-gray-400";
}

/** 確率バー（テーブル行 / カード共用） */
function ProbBar({ prob }: { prob: number }) {
  const pct = Math.round(prob * 100);
  return (
    <div className="flex items-center gap-2">
      <div className="prob-bar-track flex-1 min-w-[60px]">
        <div
          className={`prob-bar-fill ${probColor(prob)}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className={`font-mono font-semibold text-xs w-[3.4rem] text-right ${prob >= 0.75 ? "text-brand-600 dark:text-brand-400" : "text-gray-600 dark:text-slate-300"}`}>
        {pct.toFixed(1)}%
      </span>
    </div>
  );
}

function ProbabilityFilter({ value, onChange }: { value: number; onChange: (v: number) => void }) {
  return (
    <div className="flex items-center gap-2.5">
      <SlidersHorizontal size={14} className="text-gray-400 shrink-0" />
      <span className="text-xs text-gray-500 dark:text-slate-400 whitespace-nowrap">確度 ≥</span>
      <input
        type="range" min={50} max={95} step={5} value={value}
        onChange={e => onChange(Number(e.target.value))}
        className="w-24 accent-brand-600"
      />
      <span className="text-xs font-mono font-bold w-10 text-brand-600 dark:text-brand-400">{value}%</span>
    </div>
  );
}

// ── 精度サマリーカード ────────────────────────────────────────────────────
function AccuracyCard({ row }: { row: AccuracyRow }) {
  const isUp = row.signal === "UP";
  return (
    <div className={`relative overflow-hidden rounded-2xl border p-5 ${
      isUp
        ? "border-emerald-200 dark:border-emerald-800 bg-gradient-to-br from-emerald-50 to-white dark:from-emerald-950/40 dark:to-slate-800"
        : "border-red-200 dark:border-red-800 bg-gradient-to-br from-red-50 to-white dark:from-red-950/40 dark:to-slate-800"
    }`}>
      <div className={`absolute -right-4 -top-4 w-20 h-20 rounded-full opacity-10 ${isUp ? "bg-emerald-400" : "bg-red-400"}`} />
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-1.5 mb-2">
            {isUp
              ? <TrendingUp size={15} className="text-emerald-500" />
              : <TrendingDown size={15} className="text-red-400" />
            }
            <span className="text-xs font-semibold text-gray-500 dark:text-slate-400 uppercase tracking-wide">
              {isUp ? "上昇" : "下落"}予測
            </span>
          </div>
          <p className={`text-4xl font-black tabular-nums ${isUp ? "text-emerald-600" : "text-red-500"}`}>
            {row.accuracy_pct}%
          </p>
          <p className="text-xs text-gray-400 dark:text-slate-500 mt-1">的中率 (n={row.total})</p>
        </div>
        <div className="text-right">
          <p className={`text-sm font-bold ${(row.avg_return_pct ?? 0) >= 0 ? "text-emerald-600" : "text-red-500"}`}>
            {(row.avg_return_pct ?? 0) >= 0 ? "+" : ""}{row.avg_return_pct}%
          </p>
          <p className="text-xs text-gray-400 dark:text-slate-500 mt-0.5">平均リターン</p>
        </div>
      </div>
    </div>
  );
}

// ── シグナル行（デスクトップ テーブル用）────────────────────────────────
function SignalRow({ s }: { s: Signal }) {
  const [open, setOpen] = useState(false);
  const keyFactors: string[] = (() => {
    try { return s.key_factors ? JSON.parse(s.key_factors) : []; } catch { return []; }
  })();

  return (
    <>
      <tr className="group hover:bg-brand-50/40 dark:hover:bg-brand-900/10 transition-colors">
        <td className="px-4 py-3.5">
          <Link href={`/stocks/${s.Code}`} className="font-semibold hover:text-brand-600 dark:hover:text-brand-400 transition-colors">
            {s.company_name ?? s.Code}
          </Link>
          <div className="text-xs text-gray-400 mt-0.5">{s.Code}</div>
        </td>
        <td className="px-4 py-3.5 text-sm text-gray-500 dark:text-slate-400">{s.Date}</td>
        <td className="px-4 py-3.5 text-center"><SignalBadge signal={s.signal} /></td>
        <td className="px-4 py-3.5 w-40">
          <ProbBar prob={s.up_probability} />
        </td>
        <td className="px-4 py-3.5 text-right font-mono text-sm">
          {s.actual_return != null
            ? <span className={s.actual_return >= 0 ? "text-emerald-600 font-semibold" : "text-red-500 font-semibold"}>
                {s.actual_return >= 0 ? "+" : ""}{(s.actual_return * 100).toFixed(2)}%
              </span>
            : <span className="text-gray-300 dark:text-slate-600">—</span>
          }
        </td>
        <td className="px-4 py-3.5 text-center text-base">
          {s.is_correct == null ? <span className="text-gray-300 dark:text-slate-600 text-sm">—</span> : s.is_correct ? "✅" : "❌"}
        </td>
        <td className="px-4 py-3.5 text-center">
          {s.explanation && (
            <button
              onClick={() => setOpen(v => !v)}
              className="inline-flex items-center gap-1 text-xs text-brand-600 dark:text-brand-400 hover:underline font-medium"
            >
              {open ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
              AI
            </button>
          )}
        </td>
      </tr>
      {open && s.explanation && (
        <tr className="bg-brand-50/60 dark:bg-brand-900/20 border-l-2 border-brand-400">
          <td colSpan={7} className="px-6 py-3">
            <div className="flex items-start gap-2.5 text-sm">
              <Lightbulb size={15} className="mt-0.5 shrink-0 text-brand-500" />
              <div>
                <p className="text-brand-900 dark:text-brand-200 font-medium leading-relaxed">{s.explanation}</p>
                {keyFactors.length > 0 && (
                  <div className="flex flex-wrap gap-1.5 mt-2">
                    {keyFactors.map((f, i) => (
                      <span key={i} className="px-2 py-0.5 rounded-full bg-brand-100 dark:bg-brand-800 text-xs text-brand-700 dark:text-brand-300">
                        {f}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

// ── シグナルカード（モバイル用）──────────────────────────────────────────
function SignalCard({ s }: { s: Signal }) {
  const [open, setOpen] = useState(false);
  const keyFactors: string[] = (() => {
    try { return s.key_factors ? JSON.parse(s.key_factors) : []; } catch { return []; }
  })();

  return (
    <div className="signal-card rounded-xl border border-gray-200 dark:border-slate-700 bg-white dark:bg-slate-800 p-4">
      <div className="flex items-start justify-between mb-2">
        <div>
          <Link href={`/stocks/${s.Code}`} className="font-semibold text-gray-900 dark:text-white hover:text-brand-600 transition-colors">
            {s.company_name ?? s.Code}
          </Link>
          <div className="text-xs text-gray-400 mt-0.5">{s.Code} · {s.Date}</div>
        </div>
        <SignalBadge signal={s.signal} />
      </div>

      {/* 確率バー */}
      <div className="my-2.5">
        <div className="flex items-center justify-between text-xs text-gray-500 dark:text-slate-400 mb-1">
          <span>上昇確率</span>
        </div>
        <ProbBar prob={s.up_probability} />
      </div>

      {s.actual_return != null && (
        <div className="flex items-center justify-between text-sm mt-2 pt-2 border-t border-gray-100 dark:border-slate-700">
          <span className="text-xs text-gray-500 dark:text-slate-400">実績リターン</span>
          <div className="flex items-center gap-2">
            <span className={`font-mono font-bold text-sm ${s.actual_return >= 0 ? "text-emerald-600" : "text-red-500"}`}>
              {s.actual_return >= 0 ? "+" : ""}{(s.actual_return * 100).toFixed(2)}%
            </span>
            {s.is_correct != null && (
              <span className="text-base">{s.is_correct ? "✅" : "❌"}</span>
            )}
          </div>
        </div>
      )}

      {s.explanation && (
        <>
          <button
            onClick={() => setOpen(v => !v)}
            className="mt-3 w-full flex items-center justify-center gap-1.5 text-xs text-brand-600 dark:text-brand-400 border border-brand-200 dark:border-brand-700 rounded-lg py-1.5 hover:bg-brand-50 dark:hover:bg-brand-900/20 transition-colors font-medium"
          >
            <Lightbulb size={12} />
            {open ? "AI説明を閉じる" : "AI説明を見る"}
          </button>
          {open && (
            <div className="mt-2 p-3 rounded-lg bg-brand-50 dark:bg-brand-900/20 text-xs text-brand-900 dark:text-brand-200 leading-relaxed">
              <p>{s.explanation}</p>
              {keyFactors.length > 0 && (
                <div className="flex flex-wrap gap-1 mt-2">
                  {keyFactors.map((f, i) => (
                    <span key={i} className="px-1.5 py-0.5 rounded-full bg-brand-100 dark:bg-brand-800 text-brand-700 dark:text-brand-300">
                      {f}
                    </span>
                  ))}
                </div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}

// ── メインページ ──────────────────────────────────────────────────────────
export default function HomePage() {
  const { user, loading } = useAuth();
  const { toast } = useToast();
  const [tab, setTab] = useState<Tab>("ALL");
  const [minProb, setMinProb] = useState(60);
  const [csvLoading, setCsvLoading] = useState(false);

  const handleCsvDownload = async () => {
    setCsvLoading(true);
    try {
      await downloadSignalsCsv(tab === "ALL" ? undefined : tab, 30);
      toast("CSVをダウンロードしました", "success");
    } catch (e: unknown) {
      toast(e instanceof Error ? e.message : "CSVダウンロードに失敗しました", "error");
    } finally {
      setCsvLoading(false);
    }
  };

  if (!loading && !user) return <LandingPage />;

  const { data: signalData, isLoading: sigLoading } = useSWR(
    user ? ["signals", tab] : null,
    () => getLatestSignals(tab === "ALL" ? undefined : tab),
    { refreshInterval: 60_000 },
  );

  const { data: accData, isLoading: accLoading } = useSWR("accuracy", getAccuracy, {
    revalidateOnFocus: false,
  });

  const accuracyRows: AccuracyRow[] = accData?.accuracy ?? [];
  const upRow   = accuracyRows.find(r => r.signal === "UP");
  const downRow = accuracyRows.find(r => r.signal === "DOWN");

  const filtered = (signalData?.signals ?? []).filter(
    (s: Signal) => s.up_probability * 100 >= minProb,
  );

  // 最新シグナルの日付（ライブドット用）
  const latestDate = filtered[0]?.Date ?? null;

  return (
    <div className="space-y-6">
      {/* ── ヘッダー ── */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <div className="flex items-center gap-2.5 mb-0.5">
            <h1 className="text-2xl font-bold tracking-tight">AIシグナル一覧</h1>
            {/* ライブドット + 日付バッジ */}
            {!sigLoading && filtered.length > 0 && (
              <div className="flex items-center gap-1.5">
                <span className="live-dot" />
                {latestDate && (
                  <span className="text-xs text-gray-400 dark:text-slate-500 font-mono">{latestDate}</span>
                )}
              </div>
            )}
            {/* 件数バッジ */}
            {!sigLoading && filtered.length > 0 && (
              <span className="px-2 py-0.5 rounded-full bg-brand-100 dark:bg-brand-900/40 text-brand-700 dark:text-brand-300 text-xs font-bold">
                {filtered.length}件
              </span>
            )}
          </div>
          <p className="text-sm text-gray-500 dark:text-slate-400">
            LightGBM × XGBoostによる翌日騰落予測
          </p>
        </div>
        <StockSearch />
      </div>

      {/* ── 精度カード ── */}
      <div className="grid grid-cols-2 gap-3">
        {accLoading
          ? [0, 1].map(i => <StatCardSkeleton key={i} />)
          : [upRow, downRow].map((row, i) => row
              ? <AccuracyCard key={i} row={row} />
              : <StatCardSkeleton key={i} />
            )
        }
      </div>

      {/* ── Proアップグレードバナー ── */}
      {user?.plan === "free" && (
        <div className="flex items-center justify-between rounded-xl bg-gradient-to-r from-amber-50 to-orange-50 dark:from-amber-950/30 dark:to-orange-950/30 border border-amber-200 dark:border-amber-800 px-4 py-3 text-sm">
          <div>
            <p className="font-semibold text-amber-800 dark:text-amber-300">無料プランは上位 10 件まで</p>
            <p className="text-xs text-amber-600 dark:text-amber-400 mt-0.5">Pro プランで全件表示・CSV・メールアラート</p>
          </div>
          <Link
            href="/billing"
            className="shrink-0 ml-4 bg-amber-500 hover:bg-amber-600 text-white px-4 py-1.5 rounded-lg font-semibold text-xs transition-colors"
          >
            アップグレード →
          </Link>
        </div>
      )}

      {/* ── タブ + フィルター ── */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex gap-1 bg-gray-100 dark:bg-slate-800 p-1 rounded-lg">
          {(["ALL", "UP", "DOWN"] as Tab[]).map(t => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`px-4 py-1.5 rounded-md text-sm font-medium transition-all ${
                tab === t
                  ? "bg-white dark:bg-slate-700 shadow-sm text-gray-900 dark:text-white"
                  : "text-gray-500 hover:text-gray-700 dark:text-slate-400"
              }`}
            >
              {t}
            </button>
          ))}
        </div>
        <ProbabilityFilter value={minProb} onChange={setMinProb} />
        {user?.plan === "pro" && (
          <button
            onClick={handleCsvDownload}
            disabled={csvLoading}
            className="ml-auto flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-brand-50 dark:bg-brand-900/20 text-brand-700 dark:text-brand-400 border border-brand-200 dark:border-brand-700 hover:bg-brand-100 dark:hover:bg-brand-900/30 transition-colors disabled:opacity-50"
          >
            <Download size={13} />
            {csvLoading ? "処理中..." : "CSV"}
          </button>
        )}
      </div>

      {/* ── シグナル一覧 ── */}
      {sigLoading ? (
        <>
          <div className="md:hidden space-y-3">
            {[...Array(5)].map((_, i) => <SignalCardSkeleton key={i} />)}
          </div>
          <div className="hidden md:block overflow-x-auto rounded-xl border border-gray-200 dark:border-slate-700">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 dark:bg-slate-800 text-xs text-gray-500 dark:text-slate-400 uppercase tracking-wide">
                <tr>
                  {["銘柄", "日付", "シグナル", "確率", "実績", "的中", "AI"].map(h => (
                    <th key={h} className="px-4 py-3 text-left">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 dark:divide-slate-700/60">
                {[...Array(8)].map((_, i) => <SignalRowSkeleton key={i} />)}
              </tbody>
            </table>
          </div>
        </>
      ) : filtered.length === 0 ? (
        <div className="text-center py-16 text-gray-400">
          <p className="text-lg">シグナルなし</p>
          <p className="text-sm mt-1">
            {(signalData?.signals ?? []).length > 0
              ? `確度 ${minProb}% 以上のシグナルがありません（スライダーを下げてみてください）`
              : "本日のシグナルはまだ生成されていません"
            }
          </p>
        </div>
      ) : (
        <>
          {/* モバイル: カードレイアウト */}
          <div className="md:hidden space-y-3">
            {filtered.map((s: Signal) => (
              <SignalCard key={`${s.Code}-${s.Date}`} s={s} />
            ))}
          </div>

          {/* デスクトップ: テーブルレイアウト */}
          <div className="hidden md:block overflow-x-auto rounded-xl border border-gray-200 dark:border-slate-700">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 dark:bg-slate-800/80 text-xs text-gray-500 dark:text-slate-400 uppercase tracking-wide">
                <tr>
                  <th className="px-4 py-3 text-left">銘柄</th>
                  <th className="px-4 py-3 text-left">日付</th>
                  <th className="px-4 py-3 text-center">シグナル</th>
                  <th className="px-4 py-3 text-left">確率</th>
                  <th className="px-4 py-3 text-right">実績</th>
                  <th className="px-4 py-3 text-center">的中</th>
                  <th className="px-4 py-3 text-center">AI</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 dark:divide-slate-700/60 bg-white dark:bg-slate-800/40">
                {filtered.map((s: Signal) => (
                  <SignalRow key={`${s.Code}-${s.Date}`} s={s} />
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
