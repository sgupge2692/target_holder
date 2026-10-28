/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${process.env.NEXT_PUBLIC_API_URL || "http://backend:8000"}/api/:path*`,
      },
    ];
  },
};

// SENTRY_DSN が設定されている場合のみ Sentry でラップ
const SENTRY_DSN = process.env.NEXT_PUBLIC_SENTRY_DSN || process.env.SENTRY_DSN;

if (SENTRY_DSN) {
  const { withSentryConfig } = require("@sentry/nextjs");
  module.exports = withSentryConfig(nextConfig, {
    // Sentry ウィザードで生成される org / project は .env.sentry-build-plugin に書く
    silent: true,
    // ソースマップをアップロードしてスタックトレースを読みやすくする
    widenClientFileUpload: true,
    // React コンポーネントのアノテーション（エラーの追跡精度が上がる）
    reactComponentAnnotation: { enabled: true },
    // トンネル: ブラウザの adblocker をバイパス
    tunnelRoute: "/monitoring",
    // ソースマップをバンドルに含めない（セキュリティ）
    hideSourceMaps: true,
    disableLogger: true,
  });
} else {
  module.exports = nextConfig;
}
