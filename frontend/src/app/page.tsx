"use client";
import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import useSWR from "swr";
import { getLatestSignals, getAccuracy, downloadSignalsCsv, type Signal, type AccuracyRow } from "@/lib/api";
import { SignalBadge } from "@/components/SignalBadge";
import { StockSearch } from "@/components/StockSearch";
import { LandingPage } from "@/components/LandingPage";
import { SignalLimitBanner } from "@/components/SignalLimitBanner";
import { SignalRowSkeleton, SignalCardSkeleton, StatCardSkeleton } from "@/components/Skeleton";
import { useAuth } from "@/hooks/useAuth";
import { useToast } from "@/components/Toast";
import {
  ChevronDown, ChevronRight, Download, Lightbulb,
  SlidersHorizontal, TrendingUp, TrendingDown,
  Zap, RefreshCw, BarChart3, TrendingDown as ShortIcon, Lock,
  Activity, Layers,
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
    hint: "翌営業日に上昇 / 下落する可能性の高い銘柄をLGBM×XGBoostアンサンブルで配信",
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
    hint: "市場を下回ると予測される銘柄を抽出（相対的な弱さの目安。市場全体が上昇する日は下がらないこともあります）",
  },
];

function signalProb(signal: string, upProb: number): number {
  return signal === "DOWN" ? 1 - upProb : upProb;
}

function probColor(prob: number, signal: string): string {
  if (signal === "DOWN") {
    if (prob >= 0.8) return "bg-red-500 dark:bg-red-500";
    if (prob >= 0.7) return "bg-red-400 dark:bg-red-400";
    return "bg-orange-400";
  }
  if (prob >= 0.8)  return "bg-teal-500 dark:bg-teal-400";
  if (prob >= 0.7)  return "bg-teal-400 dark:bg-teal-500";
  if (prob >= 0.6)  return "bg-amber-400";
  return "bg-slate-300 dark:bg-slate-600";
}

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
      <span className={`font-mono font-black text-xs w-[3.2rem] text-right tabular-nums ${
        prob >= 0.75
          ? isDown ? "text-red-500 dark:text-red-400" : "text-teal-600 dark:text-teal-300"
          : "text-slate-500 dark:text-slate-400"
      }`}>
        {pct}%
      </span>
    </div>
  );
}

function ProbabilityFilter({ value, onChange }: { value: number; onChange: (v: number) => void }) {
  return (
    <div className="flex items-center gap-2.5">
      <SlidersHorizontal size={13} className="text-slate-400 shrink-0" />
      <span className="text-xs text-slate-500 dark:text-slate-400 whitespace-nowrap font-semibold">確度 ≥</span>
      <input
        type="range" min={50} max={95} step={5} value={value}
        onChange={e => onChange(Number(e.target.value))}
        className="w-24 accent-teal-600"
      />
      <span className="text-xs font-mono font-black w-10 text-teal-600 dark:text-teal-400">{value}%</span>
    </div>
  );
}

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
              flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-black
              whitespace-nowrap transition-all duration-150 shrink-0 relative
              tracking-wide uppercase
              ${active
                ? tab.id === "short"
                  ? "bg-red-500 text-white"
                  : "bg-teal-600 dark:bg-teal-500 text-white"
                : locked
                  ? "bg-slate-100 dark:bg-slate-800/60 text-slate-300 dark:text-slate-600 cursor-not-allowed"
                  : "bg-slate-100 dark:bg-slate-800/60 text-slate-500 dark:text-slate-400 hover:bg-slate-200 dark:hover:bg-slate-700/60"
              }
            `}
          >
            <Icon size={12} strokeWidth={2.5} />
            <span>{tab.label}</span>
            {locked && <Lock size={10} className="ml-0.5 opacity-50" />}
          </button>
        );
      })}
    </div>
  );
}

function ProLockedOverlay({ label }: { label: string }) {
  return (
    <div className="rounded border border-dashed border-amber-300 dark:border-amber-800/60 bg-amber-50/40 dark:bg-amber-900/5 p-10 text-center">
      <div className="inline-flex items-center justify-center w-10 h-10 rounded bg-amber-100 dark:bg-amber-900/30 mb-3">
        <Lock size={18} className="text-amber-500 dark:text-amber-400" />
      </div>
      <p className="font-black text-slate-800 dark:text-white mb-1 tracking-tight">「{label}」はPro限定</p>
      <p className="text-xs text-slate-500 dark:text-slate-400 mb-4">
        Proプランにアップグレードするとすべてのスタイルが利用可能になります
      </p>
      <Link
        href="/billing"
        className="inline-block bg-amber-500 hover:bg-amber-600 text-white px-5 py-2 rounded text-xs font-black transition-colors tracking-wider uppercase"
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
    <div className={`relative overflow-hidden rounded border p-4 ${
      isUp
        ? "border-teal-200 dark:border-teal-900/60 bg-gradient-to-br from-teal-50 to-white dark:from-teal-950/20 dark:to-[#0c1424]"
        : "border-red-200 dark:border-red-900/50 bg-gradient-to-br from-red-50 to-white dark:from-red-950/20 dark:to-[#0c1424]"
    }`}>
      {/* 右上の装飾 */}
      <div className={`absolute right-3 top-3 opacity-10 ${isUp ? "text-teal-500" : "text-red-500"}`}>
        {isUp ? <TrendingUp size={40} /> : <TrendingDown size={40} />}
      </div>

      <div className="flex items-center gap-1.5 mb-2">
        <span className={`text-[10px] font-black tracking-[0.14em] uppercase ${isUp ? "text-teal-600 dark:text-teal-400" : "text-red-500 dark:text-red-400"}`}>
          {isUp ? "▲ UP" : "▼ DOWN"}
        </span>
      </div>
      <p className={`text-3xl font-black tabular-nums leading-none ${isUp ? "text-teal-600 dark:text-teal-300" : "text-red-500 dark:text-red-400"}`}>
        {row.accuracy_pct}%
      </p>
      <p className="text-[10px] text-slate-400 dark:text-slate-500 mt-1 font-semibold">的中率 / n={row.total}</p>
      <div className="mt-2 pt-2 border-t border-slate-100 dark:border-[#1a2740] flex items-center justify-between">
        <span className="text-[10px] text-slate-400 dark:text-slate-500 font-semibold">平均リターン</span>
        <span className={`font-mono font-black text-sm ${(row.avg_return_pct ?? 0) >= 0 ? "text-teal-600 dark:text-teal-300" : "text-red-500 dark:text-red-400"}`}>
          {(row.avg_return_pct ?? 0) >= 0 ? "+" : ""}{row.avg_return_pct}%
        </span>
      </div>
    </div>
  );
}

// ── シグナル行（デスクトップ テーブル用）────────────────────────────────────
function SignalRow({ s }: { s: Signal }) {
  const [open, setOpen] = useState(false);
  const keyFactors: string[] = (() => {
    try { return s.key_factors ? JSON.parse(s.key_factors) : []; } catch { return []; }
  })();

  const isDown = s.signal === "DOWN";

  return (
    <>
      <tr className={`group transition-colors hover:bg-slate-50 dark:hover:bg-[#0d1a2f] ${
        isDown ? "border-l-2 border-l-red-400 dark:border-l-red-500" : "border-l-2 border-l-teal-500 dark:border-l-teal-400"
      }`}>
        <td className="px-4 py-3">
          <Link href={`/stocks/${s.Code}`} className="group/link">
            <p className="font-bold text-sm text-slate-900 dark:text-white group-hover/link:text-teal-600 dark:group-hover/link:text-teal-300 transition-colors">
              {s.company_name ?? s.Code}
            </p>
            <p className="ticker mt-0.5">{s.Code}</p>
          </Link>
        </td>
        <td className="px-4 py-3">
          <span className="font-mono text-xs text-slate-400 dark:text-slate-500">{s.Date}</span>
        </td>
        <td className="px-4 py-3 text-center"><SignalBadge signal={s.signal} /></td>
        <td className="px-4 py-3 w-40">
          <ProbBar upProb={s.up_probability} signal={s.signal} />
        </td>
        <td className="px-4 py-3 text-right font-mono text-sm">
          {s.actual_return != null
            ? <span className={`font-black ${s.actual_return >= 0 ? "text-teal-600 dark:text-teal-300" : "text-red-500 dark:text-red-400"}`}>
                {s.actual_return >= 0 ? "+" : ""}{(s.actual_return * 100).toFixed(2)}%
              </span>
            : <span className="text-slate-200 dark:text-slate-700">—</span>
          }
          {s.excess_return != null && (
            <div className="text-[10px] font-normal text-slate-400 dark:text-slate-500">
              市場比 {s.excess_return >= 0 ? "+" : ""}{(s.excess_return * 100).toFixed(2)}%
            </div>
          )}
        </td>
        <td className="px-4 py-3 text-center text-sm">
          {s.is_correct == null
            ? <span className="text-slate-200 dark:text-slate-700 text-xs">—</span>
            : s.is_correct
              ? <span className="text-teal-500 font-black text-xs">✓</span>
              : <span className="text-red-400 font-black text-xs">✗</span>
          }
        </td>
        <td className="px-4 py-3 text-center">
          {s.explanation && (
            <button
              onClick={() => setOpen(v => !v)}
              className="inline-flex items-center gap-1 text-[10px] text-teal-600 dark:text-teal-400 hover:underline font-black tracking-wider uppercase"
            >
              {open ? <ChevronDown size={11} /> : <ChevronRight size={11} />}
              解説
            </button>
          )}
        </td>
      </tr>
      {open && s.explanation && (
        <tr className="bg-teal-50/60 dark:bg-teal-900/10">
          <td colSpan={7} className="px-5 py-3">
            <div className="flex items-start gap-2.5 text-xs">
              <Lightbulb size={13} className="mt-0.5 shrink-0 text-teal-500" />
              <div>
                <p className="text-slate-700 dark:text-slate-300 leading-relaxed">{s.explanation}</p>
                {keyFactors.length > 0 && (
                  <div className="flex flex-wrap gap-1.5 mt-2">
                    {keyFactors.map((f, i) => (
                      <span key={i} className="px-2 py-0.5 rounded bg-teal-100 dark:bg-teal-900/40 text-teal-700 dark:text-teal-300 font-semibold">
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

// ── シグナルカード（モバイル）──────────────────────────────────────────────
function SignalCard({ s, isPro }: { s: Signal; isPro: boolean }) {
  const [open, setOpen] = useState(false);
  const router = useRouter();
  const keyFactors: string[] = (() => {
    try { return s.key_factors ? JSON.parse(s.key_factors) : []; } catch { return []; }
  })();
  const isDown = s.signal === "DOWN";
  const conf = Math.round(signalProb(s.signal, s.up_probability) * 100);

  return (
    <div className={`signal-card-v2 ${isDown ? "down" : "up"}`}>
      <Link href={`/stocks/${s.Code}`} className="block p-4 transition-colors active:bg-slate-50 dark:active:bg-slate-800/30">
        {/* 上段: 銘柄名 + シグナル */}
        <div className="flex items-start justify-between mb-3">
          <div className="min-w-0 pr-3">
            <p className="font-black text-sm text-slate-900 dark:text-white leading-tight truncate tracking-tight">
              {s.company_name ?? s.Code}
            </p>
            <p className="ticker mt-0.5">{s.Code} · {s.Date}</p>
          </div>
          <SignalBadge signal={s.signal} />
        </div>

        {/* 確率バー */}
        <div className="mb-2.5">
          <div className="flex items-center justify-between mb-1.5">
            <span className="text-[10px] font-black tracking-[0.1em] uppercase text-slate-400 dark:text-slate-500">
              {isDown ? "市場劣後確率" : "市場超過確率"}
            </span>
            <span className={`font-mono font-black text-lg leading-none ${
              isDown ? "text-red-500 dark:text-red-400" : "text-teal-600 dark:text-teal-300"
            }`}>
              {conf}%
            </span>
          </div>
          <div className="prob-bar-track h-[3px]">
            <div
              className={`prob-bar-fill h-[3px] ${isDown ? "bg-red-500" : conf >= 80 ? "bg-teal-500" : conf >= 70 ? "bg-teal-400" : "bg-amber-400"}`}
              style={{ width: `${conf}%` }}
            />
          </div>
        </div>

        {/* 実績リターン */}
        {s.actual_return != null && (
          <div className="flex items-center justify-between pt-2.5 border-t border-slate-100 dark:border-[#1a2740]">
            <span className="text-[10px] font-semibold uppercase tracking-widest text-slate-400 dark:text-slate-500">実績</span>
            <div className="flex items-center gap-1.5">
              <span className={`font-mono font-black text-sm ${s.actual_return >= 0 ? "text-teal-600 dark:text-teal-300" : "text-red-500 dark:text-red-400"}`}>
                {s.actual_return >= 0 ? "+" : ""}{(s.actual_return * 100).toFixed(2)}%
              </span>
              {s.is_correct != null && (
                <span className={`text-xs font-black ${s.is_correct ? "text-teal-500" : "text-red-400"}`}>
                  {s.is_correct ? "✓" : "✗"}
                </span>
              )}
            </div>
          </div>
        )}
      </Link>

      {/* ICT 分析ボタン（Pro 専用） */}
      <div className="flex border-t border-slate-100 dark:border-[#1a2740]">
        {s.explanation && (
          <button
            onClick={() => setOpen(v => !v)}
            className={`flex-1 flex items-center justify-center gap-1.5 text-[10px] py-2 font-black tracking-widest uppercase transition-colors ${
              isDown
                ? "text-red-500 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/10"
                : "text-teal-600 dark:text-teal-400 hover:bg-teal-50 dark:hover:bg-teal-900/10"
            }`}
          >
            <Lightbulb size={11} />
            {open ? "閉じる" : "解説"}
          </button>
        )}
        <button
          onClick={() => isPro ? router.push(`/ict/${s.Code}`) : null}
          title={isPro ? "ICT 詳細分析" : "Pro プランで利用可能"}
          className={`flex items-center justify-center gap-1.5 text-[10px] py-2 font-black tracking-widest uppercase transition-colors ${
            s.explanation ? "border-l border-slate-100 dark:border-[#1a2740] flex-1" : "flex-1"
          } ${
            isPro
              ? "text-amber-500 hover:bg-amber-50 dark:hover:bg-amber-900/10"
              : "text-slate-500 cursor-default opacity-50"
          }`}
        >
          <Layers size={11} />
          ICT 分析
        </button>
      </div>

      {s.explanation && open && (
        <div className={`px-4 py-3 text-xs leading-relaxed ${
          isDown
            ? "bg-red-50 dark:bg-red-900/10 text-red-900 dark:text-red-200"
            : "bg-teal-50 dark:bg-teal-900/10 text-teal-900 dark:text-teal-200"
        }`}>
          <p>{s.explanation}</p>
          {keyFactors.length > 0 && (
            <div className="flex flex-wrap gap-1 mt-2">
              {keyFactors.map((f, i) => (
                <span key={i} className={`px-1.5 py-0.5 rounded text-[10px] font-semibold ${
                  isDown
                    ? "bg-red-100 dark:bg-red-800/40 text-red-700 dark:text-red-300"
                    : "bg-teal-100 dark:bg-teal-800/40 text-teal-700 dark:text-teal-300"
                }`}>
                  {f}
                </span>
              ))}
            </div>
          )}
        </div>
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
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3">
        <div>
          <div className="flex items-center gap-3 mb-1">
            <h1 className="text-xl font-black tracking-tight text-slate-900 dark:text-white uppercase">
              Signal Feed
            </h1>
            {!sigLoading && filtered.length > 0 && (
              <div className="flex items-center gap-2">
                <span className="live-dot" />
                {latestDate && (
                  <span className="font-mono text-[10px] text-slate-400 dark:text-slate-500 tracking-wider">{latestDate}</span>
                )}
                <span className="px-1.5 py-0.5 rounded bg-teal-100 dark:bg-teal-900/30 text-teal-700 dark:text-teal-300 text-[10px] font-black tracking-wider">
                  {filtered.length}件
                </span>
              </div>
            )}
          </div>
          <p className="text-xs text-slate-400 dark:text-slate-500 font-semibold tracking-wide">
            LightGBM × XGBoost ensemble · 翌日騰落予測
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
        <div className="flex items-center justify-between rounded border border-amber-200 dark:border-amber-800/50 bg-amber-50/60 dark:bg-amber-900/8 px-4 py-2.5 text-sm">
          <div>
            <p className="font-black text-amber-800 dark:text-amber-300 text-xs tracking-wide">
              無料プランは確度の高い上位 {signalData?.free_limit ?? 3} 件まで
            </p>
            <p className="text-[10px] text-amber-600 dark:text-amber-500 mt-0.5">Pro プランで全件表示・CSV・スイング / 長期 / 信用売りモード</p>
          </div>
          <Link
            href="/billing"
            className="shrink-0 ml-4 bg-amber-500 hover:bg-amber-600 text-white px-3 py-1.5 rounded text-[10px] font-black transition-colors tracking-widest uppercase"
          >
            Upgrade →
          </Link>
        </div>
      )}

      {/* ── 投資スタイルタブ ── */}
      <div className="space-y-2.5">
        <StyleTabBar current={styleTab} onChange={handleStyleChange} isPro={isPro} />
        <div className={`flex items-start gap-2 px-3 py-2 rounded border text-[10px] font-semibold ${
          styleTab === "short"
            ? "bg-red-50 dark:bg-red-900/8 text-red-600 dark:text-red-400 border-red-200 dark:border-red-900/40"
            : "bg-teal-50 dark:bg-teal-900/8 text-teal-700 dark:text-teal-400 border-teal-200 dark:border-teal-900/40"
        }`}>
          <Activity size={11} className="shrink-0 mt-0.5" />
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
              className="ml-auto flex items-center gap-1.5 px-3 py-1.5 rounded text-[10px] font-black bg-slate-100 dark:bg-slate-800/60 text-slate-600 dark:text-slate-400 border border-slate-200 dark:border-slate-700 hover:bg-slate-200 dark:hover:bg-slate-700/60 transition-colors disabled:opacity-50 uppercase tracking-widest"
            >
              <Download size={11} />
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
          <div className="md:hidden space-y-2.5">
            {[...Array(5)].map((_, i) => <SignalCardSkeleton key={i} />)}
          </div>
          <div className="hidden md:block overflow-hidden rounded border border-slate-200 dark:border-[#1a2740]">
            <table className="w-full text-sm terminal-table">
              <thead>
                <tr>
                  {["銘柄", "日付", "シグナル", "確率", "実績", "的中", "解説"].map(h => (
                    <th key={h} className="text-left">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {[...Array(8)].map((_, i) => <SignalRowSkeleton key={i} />)}
              </tbody>
            </table>
          </div>
        </>
      ) : filtered.length === 0 ? (
        <div className="text-center py-16 text-slate-400">
          <p className="text-sm font-black tracking-widest uppercase mb-1">No Signals</p>
          <p className="text-xs text-slate-400 dark:text-slate-500">
            {(signalData?.signals ?? []).length > 0
              ? `確度 ${minProb}% 以上のシグナルがありません`
              : "本日のシグナルはまだ生成されていません"
            }
          </p>
        </div>
      ) : (
        <>
          {/* モバイル: カード */}
          <div className="md:hidden space-y-2.5">
            {filtered.map((s: Signal) => (
              <SignalCard key={`${s.Code}-${s.Date}`} s={s} isPro={isPro} />
            ))}
          </div>

          {/* デスクトップ: テーブル */}
          <div className="hidden md:block overflow-hidden rounded border border-slate-200 dark:border-[#1a2740]">
            <table className="w-full text-sm terminal-table">
              <thead>
                <tr>
                  <th className="text-left">銘柄</th>
                  <th className="text-left">日付</th>
                  <th className="text-center">シグナル</th>
                  <th className="text-left">{signalFilter === "DOWN" ? "市場劣後確率" : "市場超過確率"}</th>
                  <th className="text-right" title="翌営業日の騰落率。的中は市場平均との比較で判定します">騰落</th>
                  <th className="text-center" title="UP は市場平均を上回ったか、DOWN は下回ったかで判定">的中（対市場）</th>
                  <th className="text-center">解説</th>
                </tr>
              </thead>
              <tbody className="bg-[#0c1424]">
                {filtered.map((s: Signal) => (
                  <SignalRow key={`${s.Code}-${s.Date}`} s={s} />
                ))}
              </tbody>
            </table>
          </div>

          {/* 無料プランの制限に達したときのアップグレード誘導 */}
          {signalData?.is_limited && (
            <SignalLimitBanner
              shown={signalData.signals.length}
              totalAvailable={signalData.total_available}
              freeLimit={signalData.free_limit}
            />
          )}
        </>
      )}
    </div>
  );
}
