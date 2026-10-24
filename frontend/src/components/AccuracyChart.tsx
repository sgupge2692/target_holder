"use client";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Legend,
} from "recharts";

interface MonthlyRow { month: string; up_acc: number; down_acc: number }

export function AccuracyChart({ data }: { data: MonthlyRow[] }) {
  return (
    <ResponsiveContainer width="100%" height={220}>
      <LineChart data={data} margin={{ top: 4, right: 16, bottom: 0, left: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(100,116,139,0.2)" />
        <XAxis dataKey="month" tick={{ fontSize: 11 }} />
        <YAxis domain={[40, 100]} unit="%" tick={{ fontSize: 11 }} />
        <Tooltip formatter={(v: number) => `${v.toFixed(1)}%`} />
        <Legend />
        <Line dataKey="up_acc"   name="UP精度"   stroke="#22c55e" dot={false} strokeWidth={2} />
        <Line dataKey="down_acc" name="DOWN精度" stroke="#ef4444" dot={false} strokeWidth={2} />
      </LineChart>
    </ResponsiveContainer>
  );
}
