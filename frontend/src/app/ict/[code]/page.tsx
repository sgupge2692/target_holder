"use client";
import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  TrendingUp, TrendingDown, Minus, ArrowLeft,
  Target, ShieldAlert, AlertTriangle, Zap, ChevronDown, ChevronUp,
  Loader2, RefreshCw
} from "lucide-react";
import clsx from "clsx";

// ── 型定義 ───────────────────────────────────────────────────────────────────
interface EntryPoint {
  price: number | null;
  zone: string;
  trigger: string;
}
interface TakeProfitPoint {
  price: number | null;
  rationale: string;
  rr: string;
}
interface StopLossPoint {
  price: number | null;
  rationale: string;
}
interface IctAnalysis {
  decision: "BUY" | "SELL" | "NO_TRADE";
  decision_strength: "強" | "中" | "弱";
  current_price_area: string;
  dol: string;
  structure: string;
  entry: EntryPoint;
  stop_loss: StopLossPoint;
  take_profit_1: TakeProfitPoint;
  take_profit_2: TakeProfitPoint;
  key_confluences: string[];
  invalidation: string;
  risk_warnings: string[];
}
interface IctResult {
  code: string;
  company_name: string;
  last_close: number;
  last_date: string;
  chart_image: string;
  analysis: IctAnalysis;
}

// ── 色・ラベルユーティリティ ───────────────────────────────────────────────
function decisionColor(d: string) {
  if (d === "BUY") return "text-teal-400";
  if (d === "SELL") return "text-red-400";
  return "text-slate-400";
}
function decisionBg(d: string) {
  if (d === "BUY") return "bg-teal-900/40 border-teal-700";
  if (d === "SELL") return "bg-red-900/40 border-red-700";
  return "bg-slate-800 border-slate-600";
}
function decisionIcon(d: string) {
  if (d === "BUY") return <TrendingUp size={28} className="text-teal-400" />;
  if (d === "SELL") return <TrendingDown size={28} className="text-red-400" />;
  return <Minus size={28} className="text-slate-400" />;
}
function strengthBadge(s: string) {
  const map: Record<string, string> = { 強: "text-teal-300 bg-teal-900/40", 中: "text-amber-300 bg-amber-900/30", 弱: "text-slate-400 bg-slate-700/40" };
  return <span className={clsx("px-2 py-0.5 rounded text-[10px] font-black tracking-wider uppercase", map[s] || "text-slate-400")}>{s}</span>;
}

// ── セクションカード ─────────────────────────────────────────────────────────
function Card({ title, icon, children, className }: {
  title: string; icon: React.ReactNode; children: React.ReactNode; className?: string;
}) {
  return (
    <div className={clsx("rounded border border-slate-700/60 bg-[#0c1424] p-4", className)}>
      <div className="flex items-center gap-2 mb-3">
        {icon}
        <span className="text-[11px] font-black tracking-widest uppercase text-slate-400">{title}</span>
      </div>
      {children}
    </div>
  );
}

// ── メインページ ──────────────────────────────────────────────────────────────
export default function IctPage() {
  const { code } = useParams<{ code: string }>();
  const router = useRouter();
  const [result, setResult] = useState<IctResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showChart, setShowChart] = useState(false);
  const [ran, setRan] = useState(false);

  const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

  async function runAnalysis() {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API}/api/ict/${code}`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${localStorage.getItem("token")}` },
      });
      if (!res.ok) {
        const j = await res.json().catch(() => ({}));
        throw new Error(j.detail ?? `HTTP ${res.status}`);
      }
      setResult(await res.json());
      setRan(true);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "エラーが発生しました");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { runAnalysis(); }, [code]);

  const a = result?.analysis;

  return (
    <div className="min-h-screen bg-[#060b16] text-white pb-24">
      {/* ヘッダー */}
      <div className="sticky top-0 z-30 bg-[#060b16]/90 backdrop-blur border-b border-slate-700/40 px-4 py-3 flex items-center gap-3">
        <button onClick={() => router.back()} className="p-1.5 rounded hover:bg-slate-800 transition-colors">
          <ArrowLeft size={18} className="text-slate-400" />
        </button>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="font-mono text-xs text-slate-500 uppercase tracking-wider">{code}</span>
            {result && <span className="text-sm font-bold truncate">{result.company_name}</span>}
          </div>
          <span className="text-[10px] text-slate-500 font-black tracking-widest uppercase">ICT Chart Analysis</span>
        </div>
        {ran && (
          <button onClick={runAnalysis} disabled={loading} className="p-1.5 rounded hover:bg-slate-800 transition-colors">
            <RefreshCw size={16} className={clsx("text-slate-400", loading && "animate-spin")} />
          </button>
        )}
      </div>

      <div className="max-w-2xl mx-auto px-4 py-5 space-y-4">

        {/* ローディング */}
        {loading && (
          <div className="flex flex-col items-center justify-center py-20 gap-4">
            <Loader2 size={36} className="animate-spin text-teal-500" />
            <div className="text-center">
              <p className="text-sm font-bold text-slate-200">ICT 分析中…</p>
              <p className="text-xs text-slate-500 mt-1">チャートを読み込み、AI が解析しています</p>
            </div>
          </div>
        )}

        {/* エラー */}
        {error && !loading && (
          <div className="rounded border border-red-700/50 bg-red-900/20 p-4 flex items-start gap-3">
            <AlertTriangle size={18} className="text-red-400 mt-0.5 flex-shrink-0" />
            <div>
              <p className="text-sm font-bold text-red-300">分析エラー</p>
              <p className="text-xs text-red-400 mt-1">{error}</p>
            </div>
          </div>
        )}

        {/* 結果 */}
        {result && a && !loading && (
          <>
            {/* 判定サマリー */}
            <div className={clsx("rounded border p-4 flex items-center gap-4", decisionBg(a.decision))}>
              {decisionIcon(a.decision)}
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <span className={clsx("text-2xl font-black tracking-tight", decisionColor(a.decision))}>
                    {a.decision.replace("_", " ")}
                  </span>
                  {strengthBadge(a.decision_strength)}
                </div>
                <p className="text-xs text-slate-400 mt-1">{a.current_price_area}</p>
              </div>
              <div className="text-right">
                <p className="text-xs text-slate-500">終値</p>
                <p className="text-lg font-black font-mono">¥{result.last_close.toLocaleString()}</p>
                <p className="text-[10px] text-slate-500">{result.last_date}</p>
              </div>
            </div>

            {/* DOL / 市場構造 */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <Card title="DOL (流動性ターゲット)" icon={<Target size={14} className="text-teal-500" />}>
                <p className="text-sm text-slate-200 leading-relaxed">{a.dol}</p>
              </Card>
              <Card title="市場構造 (Structure)" icon={<Zap size={14} className="text-amber-400" />}>
                <p className="text-sm text-slate-200 leading-relaxed">{a.structure}</p>
              </Card>
            </div>

            {/* エントリー */}
            <Card title="Entry" icon={<TrendingUp size={14} className="text-teal-400" />}>
              <div className="space-y-2">
                {a.entry.price && (
                  <div className="flex justify-between items-center">
                    <span className="text-xs text-slate-400">価格</span>
                    <span className="font-mono font-black text-teal-300">¥{a.entry.price.toLocaleString()}</span>
                  </div>
                )}
                <div>
                  <span className="text-[10px] text-slate-500 uppercase tracking-wider">Zone</span>
                  <p className="text-sm text-slate-200 mt-0.5">{a.entry.zone}</p>
                </div>
                <div>
                  <span className="text-[10px] text-slate-500 uppercase tracking-wider">Trigger</span>
                  <p className="text-sm text-slate-200 mt-0.5">{a.entry.trigger}</p>
                </div>
              </div>
            </Card>

            {/* SL / TP */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <Card title="Stop Loss" icon={<ShieldAlert size={14} className="text-red-400" />}>
                {a.stop_loss.price && (
                  <div className="flex justify-between items-center mb-2">
                    <span className="text-xs text-slate-400">価格</span>
                    <span className="font-mono font-black text-red-400">¥{a.stop_loss.price.toLocaleString()}</span>
                  </div>
                )}
                <p className="text-xs text-slate-300">{a.stop_loss.rationale}</p>
              </Card>
              <div className="space-y-3">
                <Card title="Take Profit 1" icon={<Target size={14} className="text-teal-300" />}>
                  {a.take_profit_1.price && (
                    <div className="flex justify-between items-center mb-1">
                      <span className="font-mono font-black text-teal-300">¥{a.take_profit_1.price.toLocaleString()}</span>
                      <span className="text-[10px] font-bold text-amber-400 bg-amber-900/30 px-1.5 py-0.5 rounded">{a.take_profit_1.rr}</span>
                    </div>
                  )}
                  <p className="text-xs text-slate-300">{a.take_profit_1.rationale}</p>
                </Card>
                {a.take_profit_2?.price && (
                  <Card title="Take Profit 2" icon={<Target size={14} className="text-teal-200" />}>
                    <div className="flex justify-between items-center mb-1">
                      <span className="font-mono font-black text-teal-200">¥{a.take_profit_2.price.toLocaleString()}</span>
                      <span className="text-[10px] font-bold text-amber-400 bg-amber-900/30 px-1.5 py-0.5 rounded">{a.take_profit_2.rr}</span>
                    </div>
                    <p className="text-xs text-slate-300">{a.take_profit_2.rationale}</p>
                  </Card>
                )}
              </div>
            </div>

            {/* 合流根拠 */}
            {a.key_confluences?.length > 0 && (
              <Card title="Key Confluences" icon={<Zap size={14} className="text-teal-400" />}>
                <ul className="space-y-1.5">
                  {a.key_confluences.map((c, i) => (
                    <li key={i} className="flex items-start gap-2 text-sm text-slate-200">
                      <span className="text-teal-500 font-black mt-0.5 flex-shrink-0">▸</span>
                      {c}
                    </li>
                  ))}
                </ul>
              </Card>
            )}

            {/* 無効化条件 / リスク */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <Card title="Invalidation" icon={<AlertTriangle size={14} className="text-amber-400" />}>
                <p className="text-sm text-slate-200">{a.invalidation}</p>
              </Card>
              {a.risk_warnings?.length > 0 && (
                <Card title="Risk Warnings" icon={<ShieldAlert size={14} className="text-red-400" />}>
                  <ul className="space-y-1">
                    {a.risk_warnings.map((w, i) => (
                      <li key={i} className="text-xs text-slate-300 flex items-start gap-1.5">
                        <span className="text-red-500 mt-0.5">!</span>{w}
                      </li>
                    ))}
                  </ul>
                </Card>
              )}
            </div>

            {/* チャート画像（折りたたみ）*/}
            <div className="rounded border border-slate-700/60 overflow-hidden">
              <button
                onClick={() => setShowChart(v => !v)}
                className="w-full flex items-center justify-between px-4 py-3 bg-[#0c1424] hover:bg-slate-800/60 transition-colors"
              >
                <span className="text-[11px] font-black tracking-widest uppercase text-slate-400">チャート画像</span>
                {showChart ? <ChevronUp size={16} className="text-slate-500" /> : <ChevronDown size={16} className="text-slate-500" />}
              </button>
              {showChart && (
                <div className="bg-[#060b16] p-2">
                  <img src={result.chart_image} alt={`${code} chart`} className="w-full rounded" />
                </div>
              )}
            </div>

            {/* 注意書き */}
            <p className="text-[10px] text-slate-600 leading-relaxed text-center">
              この分析は AI による自動生成です。投資判断はご自身の責任で行ってください。
            </p>
          </>
        )}
      </div>
    </div>
  );
}
