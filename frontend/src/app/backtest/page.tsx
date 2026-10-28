"use client";
import useSWR from "swr";
import {
  LineChart, Line, BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, ReferenceLine,
} from "recharts";
import { getBacktestChart } from "@/lib/api";
import { TrendingUp, TrendingDown, Target, BarChart2 } from "lucide-react";

// ── 期間セレクター ────────────────────────────────────────────────
const PERIOD_OPTIONS = [
  { label: "3ヶ月", value: 3 },
  { label: "6ヶ月", value: 6 },
  { label: "12ヶ月", value: 12 },
  { label: "24ヶ月", value: 24 },
];

import { useState } from "react";

// ── KPI カード ────────────────────────────────────────────────────
function KpiCard({ label, value, sub, color }: {
  label: string; value: string; sub?: string; color?: string;
}) {
  return (
    <div className="rounded-xl border border-gray-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-5 flex flex-col gap-1">
      <div className="text-xs text-gray-500 dark:text-slate-400 uppercase tracking-wide">{label}</div>
      <div className={`text-2xl font-bold ${color ?? "text-gray-900 dark:text-white"}`}>{value}</div>
      {sub && <div className="text-xs text-gray-400 dark:text-slate-500">{sub}</div>}
    </div>
  );
}

// ── カスタムツールチップ ──────────────────────────────────────────
function CustomTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-white dark:bg-slate-800 border border-gray-200 dark:border-slate-700 rounded-lg p-3 shadow-lg text-sm">
      <p className="font-medium mb-1">{label}</p>
      {payload.map((p: any) => (
        <p key={p.name} style={{ color: p.color }}>
          {p.name}: {typeof p.value === "number" ? p.value.toFixed(1) : p.value}
          {p.name.includes("精度") ? "%" : p.name.includes("リターン") ? "%" : ""}
        </p>
      ))}
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

  return (
    <main className="max-w-5xl mx-auto px-4 py-10 space-y-8">
      {/* ヘッダー */}
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white flex items-center gap-2">
            <BarChart2 className="w-6 h-6 text-brand-600" />
            バックテスト結果
          </h1>
          <p className="text-sm text-gray-500 dark:text-slate-400 mt-1">
            過去シグナルの実績に基づく予測精度・リターン分析
          </p>
        </div>
        {/* 期間セレクター */}
        <div className="flex gap-2">
          {PERIOD_OPTIONS.map(opt => (
            <button
              key={opt.value}
              onClick={() => setMonths(opt.value)}
              className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                months === opt.value
                  ? "bg-brand-600 text-white"
                  : "bg-gray-100 dark:bg-slate-800 text-gray-600 dark:text-slate-400 hover:bg-gray-200 dark:hover:bg-slate-700"
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
          label="UP 精度（全期間）"
          value={upRow ? `${upRow.accuracy_pct}%` : "—"}
          sub={upRow ? `${upRow.correct} / ${upRow.total} 件` : ""}
          color="text-emerald-600"
        />
        <KpiCard
          label="DOWN 精度（全期間）"
          value={downRow ? `${downRow.accuracy_pct}%` : "—"}
          sub={downRow ? `${downRow.correct} / ${downRow.total} 件` : ""}
          color="text-red-500"
        />
        <KpiCard
          label="UP 平均リターン"
          value={upRow ? `${upRow.avg_return_pct > 0 ? "+" : ""}${upRow.avg_return_pct}%` : "—"}
          sub="シグナル翌日"
          color={upRow && upRow.avg_return_pct >= 0 ? "text-emerald-600" : "text-red-500"}
        />
        <KpiCard
          label="累積リターン"
          value={lastCumReturn != null ? `${lastCumReturn >= 0 ? "+" : ""}${lastCumReturn.toFixed(1)}%` : "—"}
          sub={`過去 ${months} ヶ月 (UP シグナル)`}
          color={lastCumReturn != null && lastCumReturn >= 0 ? "text-emerald-600" : "text-red-500"}
        />
      </div>

      {isLoading && (
        <div className="text-center py-20 text-gray-400 dark:text-slate-500 animate-pulse">
          データ読み込み中...
        </div>
      )}

      {/* 月別精度チャート */}
      {data && data.monthly.length > 0 && (
        <div className="rounded-xl border border-gray-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-6">
          <h2 className="text-base font-semibold text-gray-800 dark:text-white mb-4 flex items-center gap-2">
            <Target className="w-4 h-4 text-brand-600" />
            月別予測精度
          </h2>
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={data.monthly} margin={{ top: 4, right: 16, left: 0, bottom: 4 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
              <XAxis dataKey="month" tick={{ fontSize: 11 }} />
              <YAxis domain={[0, 100]} tickFormatter={v => `${v}%`} tick={{ fontSize: 11 }} />
              <Tooltip content={<CustomTooltip />} />
              <Legend />
              <ReferenceLine y={50} stroke="#9ca3af" strokeDasharray="4 4" label={{ value: "50%", position: "right", fontSize: 10 }} />
              <Bar dataKey="up_accuracy"   name="UP 精度"   fill="#10b981" radius={[3,3,0,0]} />
              <Bar dataKey="down_accuracy" name="DOWN 精度" fill="#ef4444" radius={[3,3,0,0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* 累積リターンチャート */}
      {data && data.cumulative_return.length > 0 && (
        <div className="rounded-xl border border-gray-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-6">
          <h2 className="text-base font-semibold text-gray-800 dark:text-white mb-4 flex items-center gap-2">
            <TrendingUp className="w-4 h-4 text-brand-600" />
            累積リターン推移（UP シグナル追従）
          </h2>
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={data.cumulative_return} margin={{ top: 4, right: 16, left: 0, bottom: 4 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
              <XAxis
                dataKey="date"
                tick={{ fontSize: 10 }}
                tickFormatter={v => v.slice(5)}  // MM-DD のみ表示
              />
              <YAxis tickFormatter={v => `${v.toFixed(0)}%`} tick={{ fontSize: 11 }} />
              <Tooltip
                formatter={(v: number) => [`${v.toFixed(2)}%`, "累積リターン"]}
                labelFormatter={l => `日付: ${l}`}
              />
              <ReferenceLine y={0} stroke="#9ca3af" />
              <Line
                type="monotone"
                dataKey="cumulative_return_pct"
                name="累積リターン"
                stroke="#6366f1"
                dot={false}
                strokeWidth={2}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* データなし */}
      {!isLoading && data && data.monthly.length === 0 && (
        <div className="text-center py-16 text-gray-400 dark:text-slate-500">
          <BarChart2 className="w-10 h-10 mx-auto mb-3 opacity-30" />
          <p>バックテストデータがまだありません。</p>
          <p className="text-xs mt-1">パイプライン実行後にデータが蓄積されます。</p>
        </div>
      )}

      {/* 注意書き */}
      <p className="text-xs text-gray-400 dark:text-slate-600 text-center">
        ※ 過去の精度は将来の利益を保証するものではありません。
        投資は自己責任で行ってください。
      </p>
    </main>
  );
}
