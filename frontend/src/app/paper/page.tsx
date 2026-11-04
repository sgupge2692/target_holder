"use client";
import { useState } from "react";
import useSWR, { mutate } from "swr";
import {
  getPaperTrades, getPaperTradeStats, createPaperTrade, closePaperTrade, deletePaperTrade,
  type PaperTrade,
} from "@/lib/api";
import { useAuth } from "@/hooks/useAuth";
import { SignalBadge } from "@/components/SignalBadge";
import {
  TrendingUp, TrendingDown, Plus, X, CheckCircle, Trash2,
  BarChart3, Trophy, AlertTriangle, Loader2,
} from "lucide-react";
import clsx from "clsx";

// ── 損益カラー ────────────────────────────────────────────────────────────────
const pnlColor = (v: number | null) =>
  v == null ? "text-slate-400" : v > 0 ? "text-teal-400" : v < 0 ? "text-red-400" : "text-slate-400";

const pnlStr = (v: number | null, suffix = "") =>
  v == null ? "—" : `${v > 0 ? "+" : ""}${v.toLocaleString()}${suffix}`;

// ── 新規トレード登録フォーム ─────────────────────────────────────────────────
function NewTradeModal({ onClose, onCreated }: { onClose: () => void; onCreated: () => void }) {
  const [form, setForm] = useState({
    code: "", signal: "UP" as "UP" | "DOWN",
    entry_price: "", shares: "100",
    entry_date: new Date().toISOString().slice(0, 10),
    note: "",
  });
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true); setErr("");
    try {
      await createPaperTrade({
        code: form.code.toUpperCase(),
        signal: form.signal,
        entry_price: parseFloat(form.entry_price),
        shares: parseInt(form.shares),
        entry_date: form.entry_date,
        note: form.note || undefined,
      });
      onCreated();
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : "エラーが発生しました");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4" onClick={onClose}>
      <div className="w-full max-w-sm bg-[#0c1424] border border-slate-700 rounded shadow-2xl" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-700">
          <span className="text-sm font-black tracking-widest uppercase text-white">New Trade</span>
          <button onClick={onClose} className="p-1 hover:bg-slate-700 rounded transition-colors"><X size={16} className="text-slate-400" /></button>
        </div>
        <form onSubmit={submit} className="p-5 space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-[10px] font-black tracking-widest uppercase text-slate-500 block mb-1">銘柄コード</label>
              <input required value={form.code} onChange={e => setForm(f => ({ ...f, code: e.target.value }))}
                placeholder="7203"
                className="w-full bg-[#060b16] border border-slate-700 rounded px-3 py-2 text-sm font-mono text-white focus:border-teal-600 focus:outline-none uppercase" />
            </div>
            <div>
              <label className="text-[10px] font-black tracking-widest uppercase text-slate-500 block mb-1">シグナル</label>
              <div className="flex gap-2">
                {(["UP", "DOWN"] as const).map(s => (
                  <button key={s} type="button" onClick={() => setForm(f => ({ ...f, signal: s }))}
                    className={clsx("flex-1 py-2 rounded text-[10px] font-black tracking-wider uppercase transition-colors",
                      form.signal === s
                        ? s === "UP" ? "bg-teal-600 text-white" : "bg-red-600 text-white"
                        : "bg-slate-800 text-slate-400 hover:bg-slate-700"
                    )}>{s}</button>
                ))}
              </div>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-[10px] font-black tracking-widest uppercase text-slate-500 block mb-1">エントリー価格 (¥)</label>
              <input required type="number" step="0.01" value={form.entry_price}
                onChange={e => setForm(f => ({ ...f, entry_price: e.target.value }))}
                placeholder="3850"
                className="w-full bg-[#060b16] border border-slate-700 rounded px-3 py-2 text-sm font-mono text-white focus:border-teal-600 focus:outline-none" />
            </div>
            <div>
              <label className="text-[10px] font-black tracking-widest uppercase text-slate-500 block mb-1">株数</label>
              <input type="number" value={form.shares} onChange={e => setForm(f => ({ ...f, shares: e.target.value }))}
                className="w-full bg-[#060b16] border border-slate-700 rounded px-3 py-2 text-sm font-mono text-white focus:border-teal-600 focus:outline-none" />
            </div>
          </div>
          <div>
            <label className="text-[10px] font-black tracking-widest uppercase text-slate-500 block mb-1">エントリー日</label>
            <input type="date" value={form.entry_date} onChange={e => setForm(f => ({ ...f, entry_date: e.target.value }))}
              className="w-full bg-[#060b16] border border-slate-700 rounded px-3 py-2 text-sm font-mono text-white focus:border-teal-600 focus:outline-none" />
          </div>
          <div>
            <label className="text-[10px] font-black tracking-widest uppercase text-slate-500 block mb-1">メモ（任意）</label>
            <input value={form.note} onChange={e => setForm(f => ({ ...f, note: e.target.value }))}
              placeholder="ICT OB から反発"
              className="w-full bg-[#060b16] border border-slate-700 rounded px-3 py-2 text-sm text-slate-200 focus:border-teal-600 focus:outline-none" />
          </div>
          {err && <p className="text-xs text-red-400">{err}</p>}
          <button type="submit" disabled={loading}
            className="w-full bg-teal-600 hover:bg-teal-500 text-white font-black text-sm py-2.5 rounded transition-colors flex items-center justify-center gap-2 disabled:opacity-50">
            {loading ? <Loader2 size={16} className="animate-spin" /> : <Plus size={16} />}
            登録する
          </button>
        </form>
      </div>
    </div>
  );
}

// ── 決済モーダル ──────────────────────────────────────────────────────────────
function CloseModal({ trade, onClose, onDone }: { trade: PaperTrade; onClose: () => void; onDone: () => void }) {
  const [exitPrice, setExitPrice] = useState("");
  const [exitDate, setExitDate] = useState(new Date().toISOString().slice(0, 10));
  const [loading, setLoading] = useState(false);

  const previewPnl = exitPrice
    ? (trade.signal === "UP" ? parseFloat(exitPrice) - trade.entry_price : trade.entry_price - parseFloat(exitPrice)) * trade.shares
    : null;

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    try {
      await closePaperTrade(trade.id, parseFloat(exitPrice), exitDate);
      onDone();
    } finally { setLoading(false); }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4" onClick={onClose}>
      <div className="w-full max-w-sm bg-[#0c1424] border border-slate-700 rounded shadow-2xl" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-700">
          <div>
            <span className="text-sm font-black tracking-widest uppercase text-white">決済 — </span>
            <span className="font-mono text-teal-400 text-sm">{trade.code}</span>
          </div>
          <button onClick={onClose} className="p-1 hover:bg-slate-700 rounded"><X size={16} className="text-slate-400" /></button>
        </div>
        <form onSubmit={submit} className="p-5 space-y-4">
          <div className="bg-[#060b16] rounded p-3 text-xs space-y-1">
            <div className="flex justify-between"><span className="text-slate-500">シグナル</span><SignalBadge signal={trade.signal} /></div>
            <div className="flex justify-between"><span className="text-slate-500">エントリー</span><span className="font-mono font-black text-white">¥{trade.entry_price.toLocaleString()}</span></div>
            <div className="flex justify-between"><span className="text-slate-500">株数</span><span className="font-mono font-black text-white">{trade.shares.toLocaleString()} 株</span></div>
          </div>
          <div>
            <label className="text-[10px] font-black tracking-widest uppercase text-slate-500 block mb-1">決済価格 (¥)</label>
            <input required type="number" step="0.01" value={exitPrice} onChange={e => setExitPrice(e.target.value)}
              placeholder="3920"
              className="w-full bg-[#060b16] border border-slate-700 rounded px-3 py-2 text-sm font-mono text-white focus:border-teal-600 focus:outline-none" />
          </div>
          <div>
            <label className="text-[10px] font-black tracking-widest uppercase text-slate-500 block mb-1">決済日</label>
            <input type="date" value={exitDate} onChange={e => setExitDate(e.target.value)}
              className="w-full bg-[#060b16] border border-slate-700 rounded px-3 py-2 text-sm font-mono text-white focus:border-teal-600 focus:outline-none" />
          </div>
          {previewPnl != null && (
            <div className={clsx("text-center font-black text-lg font-mono", previewPnl >= 0 ? "text-teal-400" : "text-red-400")}>
              {pnlStr(previewPnl, " 円")}
              <span className="text-xs text-slate-500 ml-2">（予定損益）</span>
            </div>
          )}
          <button type="submit" disabled={loading}
            className="w-full bg-teal-600 hover:bg-teal-500 text-white font-black text-sm py-2.5 rounded transition-colors flex items-center justify-center gap-2 disabled:opacity-50">
            {loading ? <Loader2 size={16} className="animate-spin" /> : <CheckCircle size={16} />}
            決済確定
          </button>
        </form>
      </div>
    </div>
  );
}

// ── トレード行 ────────────────────────────────────────────────────────────────
function TradeRow({ trade, onClose, onDelete }: {
  trade: PaperTrade; onClose: (t: PaperTrade) => void; onDelete: (id: number) => void;
}) {
  return (
    <tr className="border-b border-slate-800 hover:bg-slate-800/30 transition-colors">
      <td className="px-4 py-3">
        <div className="font-mono text-xs text-slate-500 uppercase tracking-wider">{trade.code}</div>
        <div className="text-xs text-slate-300 truncate max-w-[120px]">{trade.company_name ?? ""}</div>
      </td>
      <td className="px-4 py-3 text-center"><SignalBadge signal={trade.signal} /></td>
      <td className="px-4 py-3 text-right font-mono text-sm text-slate-200">¥{trade.entry_price.toLocaleString()}</td>
      <td className="px-4 py-3 text-right font-mono text-sm">
        {trade.exit_price ? <span className="text-slate-200">¥{trade.exit_price.toLocaleString()}</span> : <span className="text-slate-600">—</span>}
      </td>
      <td className="px-4 py-3 text-right font-mono text-sm">
        <span className="text-slate-500 text-xs">{trade.shares.toLocaleString()}</span>
      </td>
      <td className="px-4 py-3 text-right font-mono text-sm font-black">
        <span className={pnlColor(trade.pnl)}>{pnlStr(trade.pnl, "円")}</span>
        {trade.pnl_pct != null && (
          <div className={clsx("text-[10px]", pnlColor(trade.pnl_pct))}>
            {pnlStr(trade.pnl_pct, "%")}
          </div>
        )}
      </td>
      <td className="px-4 py-3 text-xs text-slate-500">{trade.entry_date}</td>
      <td className="px-4 py-3">
        <div className="flex items-center gap-1 justify-end">
          {trade.status === "open" && (
            <button onClick={() => onClose(trade)}
              className="px-2 py-1 rounded text-[10px] font-black tracking-wider uppercase text-teal-400 hover:bg-teal-900/30 transition-colors">
              決済
            </button>
          )}
          <button onClick={() => onDelete(trade.id)}
            className="p-1 rounded text-slate-600 hover:text-red-400 hover:bg-red-900/20 transition-colors">
            <Trash2 size={13} />
          </button>
        </div>
      </td>
    </tr>
  );
}

// ── メインページ ──────────────────────────────────────────────────────────────
export default function PaperTradePage() {
  const { user } = useAuth();
  const [tab, setTab] = useState<"open" | "closed" | "all">("open");
  const [showNew, setShowNew] = useState(false);
  const [closeTarget, setCloseTarget] = useState<PaperTrade | null>(null);

  const { data: trades, isLoading } = useSWR(["paper-trades", tab], () => getPaperTrades(tab));
  const { data: stats } = useSWR(user ? "paper-stats" : null, getPaperTradeStats);

  function refresh() {
    mutate(["paper-trades", "open"]);
    mutate(["paper-trades", "closed"]);
    mutate(["paper-trades", "all"]);
    mutate("paper-stats");
  }

  async function handleDelete(id: number) {
    if (!confirm("このトレードを削除しますか？")) return;
    await deletePaperTrade(id);
    refresh();
  }

  if (!user) return null;

  return (
    <div className="space-y-5">
      {/* ヘッダー */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-xl font-black tracking-tight text-white uppercase">Paper Trade</h1>
          <p className="text-xs text-slate-500 mt-0.5">シグナルに基づく仮想売買の記録・損益管理</p>
        </div>
        <button onClick={() => setShowNew(true)}
          className="flex items-center gap-1.5 px-4 py-2 bg-teal-600 hover:bg-teal-500 text-white text-xs font-black tracking-widest uppercase rounded transition-colors">
          <Plus size={14} />
          新規登録
        </button>
      </div>

      {/* KPI */}
      {stats && stats.total > 0 && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <div className="rounded border border-slate-700/60 bg-[#0c1424] p-4">
            <div className="text-[10px] font-black tracking-widest uppercase text-slate-500 mb-1">勝率</div>
            <div className="text-2xl font-black font-mono text-teal-400">{stats.win_rate}%</div>
            <div className="text-[10px] text-slate-500">{stats.win}勝 {stats.loss}敗</div>
          </div>
          <div className="rounded border border-slate-700/60 bg-[#0c1424] p-4">
            <div className="text-[10px] font-black tracking-widest uppercase text-slate-500 mb-1">総損益</div>
            <div className={clsx("text-2xl font-black font-mono", pnlColor(stats.total_pnl))}>{pnlStr(stats.total_pnl, "円")}</div>
            <div className="text-[10px] text-slate-500">クローズ済み {stats.total}件</div>
          </div>
          <div className="rounded border border-slate-700/60 bg-[#0c1424] p-4">
            <div className="text-[10px] font-black tracking-widest uppercase text-slate-500 mb-1">平均損益率</div>
            <div className={clsx("text-2xl font-black font-mono", pnlColor(stats.avg_pnl_pct))}>{pnlStr(stats.avg_pnl_pct, "%")}</div>
            <div className="text-[10px] text-slate-500">1トレード平均</div>
          </div>
          <div className="rounded border border-slate-700/60 bg-[#0c1424] p-4">
            <div className="text-[10px] font-black tracking-widest uppercase text-slate-500 mb-1">ベスト / ワースト</div>
            <div className="font-mono text-sm font-black">
              <span className="text-teal-400">{pnlStr(stats.best_pnl ?? null, "円")}</span>
              <span className="text-slate-600 mx-1">/</span>
              <span className="text-red-400">{pnlStr(stats.worst_pnl ?? null, "円")}</span>
            </div>
          </div>
        </div>
      )}

      {/* タブ */}
      <div className="flex gap-1 bg-[#0c1424] border border-slate-700/60 p-1 rounded w-fit">
        {(["open", "closed", "all"] as const).map(t => (
          <button key={t} onClick={() => setTab(t)}
            className={clsx("px-3 py-1 rounded text-xs font-black tracking-widest uppercase transition-all",
              tab === t ? "bg-teal-600 text-white" : "text-slate-500 hover:text-slate-300"
            )}>
            {t === "open" ? "オープン" : t === "closed" ? "クローズ" : "全件"}
          </button>
        ))}
      </div>

      {/* テーブル */}
      {isLoading ? (
        <div className="flex justify-center py-16"><Loader2 size={28} className="animate-spin text-teal-600" /></div>
      ) : trades && trades.length > 0 ? (
        <div className="rounded border border-slate-700/60 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="terminal-table w-full text-sm">
              <thead>
                <tr className="border-b border-slate-700">
                  <th className="px-4 py-3 text-left">銘柄</th>
                  <th className="px-4 py-3 text-center">シグナル</th>
                  <th className="px-4 py-3 text-right">エントリー</th>
                  <th className="px-4 py-3 text-right">決済</th>
                  <th className="px-4 py-3 text-right">株数</th>
                  <th className="px-4 py-3 text-right">損益</th>
                  <th className="px-4 py-3 text-left">日付</th>
                  <th className="px-4 py-3"></th>
                </tr>
              </thead>
              <tbody>
                {trades.map(t => (
                  <TradeRow key={t.id} trade={t} onClose={setCloseTarget} onDelete={handleDelete} />
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : (
        <div className="text-center py-20 text-slate-600">
          <BarChart3 className="w-10 h-10 mx-auto mb-3 opacity-30" />
          <p className="font-black uppercase tracking-widest text-sm">No Trades Yet</p>
          <p className="text-xs mt-1 text-slate-700">「新規登録」からペーパートレードを記録できます</p>
        </div>
      )}

      {/* モーダル */}
      {showNew && (
        <NewTradeModal
          onClose={() => setShowNew(false)}
          onCreated={() => { setShowNew(false); refresh(); }}
        />
      )}
      {closeTarget && (
        <CloseModal
          trade={closeTarget}
          onClose={() => setCloseTarget(null)}
          onDone={() => { setCloseTarget(null); refresh(); }}
        />
      )}
    </div>
  );
}
