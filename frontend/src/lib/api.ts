const BASE = "";  // next.config.js の rewrite 経由

function authHeader(): Record<string, string> {
  if (typeof window === "undefined") return {};
  const token = localStorage.getItem("token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
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
export interface MeResponse    { id: number; email: string; plan: string }

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

// ── シグナル ─────────────────────────────────────────────────

export interface Signal {
  Code: string; Date: string; signal: "UP" | "DOWN";
  up_probability: number; actual_return: number | null;
  is_correct: boolean | null; company_name: string | null;
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
