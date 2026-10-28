"use client";
import { useState } from "react";
import Link from "next/link";
import useSWR from "swr";
import { getLatestSignals, getAccuracy, downloadSignalsCsv, type Signal, type AccuracyRow } from "@/lib/api";
import { SignalBadge } from "@/components/SignalBadge";
import { StockSearch } from "@/components/StockSearch";
import { LandingPage } from "@/components/LandingPage";
import { useAuth } from "@/hooks/useAuth";
import { ChevronDown, ChevronRight, Download, Lightbulb, SlidersHorizontal } from "lucide-react";

type Tab = "ALL" | "UP" | "DOWN";

// ── 確度フィルタースライダー ─────────────────────────────────────────────
function ProbabilityFilter({
  value,
  onChange,
}: {
  value: number;
  onChange: (v: number) => void;
}) {
  return (
    <div className="flex items-center gap-3">
      <SlidersHorizontal size={15} className="text-gray-400 shrink-0" />
      <span className="text-xs text-gray-500 dark:text-slate-400 whitespace-nowrap">確度 ≥</span>
      <input
        type="range"
        min={50}
        max={95}
        step={5}
        value={value}
        onChange={e => onChange(Number(e.target.value))}
        className="w-28 accent-indigo-500"
      />
      <span className="text-xs font-mono font-semibold w-10 text-indigo-600 dark:text-indigo-400">
        {value}%
      </span>
    </div>
  );
}

function ExplanationRow({ s }: { s: Signal }) {
  const [open, setOpen] = useState(false);

  const keyFactors: string[] = (() => {
    try { return s.key_factors ? JSON.parse(s.key_factors) : []; }
    catch { return []; }
  })();

  if (!s.explanation) return null;

  return (
    <>
      <tr className="hover:bg-gray-50 dark:hover:bg-slate-800/60 transition-colors">
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
          {s.is_correct == null ? "—" : s.is_correct ? "✅" : "❌"}
        </td>
        <td className="px-4 py-3 text-center">
          <button
            onClick={() => setOpen(v => !v)}
            className="inline-flex items-center gap-1 text-xs text-indigo-600 dark:text-indigo-400 hover:underline"
          >
            {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
            理由
          </button>
        </td>
      </tr>
      {open && (
        <tr className="bg-indigo-50/60 dark:bg-indigo-900/20">
          <td colSpan={7} className="px-6 py-3">
            <div className="flex items-start gap-2 text-sm text-indigo-900 dark:text-indigo-200">
              <Lightbulb size={16} className="mt-0.5 shrink-0 text-indigo-500" />
              <div>
                <p className="font-medium mb-1">{s.explanation}</p>
                {keyFactors.length > 0 && (
                  <ul className="flex flex-wrap gap-2 mt-1">
                    {keyFactors.map((f, i) => (
                      <li key={i} className="px-2 py-0.5 rounded-full bg-indigo-100 dark:bg-indigo-800 text-xs text-indigo-700 dark:text-indigo-300">
                        {f}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

function PlainRow({ s }: { s: Signal }) {
  return (
    <tr className="hover:bg-gray-50 dark:hover:bg-slate-800/60 transition-colors">
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
        {s.is_correct == null ? "—" : s.is_correct ? "✅" : "❌"}
      </td>
      <td className="px-4 py-3" />
    </tr>
  );
}

export default function HomePage() {
  const { user, loading } = useAuth();
  const [tab, setTab] = useState<Tab>("ALL");
  const [minProb, setMinProb] = useState(60);
  const [csvLoading, setCsvLoading] = useState(false);

  const handleCsvDownload = async () => {
    setCsvLoading(true);
    try {
      await downloadSignalsCsv(tab === "ALL" ? undefined : tab, 30);
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : "CSVダウンロードに失敗しました");
    } finally {
      setCsvLoading(false);
    }
  };

  // 未ログイン時はランディングページを表示
  if (!loading && !user) {
    return <LandingPage />;
  }

  const { data: signalData, isLoading: sigLoading } = useSWR(
    user ? ["signals", tab] : null,
    () => getLatestSignals(tab === "ALL" ? undefined : tab),
    { refreshInterval: 60_000 }
  );

  const { data: accData } = useSWR("accuracy", getAccuracy, { revalidateOnFocus: false });

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
      {/* タブ + フィルター */}
      <div className="flex flex-wrap items-center gap-3">
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
      <ProbabilityFilter value={minProb} onChange={setMinProb} />
      {user?.plan === "pro" && (
        <button
          onClick={handleCsvDownload}
          disabled={csvLoading}
          className="ml-auto flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-emerald-50 dark:bg-emerald-900/20 text-emerald-700 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-700 hover:bg-emerald-100 transition-colors disabled:opacity-50"
        >
          <Download size={13} />
          {csvLoading ? "ダウンロード中..." : "CSV"}
        </button>
      )}
      </div>

      {sigLoading ? (
        <div className="text-center py-12 text-gray-400">読み込み中...</div>
      ) : (
        <>
          {user && user.plan === "free" && (
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
                  <th className="px-4 py-3 text-center">AI説明</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 dark:divide-slate-700">
                {(signalData?.signals ?? [])
                  .filter((s: Signal) => s.up_probability * 100 >= minProb)
                  .map((s: Signal) =>
                    s.explanation
                      ? <ExplanationRow key={`${s.Code}-${s.Date}`} s={s} />
                      : <PlainRow key={`${s.Code}-${s.Date}`} s={s} />
                  )}
              </tbody>
            </table>
            {(signalData?.signals ?? []).filter((s: Signal) => s.up_probability * 100 >= minProb).length === 0 && (
              <p className="text-center py-8 text-gray-400">
                {(signalData?.signals ?? []).length > 0
                  ? `確度 ${minProb}% 以上のシグナルなし（スライダーを下げると表示されます）`
                  : "シグナルなし"}
              </p>
            )}
          </div>
        </>
      )}
    </div>
  );
}
