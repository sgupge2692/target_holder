const BASE = "";  // next.config.js の rewrite 経由

function authHeader(): Record<string, string> {
  if (typeof window === "undefined") return {};
  const token = localStorage.getItem("token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    ...init,
    headers: { "Content-Type": "application/json", ...authHeader(), ...init?.headers },
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? "APIエラー");
  }
  return res.json();
}

// ── 認証 ─────────────────────────────────────────────────────

export interface TokenResponse { access_token: string; token_type: string }
export interface MeResponse    { id: number; email: string; plan: string; is_admin?: boolean }

export const register = (email: string, password: string) =>
  apiFetch<TokenResponse>("/api/auth/register", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });

export const login = (email: string, password: string) => {
  const body = new URLSearchParams({ username: email, password });
  return apiFetch<TokenResponse>("/api/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: body.toString(),
  });
};

export const getMe = () => apiFetch<MeResponse>("/api/auth/me");

// ── 課金 ─────────────────────────────────────────────────────

export type BillingInterval = "month" | "year";

export interface BillingPlans {
  yearly_available: boolean;
  monthly_amount: number | null;   // 円。Stripe の Price から取得（取得できなければ null）
  yearly_amount: number | null;
}

export const getBillingPlans = () => apiFetch<BillingPlans>("/api/billing/plans");

export const createCheckout = (interval: BillingInterval = "month") =>
  apiFetch<{ url: string }>("/api/billing/checkout", {
    method: "POST",
    body: JSON.stringify({ interval }),
  });

export const createPortal = () =>
  apiFetch<{ url: string }>("/api/billing/portal", { method: "POST" });

export interface SubscriptionInfo {
  plan: string;
  plan_expires_at: string | null;
  stripe_subscription_id: string | null;
}

export const getSubscription = () =>
  apiFetch<SubscriptionInfo>("/api/billing/subscription");

// ── シグナル ─────────────────────────────────────────────────

export interface Signal {
  Code: string; Date: string; signal: "UP" | "DOWN";
  up_probability: number; actual_return: number | null;
  excess_return?: number | null;  // 市場平均（全銘柄の中央値）に対する超過リターン。的中判定はこちらの符号
  is_correct: boolean | null; company_name: string | null;
  explanation: string | null; key_factors: string | null;
  prob_change_pt?: number | null;      // 前回予測からの上昇確率の変化（pt）。前回が無ければ null
  prev_signal?: string | null;         // 前回のシグナル
  signal_changed?: boolean | null;     // 前回からシグナルが変わったか
}
export interface AccuracyRow {
  signal: string; total: number; correct: number;
  accuracy_pct: number; avg_return_pct: number;
  avg_excess_pct?: number;   // 市場平均（全銘柄の中央値）に対する平均超過リターン
}

export interface LatestSignalsResponse {
  signals: Signal[];
  plan: string;
  total: number;            // 今回返した件数
  total_available: number;  // 制限前の総件数（「あと○件」表示用）
  is_limited: boolean;      // 無料プランの閲覧制限が効いているか
  free_limit: number;       // 無料プランで閲覧できる件数
}

export const getLatestSignals = (signal?: "UP" | "DOWN") =>
  apiFetch<LatestSignalsResponse>(
    `/api/signals/latest${signal ? `?signal=${signal}` : ""}`
  );

export const getSignalHistory = (code: string) =>
  apiFetch<{ code: string; history: Signal[]; plan: string }>(
    `/api/signals/history/${code}`
  );

export const getAccuracy = () =>
  apiFetch<{ accuracy: AccuracyRow[] }>("/api/signals/accuracy");

export interface MonthlyAccuracy {
  month: string;
  up_accuracy?: number;   up_total?: number;   up_avg_return?: number;
  down_accuracy?: number; down_total?: number; down_avg_return?: number;
}
export interface CumulativeReturn {
  date: string;
  cumulative_return_pct: number;       // UPシグナル全件の平均超過リターンを日次で積み上げ
  top_cumulative_return_pct: number;   // 各日の確度上位N件だけの同様の値
}
export interface BacktestMeta {
  first_date: string | null; last_date: string | null;
  days: number;   // 集計できた営業日数（実績の長さ）
  top_k: number;
}
export interface BacktestChart {
  monthly: MonthlyAccuracy[];
  cumulative_return: CumulativeReturn[];
  overall: AccuracyRow[];
  meta?: BacktestMeta;
}

export const getBacktestChart = (months = 12) =>
  apiFetch<BacktestChart>(`/api/signals/backtest/chart?months=${months}`);

export interface SectorStrength {
  sector_code: string;
  sector_name: string;
  stock_count: number;
  avg_up_probability: number;
  up_count: number;
  down_count: number;
}

export interface SectorHeatmap {
  date: string | null;
  sectors: SectorStrength[];
  min_stocks: number;
}

export const getSectorHeatmap = () =>
  apiFetch<SectorHeatmap>("/api/signals/sectors");

/** Pro 専用: シグナル CSV をダウンロード */
export async function downloadSignalsCsv(signal?: "UP" | "DOWN", days = 30) {
  const params = new URLSearchParams({ days: String(days) });
  if (signal) params.set("signal", signal);
  const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
  const res = await fetch(`/api/signals/export/csv?${params}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? "CSVダウンロードに失敗しました");
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `signals_${new Date().toISOString().slice(0, 10)}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

// ── 銘柄 ─────────────────────────────────────────────────────

export interface Stock { code: string; company_name: string; market_code: string; sector_code: string }
export interface Quote { Date: string; Open: number; High: number; Low: number; Close: number; AdjustmentClose: number; Volume: number }

export const searchStocks = (q: string) =>
  apiFetch<{ stocks: Stock[] }>(`/api/stocks/search?q=${encodeURIComponent(q)}`);

export const getStock = (code: string) => apiFetch<Stock>(`/api/stocks/${code}`);

export const getQuotes = (code: string) =>
  apiFetch<{ code: string; quotes: Quote[]; plan: string }>(
    `/api/stocks/${code}/quotes`
  );

export interface PeerStock {
  code: string; company_name: string; signal: string; up_probability: number;
}
export interface PeersResponse {
  code: string;
  sector_code: string | null;
  sector_name: string | null;
  stock_count: number;                 // 業種内で予測がある銘柄数
  rank: number | null;                 // 業種内の順位（市場を上回る確率が高い順）
  up_probability: number | null;
  avg_up_probability: number | null;   // 業種平均
  peers: PeerStock[];                  // Pro のみ。同業種の上位銘柄（自分を除く）
  peers_locked: boolean;
}

export const getPeers = (code: string) =>
  apiFetch<PeersResponse>(`/api/stocks/${code}/peers`);

// ── 四季報要約 ────────────────────────────────────────────────

export interface Summary {
  code: string; year_label: string; plan: string;
  overview: string | null; performance: string | null; risks: string | null;
  model: string | null; created_at: string;
}

export const getSummary = (code: string) =>
  apiFetch<Summary>(`/api/summary/${code}`);

export const generateSummary = (code: string, text: string, year_label: string) =>
  apiFetch<Summary>(`/api/summary/${code}`, {
    method: "POST",
    body: JSON.stringify({ text, year_label }),
  });

export const regenerateSummary = (code: string, text: string, year_label: string) =>
  apiFetch<Summary>(`/api/summary/${code}/regenerate`, {
    method: "POST",
    body: JSON.stringify({ text, year_label }),
  });

// ── ウォッチリスト ────────────────────────────────────────────

export interface WatchlistItem {
  code: string; company_name: string | null; created_at: string;
  signal: "UP" | "DOWN" | "NEUTRAL" | null; up_probability: number | null;
  is_correct: boolean | null; signal_date: string | null;
  latest_price: number | null;
  prev_signal?: string | null;         // 前回のシグナル
  prob_change_pt?: number | null;      // 前回予測からの上昇確率の変化（pt）
  signal_changed?: boolean | null;     // 前回からシグナルが変わったか
}

export const getWatchlist = () =>
  apiFetch<{ watchlist: WatchlistItem[]; plan: string }>("/api/watchlist");

export const getWatchlistStatus = (code: string) =>
  apiFetch<{ code: string; watched: boolean }>(`/api/watchlist/${code}/status`);

export const addToWatchlist = (code: string) =>
  apiFetch<{ code: string; watched: boolean }>(`/api/watchlist/${code}`, { method: "POST" });

export const removeFromWatchlist = (code: string) =>
  apiFetch<{ code: string; watched: boolean }>(`/api/watchlist/${code}`, { method: "DELETE" });

// ── 管理画面 ──────────────────────────────────────────────────

export interface AdminStats {
  users: { total: number; pro: number; free: number; new_this_month: number; conversion_rate_pct: number };
  revenue: { mrr: number; arr: number };
  signals: { total_30d: number; up_count_30d: number; down_count_30d: number; evaluated_30d: number; up_accuracy_30d: number | null };
  daily_signups: { date: string; count: number }[];
}

export interface AdminUser {
  id: number; email: string; plan: string; is_active: boolean;
  email_signal_alert: boolean; created_at: string;
}

export interface AdminSignalDaily {
  date: string; total: number; up: number; down: number; accuracy_pct: number | null;
}

export interface AdminModelMetric {
  id: number; trained_at: string; mode: string;
  mean_auc: number | null; std_auc: number | null;
  lgbm_auc: number | null; xgb_auc: number | null;
  ensemble_auc: number | null; n_samples: number | null;
}

export interface AdminFeature { feature: string; importance: number }

export const getAdminStats    = () => apiFetch<AdminStats>("/api/admin/stats");
export const getAdminUsers    = (page = 1) => apiFetch<{ users: AdminUser[]; total: number; page: number; per_page: number }>(`/api/admin/users?page=${page}&per_page=50`);
export const getAdminSignals  = (days = 30) => apiFetch<{ data: AdminSignalDaily[] }>(`/api/admin/signals/daily?days=${days}`);
export const getAdminMetrics  = () => apiFetch<{ metrics: AdminModelMetric[] }>("/api/admin/model/metrics");
export const getAdminFeatures = (top_n = 20) => apiFetch<{ features: AdminFeature[]; trained_at: string | null; mode: string | null }>(`/api/admin/model/features?top_n=${top_n}`);

// ── ペーパートレード ─────────────────────────────────────────────────────────
export interface PaperTrade {
  id: number;
  code: string;
  company_name: string | null;
  signal: "UP" | "DOWN";
  entry_price: number;
  shares: number;
  entry_date: string;
  exit_price: number | null;
  exit_date: string | null;
  status: "open" | "closed";
  note: string | null;
  pnl: number | null;
  pnl_pct: number | null;
}

export interface PaperTradeStats {
  total: number;
  win: number;
  loss: number;
  win_rate: number | null;
  total_pnl: number;
  avg_pnl_pct: number | null;
  best_pnl?: number;
  worst_pnl?: number;
}

export const getPaperTrades = (status?: string) =>
  apiFetch<PaperTrade[]>(`/api/paper-trades${status ? `?status=${status}` : ""}`);

export const getPaperTradeStats = () => apiFetch<PaperTradeStats>("/api/paper-trades/stats");

export const createPaperTrade = (body: {
  code: string; signal: string; entry_price: number; shares: number;
  entry_date: string; note?: string;
}) => apiFetch<{ id: number }>("/api/paper-trades", { method: "POST", body: JSON.stringify(body) });

export const closePaperTrade = (id: number, exit_price: number, exit_date: string) =>
  apiFetch<{ status: string }>(`/api/paper-trades/${id}`, {
    method: "PATCH",
    body: JSON.stringify({ exit_price, exit_date }),
  });

export const deletePaperTrade = (id: number) =>
  apiFetch<void>(`/api/paper-trades/${id}`, { method: "DELETE" });

// ── 予想バトル ──────────────────────────────────────────────

export interface BattleStock {
  code: string;
  company_name: string | null;
  sector_code: string | null;
  close: number | null;
  change_5d_pct: number | null;
  my_pick: "UP" | "DOWN" | null;
}

export interface BattleToday {
  round_date: string | null;
  closed: boolean;
  stocks: BattleStock[];
  answered: number;
  round_size: number;
  disclaimer: string;
}

export interface BattleDuel {
  code: string;
  company_name: string | null;
  round_date: string;
  pick: "UP" | "DOWN";
  settled: boolean;
  ai_signal: "UP" | "DOWN" | null;
  ai_up_probability: number | null;
  excess_return_pct: number | null;
  user_correct: boolean | null;
  ai_correct: boolean | null;
  outcome: "win" | "lose" | "draw" | null;
}

export interface BattleSummary {
  settled: number;
  pending: number;
  user_correct: number;
  user_win_rate: number | null;
  ai_correct: number;
  ai_win_rate: number | null;
  duel_wins: number;
  duel_losses: number;
  duel_draws: number;
  current_streak: number;
  best_streak: number;
  title: string;
  title_needs: number;
}

export interface BattleMe {
  summary: BattleSummary;
  recent: BattleDuel[];
  handle: string;
  disclaimer: string;
}

export interface LeaderboardEntry {
  rank: number;
  handle: string;
  settled: number;
  wins: number;
  win_rate: number;
  current_streak: number;
  best_streak: number;
}

export interface Leaderboard {
  entries: LeaderboardEntry[];
  min_picks: number;
  note: string;
  disclaimer: string;
}

export const getBattleToday = () => apiFetch<BattleToday>("/api/battle/today");
export const getBattleMe = () => apiFetch<BattleMe>("/api/battle/me");
export const getLeaderboard = () => apiFetch<Leaderboard>("/api/battle/leaderboard");
export const postBattlePick = (code: string, pick: "UP" | "DOWN") =>
  apiFetch<{ code: string; pick: string; round_date: string }>("/api/battle/pick", {
    method: "POST",
    body: JSON.stringify({ code, pick }),
  });
