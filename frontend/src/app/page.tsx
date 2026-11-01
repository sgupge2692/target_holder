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
  Zap, RefreshCw, BarChart3, TrendingDown as ShortIcon, Lock,
} from "lucide-react";

// ── タブ定義 ─────────────────────────────────────────────────────────────────
type SignalFilter = "ALL" | "UP" | "DOWN";
type StyleTab = "daytrade" | "swing" | "longterm" | "short";

interface StyleConfig {
  id: StyleTab;
  label: string;
  icon: React.ElementType;
  description: string;
  proOnly: boolean;
  defaultMinProb: number;
  signalFilter: SignalFilter;
  hint: string;
}

const STYLE_TABS: StyleConfig[] = [
  {
    id: "daytrade",
    label: "デイトレ",
    icon: Zap,
    description: "翌日の短期騰落を予測",
    proOnly: false,
    defaultMinProb: 65,
    signalFilter: "ALL",
    hint: "AIが翌営業日に上昇 / 下落する可能性の高い銘柄を配信",
  },
  {
    id: "swing",
    label: "スイング",
    icon: RefreshCw,
    description: "数日〜2週間の中期保有",
    proOnly: true,
    defaultMinProb: 70,
    signalFilter: "UP",
    hint: "高確度（70%以上）の上昇シグナルのみ表示。数日〜2週間の保有を想定",
  },
  {
    id: "longterm",
    label: "長期保有",
    icon: BarChart3,
    description: "月次・四半期視点のトレンド",
    proOnly: true,
    defaultMinProb: 75,
    signalFilter: "UP",
    hint: "強い上昇トレンドを示す銘柄のみ（確度75%以上）。長期保有・積み立て向け",
  },
  {
    id: "short",
    label: "信用売り",
    icon: ShortIcon,
    description: "下落シグナル銘柄を抽出",
    proOnly: true,
    defaultMinProb: 65,
    signalFilter: "DOWN",
    hint: "下落確率の高い銘柄を抽出。信用売り・空売りの参考に",
  },
];

/** シグナルの「確度」= UP なら up_probability、DOWN なら 1 - up_probability */
function signalProb(signal: string, upProb: number): number {
  return signal === "DOWN" ? 1 - upProb : upProb;
}

/** 確率を色クラスに変換（UP:緑系 / DOWN:赤系） */
function probColor(prob: number, signal: string): string {
  if (signal === "DOWN") {
    if (prob >= 0.8) return "bg-red-500";
    if (prob >= 0.7) return "bg-red-400";
    if (prob >= 0.6) return "bg-orange-400";
    return "bg-gray-400";
  }
  if (prob >= 0.8)  return "bg-brand-500";
  if (prob >= 0.7)  return "bg-emerald-400";
  if (prob >= 0.6)  return "bg-amber-400";
  return "bg-gray-400";
}

/** 確率バー（テーブル行 / カード共用）*/
function ProbBar({ upProb, signal }: { upProb: number; signal: string }) {
  const prob = signalProb(signal, upProb);
  const pct = Math.round(prob * 100);
  const isDown = signal === "DOWN";
  return (
    <div className="flex items-center gap-2">
      <div className="prob-bar-track flex-1 min-w-[60px]">
        <div
          className={`prob-bar-fill ${probColor(prob, signal)}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className={`font-mono font-semibold text-xs w-[3.4rem] text-right ${
        prob >= 0.75
          ? isDown ? "text-red-500 dark:text-red-400" : "text-brand-600 dark:text-brand-400"
          : "text-gray-600 dark:text-slate-300"
      }`}>
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

// ── 投資スタイルタブ ──────────────────────────────────────────────────────────
function StyleTabBar({
  current, onChange, isPro,
}: {
  current: StyleTab;
  onChange: (t: StyleTab) => void;
  isPro: boolean;
}) {
  return (
    <div className="flex gap-1 overflow-x-auto no-scrollbar">
      {STYLE_TABS.map(tab => {
        const Icon = tab.icon;
        const locked = tab.proOnly && !isPro;
        const active = current === tab.id;
        return (
          <button
            key={tab.id}
            onClick={() => !locked && onChange(tab.id)}
            title={locked ? "Proプラン限定" : tab.description}
            className={`
              flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-sm font-semibold
              whitespace-nowrap transition-all duration-150 shrink-0 relative
              ${active
                ? tab.id === "short"
                  ? "bg-red-500 text-white shadow-sm"
                  : "bg-brand-600 text-white shadow-sm"
                : locked
                  ? "bg-gray-100 dark:bg-slate-800 text-gray-400 dark:text-slate-500 cursor-not-allowed"
                  : "bg-gray-100 dark:bg-slate-800 text-gray-600 dark:text-slate-300 hover:bg-gray-200 dark:hover:bg-slate-700"
              }
            `}
          >
            <Icon size={14} strokeWidth={2.2} />
            <span>{tab.label}</span>
            {locked && (
              <Lock size={11} className="ml-0.5 opacity-60" />
            )}
          </button>
        );
      })}
    </div>
  );
}

// ── Proロックオーバーレイ ────────────────────────────────────────────────────
function ProLockedOverlay({ label }: { label: string }) {
  return (
    <div className="rounded-2xl border-2 border-dashed border-amber-300 dark:border-amber-700 bg-amber-50/60 dark:bg-amber-900/10 p-10 text-center">
      <div className="inline-flex items-center justify-center w-12 h-12 rounded-2xl bg-amber-100 dark:bg-amber-800/40 mb-3">
        <Lock size={22} className="text-amber-500" />
      </div>
      <p className="font-bold text-gray-800 dark:text-white mb-1">「{label}」はPro限定</p>
      <p className="text-sm text-gray-500 dark:text-slate-400 mb-4">
        Proプランにアップグレードするとすべてのスタイルが利用可能になります
      </p>
      <Link
        href="/billing"
        className="inline-block bg-amber-500 hover:bg-amber-600 text-white px-6 py-2 rounded-xl font-bold text-sm transition-colors"
      >
        Proにアップグレード →
      </Link>
    </div>
  );
}

// ── 精度サマリーカード ────────────────────────────────────────────────────────
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

// ── シグナル行（デスクトップ テーブル用）────────────────────────────────────
function SignalRow({ s, activeFilter }: { s: Signal; activeFilter: SignalFilter }) {
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
          <ProbBar upProb={s.up_probability} signal={s.signal} />
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

// ── シグナルカード（モバイルファースト）──────────────────────────────────────
function SignalCard({ s }: { s: Signal }) {
  const [open, setOpen] = useState(false);
  const keyFactors: string[] = (() => {
    try { return s.key_factors ? JSON.parse(s.key_factors) : []; } catch { return []; }
  })();
  const isDown = s.signal === "DOWN";
  const conf = Math.round(signalProb(s.signal, s.up_probability) * 100);

  return (
    <div className="signal-card-v2">
      <Link href={`/stocks/${s.Code}`} className="block p-4 active:bg-gray-50 dark:active:bg-slate-700/50 transition-colors">
        {/* 上段: 銘柄名 + シグナルバッジ */}
        <div className="flex items-start justify-between mb-3">
          <div className="min-w-0 pr-3">
            <p className="font-bold text-base text-gray-900 dark:text-white leading-tight truncate">
              {s.company_name ?? s.Code}
            </p>
            <p className="text-xs text-gray-400 dark:text-slate-500 mt-0.5">{s.Code} · {s.Date}</p>
          </div>
          <SignalBadge signal={s.signal} />
        </div>

        {/* 確率バー + 数値 */}
        <div className="mb-3">
          <div className="flex items-center justify-between text-xs text-gray-400 dark:text-slate-500 mb-1.5">
            <span>{isDown ? "下落確率" : "上昇確率"}</span>
            <span className={`font-mono font-black text-base ${isDown ? "text-red-500 dark:text-red-400" : "text-emerald-600 dark:text-emerald-400"}`}>
              {conf}%
            </span>
          </div>
          <div className="prob-bar-track h-2">
            <div
              className={`prob-bar-fill h-2 ${isDown ? "bg-red-500" : conf >= 80 ? "bg-emerald-500" : conf >= 70 ? "bg-emerald-400" : "bg-amber-400"}`}
              style={{ width: `${conf}%` }}
            />
          </div>
        </div>

        {/* 実績リターン */}
        {s.actual_return != null && (
          <div className="flex items-center justify-between pt-2.5 border-t border-gray-100 dark:border-slate-700/60">
            <span className="text-xs text-gray-400 dark:text-slate-500">実績リターン</span>
            <div className="flex items-center gap-1.5">
              <span className={`font-mono font-bold text-sm ${s.actual_return >= 0 ? "text-emerald-600" : "text-red-500"}`}>
                {s.actual_return >= 0 ? "+" : ""}{(s.actual_return * 100).toFixed(2)}%
              </span>
              {s.is_correct != null && (
                <span className="text-sm">{s.is_correct ? "✅" : "❌"}</span>
              )}
            </div>
          </div>
        )}
      </Link>

      {s.explanation && (
        <>
          <button
            onClick={() => setOpen(v => !v)}
            className={`w-full flex items-center justify-center gap-1.5 text-xs py-2.5 border-t font-semibold transition-colors ${
              isDown
                ? "border-red-100 dark:border-red-900/30 text-red-500 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/10"
                : "border-emerald-100 dark:border-emerald-900/30 text-emerald-600 dark:text-emerald-400 hover:bg-emerald-50 dark:hover:bg-emerald-900/10"
            }`}
          >
            <Lightbulb size={13} />
            {open ? "閉じる" : "AI説明を見る"}
          </button>
          {open && (
            <div className={`px-4 py-3 text-xs leading-relaxed ${
              isDown
                ? "bg-red-50 dark:bg-red-900/10 text-red-900 dark:text-red-200"
                : "bg-emerald-50 dark:bg-emerald-900/10 text-emerald-900 dark:text-emerald-200"
            }`}>
              <p>{s.explanation}</p>
              {keyFactors.length > 0 && (
                <div className="flex flex-wrap gap-1 mt-2">
                  {keyFactors.map((f, i) => (
                    <span key={i} className={`px-1.5 py-0.5 rounded-full text-xs ${
                      isDown
                        ? "bg-red-100 dark:bg-red-800/40 text-red-700 dark:text-red-300"
                        : "bg-emerald-100 dark:bg-emerald-800/40 text-emerald-700 dark:text-emerald-300"
                    }`}>
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

// ── メインページ ──────────────────────────────────────────────────────────────
export default function HomePage() {
  const { user, loading } = useAuth();
  const { toast } = useToast();
  const [styleTab, setStyleTab] = useState<StyleTab>("daytrade");
  const [minProb, setMinProb] = useState(65);
  const [csvLoading, setCsvLoading] = useState(false);

  const styleConfig = STYLE_TABS.find(t => t.id === styleTab)!;
  const signalFilter = styleConfig.signalFilter;
  const isPro = user?.plan === "pro";

  // hooks は早期 return より前に置く（React の rules of hooks）
  const { data: signalData, isLoading: sigLoading } = useSWR(
    user ? ["signals", signalFilter] : null,
    () => getLatestSignals(signalFilter === "ALL" ? undefined : signalFilter),
    { refreshInterval: 60_000 },
  );

  const { data: accData, isLoading: accLoading } = useSWR("accuracy", getAccuracy, {
    revalidateOnFocus: false,
  });

  const handleCsvDownload = async () => {
    setCsvLoading(true);
    try {
      await downloadSignalsCsv(signalFilter === "ALL" ? undefined : signalFilter, 30);
      toast("CSVをダウンロードしました", "success");
    } catch (e: unknown) {
      toast(e instanceof Error ? e.message : "CSVダウンロードに失敗しました", "error");
    } finally {
      setCsvLoading(false);
    }
  };

  // スタイルタブ変更時に確度フィルターをリセット
  const handleStyleChange = (next: StyleTab) => {
    const cfg = STYLE_TABS.find(t => t.id === next)!;
    setStyleTab(next);
    setMinProb(cfg.defaultMinProb);
  };

  if (!loading && !user) return <LandingPage />;

  const accuracyRows: AccuracyRow[] = accData?.accuracy ?? [];
  const upRow   = accuracyRows.find(r => r.signal === "UP");
  const downRow = accuracyRows.find(r => r.signal === "DOWN");

  const filtered = (signalData?.signals ?? []).filter(
    (s: Signal) => signalProb(s.signal, s.up_probability) * 100 >= minProb,
  );

  const latestDate = filtered[0]?.Date ?? null;
  const isLocked = styleConfig.proOnly && !isPro;

  return (
    <div className="space-y-5">
      {/* ── ヘッダー ── */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <div className="flex items-center gap-2.5 mb-0.5">
            <h1 className="text-2xl font-bold tracking-tight">AIシグナル</h1>
            {!sigLoading && filtered.length > 0 && (
              <div className="flex items-center gap-1.5">
                <span className="live-dot" />
                {latestDate && (
                  <span className="text-xs text-gray-400 dark:text-slate-500 font-mono">{latestDate}</span>
                )}
              </div>
            )}
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
            <p className="text-xs text-amber-600 dark:text-amber-400 mt-0.5">Pro プランで全件表示・CSV・スイング/長期/信用売りモード</p>
          </div>
          <Link
            href="/billing"
            className="shrink-0 ml-4 bg-amber-500 hover:bg-amber-600 text-white px-4 py-1.5 rounded-lg font-semibold text-xs transition-colors"
          >
            アップグレード →
          </Link>
        </div>
      )}

      {/* ── 投資スタイルタブ ── */}
      <div className="space-y-3">
        <StyleTabBar current={styleTab} onChange={handleStyleChange} isPro={isPro} />

        {/* スタイル説明ヒント */}
        <div className={`flex items-start gap-2 px-3.5 py-2.5 rounded-xl text-xs ${
          styleTab === "short"
            ? "bg-red-50 dark:bg-red-900/10 text-red-700 dark:text-red-300 border border-red-100 dark:border-red-800/40"
            : "bg-brand-50 dark:bg-brand-900/10 text-brand-700 dark:text-brand-300 border border-brand-100 dark:border-brand-800/40"
        }`}>
          <Lightbulb size={13} className="shrink-0 mt-0.5" />
          <span>{styleConfig.hint}</span>
        </div>
      </div>

      {/* ── フィルター行 ── */}
      {!isLocked && (
        <div className="flex flex-wrap items-center gap-3">
          <ProbabilityFilter value={minProb} onChange={setMinProb} />
          {isPro && (
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
      )}

      {/* ── コンテンツエリア ── */}
      {isLocked ? (
        <ProLockedOverlay label={styleConfig.label} />
      ) : sigLoading ? (
        <>
          <div className="md:hidden space-y-3">
            {[...Array(5)].map((_, i) => <SignalCardSkeleton key={i} />)}
          </div>
          <div className="hidden md:block overflow-x-auto rounded-xl border border-gray-200 dark:border-slate-700">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 dark:bg-slate-800 text-xs text-gray-500 dark:text-slate-400 uppercase tracking-wide">
                <tr>
                  {["銘柄", "日付", "シグナル", signalFilter === "DOWN" ? "下落確率" : "上昇確率", "実績", "的中", "AI"].map(h => (
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
                  <th className="px-4 py-3 text-left">{signalFilter === "DOWN" ? "下落確率" : "上昇確率"}</th>
                  <th className="px-4 py-3 text-right">実績</th>
                  <th className="px-4 py-3 text-center">的中</th>
                  <th className="px-4 py-3 text-center">AI</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 dark:divide-slate-700/60 bg-white dark:bg-slate-800/40">
                {filtered.map((s: Signal) => (
                  <SignalRow key={`${s.Code}-${s.Date}`} s={s} activeFilter={signalFilter} />
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
