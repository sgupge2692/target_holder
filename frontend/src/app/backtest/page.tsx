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
  { label: "3ヶ月", value: 3 },
  { label: "6ヶ月", value: 6 },
  { label: "12ヶ月", value: 12 },
  { label: "24ヶ月", value: 24 },
];

// ── KPI カード ────────────────────────────────────────────────────
function KpiCard({
  label, value, sub, color, icon, trend,
}: {
  label: string; value: string; sub?: string;
  color?: string; icon?: React.ReactNode; trend?: number;
}) {
  return (
    <div className="rounded-xl border border-gray-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-5 flex flex-col gap-2 relative overflow-hidden">
      <div className="absolute right-4 top-4 opacity-5 scale-150">{icon}</div>
      <div className="text-xs text-gray-500 dark:text-slate-400 uppercase tracking-wide font-semibold">{label}</div>
      <div className={`text-2xl font-black tabular-nums ${color ?? "text-gray-900 dark:text-white"}`}>{value}</div>
      <div className="flex items-center gap-2">
        {sub && <div className="text-xs text-gray-400 dark:text-slate-500">{sub}</div>}
        {trend != null && (
          <span className={`ml-auto text-xs font-semibold px-1.5 py-0.5 rounded-full ${trend >= 0 ? "bg-emerald-50 text-emerald-600 dark:bg-emerald-900/20 dark:text-emerald-400" : "bg-red-50 text-red-500 dark:bg-red-900/20"}`}>
            {trend >= 0 ? "+" : ""}{trend.toFixed(1)}%
          </span>
        )}
      </div>
    </div>
  );
}

// ── カスタムツールチップ ──────────────────────────────────────────
function CustomTooltip({ active, payload, label }: { active?: boolean; payload?: { name: string; value: number; color: string }[]; label?: string }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-white dark:bg-slate-800 border border-gray-200 dark:border-slate-700 rounded-xl p-3 shadow-xl text-sm min-w-[140px]">
      <p className="font-semibold text-gray-700 dark:text-slate-200 mb-2">{label}</p>
      {payload.map((p) => (
        <div key={p.name} className="flex items-center justify-between gap-4">
          <span style={{ color: p.color }} className="font-medium">{p.name}</span>
          <span className="font-mono font-bold" style={{ color: p.color }}>
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
    <div className="rounded-xl border border-gray-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-6">
      <div className="skeleton h-5 w-40 mb-5 rounded" />
      <div className="skeleton h-64 w-full rounded-lg" />
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

  // 月別精度の平均（最後の月との差でトレンド表示）
  const monthly = data?.monthly ?? [];
  const upTrend = monthly.length >= 2
    ? (monthly.at(-1)?.up_accuracy ?? 0) - (monthly.at(-2)?.up_accuracy ?? 0)
    : undefined;

  return (
    <div className="space-y-8">
      {/* ヘッダー */}
      <div className="flex items-start justify-between flex-wrap gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <BarChart2 className="w-5 h-5 text-brand-600" />
            <h1 className="text-2xl font-bold text-gray-900 dark:text-white">バックテスト結果</h1>
          </div>
          <p className="text-sm text-gray-500 dark:text-slate-400">
            過去シグナルの実績に基づく予測精度・リターン分析
          </p>
        </div>
        {/* 期間セレクター */}
        <div className="flex gap-1.5 bg-gray-100 dark:bg-slate-800 p-1 rounded-lg">
          {PERIOD_OPTIONS.map(opt => (
            <button
              key={opt.value}
              onClick={() => setMonths(opt.value)}
              className={`px-3.5 py-1.5 rounded-md text-sm font-medium transition-all ${
                months === opt.value
                  ? "bg-white dark:bg-slate-700 shadow-sm text-gray-900 dark:text-white"
                  : "text-gray-500 hover:text-gray-700 dark:text-slate-400"
              }`}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      {/* KPI カード */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <KpiCard
          label="UP 精度"
          value={upRow ? `${upRow.accuracy_pct}%` : "—"}
          sub={upRow ? `${upRow.correct} / ${upRow.total} 件` : "集計中"}
          color="text-emerald-600"
          icon={<TrendingUp className="w-10 h-10 text-emerald-500" />}
          trend={upTrend}
        />
        <KpiCard
          label="DOWN 精度"
          value={downRow ? `${downRow.accuracy_pct}%` : "—"}
          sub={downRow ? `${downRow.correct} / ${downRow.total} 件` : "集計中"}
          color="text-red-500"
          icon={<TrendingDown className="w-10 h-10 text-red-400" />}
        />
        <KpiCard
          label="UP 平均リターン"
          value={upRow ? `${upRow.avg_return_pct >= 0 ? "+" : ""}${upRow.avg_return_pct}%` : "—"}
          sub="シグナル翌日 1日騰落"
          color={upRow && upRow.avg_return_pct >= 0 ? "text-emerald-600" : "text-red-500"}
          icon={<Zap className="w-10 h-10 text-amber-400" />}
        />
        <KpiCard
          label="累積リターン"
          value={lastCumReturn != null ? `${lastCumReturn >= 0 ? "+" : ""}${lastCumReturn.toFixed(1)}%` : "—"}
          sub={`過去 ${months} ヶ月 UPシグナル追従`}
          color={lastCumReturn != null && lastCumReturn >= 0 ? "text-brand-600 dark:text-brand-400" : "text-red-500"}
          icon={<BarChart2 className="w-10 h-10 text-brand-500" />}
        />
      </div>

      {isLoading && (
        <>
          <div className="grid md:grid-cols-2 gap-5">
            <ChartSkeleton /><ChartSkeleton />
          </div>
        </>
      )}

      {/* チャートエリア */}
      {data && (
        <div className="grid md:grid-cols-2 gap-5">
          {/* 月別精度 */}
          {monthly.length > 0 && (
            <div className="rounded-xl border border-gray-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-6">
              <h2 className="text-sm font-semibold text-gray-800 dark:text-white mb-4 flex items-center gap-2">
                <Target className="w-4 h-4 text-brand-600" />
                月別予測精度
              </h2>
              <ResponsiveContainer width="100%" height={260}>
                <BarChart data={monthly} margin={{ top: 4, right: 8, left: -16, bottom: 4 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" className="dark:stroke-slate-700" />
                  <XAxis dataKey="month" tick={{ fontSize: 10 }} />
                  <YAxis domain={[0, 100]} tickFormatter={v => `${v}%`} tick={{ fontSize: 10 }} />
                  <Tooltip content={<CustomTooltip />} />
                  <Legend wrapperStyle={{ fontSize: "12px" }} />
                  <ReferenceLine y={50} stroke="#94a3b8" strokeDasharray="4 4" />
                  <Bar dataKey="up_accuracy"   name="UP 精度"   fill="#10b981" radius={[4,4,0,0]} />
                  <Bar dataKey="down_accuracy" name="DOWN 精度" fill="#ef4444" radius={[4,4,0,0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* 累積リターン */}
          {data.cumulative_return.length > 0 && (
            <div className="rounded-xl border border-gray-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-6">
              <h2 className="text-sm font-semibold text-gray-800 dark:text-white mb-4 flex items-center gap-2">
                <TrendingUp className="w-4 h-4 text-brand-600" />
                累積リターン推移（UPシグナル追従）
              </h2>
              <ResponsiveContainer width="100%" height={260}>
                <AreaChart data={data.cumulative_return} margin={{ top: 4, right: 8, left: -12, bottom: 4 }}>
                  <defs>
                    <linearGradient id="retGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#16a34a" stopOpacity={0.2} />
                      <stop offset="95%" stopColor="#16a34a" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" className="dark:stroke-slate-700" />
                  <XAxis
                    dataKey="date"
                    tick={{ fontSize: 10 }}
                    tickFormatter={v => v.slice(5)}
                  />
                  <YAxis tickFormatter={v => `${v.toFixed(0)}%`} tick={{ fontSize: 10 }} />
                  <Tooltip
                    formatter={(v: number) => [`${v.toFixed(2)}%`, "累積リターン"]}
                    labelFormatter={l => `日付: ${l}`}
                    contentStyle={{ borderRadius: "12px", border: "1px solid #e5e7eb", fontSize: "13px" }}
                  />
                  <ReferenceLine y={0} stroke="#94a3b8" />
                  <Area
                    type="monotone"
                    dataKey="cumulative_return_pct"
                    name="累積リターン"
                    stroke="#16a34a"
                    fill="url(#retGrad)"
                    dot={false}
                    strokeWidth={2.5}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>
      )}

      {/* データなし */}
      {!isLoading && data && monthly.length === 0 && (
        <div className="text-center py-20 text-gray-400 dark:text-slate-500">
          <BarChart2 className="w-10 h-10 mx-auto mb-3 opacity-30" />
          <p className="font-medium">バックテストデータがまだありません</p>
          <p className="text-xs mt-1">パイプライン実行後にデータが蓄積されます</p>
        </div>
      )}

      <p className="text-xs text-gray-400 dark:text-slate-600 text-center">
        ※ 過去の精度は将来の利益を保証するものではありません。投資は自己責任で行ってください。
      </p>
    </div>
  );
}
