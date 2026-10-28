import * as Sentry from "@sentry/nextjs";

const dsn = process.env.NEXT_PUBLIC_SENTRY_DSN;

if (dsn) {
  Sentry.init({
    dsn,
    // パフォーマンストレース: 本番10%サンプリング
    tracesSampleRate: process.env.NODE_ENV === "production" ? 0.1 : 1.0,
    // セッションリプレイ: エラー時のみ記録
    replaysOnErrorSampleRate: 1.0,
    replaysSessionSampleRate: 0.05,
    environment: process.env.NODE_ENV,
    release: process.env.NEXT_PUBLIC_RELEASE,
    // ノイズを減らすフィルター
    ignoreErrors: [
      "ResizeObserver loop limit exceeded",
      "Non-Error promise rejection captured",
      /ChunkLoadError/,
    ],
    beforeSend(event) {
      // ローカル開発時は送信しない
      if (process.env.NODE_ENV !== "production") return null;
      return event;
    },
  });
}
