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
    <div className="bg-[#0c1424] border border-slate-700/60 rounded p-5 flex items-start gap-4">
      <div className={`w-10 h-10 rounded flex items-center justify-center shrink-0 ${color}`}>
        {icon}
      </div>
      <div className="min-w-0">
        <div className="text-[10px] font-black tracking-widest uppercase text-slate-500 mb-0.5">{label}</div>
        <div className="text-2xl font-black text-white tabular-nums leading-none font-mono">{value}</div>
        {sub && <div className="text-xs text-slate-500 mt-1">{sub}</div>}
      </div>
    </div>
  );
}

// ── ミニバーチャート ────────────────────────────────────────────────────────
function MiniBarChart({ data }: { data: { date: string; count: number }[] }) {
  if (!data.length) return <div className="h-20 flex items-center justify-center text-xs text-slate-600">データなし</div>;
  const max = Math.max(...data.map(d => d.count), 1);
  return (
    <div className="flex items-end gap-1.5 h-16">
      {data.map(d => (
        <div key={d.date} className="flex-1 flex flex-col items-center gap-1 group">
          <div
            className="w-full bg-teal-500 rounded-sm transition-all group-hover:bg-teal-400 relative"
            style={{ height: `${Math.max((d.count / max) * 100, 8)}%` }}
            title={`${d.date}: ${d.count}人`}
          />
          <span className="text-[9px] text-slate-600 font-mono">{d.date.slice(5)}</span>
        </div>
      ))}
    </div>
  );
}

// ── 日次シグナルテーブル ────────────────────────────────────────────────────
function SignalTable({ rows }: { rows: AdminSignalDaily[] }) {
  if (!rows.length) return <p className="text-center text-slate-600 py-8 text-sm">データなし</p>;
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-[10px] font-black tracking-widest uppercase text-slate-500 border-b border-slate-700/40 bg-[#060b16]">
            <th className="pb-2.5 pt-2 px-2 text-left">日付</th>
            <th className="pb-2.5 pt-2 px-2 text-right">件数</th>
            <th className="pb-2.5 pt-2 px-2 text-right">↑UP</th>
            <th className="pb-2.5 pt-2 px-2 text-right">↓DOWN</th>
            <th className="pb-2.5 pt-2 px-2 text-right">的中率</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-700/30">
          {rows.map(r => (
            <tr key={r.date} className="hover:bg-slate-800/20 transition-colors">
              <td className="py-2 px-2 tabular-nums text-xs text-slate-500 font-mono">{r.date}</td>
              <td className="py-2 px-2 text-right font-mono font-semibold text-slate-300">{r.total}</td>
              <td className="py-2 px-2 text-right font-mono text-teal-400">{r.up}</td>
              <td className="py-2 px-2 text-right font-mono text-red-400">{r.down}</td>
              <td className="py-2 px-2 text-right">
                {r.accuracy_pct != null ? (
                  <span className={`font-bold font-mono ${r.accuracy_pct >= 60 ? "text-teal-400" : "text-slate-500"}`}>
                    {r.accuracy_pct.toFixed(1)}%
                  </span>
                ) : <span className="text-slate-700">—</span>}
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
  if (!rows.length) return <p className="text-center text-slate-600 py-8 text-sm">学習履歴なし</p>;
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-[10px] font-black tracking-widest uppercase text-slate-500 border-b border-slate-700/40 bg-[#060b16]">
            <th className="pb-2.5 pt-2 px-2 text-left">日時</th>
            <th className="pb-2.5 pt-2 px-2 text-center">モード</th>
            <th className="pb-2.5 pt-2 px-2 text-right">LGBM AUC</th>
            <th className="pb-2.5 pt-2 px-2 text-right">XGB AUC</th>
            <th className="pb-2.5 pt-2 px-2 text-right">Ensemble AUC</th>
            <th className="pb-2.5 pt-2 px-2 text-right">サンプル数</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-700/30">
          {rows.map(r => (
            <tr key={r.id} className="hover:bg-slate-800/20 transition-colors">
              <td className="py-2 px-2 tabular-nums text-xs text-slate-500 font-mono">{r.trained_at.slice(0, 16).replace("T", " ")}</td>
              <td className="py-2 px-2 text-center">
                <span className="px-2 py-0.5 rounded text-xs font-black tracking-widest uppercase bg-slate-800 text-slate-400">
                  {r.mode}
                </span>
              </td>
              <td className="py-2 px-2 text-right font-mono text-xs text-slate-300">{r.lgbm_auc?.toFixed(4) ?? "—"}</td>
              <td className="py-2 px-2 text-right font-mono text-xs text-slate-300">{r.xgb_auc?.toFixed(4) ?? "—"}</td>
              <td className="py-2 px-2 text-right font-mono text-xs font-black text-teal-400">
                {r.ensemble_auc?.toFixed(4) ?? "—"}
              </td>
              <td className="py-2 px-2 text-right font-mono text-xs text-slate-300">{r.n_samples?.toLocaleString() ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ── 特徴量重要度バーチャート ────────────────────────────────────────────────
function FeatureChart({ features }: { features: { feature: string; importance: number }[] }) {
  if (!features.length) return <p className="text-center text-slate-600 py-8 text-sm">データなし</p>;
  const max = features[0]?.importance ?? 1;
  return (
    <div className="space-y-2">
      {features.map((f, i) => (
        <div key={f.feature} className="flex items-center gap-3">
          <span className="text-xs text-slate-600 w-4 text-right tabular-nums font-mono">{i + 1}</span>
          <span className="text-xs font-mono text-slate-400 w-36 truncate shrink-0">{f.feature}</span>
          <div className="flex-1 h-2 bg-slate-800 rounded overflow-hidden">
            <div
              className="h-full rounded bg-teal-500"
              style={{ width: `${(f.importance / max) * 100}%` }}
            />
          </div>
          <span className="text-xs font-mono text-slate-500 w-14 text-right tabular-nums">
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
            <tr className="text-[10px] font-black tracking-widest uppercase text-slate-500 border-b border-slate-700/40 bg-[#060b16]">
              <th className="pb-2.5 pt-2 px-2 text-left">メール</th>
              <th className="pb-2.5 pt-2 px-2 text-center">プラン</th>
              <th className="pb-2.5 pt-2 px-2 text-center">アラート</th>
              <th className="pb-2.5 pt-2 px-2 text-center">ステータス</th>
              <th className="pb-2.5 pt-2 px-2 text-right">登録日</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-700/30">
            {users.map(u => (
              <tr key={u.id} className="hover:bg-slate-800/20 transition-colors">
                <td className="py-2.5 px-2 text-xs text-slate-400 font-mono max-w-[200px] truncate">{u.email}</td>
                <td className="py-2.5 px-2 text-center">
                  <span className={`px-2 py-0.5 rounded text-xs font-black tracking-widest uppercase ${
                    u.plan === "pro"
                      ? "bg-teal-900/40 text-teal-400 border border-teal-700/40"
                      : "bg-slate-800 text-slate-500"
                  }`}>
                    {u.plan.toUpperCase()}
                  </span>
                </td>
                <td className="py-2.5 px-2 text-center text-base">{u.email_signal_alert ? "✓" : "—"}</td>
                <td className="py-2.5 px-2 text-center">
                  <span className={`inline-block w-2 h-2 rounded-full ${u.is_active ? "bg-teal-500" : "bg-slate-700"}`} />
                </td>
                <td className="py-2.5 px-2 text-right text-xs text-slate-500 tabular-nums font-mono">
                  {u.created_at.slice(0, 10)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {pages > 1 && (
        <div className="flex items-center justify-between text-xs text-slate-500">
          <span>全 {total} 件 — {page} / {pages} ページ</span>
          <div className="flex gap-1">
            <button
              disabled={page <= 1}
              onClick={() => onPage(page - 1)}
              className="p-1.5 rounded hover:bg-slate-800 disabled:opacity-30 transition-colors"
            >
              <ChevronLeft size={14} />
            </button>
            <button
              disabled={page >= pages}
              onClick={() => onPage(page + 1)}
              className="p-1.5 rounded hover:bg-slate-800 disabled:opacity-30 transition-colors"
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

  if (loading) return <div className="flex items-center justify-center h-48 text-slate-500 text-sm">読み込み中...</div>;
  if (!user || !user.is_admin) {
    return (
      <div className="text-center py-20 space-y-3">
        <p className="text-slate-500">管理者のみアクセス可能です</p>
        <Link href="/" className="text-sm text-teal-500 hover:underline">← ホームへ戻る</Link>
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      {/* ヘッダー */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-black text-white">管理画面</h1>
          <p className="text-[10px] font-black tracking-widest uppercase text-slate-500 mt-0.5">Admin Dashboard</p>
        </div>
        <Link
          href="/"
          className="flex items-center gap-1.5 text-xs text-slate-500 hover:text-slate-200 transition-colors"
        >
          <ChevronLeft size={14} />サービスへ戻る
        </Link>
      </div>

      {/* タブ */}
      <div className="flex gap-1 bg-[#060b16] rounded p-1 border border-slate-700/60 w-fit">
        {TABS.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            onClick={() => setTab(id)}
            className={`flex items-center gap-1.5 px-4 py-2 rounded text-xs font-black tracking-widest uppercase transition-all ${
              tab === id
                ? "bg-[#0c1424] text-teal-400 shadow-sm border border-slate-700/60"
                : "text-slate-600 hover:text-slate-400"
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
              {[...Array(4)].map((_, i) => <div key={i} className="skeleton h-24 rounded" />)}
            </div>
          ) : stats ? (
            <>
              {/* KPI グリッド */}
              <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                <KpiCard
                  label="総ユーザー"
                  value={stats.users.total.toLocaleString()}
                  sub={`今月 +${stats.users.new_this_month}人`}
                  icon={<Users size={18} className="text-blue-400" />}
                  color="bg-blue-900/20"
                />
                <KpiCard
                  label="Proユーザー"
                  value={stats.users.pro.toLocaleString()}
                  sub={`転換率 ${stats.users.conversion_rate_pct}%`}
                  icon={<Zap size={18} className="text-teal-400" />}
                  color="bg-teal-900/20"
                />
                <KpiCard
                  label="MRR"
                  value={`¥${stats.revenue.mrr.toLocaleString()}`}
                  sub={`ARR ¥${(stats.revenue.arr / 10000).toFixed(0)}万`}
                  icon={<DollarSign size={18} className="text-amber-400" />}
                  color="bg-amber-900/20"
                />
                <KpiCard
                  label="30日シグナル"
                  value={stats.signals.total_30d.toLocaleString()}
                  sub={stats.signals.up_accuracy_30d != null ? `UP的中率 ${stats.signals.up_accuracy_30d}%` : "実績未評価"}
                  icon={<TrendingUp size={18} className="text-violet-400" />}
                  color="bg-violet-900/20"
                />
              </div>

              {/* 内訳 */}
              <div className="grid md:grid-cols-2 gap-4">
                {/* ユーザー内訳 */}
                <div className="bg-[#0c1424] border border-slate-700/60 rounded p-5 space-y-4">
                  <h3 className="text-[10px] font-black tracking-widest uppercase text-slate-500">ユーザー内訳</h3>
                  <div className="space-y-3">
                    {[
                      { label: "Proプラン",  value: stats.users.pro,   color: "bg-teal-500",  pct: stats.users.conversion_rate_pct },
                      { label: "Freeプラン", value: stats.users.free,  color: "bg-slate-700", pct: 100 - stats.users.conversion_rate_pct },
                    ].map(r => (
                      <div key={r.label} className="space-y-1">
                        <div className="flex items-center justify-between text-xs">
                          <span className="text-slate-500">{r.label}</span>
                          <span className="font-bold font-mono text-slate-300">{r.value.toLocaleString()}人</span>
                        </div>
                        <div className="h-2 bg-slate-800 rounded overflow-hidden">
                          <div className={`h-full rounded ${r.color}`} style={{ width: `${r.pct}%` }} />
                        </div>
                      </div>
                    ))}
                  </div>
                  <div className="pt-1">
                    <div className="text-[10px] font-black tracking-widest uppercase text-slate-600 mb-2">過去7日間の新規登録</div>
                    <MiniBarChart data={stats.daily_signups} />
                  </div>
                </div>

                {/* シグナル内訳 */}
                <div className="bg-[#0c1424] border border-slate-700/60 rounded p-5 space-y-4">
                  <h3 className="text-[10px] font-black tracking-widest uppercase text-slate-500">30日シグナル内訳</h3>
                  <div className="grid grid-cols-2 gap-3">
                    {[
                      { label: "UP シグナル",  value: stats.signals.up_count_30d,   icon: <ArrowUp size={14} />,   color: "text-teal-400 bg-teal-900/20 border border-teal-700/30" },
                      { label: "DOWN シグナル", value: stats.signals.down_count_30d, icon: <ArrowDown size={14} />, color: "text-red-400 bg-red-900/20 border border-red-700/30" },
                      { label: "評価済み",      value: stats.signals.evaluated_30d,  icon: <Activity size={14} />, color: "text-slate-400 bg-slate-800/60 border border-slate-700/40" },
                      { label: "UP的中率",      value: stats.signals.up_accuracy_30d != null ? `${stats.signals.up_accuracy_30d}%` : "—", icon: <TrendingUp size={14} />, color: "text-violet-400 bg-violet-900/20 border border-violet-700/30" },
                    ].map(r => (
                      <div key={r.label} className={`flex items-center gap-2 rounded px-3 py-3 ${r.color}`}>
                        {r.icon}
                        <div>
                          <div className="text-base font-black tabular-nums font-mono">{typeof r.value === "number" ? r.value.toLocaleString() : r.value}</div>
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
        <div className="bg-[#0c1424] border border-slate-700/60 rounded p-5 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-[10px] font-black tracking-widest uppercase text-slate-500">
              ユーザー一覧
              {userData && <span className="ml-2 text-slate-600 font-normal normal-case tracking-normal text-xs">全 {userData.total} 件</span>}
            </h3>
            <button
              onClick={() => setUserPage(1)}
              className="p-1.5 rounded hover:bg-slate-800 transition-colors text-slate-500"
            >
              <RefreshCw size={13} />
            </button>
          </div>
          {usersLoading ? (
            <div className="space-y-2">
              {[...Array(8)].map((_, i) => <div key={i} className="skeleton h-9 rounded" />)}
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
        <div className="bg-[#0c1424] border border-slate-700/60 rounded p-5 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-[10px] font-black tracking-widest uppercase text-slate-500">日次シグナル統計</h3>
            <div className="flex items-center gap-1 bg-[#060b16] rounded p-1 border border-slate-700/60">
              {[7, 30, 90].map(d => (
                <button
                  key={d}
                  onClick={() => setSigDays(d)}
                  className={`px-3 py-1 rounded text-xs font-black tracking-widest uppercase transition-all ${
                    sigDays === d
                      ? "bg-[#0c1424] text-teal-400 border border-slate-700/60"
                      : "text-slate-600 hover:text-slate-400"
                  }`}
                >
                  {d}日
                </button>
              ))}
            </div>
          </div>
          {sigsLoading ? (
            <div className="space-y-2">{[...Array(10)].map((_, i) => <div key={i} className="skeleton h-9 rounded" />)}</div>
          ) : (
            <SignalTable rows={sigData?.data ?? []} />
          )}
        </div>
      )}

      {/* ── モデルタブ ── */}
      {tab === "model" && (
        <div className="space-y-5">
          {/* メトリクス履歴 */}
          <div className="bg-[#0c1424] border border-slate-700/60 rounded p-5 space-y-4">
            <h3 className="text-[10px] font-black tracking-widest uppercase text-slate-500">学習履歴（最新20件）</h3>
            <MetricsTable rows={metricsData?.metrics ?? []} />
          </div>

          {/* 特徴量重要度 */}
          <div className="bg-[#0c1424] border border-slate-700/60 rounded p-5 space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-[10px] font-black tracking-widest uppercase text-slate-500">特徴量重要度</h3>
                {featData?.trained_at && (
                  <p className="text-xs text-slate-600 mt-0.5 font-mono">
                    最終学習: {featData.trained_at.slice(0, 16).replace("T", " ")} ({featData.mode})
                  </p>
                )}
              </div>
              <div className="flex items-center gap-1 bg-[#060b16] rounded p-1 border border-slate-700/60">
                {[10, 20, 30].map(n => (
                  <button
                    key={n}
                    onClick={() => setFeatureN(n)}
                    className={`px-3 py-1 rounded text-xs font-black tracking-widest uppercase transition-all ${
                      featureN === n
                        ? "bg-[#0c1424] text-teal-400 border border-slate-700/60"
                        : "text-slate-600 hover:text-slate-400"
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
