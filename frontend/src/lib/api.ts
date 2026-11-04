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

export const createCheckout = () =>
  apiFetch<{ url: string }>("/api/billing/checkout", { method: "POST" });

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
  is_correct: boolean | null; company_name: string | null;
  explanation: string | null; key_factors: string | null;
}
export interface AccuracyRow {
  signal: string; total: number; correct: number;
  accuracy_pct: number; avg_return_pct: number;
}

export const getLatestSignals = (signal?: "UP" | "DOWN") =>
  apiFetch<{ signals: Signal[]; plan: string; total: number }>(
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
export interface CumulativeReturn { date: string; cumulative_return_pct: number }
export interface BacktestChart {
  monthly: MonthlyAccuracy[];
  cumulative_return: CumulativeReturn[];
  overall: AccuracyRow[];
}

export const getBacktestChart = (months = 12) =>
  apiFetch<BacktestChart>(`/api/signals/backtest/chart?months=${months}`);

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
  signal: "UP" | "DOWN" | null; up_probability: number | null;
  is_correct: boolean | null; signal_date: string | null;
  latest_price: number | null;
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
