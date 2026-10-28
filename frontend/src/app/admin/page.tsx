"use client";
import useSWR from "swr";
import { apiFetch } from "@/lib/api";
import { useAuth } from "@/hooks/useAuth";
import { useRouter } from "next/navigation";
import {
  BarChart, Bar, LineChart, Line,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine,
} from "recharts";
import {
  Users, TrendingUp, DollarSign, Target,
  BarChart2, ShieldAlert, Brain, Cpu,
} from "lucide-react";

// ── 型 ───────────────────────────────────────────────────────────────────

interface Stats {
  users: {
    total: number; pro: number; free: number;
    new_this_month: number; conversion_rate_pct: number;
  };
  revenue: { mrr: number; arr: number };
  signals: {
    total_30d: number; up_count_30d: number; down_count_30d: number;
    evaluated_30d: number; up_accuracy_30d: number | null;
  };
  daily_signups: { date: string; count: number }[];
}

interface UserRow {
  id: number; email: string; plan: string;
  is_active: boolean; email_signal_alert: boolean; created_at: string;
}

interface ModelMetricRow {
  id: number; trained_at: string; mode: string;
  mean_auc: number | null; std_auc: number | null;
  lgbm_auc: number | null; xgb_auc: number | null;
  ensemble_auc: number | null; n_samples: number | null;
}

interface FeatureImportance {
  name: string; importance: number;
}

// ── コンポーネント ────────────────────────────────────────────────────────

function KpiCard({
  icon, label, value, sub, color = "text-gray-900 dark:text-white",
}: {
  icon: React.ReactNode; label: string; value: string; sub?: string; color?: string;
}) {
  return (
    <div className="rounded-xl border border-gray-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-5">
      <div className="flex items-center gap-2 text-gray-400 dark:text-slate-500 mb-2">
        {icon}
        <span className="text-xs uppercase tracking-wide">{label}</span>
      </div>
      <div className={`text-2xl font-bold ${color}`}>{value}</div>
      {sub && <div className="text-xs text-gray-400 dark:text-slate-500 mt-0.5">{sub}</div>}
    </div>
  );
}

// ── ページ本体 ────────────────────────────────────────────────────────────

export default function AdminPage() {
  const { user, loading } = useAuth();
  const router = useRouter();

  const { data: stats, isLoading: statsLoading } = useSWR<Stats>(
    user ? "admin-stats" : null,
    () => apiFetch<Stats>("/api/admin/stats"),
    { refreshInterval: 60000 },
  );

  const { data: usersData, isLoading: usersLoading } = useSWR<{ users: UserRow[]; total: number }>(
    user ? "admin-users" : null,
    () => apiFetch<{ users: UserRow[]; total: number }>("/api/admin/users?per_page=20"),
  );

  const { data: dailySig } = useSWR<{ data: { date: string; total: number; up: number; accuracy_pct: number | null }[] }>(
    user ? "admin-daily-sig" : null,
    () => apiFetch<{ data: { date: string; total: number; up: number; accuracy_pct: number | null }[] }>("/api/admin/signals/daily?days=14"),
  );

  const { data: modelMetrics } = useSWR<{ metrics: ModelMetricRow[] }>(
    user ? "admin-model-metrics" : null,
    () => apiFetch<{ metrics: ModelMetricRow[] }>("/api/admin/model/metrics?limit=15"),
  );

  const { data: featureData } = useSWR<{ features: FeatureImportance[]; trained_at: string | null; mode: string | null }>(
    user ? "admin-features" : null,
    () => apiFetch<{ features: FeatureImportance[]; trained_at: string | null; mode: string | null }>("/api/admin/model/features?top_n=15"),
  );

  if (loading) return <div className="text-center py-16 text-gray-400">読み込み中...</div>;
  if (!user) { router.push("/auth"); return null; }

  // 403 エラーは SWR が error に入る — 非管理者向けメッセージ
  if (!statsLoading && !stats) {
    return (
      <div className="max-w-lg mx-auto py-20 text-center">
        <ShieldAlert className="w-12 h-12 mx-auto text-red-400 mb-4" />
        <h1 className="text-xl font-bold text-gray-700 dark:text-slate-200">アクセス拒否</h1>
        <p className="text-gray-500 dark:text-slate-400 mt-2">管理者権限が必要です。</p>
      </div>
    );
  }

  return (
    <main className="max-w-6xl mx-auto px-4 py-10 space-y-8">
      {/* ヘッダー */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white flex items-center gap-2">
          <ShieldAlert className="w-6 h-6 text-brand-600" />
          管理ダッシュボード
        </h1>
        <p className="text-sm text-gray-500 dark:text-slate-400 mt-1">リアルタイム事業KPI</p>
      </div>

      {/* KPI カード */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <KpiCard
            icon={<Users className="w-4 h-4" />}
            label="総ユーザー"
            value={stats.users.total.toLocaleString()}
            sub={`今月 +${stats.users.new_this_month}`}
          />
          <KpiCard
            icon={<TrendingUp className="w-4 h-4" />}
            label="Proユーザー"
            value={stats.users.pro.toLocaleString()}
            sub={`転換率 ${stats.users.conversion_rate_pct}%`}
            color="text-brand-600"
          />
          <KpiCard
            icon={<DollarSign className="w-4 h-4" />}
            label="MRR"
            value={`¥${stats.revenue.mrr.toLocaleString()}`}
            sub={`ARR ¥${stats.revenue.arr.toLocaleString()}`}
            color="text-emerald-600"
          />
          <KpiCard
            icon={<Target className="w-4 h-4" />}
            label="UP精度（30日）"
            value={stats.signals.up_accuracy_30d != null
              ? `${stats.signals.up_accuracy_30d}%`
              : "—"}
            sub={`評価済み ${stats.signals.evaluated_30d}件`}
            color={
              stats.signals.up_accuracy_30d != null && stats.signals.up_accuracy_30d >= 55
                ? "text-emerald-600"
                : "text-red-500"
            }
          />
        </div>
      )}

      {/* 日次サインアップ */}
      {stats && stats.daily_signups.length > 0 && (
        <div className="rounded-xl border border-gray-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-6">
          <h2 className="text-base font-semibold text-gray-800 dark:text-white mb-4 flex items-center gap-2">
            <Users className="w-4 h-4 text-brand-600" />
            日次新規登録（過去7日）
          </h2>
          <ResponsiveContainer width="100%" height={180}>
            <BarChart data={stats.daily_signups}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
              <XAxis dataKey="date" tick={{ fontSize: 11 }} tickFormatter={v => v.slice(5)} />
              <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
              <Tooltip />
              <Bar dataKey="count" name="新規登録" fill="#22c55e" radius={[3, 3, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* 日次シグナル精度 */}
      {dailySig && dailySig.data.length > 0 && (
        <div className="rounded-xl border border-gray-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-6">
          <h2 className="text-base font-semibold text-gray-800 dark:text-white mb-4 flex items-center gap-2">
            <BarChart2 className="w-4 h-4 text-brand-600" />
            日次シグナル数（過去14日）
          </h2>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={[...dailySig.data].reverse()}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
              <XAxis dataKey="date" tick={{ fontSize: 10 }} tickFormatter={v => v.slice(5)} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip />
              <Bar dataKey="up" name="UP" fill="#10b981" stackId="a" radius={[0, 0, 0, 0]} />
              <Bar dataKey="down" name="DOWN" fill="#ef4444" stackId="a" radius={[3, 3, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* モデル学習メトリクス履歴 */}
      {modelMetrics && modelMetrics.metrics.length > 0 && (
        <div className="rounded-xl border border-gray-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-6">
          <h2 className="text-base font-semibold text-gray-800 dark:text-white mb-4 flex items-center gap-2">
            <Brain className="w-4 h-4 text-brand-600" />
            モデルAUC推移
          </h2>
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={[...modelMetrics.metrics].reverse()}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
              <XAxis
                dataKey="trained_at"
                tick={{ fontSize: 10 }}
                tickFormatter={v => v.slice(5, 10)}
              />
              <YAxis domain={[0.45, 0.75]} tick={{ fontSize: 11 }} tickFormatter={v => v.toFixed(2)} />
              <Tooltip formatter={(v: number) => v?.toFixed(4)} labelFormatter={l => l?.slice(0, 16)} />
              <ReferenceLine y={0.6} stroke="#22c55e" strokeDasharray="4 4" label={{ value: "60%", fontSize: 10, fill: "#22c55e" }} />
              <Line type="monotone" dataKey="mean_auc" name="LightGBM AUC" stroke="#6366f1" strokeWidth={2} dot={{ r: 3 }} connectNulls />
              <Line type="monotone" dataKey="ensemble_auc" name="Ensemble AUC" stroke="#f59e0b" strokeWidth={2} dot={{ r: 3 }} connectNulls />
            </LineChart>
          </ResponsiveContainer>
          {/* 最新メトリクステーブル */}
          <div className="overflow-x-auto mt-4">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-gray-500 dark:text-slate-400 border-b border-gray-100 dark:border-slate-700">
                  <th className="py-2 text-left px-2">学習日時</th>
                  <th className="py-2 text-center px-2">モード</th>
                  <th className="py-2 text-right px-2">Mean AUC</th>
                  <th className="py-2 text-right px-2">LGBM</th>
                  <th className="py-2 text-right px-2">XGB</th>
                  <th className="py-2 text-right px-2">Ensemble</th>
                  <th className="py-2 text-right px-2">サンプル数</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50 dark:divide-slate-800">
                {modelMetrics.metrics.map(m => (
                  <tr key={m.id} className="hover:bg-gray-50 dark:hover:bg-slate-800/50">
                    <td className="py-1.5 px-2 text-gray-400">{m.trained_at.slice(0, 16)}</td>
                    <td className="py-1.5 px-2 text-center">
                      <span className={`px-1.5 py-0.5 rounded text-xs ${
                        m.mode === "ensemble" ? "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300"
                        : m.mode === "tune" ? "bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-300"
                        : "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300"
                      }`}>
                        {m.mode}
                      </span>
                    </td>
                    <td className={`py-1.5 px-2 text-right font-mono ${(m.mean_auc ?? 0) >= 0.6 ? "text-emerald-600" : "text-gray-600 dark:text-slate-400"}`}>
                      {m.mean_auc?.toFixed(4) ?? "—"}
                    </td>
                    <td className="py-1.5 px-2 text-right font-mono text-gray-500">{m.lgbm_auc?.toFixed(4) ?? "—"}</td>
                    <td className="py-1.5 px-2 text-right font-mono text-gray-500">{m.xgb_auc?.toFixed(4) ?? "—"}</td>
                    <td className="py-1.5 px-2 text-right font-mono text-gray-500">{m.ensemble_auc?.toFixed(4) ?? "—"}</td>
                    <td className="py-1.5 px-2 text-right text-gray-400">{m.n_samples?.toLocaleString() ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* 特徴量重要度 */}
      {featureData && featureData.features.length > 0 && (
        <div className="rounded-xl border border-gray-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-6">
          <h2 className="text-base font-semibold text-gray-800 dark:text-white mb-1 flex items-center gap-2">
            <Cpu className="w-4 h-4 text-brand-600" />
            特徴量重要度（上位15件）
          </h2>
          {featureData.trained_at && (
            <p className="text-xs text-gray-400 dark:text-slate-500 mb-4">
              最終学習: {featureData.trained_at.slice(0, 16)} ({featureData.mode})
            </p>
          )}
          <ResponsiveContainer width="100%" height={340}>
            <BarChart
              data={[...featureData.features].reverse()}
              layout="vertical"
              margin={{ left: 120, right: 20 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
              <XAxis type="number" tick={{ fontSize: 10 }} />
              <YAxis type="category" dataKey="name" tick={{ fontSize: 10 }} width={115} />
              <Tooltip formatter={(v: number) => v.toFixed(0)} />
              <Bar dataKey="importance" name="重要度" fill="#6366f1" radius={[0, 3, 3, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* ユーザー一覧 */}
      <div className="rounded-xl border border-gray-200 dark:border-slate-700 bg-white dark:bg-slate-900 overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-100 dark:border-slate-700 flex items-center justify-between">
          <h2 className="text-base font-semibold text-gray-800 dark:text-white flex items-center gap-2">
            <Users className="w-4 h-4 text-brand-600" />
            最近の登録ユーザー
          </h2>
          {usersData && (
            <span className="text-xs text-gray-400 dark:text-slate-500">計 {usersData.total} 人</span>
          )}
        </div>
        {usersLoading ? (
          <div className="text-center py-8 text-gray-400 animate-pulse">読み込み中...</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-gray-500 dark:text-slate-400 uppercase border-b border-gray-100 dark:border-slate-700">
                  <th className="px-6 py-3">メール</th>
                  <th className="px-4 py-3">プラン</th>
                  <th className="px-4 py-3">メールアラート</th>
                  <th className="px-4 py-3">登録日</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50 dark:divide-slate-800">
                {usersData?.users.map(u => (
                  <tr key={u.id} className="hover:bg-gray-50 dark:hover:bg-slate-800/50 transition-colors">
                    <td className="px-6 py-3 font-medium text-gray-800 dark:text-slate-200">{u.email}</td>
                    <td className="px-4 py-3">
                      <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${
                        u.plan === "pro"
                          ? "bg-brand-100 text-brand-700 dark:bg-brand-900/40 dark:text-brand-300"
                          : "bg-gray-100 text-gray-600 dark:bg-slate-700 dark:text-slate-300"
                      }`}>
                        {u.plan === "pro" ? "Pro" : "Free"}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-gray-500 dark:text-slate-400">
                      {u.email_signal_alert ? "✓ ON" : "—"}
                    </td>
                    <td className="px-4 py-3 text-gray-400 dark:text-slate-500">
                      {u.created_at.slice(0, 10)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </main>
  );
}
