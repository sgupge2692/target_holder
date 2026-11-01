"use client";
import { useState } from "react";
import useSWR from "swr";
import Link from "next/link";
import {
  getAdminStats, getAdminUsers, getAdminSignals,
  getAdminMetrics, getAdminFeatures,
  type AdminUser, type AdminSignalDaily, type AdminModelMetric,
} from "@/lib/api";
import { useAuth } from "@/hooks/useAuth";
import {
  Users, TrendingUp, Zap, Brain,
  RefreshCw, ChevronLeft, ChevronRight,
  ArrowUp, ArrowDown, Activity, DollarSign,
} from "lucide-react";

// ── KPI カード ─────────────────────────────────────────────────────────────
function KpiCard({
  label, value, sub, icon, color,
}: { label: string; value: string; sub?: string; icon: React.ReactNode; color: string }) {
  return (
    <div className="bg-white dark:bg-surface-900 border border-surface-100 dark:border-surface-800 rounded-2xl p-5 flex items-start gap-4">
      <div className={`w-10 h-10 rounded-xl flex items-center justify-center shrink-0 ${color}`}>
        {icon}
      </div>
      <div className="min-w-0">
        <div className="text-xs text-surface-400 dark:text-surface-500 font-medium mb-0.5">{label}</div>
        <div className="text-2xl font-black text-surface-900 dark:text-white tabular-nums leading-none">{value}</div>
        {sub && <div className="text-xs text-surface-400 dark:text-surface-500 mt-1">{sub}</div>}
      </div>
    </div>
  );
}

// ── ミニバーチャート (新規登録推移) ────────────────────────────────────────
function MiniBarChart({ data }: { data: { date: string; count: number }[] }) {
  if (!data.length) return <div className="h-20 flex items-center justify-center text-xs text-surface-400">データなし</div>;
  const max = Math.max(...data.map(d => d.count), 1);
  return (
    <div className="flex items-end gap-1.5 h-16">
      {data.map(d => (
        <div key={d.date} className="flex-1 flex flex-col items-center gap-1 group">
          <div
            className="w-full bg-brand-500 dark:bg-brand-400 rounded-sm transition-all group-hover:bg-brand-600 dark:group-hover:bg-brand-300 relative"
            style={{ height: `${Math.max((d.count / max) * 100, 8)}%` }}
            title={`${d.date}: ${d.count}人`}
          />
          <span className="text-[9px] text-surface-400 dark:text-surface-600">{d.date.slice(5)}</span>
        </div>
      ))}
    </div>
  );
}

// ── 日次シグナルテーブル ────────────────────────────────────────────────────
function SignalTable({ rows }: { rows: AdminSignalDaily[] }) {
  if (!rows.length) return <p className="text-center text-surface-400 py-8 text-sm">データなし</p>;
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-xs text-surface-400 dark:text-surface-500 uppercase tracking-wide border-b border-surface-100 dark:border-surface-800">
            <th className="pb-2.5 text-left">日付</th>
            <th className="pb-2.5 text-right">件数</th>
            <th className="pb-2.5 text-right">↑UP</th>
            <th className="pb-2.5 text-right">↓DOWN</th>
            <th className="pb-2.5 text-right">的中率</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-surface-50 dark:divide-surface-800">
          {rows.map(r => (
            <tr key={r.date} className="hover:bg-surface-50 dark:hover:bg-surface-800/30 transition-colors">
              <td className="py-2 tabular-nums text-xs text-surface-500">{r.date}</td>
              <td className="py-2 text-right font-mono font-semibold text-surface-700 dark:text-surface-300">{r.total}</td>
              <td className="py-2 text-right font-mono text-brand-600 dark:text-brand-400">{r.up}</td>
              <td className="py-2 text-right font-mono text-danger-500 dark:text-danger-400">{r.down}</td>
              <td className="py-2 text-right">
                {r.accuracy_pct != null ? (
                  <span className={`font-bold ${r.accuracy_pct >= 60 ? "text-brand-600 dark:text-brand-400" : "text-surface-400"}`}>
                    {r.accuracy_pct.toFixed(1)}%
                  </span>
                ) : <span className="text-surface-300 dark:text-surface-700">—</span>}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ── モデルメトリクス ────────────────────────────────────────────────────────
function MetricsTable({ rows }: { rows: AdminModelMetric[] }) {
  if (!rows.length) return <p className="text-center text-surface-400 py-8 text-sm">学習履歴なし</p>;
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-xs text-surface-400 dark:text-surface-500 uppercase tracking-wide border-b border-surface-100 dark:border-surface-800">
            <th className="pb-2.5 text-left">日時</th>
            <th className="pb-2.5 text-center">モード</th>
            <th className="pb-2.5 text-right">LGBM AUC</th>
            <th className="pb-2.5 text-right">XGB AUC</th>
            <th className="pb-2.5 text-right">Ensemble AUC</th>
            <th className="pb-2.5 text-right">サンプル数</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-surface-50 dark:divide-surface-800">
          {rows.map(r => (
            <tr key={r.id} className="hover:bg-surface-50 dark:hover:bg-surface-800/30 transition-colors">
              <td className="py-2 tabular-nums text-xs text-surface-500">{r.trained_at.slice(0, 16).replace("T", " ")}</td>
              <td className="py-2 text-center">
                <span className="px-2 py-0.5 rounded-full text-xs font-bold bg-surface-100 dark:bg-surface-800 text-surface-600 dark:text-surface-400">
                  {r.mode}
                </span>
              </td>
              <td className="py-2 text-right font-mono text-xs">{r.lgbm_auc?.toFixed(4) ?? "—"}</td>
              <td className="py-2 text-right font-mono text-xs">{r.xgb_auc?.toFixed(4) ?? "—"}</td>
              <td className="py-2 text-right font-mono text-xs font-bold text-brand-600 dark:text-brand-400">
                {r.ensemble_auc?.toFixed(4) ?? "—"}
              </td>
              <td className="py-2 text-right font-mono text-xs">{r.n_samples?.toLocaleString() ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ── 特徴量重要度バーチャート ────────────────────────────────────────────────
function FeatureChart({ features }: { features: { feature: string; importance: number }[] }) {
  if (!features.length) return <p className="text-center text-surface-400 py-8 text-sm">データなし</p>;
  const max = features[0]?.importance ?? 1;
  return (
    <div className="space-y-2">
      {features.map((f, i) => (
        <div key={f.feature} className="flex items-center gap-3">
          <span className="text-xs text-surface-400 dark:text-surface-500 w-4 text-right tabular-nums">{i + 1}</span>
          <span className="text-xs font-mono text-surface-700 dark:text-surface-300 w-36 truncate shrink-0">{f.feature}</span>
          <div className="flex-1 h-3 bg-surface-100 dark:bg-surface-800 rounded-full overflow-hidden">
            <div
              className="h-full rounded-full bg-gradient-to-r from-brand-500 to-brand-400"
              style={{ width: `${(f.importance / max) * 100}%` }}
            />
          </div>
          <span className="text-xs font-mono text-surface-400 dark:text-surface-500 w-14 text-right tabular-nums">
            {f.importance.toFixed(0)}
          </span>
        </div>
      ))}
    </div>
  );
}

// ── ユーザー一覧 ────────────────────────────────────────────────────────────
function UserTable({ users, total, page, onPage }: {
  users: AdminUser[]; total: number; page: number; onPage: (p: number) => void;
}) {
  const pages = Math.ceil(total / 50);
  return (
    <div className="space-y-3">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-xs text-surface-400 dark:text-surface-500 uppercase tracking-wide border-b border-surface-100 dark:border-surface-800">
              <th className="pb-2.5 text-left">メール</th>
              <th className="pb-2.5 text-center">プラン</th>
              <th className="pb-2.5 text-center">アラート</th>
              <th className="pb-2.5 text-center">ステータス</th>
              <th className="pb-2.5 text-right">登録日</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-surface-50 dark:divide-surface-800">
            {users.map(u => (
              <tr key={u.id} className="hover:bg-surface-50 dark:hover:bg-surface-800/30 transition-colors">
                <td className="py-2.5 text-xs text-surface-600 dark:text-surface-300 font-mono max-w-[200px] truncate">{u.email}</td>
                <td className="py-2.5 text-center">
                  <span className={`px-2 py-0.5 rounded-full text-xs font-bold ${
                    u.plan === "pro"
                      ? "bg-brand-100 dark:bg-brand-900/30 text-brand-700 dark:text-brand-400"
                      : "bg-surface-100 dark:bg-surface-800 text-surface-500"
                  }`}>
                    {u.plan.toUpperCase()}
                  </span>
                </td>
                <td className="py-2.5 text-center text-base">{u.email_signal_alert ? "✓" : "—"}</td>
                <td className="py-2.5 text-center">
                  <span className={`inline-block w-2 h-2 rounded-full ${u.is_active ? "bg-brand-500" : "bg-surface-300"}`} />
                </td>
                <td className="py-2.5 text-right text-xs text-surface-400 tabular-nums">
                  {u.created_at.slice(0, 10)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {pages > 1 && (
        <div className="flex items-center justify-between text-xs text-surface-400">
          <span>全 {total} 件 — {page} / {pages} ページ</span>
          <div className="flex gap-1">
            <button
              disabled={page <= 1}
              onClick={() => onPage(page - 1)}
              className="p-1.5 rounded-lg hover:bg-surface-100 dark:hover:bg-surface-800 disabled:opacity-30 transition-colors"
            >
              <ChevronLeft size={14} />
            </button>
            <button
              disabled={page >= pages}
              onClick={() => onPage(page + 1)}
              className="p-1.5 rounded-lg hover:bg-surface-100 dark:hover:bg-surface-800 disabled:opacity-30 transition-colors"
            >
              <ChevronRight size={14} />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

// ── タブ ────────────────────────────────────────────────────────────────────
type Tab = "overview" | "users" | "signals" | "model";
const TABS: { id: Tab; label: string; icon: React.ElementType }[] = [
  { id: "overview", label: "概要",       icon: Activity  },
  { id: "users",    label: "ユーザー",   icon: Users     },
  { id: "signals",  label: "シグナル",   icon: TrendingUp },
  { id: "model",    label: "モデル",     icon: Brain     },
];

// ── メイン ─────────────────────────────────────────────────────────────────
export default function AdminPage() {
  const { user, loading } = useAuth();
  const [tab,       setTab]     = useState<Tab>("overview");
  const [userPage,  setUserPage] = useState(1);
  const [sigDays,   setSigDays]  = useState(30);
  const [featureN,  setFeatureN] = useState(20);

  const { data: stats,    isLoading: statsLoading    } = useSWR("admin:stats",    getAdminStats,   { revalidateOnFocus: false });
  const { data: userData, isLoading: usersLoading    } = useSWR(tab === "users"   ? ["admin:users",    userPage]  : null, () => getAdminUsers(userPage));
  const { data: sigData,  isLoading: sigsLoading     } = useSWR(tab === "signals" ? ["admin:signals",  sigDays]   : null, () => getAdminSignals(sigDays));
  const { data: metricsData                           } = useSWR(tab === "model"   ? "admin:metrics"               : null, getAdminMetrics);
  const { data: featData                              } = useSWR(tab === "model"   ? ["admin:features", featureN]  : null, () => getAdminFeatures(featureN));

  if (loading) return <div className="flex items-center justify-center h-48 text-surface-400 text-sm">読み込み中...</div>;
  if (!user || user.plan !== "pro") {
    return (
      <div className="text-center py-20 space-y-3">
        <p className="text-surface-400">管理者のみアクセス可能です</p>
        <Link href="/" className="text-sm text-brand-600 hover:underline">← ホームへ戻る</Link>
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      {/* ヘッダー */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-black text-surface-900 dark:text-white">管理画面</h1>
          <p className="text-xs text-surface-400 mt-0.5">Admin Dashboard</p>
        </div>
        <Link
          href="/"
          className="flex items-center gap-1.5 text-xs text-surface-400 hover:text-surface-700 dark:hover:text-surface-200 transition-colors"
        >
          <ChevronLeft size={14} />サービスへ戻る
        </Link>
      </div>

      {/* タブ */}
      <div className="flex gap-1 bg-surface-50 dark:bg-surface-800 rounded-xl p-1 border border-surface-100 dark:border-surface-700 w-fit">
        {TABS.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            onClick={() => setTab(id)}
            className={`flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-semibold transition-all ${
              tab === id
                ? "bg-white dark:bg-surface-700 text-brand-600 dark:text-brand-400 shadow-sm"
                : "text-surface-400 dark:text-surface-500 hover:text-surface-700 dark:hover:text-surface-300"
            }`}
          >
            <Icon size={14} />
            {label}
          </button>
        ))}
      </div>

      {/* ── 概要タブ ── */}
      {tab === "overview" && (
        <div className="space-y-5">
          {statsLoading ? (
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
              {[...Array(4)].map((_, i) => <div key={i} className="skeleton h-24 rounded-2xl" />)}
            </div>
          ) : stats ? (
            <>
              {/* KPI グリッド */}
              <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                <KpiCard
                  label="総ユーザー"
                  value={stats.users.total.toLocaleString()}
                  sub={`今月 +${stats.users.new_this_month}人`}
                  icon={<Users size={18} className="text-blue-600 dark:text-blue-400" />}
                  color="bg-blue-50 dark:bg-blue-900/20"
                />
                <KpiCard
                  label="Proユーザー"
                  value={stats.users.pro.toLocaleString()}
                  sub={`転換率 ${stats.users.conversion_rate_pct}%`}
                  icon={<Zap size={18} className="text-brand-600 dark:text-brand-400" />}
                  color="bg-brand-50 dark:bg-brand-900/20"
                />
                <KpiCard
                  label="MRR"
                  value={`¥${stats.revenue.mrr.toLocaleString()}`}
                  sub={`ARR ¥${(stats.revenue.arr / 10000).toFixed(0)}万`}
                  icon={<DollarSign size={18} className="text-amber-600 dark:text-amber-400" />}
                  color="bg-amber-50 dark:bg-amber-900/20"
                />
                <KpiCard
                  label="30日シグナル"
                  value={stats.signals.total_30d.toLocaleString()}
                  sub={stats.signals.up_accuracy_30d != null ? `UP的中率 ${stats.signals.up_accuracy_30d}%` : "実績未評価"}
                  icon={<TrendingUp size={18} className="text-violet-600 dark:text-violet-400" />}
                  color="bg-violet-50 dark:bg-violet-900/20"
                />
              </div>

              {/* 内訳 */}
              <div className="grid md:grid-cols-2 gap-4">
                {/* ユーザー内訳 */}
                <div className="bg-white dark:bg-surface-900 border border-surface-100 dark:border-surface-800 rounded-2xl p-5 space-y-4">
                  <h3 className="text-sm font-bold text-surface-700 dark:text-surface-300">ユーザー内訳</h3>
                  <div className="space-y-3">
                    {[
                      { label: "Proプラン",  value: stats.users.pro,   color: "bg-brand-500",  pct: stats.users.conversion_rate_pct },
                      { label: "Freeプラン", value: stats.users.free,  color: "bg-surface-200 dark:bg-surface-700", pct: 100 - stats.users.conversion_rate_pct },
                    ].map(r => (
                      <div key={r.label} className="space-y-1">
                        <div className="flex items-center justify-between text-xs">
                          <span className="text-surface-500 dark:text-surface-400">{r.label}</span>
                          <span className="font-bold text-surface-700 dark:text-surface-200">{r.value.toLocaleString()}人</span>
                        </div>
                        <div className="h-2 bg-surface-100 dark:bg-surface-800 rounded-full overflow-hidden">
                          <div className={`h-full rounded-full ${r.color}`} style={{ width: `${r.pct}%` }} />
                        </div>
                      </div>
                    ))}
                  </div>
                  <div className="pt-1">
                    <div className="text-xs text-surface-400 mb-2">過去7日間の新規登録</div>
                    <MiniBarChart data={stats.daily_signups} />
                  </div>
                </div>

                {/* シグナル内訳 */}
                <div className="bg-white dark:bg-surface-900 border border-surface-100 dark:border-surface-800 rounded-2xl p-5 space-y-4">
                  <h3 className="text-sm font-bold text-surface-700 dark:text-surface-300">30日シグナル内訳</h3>
                  <div className="grid grid-cols-2 gap-3">
                    {[
                      { label: "UP シグナル",  value: stats.signals.up_count_30d,   icon: <ArrowUp size={14} />,   color: "text-brand-600 dark:text-brand-400 bg-brand-50 dark:bg-brand-900/20" },
                      { label: "DOWN シグナル", value: stats.signals.down_count_30d, icon: <ArrowDown size={14} />, color: "text-danger-500 dark:text-danger-400 bg-danger-50 dark:bg-danger-900/20" },
                      { label: "評価済み",      value: stats.signals.evaluated_30d,  icon: <Activity size={14} />, color: "text-surface-600 dark:text-surface-400 bg-surface-50 dark:bg-surface-800" },
                      { label: "UP的中率",      value: stats.signals.up_accuracy_30d != null ? `${stats.signals.up_accuracy_30d}%` : "—", icon: <TrendingUp size={14} />, color: "text-violet-600 dark:text-violet-400 bg-violet-50 dark:bg-violet-900/20" },
                    ].map(r => (
                      <div key={r.label} className={`flex items-center gap-2 rounded-xl px-3 py-3 ${r.color}`}>
                        {r.icon}
                        <div>
                          <div className="text-base font-black tabular-nums">{typeof r.value === "number" ? r.value.toLocaleString() : r.value}</div>
                          <div className="text-[10px] opacity-70">{r.label}</div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </>
          ) : null}
        </div>
      )}

      {/* ── ユーザータブ ── */}
      {tab === "users" && (
        <div className="bg-white dark:bg-surface-900 border border-surface-100 dark:border-surface-800 rounded-2xl p-5 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-bold text-surface-700 dark:text-surface-300">
              ユーザー一覧
              {userData && <span className="ml-2 text-xs text-surface-400 font-normal">全 {userData.total} 件</span>}
            </h3>
            <button
              onClick={() => setUserPage(1)}
              className="p-1.5 rounded-lg hover:bg-surface-100 dark:hover:bg-surface-800 transition-colors text-surface-400"
            >
              <RefreshCw size={13} />
            </button>
          </div>
          {usersLoading ? (
            <div className="space-y-2">
              {[...Array(8)].map((_, i) => <div key={i} className="skeleton h-9 rounded-lg" />)}
            </div>
          ) : userData ? (
            <UserTable
              users={userData.users}
              total={userData.total}
              page={userPage}
              onPage={setUserPage}
            />
          ) : null}
        </div>
      )}

      {/* ── シグナルタブ ── */}
      {tab === "signals" && (
        <div className="bg-white dark:bg-surface-900 border border-surface-100 dark:border-surface-800 rounded-2xl p-5 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-bold text-surface-700 dark:text-surface-300">日次シグナル統計</h3>
            <div className="flex items-center gap-1 bg-surface-50 dark:bg-surface-800 rounded-xl p-1 border border-surface-100 dark:border-surface-700">
              {[7, 30, 90].map(d => (
                <button
                  key={d}
                  onClick={() => setSigDays(d)}
                  className={`px-3 py-1 rounded-lg text-xs font-semibold transition-all ${
                    sigDays === d
                      ? "bg-white dark:bg-surface-700 text-brand-600 dark:text-brand-400 shadow-sm"
                      : "text-surface-400 hover:text-surface-700"
                  }`}
                >
                  {d}日
                </button>
              ))}
            </div>
          </div>
          {sigsLoading ? (
            <div className="space-y-2">{[...Array(10)].map((_, i) => <div key={i} className="skeleton h-9 rounded-lg" />)}</div>
          ) : (
            <SignalTable rows={sigData?.data ?? []} />
          )}
        </div>
      )}

      {/* ── モデルタブ ── */}
      {tab === "model" && (
        <div className="space-y-5">
          {/* メトリクス履歴 */}
          <div className="bg-white dark:bg-surface-900 border border-surface-100 dark:border-surface-800 rounded-2xl p-5 space-y-4">
            <h3 className="text-sm font-bold text-surface-700 dark:text-surface-300">学習履歴（最新20件）</h3>
            <MetricsTable rows={metricsData?.metrics ?? []} />
          </div>

          {/* 特徴量重要度 */}
          <div className="bg-white dark:bg-surface-900 border border-surface-100 dark:border-surface-800 rounded-2xl p-5 space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-sm font-bold text-surface-700 dark:text-surface-300">特徴量重要度</h3>
                {featData?.trained_at && (
                  <p className="text-xs text-surface-400 mt-0.5">
                    最終学習: {featData.trained_at.slice(0, 16).replace("T", " ")} ({featData.mode})
                  </p>
                )}
              </div>
              <div className="flex items-center gap-1 bg-surface-50 dark:bg-surface-800 rounded-xl p-1 border border-surface-100 dark:border-surface-700">
                {[10, 20, 30].map(n => (
                  <button
                    key={n}
                    onClick={() => setFeatureN(n)}
                    className={`px-3 py-1 rounded-lg text-xs font-semibold transition-all ${
                      featureN === n
                        ? "bg-white dark:bg-surface-700 text-brand-600 dark:text-brand-400 shadow-sm"
                        : "text-surface-400 hover:text-surface-700"
                    }`}
                  >
                    Top {n}
                  </button>
                ))}
              </div>
            </div>
            <FeatureChart features={featData?.features ?? []} />
          </div>
        </div>
      )}
    </div>
  );
}
