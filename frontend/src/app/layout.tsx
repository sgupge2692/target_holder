import type { Metadata } from "next";
import "./globals.css";
import { Navbar } from "@/components/Navbar";

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL ?? "https://stock-intelligence.app";

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: {
    default: "Stock Intelligence | AIが選ぶ翌日上昇銘柄",
    template: "%s | Stock Intelligence",
  },
  description:
    "LightGBM × XGBoost アンサンブルAIが毎朝、翌日上昇の可能性が高い銘柄をシグナル配信。46種のテクニカル指標 × セクター相対分析 × ニュースセンチメントで高精度予測。無料プランあり。",
  keywords: ["株価予測", "AI投資", "テクニカル分析", "株シグナル", "機械学習", "LightGBM", "日本株"],
  authors: [{ name: "Stock Intelligence" }],
  openGraph: {
    type: "website",
    locale: "ja_JP",
    url: SITE_URL,
    siteName: "Stock Intelligence",
    title: "Stock Intelligence | AIが選ぶ翌日上昇銘柄",
    description:
      "毎朝AIが翌日上昇銘柄をシグナル配信。46種指標 × セクター分析 × ニュースセンチメント。無料で始められます。",
    images: [
      {
        url: "/og-image.png",
        width: 1200,
        height: 630,
        alt: "Stock Intelligence - AI株価シグナル",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "Stock Intelligence | AIが選ぶ翌日上昇銘柄",
    description: "毎朝AIが翌日上昇銘柄をシグナル配信。無料で始められます。",
    images: ["/og-image.png"],
  },
  robots: {
    index: true,
    follow: true,
    googleBot: { index: true, follow: true },
  },
  alternates: { canonical: SITE_URL },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ja" suppressHydrationWarning>
      <body className="min-h-screen bg-gray-50 dark:bg-slate-900 text-gray-900 dark:text-slate-100">
        <Navbar />
        <main className="max-w-6xl mx-auto px-4 py-8">{children}</main>
      </body>
    </html>
  );
}
