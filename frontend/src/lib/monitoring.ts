/**
 * フロントエンドエラー監視
 * NEXT_PUBLIC_SENTRY_DSN が設定されている場合は Sentry に送信、
 * それ以外はコンソールに出力するだけ。
 *
 * 使い方:
 *   import { captureError, captureMessage } from "@/lib/monitoring";
 *   captureError(err, { context: "fetch signals" });
 */

type ErrorContext = Record<string, unknown>;

let _sentryLoaded = false;

async function _loadSentry() {
  if (_sentryLoaded) return;
  const dsn = process.env.NEXT_PUBLIC_SENTRY_DSN;
  if (!dsn) return;

  try {
    const Sentry = await import("@sentry/nextjs");
    if (!Sentry.getClient()) {
      Sentry.init({
        dsn,
        tracesSampleRate: 0.1,
        environment: process.env.NODE_ENV,
        release: process.env.NEXT_PUBLIC_RELEASE,
      });
    }
    _sentryLoaded = true;
  } catch {
    // Sentry が未インストールでも動作継続
  }
}

export async function captureError(err: unknown, context?: ErrorContext) {
  if (process.env.NODE_ENV !== "production") {
    console.error("[captureError]", err, context);
    return;
  }
  try {
    await _loadSentry();
    const Sentry = await import("@sentry/nextjs");
    Sentry.withScope(scope => {
      if (context) scope.setExtras(context);
      Sentry.captureException(err);
    });
  } catch {
    console.error("[captureError] fallback:", err);
  }
}

export async function captureMessage(message: string, level: "info" | "warning" | "error" = "info") {
  if (process.env.NODE_ENV !== "production") {
    console.log(`[captureMessage:${level}]`, message);
    return;
  }
  try {
    await _loadSentry();
    const Sentry = await import("@sentry/nextjs");
    Sentry.captureMessage(message, level);
  } catch {
    console.log(`[captureMessage] fallback:`, message);
  }
}
