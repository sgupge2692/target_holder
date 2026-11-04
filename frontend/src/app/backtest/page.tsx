"use client";
import { useState } from "react";
import useSWR from "swr";
import {
  LineChart, Line, BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ResponsiveContainer, ReferenceLine, Area, AreaChart,
} from "recharts";
import { getBacktestChart } from "@/lib/api";
import { TrendingUp, TrendingDown, Target, BarChart2, Zap } from "lucide-react";

const PERIOD_OPTIONS = [
  { label: "3M", value: 3 },
  { label: "6M", value: 6 },
  { label: "12M", value: 12 },
  { label: "24M", value: 24 },
];

// ── KPI カード ────────────────────────────────────────────────────
function KpiCard({
  label, value, sub, up, icon, trend,
}: {
  label: string; value: string; sub?: string;
  up?: boolean; icon?: React.ReactNode; trend?: number;
}) {
  return (
    <div className="rounded border border-slate-700/60 bg-[#0c1424] p-4 flex flex-col gap-1.5 relative overflow-hidden">
      <div className="absolute right-3 top-3 opacity-[0.04] scale-150">{icon}</div>
      <div className="text-[10px] font-black tracking-widest uppercase text-slate-500">{label}</div>
      <div className={`text-2xl font-black tabular-nums font-mono ${
        up === true ? "text-teal-400" : up === false ? "text-red-400" : "text-white"
      }`}>{value}</div>
      <div className="flex items-center gap-2">
        {sub && <div className="text-[10px] text-slate-500">{sub}</div>}
        {trend != null && (
          <span className={`ml-auto text-[10px] font-black px-1.5 py-0.5 rounded tracking-wider ${
            trend >= 0 ? "bg-teal-900/40 text-teal-400" : "bg-red-900/30 text-red-400"
          }`}>
            {trend >= 0 ? "+" : ""}{trend.toFixed(1)}%
          </span>
        )}
      </div>
    </div>
  );
}

// ── カスタムツールチップ ──────────────────────────────────────────
function CustomTooltip({ active, payload, label }: {
  active?: boolean; payload?: { name: string; value: number; color: string }[]; label?: string;
}) {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-[#0c1424] border border-slate-700 rounded p-3 shadow-xl text-xs min-w-[140px]">
      <p className="font-black text-slate-300 mb-2 tracking-wider uppercase">{label}</p>
      {payload.map((p) => (
        <div key={p.name} className="flex items-center justify-between gap-4">
          <span style={{ color: p.color }} className="font-semibold">{p.name}</span>
          <span className="font-mono font-black" style={{ color: p.color }}>
            {typeof p.value === "number" ? p.value.toFixed(1) : p.value}%
          </span>
        </div>
      ))}
    </div>
  );
}

// ── スケルトン ────────────────────────────────────────────────────
function ChartSkeleton() {
  return (
    <div className="rounded border border-slate-700/60 bg-[#0c1424] p-5">
      <div className="skeleton h-4 w-36 mb-5 rounded" />
      <div className="skeleton h-60 w-full rounded" />
    </div>
  );
}

export default function BacktestPage() {
  const [months, setMonths] = useState(12);
  const { data, isLoading } = useSWR(
    ["backtest", months],
    () => getBacktestChart(months),
    { refreshInterval: 60000 },
  );

  const overall = data?.overall ?? [];
  const upRow    = overall.find(r => r.signal === "UP");
  const downRow  = overall.find(r => r.signal === "DOWN");
  const lastCumReturn = data?.cumulative_return?.at(-1)?.cumulative_return_pct ?? null;

  const monthly = data?.monthly ?? [];
  const upTrend = monthly.length >= 2
    ? (monthly.at(-1)?.up_accuracy ?? 0) - (monthly.at(-2)?.up_accuracy ?? 0)
    : undefined;

  return (
    <div className="space-y-6">
      {/* ヘッダー */}
      <div className="flex items-start justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-xl font-black tracking-tight text-white uppercase">Backtest Results</h1>
          <p className="text-xs text-slate-500 mt-0.5 tracking-wide">過去シグナルの予測精度・累積リターン分析</p>
        </div>
        {/* 期間セレクター */}
        <div className="flex gap-1 bg-[#0c1424] border border-slate-700/60 p-1 rounded">
          {PERIOD_OPTIONS.map(opt => (
            <button
              key={opt.value}
              onClick={() => setMonths(opt.value)}
              className={`px-3 py-1 rounded text-xs font-black tracking-widest uppercase transition-all ${
                months === opt.value
                  ? "bg-teal-600 text-white"
                  : "text-slate-500 hover:text-slate-300"
              }`}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      {/* KPI カード */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <KpiCard
          label="▲ UP 精度"
          value={upRow ? `${upRow.accuracy_pct}%` : "—"}
          sub={upRow ? `${upRow.correct} / ${upRow.total} 件` : "集計中"}
          up={true}
          icon={<TrendingUp className="w-10 h-10" />}
          trend={upTrend}
        />
        <KpiCard
          label="▼ DOWN 精度"
          value={downRow ? `${downRow.accuracy_pct}%` : "—"}
          sub={downRow ? `${downRow.correct} / ${downRow.total} 件` : "集計中"}
          up={false}
          icon={<TrendingDown className="w-10 h-10" />}
        />
        <KpiCard
          label="UP 平均リターン"
          value={upRow ? `${upRow.avg_return_pct >= 0 ? "+" : ""}${upRow.avg_return_pct}%` : "—"}
          sub="翌日騰落"
          up={upRow ? upRow.avg_return_pct >= 0 : undefined}
          icon={<Zap className="w-10 h-10" />}
        />
        <KpiCard
          label="累積リターン"
          value={lastCumReturn != null ? `${lastCumReturn >= 0 ? "+" : ""}${lastCumReturn.toFixed(1)}%` : "—"}
          sub={`過去 ${months}M UP追従`}
          up={lastCumReturn != null ? lastCumReturn >= 0 : undefined}
          icon={<BarChart2 className="w-10 h-10" />}
        />
      </div>

      {isLoading && (
        <div className="grid md:grid-cols-2 gap-4">
          <ChartSkeleton /><ChartSkeleton />
        </div>
      )}

      {/* チャートエリア */}
      {data && (
        <div className="grid md:grid-cols-2 gap-4">
          {/* 月別精度 */}
          {monthly.length > 0 && (
            <div className="rounded border border-slate-700/60 bg-[#0c1424] p-5">
              <h2 className="text-[10px] font-black tracking-widest uppercase text-slate-400 mb-4 flex items-center gap-2">
                <Target className="w-3.5 h-3.5 text-teal-500" />
                月別予測精度
              </h2>
              <ResponsiveContainer width="100%" height={260}>
                <BarChart data={monthly} margin={{ top: 4, right: 8, left: -16, bottom: 4 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                  <XAxis dataKey="month" tick={{ fontSize: 9, fill: "#475569" }} />
                  <YAxis domain={[0, 100]} tickFormatter={v => `${v}%`} tick={{ fontSize: 9, fill: "#475569" }} />
                  <Tooltip content={<CustomTooltip />} />
                  <Legend wrapperStyle={{ fontSize: "11px", color: "#64748b" }} />
                  <ReferenceLine y={50} stroke="#334155" strokeDasharray="4 4" />
                  <Bar dataKey="up_accuracy"   name="UP 精度"   fill="#0d9488" radius={[2,2,0,0]} />
                  <Bar dataKey="down_accuracy" name="DOWN 精度" fill="#dc2626" radius={[2,2,0,0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* 累積リターン */}
          {data.cumulative_return.length > 0 && (
            <div className="rounded border border-slate-700/60 bg-[#0c1424] p-5">
              <h2 className="text-[10px] font-black tracking-widest uppercase text-slate-400 mb-4 flex items-center gap-2">
                <TrendingUp className="w-3.5 h-3.5 text-teal-500" />
                累積リターン（UPシグナル追従）
              </h2>
              <ResponsiveContainer width="100%" height={260}>
                <AreaChart data={data.cumulative_return} margin={{ top: 4, right: 8, left: -12, bottom: 4 }}>
                  <defs>
                    <linearGradient id="retGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%"  stopColor="#0d9488" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="#0d9488" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                  <XAxis
                    dataKey="date"
                    tick={{ fontSize: 9, fill: "#475569" }}
                    tickFormatter={v => v.slice(5)}
                  />
                  <YAxis tickFormatter={v => `${v.toFixed(0)}%`} tick={{ fontSize: 9, fill: "#475569" }} />
                  <Tooltip
                    formatter={(v: number) => [`${v.toFixed(2)}%`, "累積リターン"]}
                    labelFormatter={l => `日付: ${l}`}
                    contentStyle={{ background: "#0c1424", border: "1px solid #334155", borderRadius: "4px", fontSize: "12px", color: "#cbd5e1" }}
                  />
                  <ReferenceLine y={0} stroke="#334155" />
                  <Area
                    type="monotone"
                    dataKey="cumulative_return_pct"
                    name="累積リターン"
                    stroke="#0d9488"
                    fill="url(#retGrad)"
                    dot={false}
                    strokeWidth={2}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>
      )}

      {/* データなし */}
      {!isLoading && data && monthly.length === 0 && (
        <div className="text-center py-20 text-slate-600">
          <BarChart2 className="w-10 h-10 mx-auto mb-3 opacity-30" />
          <p className="font-black uppercase tracking-widest text-sm">No Data Yet</p>
          <p className="text-xs mt-1 text-slate-700">パイプライン実行後にデータが蓄積されます</p>
        </div>
      )}

      <p className="text-[10px] text-slate-700 text-center">
        ※ 過去の精度は将来の利益を保証するものではありません。投資は自己責任で行ってください。
      </p>
    </div>
  );
}
