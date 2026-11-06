"use client";
import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/hooks/useAuth";
import {
  Plus, Pencil, Trash2, TrendingUp, TrendingDown, Wallet,
  Home, Car, PiggyBank, Landmark, Package, RefreshCw,
  ChevronDown, ChevronUp, Zap, ArrowRight
} from "lucide-react";

// ─── シグナル型 ───────────────────────────────────────────────
interface WatchlistItem {
  code: string;
  company_name: string | null;
  signal: "buy" | "sell" | "hold" | null;
  up_probability: number | null;
  latest_price: number | null;
}

// ─── シミュレーションカード ───────────────────────────────────
function SignalSimulator({
  watchlist,
  netWorth,
}: {
  watchlist: WatchlistItem[];
  netWorth: number;
}) {
  const [investAmount, setInvestAmount] = useState(1000000);
  const buySignals = watchlist.filter(
    w => w.signal === "buy" && w.up_probability !== null && w.up_probability > 0.55
  );

  if (buySignals.length === 0) {
    return (
      <div className="text-center py-6 text-sm text-slate-500">
        現在ウォッチリストに「買い」シグナルの銘柄がありません
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <span className="text-xs text-slate-500 shrink-0">投資額</span>
        <input
          type="range"
          min={100000}
          max={10000000}
          step={100000}
          value={investAmount}
          onChange={e => setInvestAmount(Number(e.target.value))}
          className="flex-1 accent-teal-500"
        />
        <span className="text-sm font-black text-white w-20 text-right font-mono">
          {(investAmount / 10000).toFixed(0)}万円
        </span>
      </div>

      <div className="space-y-2">
        {buySignals.slice(0, 5).map(item => {
          const prob = item.up_probability!;
          const expectedReturn = prob * 0.03 - (1 - prob) * 0.02;
          const expectedGain = investAmount * expectedReturn;
          const newNetWorth = netWorth + expectedGain;
          const changeRate = netWorth > 0 ? (expectedGain / netWorth) * 100 : 0;
          const isPositive = expectedGain >= 0;

          return (
            <div key={item.code} className="flex items-center gap-3 p-3 bg-[#060b16] rounded">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-black text-teal-400 font-mono">{item.code}</span>
                  <span className="text-xs text-slate-500 truncate">{item.company_name}</span>
                </div>
                <div className="flex items-center gap-2 mt-0.5">
                  <div className="h-1.5 rounded-full bg-slate-700 flex-1 overflow-hidden">
                    <div
                      className="h-full bg-teal-500 rounded-full"
                      style={{ width: `${prob * 100}%` }}
                    />
                  </div>
                  <span className="text-xs text-slate-500 font-mono">{(prob * 100).toFixed(0)}%</span>
                </div>
              </div>
              <ArrowRight size={12} className="text-slate-600 shrink-0" />
              <div className="text-right shrink-0">
                <div className={`text-sm font-black font-mono ${isPositive ? "text-teal-400" : "text-red-400"}`}>
                  {isPositive ? "+" : ""}{(expectedGain / 10000).toFixed(1)}万円
                </div>
                <div className="text-xs text-slate-500 font-mono">
                  純資産 {isPositive ? "+" : ""}{changeRate.toFixed(2)}%
                </div>
              </div>
            </div>
          );
        })}
      </div>

      <p className="text-xs text-slate-600 text-center">
        ※ 期待値計算（上昇確率×+3% − 下降確率×2%）。投資判断の参考に限ります。
      </p>
    </div>
  );
}

// ─── 型定義 ───────────────────────────────────────────────────
type Category = "cash" | "stock" | "realestate" | "vehicle" | "other" | "liability";

interface Account {
  id: number;
  name: string;
  category: Category;
  currency: string;
  note: string | null;
  is_active: boolean;
  sort_order: number;
  latest_amount: number | null;
  latest_date: string | null;
}

interface Summary {
  by_category: Record<string, number>;
  total_assets: number;
  total_liabilities: number;
  net_worth: number;
}

interface HistoryPoint {
  month: string;
  assets: number;
  liabilities: number;
  net_worth: number;
}

// ─── カテゴリ設定 ─────────────────────────────────────────────
const CATEGORY_CONFIG: Record<Category, {
  label: string; color: string; bg: string; icon: React.ReactNode; isLiability?: boolean
}> = {
  cash:        { label: "現金・預金",     color: "text-blue-400",   bg: "bg-blue-900/20",   icon: <PiggyBank size={16} /> },
  stock:       { label: "株式・投資信託", color: "text-teal-400",   bg: "bg-teal-900/20",   icon: <TrendingUp size={16} /> },
  realestate:  { label: "不動産",         color: "text-amber-400",  bg: "bg-amber-900/20",  icon: <Home size={16} /> },
  vehicle:     { label: "車・乗り物",     color: "text-purple-400", bg: "bg-purple-900/20", icon: <Car size={16} /> },
  other:       { label: "その他資産",     color: "text-teal-400",   bg: "bg-teal-900/20",   icon: <Package size={16} /> },
  liability:   { label: "負債・ローン",   color: "text-red-400",    bg: "bg-red-900/20",    icon: <Landmark size={16} />, isLiability: true },
};

// ─── ユーティリティ ──────────────────────────────────────────
const fmt = (n: number) =>
  new Intl.NumberFormat("ja-JP", { style: "currency", currency: "JPY", maximumFractionDigits: 0 }).format(n);

const fmtShort = (n: number) => {
  if (Math.abs(n) >= 1e8) return `${(n / 1e8).toFixed(1)}億円`;
  if (Math.abs(n) >= 1e4) return `${(n / 1e4).toFixed(0)}万円`;
  return fmt(n);
};

const today = () => new Date().toISOString().slice(0, 10);

// ─── ミニ棒グラフ ────────────────────────────────────────────
function MiniBar({ data }: { data: HistoryPoint[] }) {
  if (data.length < 2) return null;
  const values = data.map(d => d.net_worth);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;

  return (
    <div className="flex items-end gap-0.5 h-12">
      {data.map((d, i) => {
        const h = Math.max(4, ((d.net_worth - min) / range) * 44);
        const isLatest = i === data.length - 1;
        const isPositive = d.net_worth >= 0;
        return (
          <div key={d.month} className="group relative flex-1" title={`${d.month.slice(0, 7)}: ${fmtShort(d.net_worth)}`}>
            <div
              className={`rounded-sm transition-all ${
                isLatest
                  ? isPositive ? "bg-teal-500" : "bg-red-500"
                  : isPositive ? "bg-teal-700" : "bg-red-700"
              }`}
              style={{ height: `${h}px` }}
            />
          </div>
        );
      })}
    </div>
  );
}

// ─── メインコンポーネント ────────────────────────────────────
export default function AssetsPage() {
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();

  const [accounts, setAccounts] = useState<Account[]>([]);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [history, setHistory] = useState<HistoryPoint[]>([]);
  const [watchlist, setWatchlist] = useState<WatchlistItem[]>([]);
  const [loading, setLoading] = useState(true);

  const [showAddAccount, setShowAddAccount] = useState(false);
  const [editAccount, setEditAccount] = useState<Account | null>(null);
  const [newName, setNewName] = useState("");
  const [newCategory, setNewCategory] = useState<Category>("cash");
  const [newNote, setNewNote] = useState("");

  const [activeInput, setActiveInput] = useState<number | null>(null);
  const [inputAmount, setInputAmount] = useState("");
  const [inputMemo, setInputMemo] = useState("");
  const [inputDate, setInputDate] = useState(today());

  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({});

  const apiBase = process.env.NEXT_PUBLIC_API_URL ?? "";

  const apiFetch = useCallback(async (path: string, opts?: RequestInit) => {
    const token = localStorage.getItem("token");
    const res = await fetch(`${apiBase}${path}`, {
      ...opts,
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}`, ...(opts?.headers ?? {}) },
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  }, [apiBase]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [acctRes, sumRes, histRes, wlRes] = await Promise.all([
        apiFetch("/api/assets/accounts"),
        apiFetch("/api/assets/summary"),
        apiFetch("/api/assets/history?months=12"),
        apiFetch("/api/watchlist").catch(() => ({ watchlist: [] })),
      ]);
      setAccounts(acctRes.accounts);
      setSummary(sumRes);
      setHistory(histRes.history);
      setWatchlist(wlRes.watchlist ?? []);
    } catch {}
    setLoading(false);
  }, [apiFetch]);

  useEffect(() => {
    if (!authLoading && !user) router.replace("/auth");
  }, [authLoading, user, router]);

  useEffect(() => {
    if (user) load();
  }, [user, load]);

  const handleCreateAccount = async () => {
    if (!newName.trim()) return;
    try {
      await apiFetch("/api/assets/accounts", {
        method: "POST",
        body: JSON.stringify({ name: newName.trim(), category: newCategory, note: newNote }),
      });
      setShowAddAccount(false);
      setNewName(""); setNewNote("");
      await load();
    } catch (e: any) {
      alert("エラー: " + e.message);
    }
  };

  const handleDeleteAccount = async (id: number) => {
    if (!confirm("この資産項目を削除しますか？記録も全て削除されます。")) return;
    try {
      await apiFetch(`/api/assets/accounts/${id}`, { method: "DELETE" });
      await load();
    } catch (e: any) {
      alert("エラー: " + e.message);
    }
  };

  const handleUpsertSnapshot = async (accountId: number) => {
    const amount = parseFloat(inputAmount.replace(/,/g, ""));
    if (isNaN(amount)) return;
    try {
      await apiFetch("/api/assets/snapshots", {
        method: "POST",
        body: JSON.stringify({
          account_id: accountId,
          snapshot_date: inputDate,
          amount,
          memo: inputMemo || null,
        }),
      });
      setActiveInput(null);
      setInputAmount(""); setInputMemo("");
      await load();
    } catch (e: any) {
      alert("エラー: " + e.message);
    }
  };

  if (authLoading || loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="w-8 h-8 border-2 border-teal-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  const byCategory = Object.keys(CATEGORY_CONFIG).reduce<Record<string, Account[]>>((acc, cat) => {
    acc[cat] = accounts.filter(a => a.category === cat && a.is_active);
    return acc;
  }, {});

  const netWorth = summary?.net_worth ?? 0;
  const netPositive = netWorth >= 0;
  const lastMonth = history.length >= 2 ? history[history.length - 2].net_worth : null;
  const netChange = lastMonth !== null ? netWorth - lastMonth : null;

  return (
    <div className="max-w-4xl mx-auto px-4 py-8 space-y-6">

      {/* ─── ヘッダー ─── */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-black tracking-tight text-white flex items-center gap-2">
            <Wallet className="text-teal-500" size={24} />
            資産管理
          </h1>
          <p className="text-sm text-slate-500 mt-0.5">現金・不動産・車・株まで、全財産を一括管理</p>
        </div>
        <button
          onClick={() => { setShowAddAccount(true); setEditAccount(null); }}
          className="flex items-center gap-1.5 bg-teal-600 hover:bg-teal-500 text-white px-4 py-2 rounded text-xs font-black tracking-widest uppercase transition-colors"
        >
          <Plus size={15} /> 資産を追加
        </button>
      </div>

      {/* ─── 純資産サマリーカード ─── */}
      <div className="rounded border border-slate-700/60 bg-[#0c1424] p-6">
        <div className="flex flex-col md:flex-row md:items-center gap-6">
          <div className="flex-1">
            <p className="text-[10px] font-black tracking-widest uppercase text-slate-500 mb-1">純資産（ネットワース）</p>
            <div className={`text-4xl font-black font-mono ${netPositive ? "text-teal-400" : "text-red-400"}`}>
              {fmtShort(netWorth)}
            </div>
            {netChange !== null && (
              <div className={`flex items-center gap-1 mt-1 text-sm font-semibold font-mono ${netChange >= 0 ? "text-teal-500" : "text-red-400"}`}>
                {netChange >= 0 ? <TrendingUp size={14} /> : <TrendingDown size={14} />}
                前月比 {netChange >= 0 ? "+" : ""}{fmtShort(netChange)}
              </div>
            )}
          </div>

          <div className="flex gap-6">
            <div className="text-center">
              <p className="text-[10px] font-black tracking-widest uppercase text-slate-500 mb-1">総資産</p>
              <p className="text-xl font-black font-mono text-white">{fmtShort(summary?.total_assets ?? 0)}</p>
            </div>
            <div className="text-center">
              <p className="text-[10px] font-black tracking-widest uppercase text-slate-500 mb-1">総負債</p>
              <p className="text-xl font-black font-mono text-red-400">{fmtShort(summary?.total_liabilities ?? 0)}</p>
            </div>
          </div>

          <div className="w-32">
            <p className="text-[10px] font-black tracking-widest uppercase text-slate-500 mb-1">推移（12ヶ月）</p>
            <MiniBar data={history} />
          </div>
        </div>

        {summary && summary.total_assets > 0 && (
          <div className="mt-4">
            <div className="flex h-2 rounded-full overflow-hidden gap-0.5">
              {(["cash","stock","realestate","vehicle","other"] as Category[]).map(cat => {
                const v = summary.by_category[cat] ?? 0;
                const pct = (v / summary.total_assets) * 100;
                if (pct < 1) return null;
                const colorMap: Record<string, string> = {
                  cash: "bg-blue-500", stock: "bg-teal-500", realestate: "bg-amber-500",
                  vehicle: "bg-purple-500", other: "bg-teal-400",
                };
                return (
                  <div
                    key={cat}
                    title={`${CATEGORY_CONFIG[cat].label}: ${fmtShort(v)} (${pct.toFixed(0)}%)`}
                    className={`${colorMap[cat]} transition-all`}
                    style={{ width: `${pct}%` }}
                  />
                );
              })}
            </div>
            <div className="flex flex-wrap gap-x-4 gap-y-1 mt-2">
              {(["cash","stock","realestate","vehicle","other"] as Category[]).map(cat => {
                const v = summary.by_category[cat] ?? 0;
                if (!v) return null;
                const cfg = CATEGORY_CONFIG[cat];
                return (
                  <span key={cat} className={`text-xs flex items-center gap-1 ${cfg.color}`}>
                    {cfg.icon} {cfg.label} {fmtShort(v)}
                  </span>
                );
              })}
            </div>
          </div>
        )}
      </div>

      {/* ─── AIシグナル × 資産シミュレーター ─── */}
      <div className="rounded border border-teal-700/40 bg-teal-900/10 overflow-hidden">
        <div className="px-4 pt-4 pb-3 flex items-center gap-2 border-b border-teal-700/30">
          <div className="w-7 h-7 rounded bg-teal-600 flex items-center justify-center shrink-0">
            <Zap size={14} className="text-white" />
          </div>
          <div>
            <p className="text-sm font-black text-teal-300 tracking-wide">AIシグナル × 純資産シミュレーター</p>
            <p className="text-xs text-teal-500">ウォッチリストの買いシグナル銘柄に投資したら純資産はどう変わる？</p>
          </div>
        </div>
        <div className="p-4">
          <SignalSimulator watchlist={watchlist} netWorth={netWorth} />
        </div>
      </div>

      {/* ─── 口座一覧（カテゴリ別）─── */}
      {(Object.entries(CATEGORY_CONFIG) as [Category, typeof CATEGORY_CONFIG[Category]][]).map(([cat, cfg]) => {
        const items = byCategory[cat] ?? [];
        const total = items.reduce((s, a) => s + (a.latest_amount ?? 0), 0);
        const isOpen = !collapsed[cat];

        return (
          <div key={cat} className="rounded border border-slate-700/60 overflow-hidden">
            <button
              onClick={() => setCollapsed(p => ({ ...p, [cat]: !p[cat] }))}
              className="w-full flex items-center justify-between px-4 py-3 bg-[#060b16] hover:bg-slate-800/60 transition-colors"
            >
              <div className="flex items-center gap-2">
                <span className={`${cfg.color}`}>{cfg.icon}</span>
                <span className="font-semibold text-sm text-slate-200">{cfg.label}</span>
                <span className="text-[10px] text-slate-500 bg-slate-700/50 rounded px-2 py-0.5 font-black tracking-widest uppercase">{items.length}</span>
              </div>
              <div className="flex items-center gap-3">
                <span className={`text-sm font-black font-mono ${cfg.isLiability ? "text-red-400" : "text-slate-200"}`}>
                  {cfg.isLiability ? "−" : ""}{fmtShort(total)}
                </span>
                {isOpen ? <ChevronUp size={14} className="text-slate-500" /> : <ChevronDown size={14} className="text-slate-500" />}
              </div>
            </button>

            {isOpen && (
              <div className="divide-y divide-slate-700/40 bg-[#0c1424]">
                {items.length === 0 ? (
                  <div className="px-4 py-6 text-center">
                    <p className="text-sm text-slate-500">まだ登録されていません</p>
                    <button
                      onClick={() => { setNewCategory(cat); setShowAddAccount(true); }}
                      className="mt-2 text-xs text-teal-500 hover:text-teal-400 font-black tracking-wide transition-colors"
                    >
                      + {cfg.label}を追加
                    </button>
                  </div>
                ) : (
                  items.map(acct => (
                    <div key={acct.id} className="px-4 py-3">
                      <div className="flex items-center justify-between">
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium text-slate-200 truncate">{acct.name}</p>
                          {acct.note && <p className="text-xs text-slate-500 truncate">{acct.note}</p>}
                          {acct.latest_date && (
                            <p className="text-xs text-slate-600 font-mono">{acct.latest_date} 時点</p>
                          )}
                        </div>

                        <div className="flex items-center gap-3 shrink-0 ml-3">
                          {acct.latest_amount !== null ? (
                            <span className={`text-base font-black font-mono ${cfg.isLiability ? "text-red-400" : "text-white"}`}>
                              {fmtShort(acct.latest_amount)}
                            </span>
                          ) : (
                            <span className="text-sm text-slate-600">未記録</span>
                          )}

                          <button
                            onClick={() => {
                              setActiveInput(acct.id === activeInput ? null : acct.id);
                              setInputAmount(acct.latest_amount?.toString() ?? "");
                              setInputDate(today());
                              setInputMemo("");
                            }}
                            className="w-7 h-7 rounded flex items-center justify-center text-slate-500 hover:text-teal-400 hover:bg-teal-900/30 transition-colors"
                            title="残高を更新"
                          >
                            <Pencil size={13} />
                          </button>
                          <button
                            onClick={() => handleDeleteAccount(acct.id)}
                            className="w-7 h-7 rounded flex items-center justify-center text-slate-500 hover:text-red-400 hover:bg-red-900/20 transition-colors"
                            title="削除"
                          >
                            <Trash2 size={13} />
                          </button>
                        </div>
                      </div>

                      {activeInput === acct.id && (
                        <div className="mt-2 p-3 bg-[#060b16] rounded space-y-2">
                          <div className="flex gap-2">
                            <input
                              type="number"
                              value={inputAmount}
                              onChange={e => setInputAmount(e.target.value)}
                              placeholder="残高（円）"
                              className="flex-1 bg-[#0c1424] border border-slate-700/60 rounded px-3 py-1.5 text-sm text-slate-200 focus:outline-none focus:ring-1 focus:ring-teal-500/50 font-mono"
                            />
                            <input
                              type="date"
                              value={inputDate}
                              onChange={e => setInputDate(e.target.value)}
                              className="bg-[#0c1424] border border-slate-700/60 rounded px-3 py-1.5 text-sm text-slate-200 focus:outline-none focus:ring-1 focus:ring-teal-500/50"
                            />
                          </div>
                          <input
                            type="text"
                            value={inputMemo}
                            onChange={e => setInputMemo(e.target.value)}
                            placeholder="メモ（任意）"
                            className="w-full bg-[#0c1424] border border-slate-700/60 rounded px-3 py-1.5 text-sm text-slate-200 focus:outline-none focus:ring-1 focus:ring-teal-500/50"
                          />
                          <div className="flex gap-2 justify-end">
                            <button
                              onClick={() => setActiveInput(null)}
                              className="px-3 py-1.5 text-xs text-slate-500 hover:text-slate-300 rounded transition-colors"
                            >
                              キャンセル
                            </button>
                            <button
                              onClick={() => handleUpsertSnapshot(acct.id)}
                              className="px-3 py-1.5 text-xs bg-teal-600 hover:bg-teal-500 text-white rounded font-black tracking-widest uppercase transition-colors"
                            >
                              保存
                            </button>
                          </div>
                        </div>
                      )}
                    </div>
                  ))
                )}

                {items.length > 0 && (
                  <div className="px-4 py-2">
                    <button
                      onClick={() => { setNewCategory(cat); setShowAddAccount(true); }}
                      className="text-xs text-slate-500 hover:text-teal-400 transition-colors flex items-center gap-1"
                    >
                      <Plus size={12} /> {cfg.label}を追加
                    </button>
                  </div>
                )}
              </div>
            )}
          </div>
        );
      })}

      {/* ─── 口座追加モーダル ─── */}
      {showAddAccount && (
        <div className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-4" onClick={() => setShowAddAccount(false)}>
          <div className="bg-[#0c1424] border border-slate-700/60 rounded p-6 w-full max-w-sm shadow-xl" onClick={e => e.stopPropagation()}>
            <h2 className="text-lg font-black tracking-tight text-white mb-4">資産を追加</h2>

            <div className="space-y-3">
              <div>
                <label className="text-[10px] font-black tracking-widest uppercase text-slate-500 block mb-1">名前</label>
                <input
                  autoFocus
                  value={newName}
                  onChange={e => setNewName(e.target.value)}
                  placeholder="例: 三菱UFJ普通預金、自宅、マイカー..."
                  className="w-full border border-slate-700/60 rounded px-3 py-2 text-sm bg-[#060b16] text-slate-200 focus:outline-none focus:ring-1 focus:ring-teal-500/50"
                />
              </div>

              <div>
                <label className="text-[10px] font-black tracking-widest uppercase text-slate-500 block mb-1">カテゴリ</label>
                <div className="grid grid-cols-3 gap-2">
                  {(Object.entries(CATEGORY_CONFIG) as [Category, typeof CATEGORY_CONFIG[Category]][]).map(([cat, cfg]) => (
                    <button
                      key={cat}
                      onClick={() => setNewCategory(cat)}
                      className={`flex flex-col items-center gap-1 px-2 py-2.5 rounded border text-xs font-semibold transition-all ${
                        newCategory === cat
                          ? `border-teal-500/60 ${cfg.bg} ${cfg.color}`
                          : "border-slate-700/60 text-slate-500 hover:border-teal-500/40"
                      }`}
                    >
                      {cfg.icon}
                      <span className="text-center leading-tight">{cfg.label}</span>
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <label className="text-[10px] font-black tracking-widest uppercase text-slate-500 block mb-1">メモ（任意）</label>
                <input
                  value={newNote}
                  onChange={e => setNewNote(e.target.value)}
                  placeholder="例: 住宅ローン残高、駐車場代など"
                  className="w-full border border-slate-700/60 rounded px-3 py-2 text-sm bg-[#060b16] text-slate-200 focus:outline-none focus:ring-1 focus:ring-teal-500/50"
                />
              </div>
            </div>

            <div className="flex gap-2 mt-5">
              <button
                onClick={() => setShowAddAccount(false)}
                className="flex-1 py-2.5 rounded border border-slate-700/60 text-sm text-slate-400 hover:bg-slate-800/60 transition-colors"
              >
                キャンセル
              </button>
              <button
                onClick={handleCreateAccount}
                disabled={!newName.trim()}
                className="flex-1 py-2.5 rounded bg-teal-600 hover:bg-teal-500 disabled:opacity-40 text-white text-xs font-black tracking-widest uppercase transition-colors"
              >
                追加
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ─── 空状態 ─── */}
      {accounts.length === 0 && !loading && (
        <div className="text-center py-16 space-y-4">
          <div className="w-16 h-16 rounded bg-slate-800/60 flex items-center justify-center mx-auto">
            <Wallet size={28} className="text-slate-500" />
          </div>
          <div>
            <p className="font-black text-slate-300">まだ資産が登録されていません</p>
            <p className="text-sm text-slate-500 mt-1">現金・株・不動産・車・ローンを登録して純資産を把握しましょう</p>
          </div>
          <button
            onClick={() => setShowAddAccount(true)}
            className="inline-flex items-center gap-2 bg-teal-600 hover:bg-teal-500 text-white px-6 py-2.5 rounded text-xs font-black tracking-widest uppercase transition-colors"
          >
            <Plus size={15} /> 最初の資産を追加
          </button>
        </div>
      )}

    </div>
  );
}
