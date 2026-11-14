"use client";
import { useState } from "react";
import useSWR, { mutate } from "swr";
import Link from "next/link";
import {
  getBattleToday, getBattleMe, getLeaderboard,
  postBattlePick,
  type BattleStock, type BattleDuel, type BattleSummary, type LeaderboardEntry,
} from "@/lib/api";
import { useAuth } from "@/hooks/useAuth";
import { TrendingUp, TrendingDown, Trophy, Zap, Clock, CheckCircle2, XCircle, Minus, ChevronRight, Swords, Star } from "lucide-react";

// ── タブ ─────────────────────────────────────────────────────
type Tab = "today" | "me" | "ranking";

// ── 称号バッジ ────────────────────────────────────────────────
function TitleBadge({ title }: { title: string }) {
  const colors: Record<string, string> = {
    "株の仙人": "bg-amber-400/20 text-amber-300 border-amber-400/40",
    "相場の読み手": "bg-teal-400/20 text-teal-300 border-teal-400/40",
    "ふつうの投資家": "bg-slate-400/20 text-slate-300 border-slate-400/40",
    "逆張りの達人": "bg-purple-400/20 text-purple-300 border-purple-400/40",
    "ビギナーズラック?": "bg-amber-300/20 text-amber-200 border-amber-300/40",
    "見習いトレーダー": "bg-slate-500/20 text-slate-400 border-slate-500/40",
  };
  return (
    <span className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full border text-xs font-bold tracking-wide ${colors[title] ?? "bg-slate-500/20 text-slate-400 border-slate-500/40"}`}>
      <Star size={10} />
      {title}
    </span>
  );
}

// ── 株価変化バッジ ────────────────────────────────────────────
function ChangeBadge({ pct }: { pct: number | null }) {
  if (pct == null) return <span className="text-slate-500 text-xs">—</span>;
  const up = pct >= 0;
  return (
    <span className={`font-mono text-xs font-semibold ${up ? "text-teal-400" : "text-red-400"}`}>
      {up ? "▲" : "▼"}{Math.abs(pct).toFixed(1)}%
    </span>
  );
}

// ── 今日の出題カード ──────────────────────────────────────────
function StockCard({ stock, closed, onPick }: {
  stock: BattleStock;
  closed: boolean;
  onPick: (code: string, pick: "UP" | "DOWN") => Promise<void>;
}) {
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");
  const answered = !!stock.my_pick;

  const pick = async (p: "UP" | "DOWN") => {
    if (answered || closed || loading) return;
    setLoading(true);
    setErr("");
    try {
      await onPick(stock.code, p);
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : "エラーが発生しました");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className={`rounded-xl border p-4 flex flex-col gap-3 transition-all
      ${answered
        ? "border-teal-600/40 bg-teal-900/10"
        : closed
          ? "border-slate-700/40 bg-slate-800/20 opacity-60"
          : "border-slate-700/50 bg-slate-800/30 hover:border-slate-600/60"
      }`}>
      {/* 銘柄情報 */}
      <div className="flex items-start justify-between gap-2">
        <div>
          <Link href={`/stocks/${stock.code}`} className="font-bold text-sm text-slate-100 hover:text-teal-400 transition-colors">
            {stock.company_name ?? stock.code}
          </Link>
          <div className="text-[11px] text-slate-500 font-mono mt-0.5">{stock.code}</div>
        </div>
        <div className="text-right shrink-0">
          {stock.close != null && (
            <div className="font-mono font-bold text-sm text-slate-200">¥{stock.close.toLocaleString()}</div>
          )}
          <div className="mt-0.5">
            <ChangeBadge pct={stock.change_5d_pct} />
            {stock.change_5d_pct != null && <span className="text-[10px] text-slate-600 ml-1">5日</span>}
          </div>
        </div>
      </div>

      {/* 予想ボタン / 回答済み表示 */}
      {answered ? (
        <div className="flex items-center gap-2">
          <div className={`flex-1 rounded-lg py-2 flex items-center justify-center gap-1.5 font-black text-sm
            ${stock.my_pick === "UP" ? "bg-teal-600/30 text-teal-300 border border-teal-600/40" : "bg-red-600/30 text-red-300 border border-red-600/40"}`}>
            {stock.my_pick === "UP" ? <TrendingUp size={14} /> : <TrendingDown size={14} />}
            {stock.my_pick === "UP" ? "上昇予想 ✓" : "下落予想 ✓"}
          </div>
        </div>
      ) : closed ? (
        <div className="rounded-lg bg-slate-700/30 py-2 text-center text-xs text-slate-500 font-semibold">
          締め切り済み（結果待ち）
        </div>
      ) : (
        <div className="flex gap-2">
          <button
            onClick={() => pick("UP")}
            disabled={loading}
            className="flex-1 rounded-lg py-2.5 flex items-center justify-center gap-1.5 font-black text-xs tracking-wide uppercase border border-teal-600/50 text-teal-400 hover:bg-teal-600/20 active:scale-95 transition-all disabled:opacity-40"
          >
            <TrendingUp size={14} />上昇
          </button>
          <button
            onClick={() => pick("DOWN")}
            disabled={loading}
            className="flex-1 rounded-lg py-2.5 flex items-center justify-center gap-1.5 font-black text-xs tracking-wide uppercase border border-red-600/50 text-red-400 hover:bg-red-600/20 active:scale-95 transition-all disabled:opacity-40"
          >
            <TrendingDown size={14} />下落
          </button>
        </div>
      )}
      {err && <p className="text-xs text-red-400">{err}</p>}
    </div>
  );
}

// ── 対戦結果行 ────────────────────────────────────────────────
function DuelRow({ d }: { d: BattleDuel }) {
  const outcomeIcon = d.outcome === "win" ? <CheckCircle2 size={14} className="text-teal-400" />
    : d.outcome === "lose" ? <XCircle size={14} className="text-red-400" />
    : d.outcome === "draw" ? <Minus size={14} className="text-slate-500" />
    : <Clock size={14} className="text-amber-400" />;
  const outcomeText = d.outcome === "win" ? "勝ち" : d.outcome === "lose" ? "負け" : d.outcome === "draw" ? "引き分け" : "判定待ち";
  const outcomeColor = d.outcome === "win" ? "text-teal-400" : d.outcome === "lose" ? "text-red-400" : "text-slate-400";

  return (
    <div className="flex items-center gap-3 py-2.5 px-3 rounded-lg hover:bg-slate-800/40 transition-colors">
      <div className="shrink-0">{outcomeIcon}</div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="font-semibold text-sm text-slate-200 truncate">{d.company_name ?? d.code}</span>
          <span className="text-[10px] font-mono text-slate-600 shrink-0">{d.code}</span>
        </div>
        <div className="flex items-center gap-2 mt-0.5 flex-wrap">
          <span className={`text-[11px] font-bold ${d.pick === "UP" ? "text-teal-400" : "text-red-400"}`}>
            あなた: {d.pick === "UP" ? "▲上昇" : "▼下落"}
          </span>
          {d.settled && d.ai_signal && (
            <span className={`text-[11px] font-bold ${d.ai_signal === "UP" ? "text-teal-300/70" : "text-red-300/70"}`}>
              AI: {d.ai_signal === "UP" ? "▲上昇" : "▼下落"}
            </span>
          )}
          {d.excess_return_pct != null && (
            <span className={`font-mono text-[11px] font-bold ${d.excess_return_pct > 0 ? "text-teal-400" : "text-red-400"}`}>
              超過{d.excess_return_pct > 0 ? "+" : ""}{d.excess_return_pct.toFixed(2)}%
            </span>
          )}
        </div>
      </div>
      <div className={`shrink-0 text-xs font-black tracking-wide ${outcomeColor}`}>{outcomeText}</div>
    </div>
  );
}

// ── 戦績サマリー ──────────────────────────────────────────────
function SummaryPanel({ s, handle }: { s: BattleSummary; handle: string }) {
  const userPct = s.user_win_rate != null ? (s.user_win_rate * 100).toFixed(1) : null;
  const aiPct = s.ai_win_rate != null ? (s.ai_win_rate * 100).toFixed(1) : null;

  return (
    <div className="space-y-4">
      {/* ハンドル & 称号 */}
      <div className="flex items-center gap-3 flex-wrap">
        <span className="font-black text-lg text-slate-100">{handle}</span>
        <TitleBadge title={s.title} />
        {s.settled < s.title_needs && (
          <span className="text-[11px] text-slate-500">（あと{s.title_needs - s.settled}戦確定で称号決定）</span>
        )}
      </div>

      {/* スコアボード */}
      <div className="grid grid-cols-2 gap-3">
        <div className="rounded-xl border border-teal-600/30 bg-teal-900/10 p-4 text-center">
          <div className="text-3xl font-black tabular-nums text-teal-300">{userPct ?? "—"}%</div>
          <div className="text-xs text-slate-400 mt-1">あなたの的中率</div>
          <div className="text-[11px] text-slate-600 mt-0.5">{s.user_correct}/{s.settled}問</div>
        </div>
        <div className="rounded-xl border border-slate-700/40 bg-slate-800/20 p-4 text-center">
          <div className="text-3xl font-black tabular-nums text-slate-300">{aiPct ?? "—"}%</div>
          <div className="text-xs text-slate-400 mt-1">AIの的中率</div>
          <div className="text-[11px] text-slate-600 mt-0.5">{s.ai_correct}/{s.settled}問</div>
        </div>
      </div>

      {/* AI対戦成績 */}
      <div className="rounded-xl border border-slate-700/40 bg-slate-800/20 p-4">
        <div className="text-xs font-black text-slate-400 mb-3 tracking-widest uppercase">AI との対戦成績</div>
        <div className="flex justify-around">
          <div className="text-center">
            <div className="text-2xl font-black text-teal-400">{s.duel_wins}</div>
            <div className="text-[11px] text-slate-500 mt-0.5">勝ち</div>
          </div>
          <div className="text-center">
            <div className="text-2xl font-black text-red-400">{s.duel_losses}</div>
            <div className="text-[11px] text-slate-500 mt-0.5">負け</div>
          </div>
          <div className="text-center">
            <div className="text-2xl font-black text-slate-400">{s.duel_draws}</div>
            <div className="text-[11px] text-slate-500 mt-0.5">引き分け</div>
          </div>
        </div>
      </div>

      {/* 連勝 */}
      <div className="flex gap-3">
        <div className="flex-1 rounded-xl border border-amber-600/30 bg-amber-900/10 p-3 text-center">
          <div className="flex items-center justify-center gap-1.5 mb-1">
            <Zap size={14} className="text-amber-400" />
            <span className="text-xs text-amber-400 font-bold">現在の連勝</span>
          </div>
          <div className="text-2xl font-black tabular-nums text-amber-300">{s.current_streak}</div>
        </div>
        <div className="flex-1 rounded-xl border border-slate-700/40 bg-slate-800/20 p-3 text-center">
          <div className="flex items-center justify-center gap-1.5 mb-1">
            <Trophy size={14} className="text-slate-400" />
            <span className="text-xs text-slate-400 font-bold">最高連勝</span>
          </div>
          <div className="text-2xl font-black tabular-nums text-slate-300">{s.best_streak}</div>
        </div>
      </div>

      {s.pending > 0 && (
        <div className="rounded-lg bg-amber-900/15 border border-amber-700/30 px-3 py-2 flex items-center gap-2">
          <Clock size={13} className="text-amber-400 shrink-0" />
          <span className="text-xs text-amber-300">{s.pending}問の判定が翌営業日以降に確定します</span>
        </div>
      )}
    </div>
  );
}

// ── ランキング行 ──────────────────────────────────────────────
function RankRow({ e }: { e: LeaderboardEntry }) {
  const medal = e.rank === 1 ? "🥇" : e.rank === 2 ? "🥈" : e.rank === 3 ? "🥉" : null;
  return (
    <div className={`flex items-center gap-3 px-3 py-2.5 rounded-lg transition-colors
      ${e.rank <= 3 ? "bg-amber-900/10 border border-amber-700/20" : "hover:bg-slate-800/40"}`}>
      <div className="w-6 text-center shrink-0">
        {medal ? <span className="text-base">{medal}</span> : <span className="font-mono text-xs text-slate-500">{e.rank}</span>}
      </div>
      <div className="flex-1 min-w-0">
        <div className="font-bold text-sm text-slate-200">{e.handle}</div>
        <div className="text-[11px] text-slate-500 mt-0.5">
          {e.settled}戦 ・ 連勝{e.current_streak} ・ 最高{e.best_streak}
        </div>
      </div>
      <div className="text-right shrink-0">
        <div className="font-mono font-black text-sm text-teal-400">{(e.win_rate * 100).toFixed(1)}%</div>
        <div className="text-[10px] text-slate-600">{e.wins}問正解</div>
      </div>
    </div>
  );
}

// ── メインページ ──────────────────────────────────────────────
export default function BattlePage() {
  const { user, loading: authLoading } = useAuth();
  const [tab, setTab] = useState<Tab>("today");

  const { data: today, isLoading: todayLoading } = useSWR(
    user ? "battle-today" : null, getBattleToday, { revalidateOnFocus: false }
  );
  const { data: me, isLoading: meLoading } = useSWR(
    user && tab === "me" ? "battle-me" : null, getBattleMe
  );
  const { data: lb, isLoading: lbLoading } = useSWR(
    tab === "ranking" ? "battle-leaderboard" : null, getLeaderboard
  );

  const handlePick = async (code: string, pick: "UP" | "DOWN") => {
    await postBattlePick(code, pick);
    mutate("battle-today");
  };

  if (authLoading) return <div className="text-center py-20 text-slate-500 text-sm">読み込み中...</div>;

  if (!user) {
    return (
      <div className="max-w-lg mx-auto px-4 py-16 text-center space-y-5">
        <div className="text-5xl">⚔️</div>
        <h1 className="text-2xl font-black text-slate-100 tracking-tight">AI vs あなた 予想バトル</h1>
        <p className="text-sm text-slate-400 leading-relaxed">
          今日のAIシグナル銘柄について、あなたも「市場平均より上か下か」を予想してAIと勝負。
          翌営業日に答え合わせ。連勝記録とランキングで腕前を確認しよう。
        </p>
        <Link
          href="/auth"
          className="inline-block rounded-xl bg-teal-600 hover:bg-teal-500 px-8 py-3 font-black text-sm uppercase tracking-widest text-white transition-colors"
        >
          無料登録して参戦する
        </Link>
        {/* ランキングはログインなしで見られる */}
        <button
          onClick={() => setTab("ranking")}
          className="block w-full text-xs text-slate-500 hover:text-slate-300 transition-colors"
        >
          ランキングだけ見る →
        </button>
        {tab === "ranking" && (
          <LeaderboardTab lb={lb as import('@/lib/api').Leaderboard | undefined} lbLoading={lbLoading} />
        )}
      </div>
    );
  }

  const tabs: { id: Tab; label: string; icon: React.ReactNode }[] = [
    { id: "today", label: "今日の出題", icon: <Swords size={14} /> },
    { id: "me", label: "わたしの戦績", icon: <Trophy size={14} /> },
    { id: "ranking", label: "ランキング", icon: <Star size={14} /> },
  ];

  return (
    <div className="max-w-2xl mx-auto px-4 py-6 space-y-5">
      {/* ヘッダー */}
      <div>
        <h1 className="text-xl font-black tracking-tight text-slate-100 flex items-center gap-2">
          <Swords size={20} className="text-teal-400" />
          AI vs あなた 予想バトル
        </h1>
        <p className="text-xs text-slate-500 mt-1">
          AIのシグナル銘柄で「市場平均より上か下か」を予想。翌営業日に自動で採点。
        </p>
      </div>

      {/* タブ */}
      <div className="flex gap-1 p-1 rounded-xl bg-slate-800/50 border border-slate-700/40">
        {tabs.map(t => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`flex-1 flex items-center justify-center gap-1.5 py-2 rounded-lg text-xs font-bold transition-all
              ${tab === t.id
                ? "bg-teal-600 text-white shadow"
                : "text-slate-400 hover:text-slate-200"
              }`}
          >
            {t.icon}{t.label}
          </button>
        ))}
      </div>

      {/* 今日の出題タブ */}
      {tab === "today" && (
        <div className="space-y-4">
          {todayLoading && <div className="text-center py-10 text-slate-500 text-sm">読み込み中...</div>}
          {!todayLoading && !today?.round_date && (
            <div className="rounded-xl border border-slate-700/40 bg-slate-800/20 p-8 text-center space-y-2">
              <div className="text-3xl">📭</div>
              <p className="text-sm text-slate-400 font-semibold">今日の出題はまだありません</p>
              <p className="text-xs text-slate-600">毎営業日夕方に更新されます。</p>
            </div>
          )}
          {today?.round_date && (
            <>
              {/* 進捗バー */}
              <div className="flex items-center justify-between text-xs text-slate-400">
                <span className="font-bold">基準日: {today.round_date}</span>
                <span className={`font-bold ${today.answered === today.round_size ? "text-teal-400" : "text-amber-400"}`}>
                  {today.answered}/{today.round_size}問 回答済み
                </span>
              </div>
              <div className="h-1.5 rounded-full bg-slate-700/50 overflow-hidden">
                <div
                  className="h-full rounded-full bg-teal-500 transition-all duration-500"
                  style={{ width: `${(today.answered / (today.round_size || 1)) * 100}%` }}
                />
              </div>

              {today.closed && (
                <div className="rounded-lg bg-amber-900/15 border border-amber-700/30 px-3 py-2.5 flex items-center gap-2">
                  <Clock size={13} className="text-amber-400 shrink-0" />
                  <span className="text-xs text-amber-300 leading-relaxed">
                    この出題の結果が出ました。AIの予想と答えは「わたしの戦績」で確認できます。
                  </span>
                  <button
                    onClick={() => setTab("me")}
                    className="shrink-0 flex items-center gap-0.5 text-xs font-bold text-teal-400 hover:text-teal-300"
                  >
                    確認 <ChevronRight size={12} />
                  </button>
                </div>
              )}

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {today.stocks.map(s => (
                  <StockCard
                    key={s.code}
                    stock={s}
                    closed={today.closed}
                    onPick={handlePick}
                  />
                ))}
              </div>

              {today.answered === today.round_size && !today.closed && (
                <div className="rounded-xl bg-teal-900/20 border border-teal-600/30 p-4 text-center space-y-1">
                  <div className="text-xl">🎯</div>
                  <p className="text-sm font-bold text-teal-300">全問回答済み！</p>
                  <p className="text-xs text-slate-400">結果は翌営業日に確定します。</p>
                </div>
              )}

              <p className="text-[11px] text-slate-600 leading-relaxed">
                {today.disclaimer}　AIの予想は結果が出るまで表示しません（後出しを防ぐため）。
              </p>
            </>
          )}
        </div>
      )}

      {/* わたしの戦績タブ */}
      {tab === "me" && (
        <div className="space-y-5">
          {meLoading && <div className="text-center py-10 text-slate-500 text-sm">読み込み中...</div>}
          {me && (
            <>
              <SummaryPanel s={me.summary} handle={me.handle} />
              {me.recent.length > 0 && (
                <div>
                  <div className="text-xs font-black text-slate-400 mb-2 tracking-widest uppercase">直近の対戦</div>
                  <div className="space-y-0.5">
                    {me.recent.map((d, i) => <DuelRow key={i} d={d} />)}
                  </div>
                </div>
              )}
              {me.recent.length === 0 && (
                <div className="rounded-xl border border-slate-700/40 bg-slate-800/20 p-8 text-center space-y-2">
                  <div className="text-3xl">🎮</div>
                  <p className="text-sm text-slate-400 font-semibold">まだ対戦がありません</p>
                  <button onClick={() => setTab("today")} className="text-xs text-teal-400 hover:text-teal-300 font-bold">
                    今日の出題を見る →
                  </button>
                </div>
              )}
              <p className="text-[11px] text-slate-600">{me.disclaimer}</p>
            </>
          )}
        </div>
      )}

      {/* ランキングタブ */}
      {tab === "ranking" && <LeaderboardTab lb={lb as import('@/lib/api').Leaderboard | undefined} lbLoading={lbLoading} />}
    </div>
  );
}

function LeaderboardTab({ lb, lbLoading }: { lb: import('@/lib/api').Leaderboard | undefined; lbLoading: boolean }) {
  return (
    <div className="space-y-4">
      {lbLoading && <div className="text-center py-10 text-slate-500 text-sm">読み込み中...</div>}
      {lb && lb.entries.length === 0 && (
        <div className="rounded-xl border border-slate-700/40 bg-slate-800/20 p-8 text-center space-y-2">
          <div className="text-3xl">🏆</div>
          <p className="text-sm text-slate-400 font-semibold">まだランキングに載っている人がいません</p>
          <p className="text-xs text-slate-600">確定した対戦が{lb.min_picks}戦以上でランキングに表示されます。</p>
        </div>
      )}
      {lb && lb.entries.length > 0 && (
        <>
          <div className="space-y-1.5">
            {lb.entries.map(e => <RankRow key={e.rank} e={e} />)}
          </div>
          <p className="text-[11px] text-slate-600 leading-relaxed">{lb.note}</p>
          <p className="text-[11px] text-slate-600 leading-relaxed">{lb.disclaimer}</p>
        </>
      )}
    </div>
  );
}
