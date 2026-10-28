"use client";
import Link from "next/link";
import useSWR from "swr";
import { getAccuracy, getBacktestChart, type AccuracyRow } from "@/lib/api";
import {
  TrendingUp, TrendingDown, Zap, Lock, BarChart2,
  CheckCircle2, ChevronRight, Star,
} from "lucide-react";

// ── ヒーロー精度バッジ ─────────────────────────────────────────
function AccuracyBadge({ row }: { row: AccuracyRow }) {
  const isUp = row.signal === "UP";
  return (
    <div className={`flex items-center gap-3 rounded-2xl px-5 py-4 ${
      isUp
        ? "bg-emerald-50 dark:bg-emerald-900/20 border border-emerald-200 dark:border-emerald-700"
        : "bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-700"
    }`}>
      {isUp
        ? <TrendingUp className="w-7 h-7 text-emerald-500 shrink-0" />
        : <TrendingDown className="w-7 h-7 text-red-400 shrink-0" />
      }
      <div>
        <div className={`text-3xl font-extrabold ${isUp ? "text-emerald-600" : "text-red-500"}`}>
          {row.accuracy_pct}%
        </div>
        <div className="text-xs text-gray-500 dark:text-slate-400 mt-0.5">
          {isUp ? "上昇" : "下落"}予測精度（n={row.total}）
        </div>
      </div>
    </div>
  );
}

// ── 機能カード ─────────────────────────────────────────────────
function FeatureCard({ icon, title, desc }: { icon: React.ReactNode; title: string; desc: string }) {
  return (
    <div className="rounded-xl border border-gray-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-6">
      <div className="mb-3 text-brand-600 dark:text-brand-400">{icon}</div>
      <h3 className="font-semibold text-gray-900 dark:text-white mb-1">{title}</h3>
      <p className="text-sm text-gray-500 dark:text-slate-400 leading-relaxed">{desc}</p>
    </div>
  );
}

// ── 料金カード ─────────────────────────────────────────────────
function PricingCard({
  plan, price, period, features, highlighted, cta, href,
}: {
  plan: string; price: string; period: string;
  features: string[]; highlighted?: boolean;
  cta: string; href: string;
}) {
  return (
    <div className={`rounded-2xl border p-7 flex flex-col gap-5 ${
      highlighted
        ? "border-brand-500 bg-brand-50 dark:bg-brand-900/20 ring-2 ring-brand-400"
        : "border-gray-200 dark:border-slate-700 bg-white dark:bg-slate-900"
    }`}>
      <div>
        <div className="flex items-center gap-2 mb-1">
          <span className="text-sm font-semibold uppercase tracking-wide text-gray-500 dark:text-slate-400">{plan}</span>
          {highlighted && (
            <span className="px-2 py-0.5 rounded-full bg-brand-500 text-white text-xs font-bold">人気</span>
          )}
        </div>
        <div className="flex items-end gap-1">
          <span className="text-4xl font-extrabold text-gray-900 dark:text-white">{price}</span>
          <span className="text-sm text-gray-500 dark:text-slate-400 mb-1">{period}</span>
        </div>
      </div>

      <ul className="space-y-2.5">
        {features.map((f, i) => (
          <li key={i} className="flex items-start gap-2 text-sm text-gray-700 dark:text-slate-300">
            <CheckCircle2 className="w-4 h-4 mt-0.5 shrink-0 text-brand-500" />
            {f}
          </li>
        ))}
      </ul>

      <Link
        href={href}
        className={`mt-auto block text-center py-3 rounded-xl font-semibold text-sm transition-colors ${
          highlighted
            ? "bg-brand-600 hover:bg-brand-700 text-white"
            : "bg-gray-100 dark:bg-slate-800 hover:bg-gray-200 dark:hover:bg-slate-700 text-gray-900 dark:text-white"
        }`}
      >
        {cta}
      </Link>
    </div>
  );
}

// ── ランディングページ本体 ─────────────────────────────────────
export function LandingPage() {
  const { data: accData } = useSWR("accuracy", getAccuracy, { revalidateOnFocus: false });
  const { data: btData }  = useSWR(["backtest", 12], () => getBacktestChart(12), { revalidateOnFocus: false });

  const accuracyRows: AccuracyRow[] = accData?.accuracy ?? [];
  const upRow   = accuracyRows.find(r => r.signal === "UP");
  const downRow = accuracyRows.find(r => r.signal === "DOWN");
  const lastCumReturn = btData?.cumulative_return?.at(-1)?.cumulative_return_pct ?? null;

  return (
    <div className="space-y-24 pb-24">

      {/* ── HERO ─────────────────────────────────────────────── */}
      <section className="text-center space-y-6 pt-12">
        <div className="inline-flex items-center gap-2 rounded-full bg-brand-50 dark:bg-brand-900/30 border border-brand-200 dark:border-brand-700 px-4 py-1.5 text-xs font-medium text-brand-700 dark:text-brand-300">
          <Zap className="w-3.5 h-3.5" />
          LightGBM × XGBoost アンサンブル予測
        </div>

        <h1 className="text-4xl sm:text-5xl font-extrabold text-gray-900 dark:text-white leading-tight">
          AIが毎朝、<br className="sm:hidden" />
          <span className="text-brand-600 dark:text-brand-400">翌日の上昇銘柄</span>を選ぶ
        </h1>

        <p className="text-lg text-gray-500 dark:text-slate-400 max-w-xl mx-auto">
          46種のテクニカル指標 × セクター相対分析 × ニュースセンチメントで、
          高精度な騰落シグナルを毎日配信します。
        </p>

        <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
          <Link
            href="/auth"
            className="inline-flex items-center gap-2 bg-brand-600 hover:bg-brand-700 text-white px-7 py-3.5 rounded-xl font-semibold text-base transition-colors shadow-md"
          >
            無料で始める
            <ChevronRight className="w-4 h-4" />
          </Link>
          <Link
            href="/backtest"
            className="inline-flex items-center gap-2 text-gray-600 dark:text-slate-300 hover:text-brand-600 dark:hover:text-brand-400 font-medium text-sm transition-colors"
          >
            <BarChart2 className="w-4 h-4" />
            バックテスト結果を見る
          </Link>
        </div>

        {/* 精度バッジ */}
        {(upRow || downRow) && (
          <div className="flex flex-col sm:flex-row justify-center gap-4 mt-4">
            {upRow   && <AccuracyBadge row={upRow}   />}
            {downRow && <AccuracyBadge row={downRow} />}
            {lastCumReturn != null && (
              <div className="flex items-center gap-3 rounded-2xl px-5 py-4 bg-indigo-50 dark:bg-indigo-900/20 border border-indigo-200 dark:border-indigo-700">
                <TrendingUp className="w-7 h-7 text-indigo-500 shrink-0" />
                <div>
                  <div className={`text-3xl font-extrabold ${lastCumReturn >= 0 ? "text-indigo-600" : "text-red-500"}`}>
                    {lastCumReturn >= 0 ? "+" : ""}{lastCumReturn.toFixed(1)}%
                  </div>
                  <div className="text-xs text-gray-500 dark:text-slate-400 mt-0.5">
                    累積リターン（過去12ヶ月）
                  </div>
                </div>
              </div>
            )}
          </div>
        )}
      </section>

      {/* ── 機能 ─────────────────────────────────────────────── */}
      <section className="space-y-6">
        <h2 className="text-2xl font-bold text-center text-gray-900 dark:text-white">主な機能</h2>
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-5">
          <FeatureCard
            icon={<Zap className="w-6 h-6" />}
            title="毎朝 AIシグナル配信"
            desc="終値確定後に全上場銘柄を解析。60%以上の確度を持つUP/DOWNシグナルのみ表示します。"
          />
          <FeatureCard
            icon={<TrendingUp className="w-6 h-6" />}
            title="AI説明付きシグナル"
            desc="「なぜ上昇と予測したか」をAIが日本語で説明。主要テクニカル指標もチップ表示。"
          />
          <FeatureCard
            icon={<BarChart2 className="w-6 h-6" />}
            title="バックテスト実績"
            desc="過去シグナルの的中率・平均リターンを月別グラフで公開。透明性のある実績開示。"
          />
          <FeatureCard
            icon={<Star className="w-6 h-6" />}
            title="セクター相対分析"
            desc="同セクター内での相対的な強さを分析。市場全体が下げても出遅れ銘柄を発掘。"
          />
          <FeatureCard
            icon={<TrendingDown className="w-6 h-6" />}
            title="銘柄詳細ページ"
            desc="株価チャート・シグナル履歴・四季報サマリーをワンストップで確認できます。"
          />
          <FeatureCard
            icon={<Lock className="w-6 h-6" />}
            title="安心のセキュリティ"
            desc="JWT認証 + Stripe 決済。カード情報はStripeが保管し、当サービスには渡りません。"
          />
        </div>
      </section>

      {/* ── 料金 ─────────────────────────────────────────────── */}
      <section className="space-y-8" id="pricing">
        <div className="text-center space-y-2">
          <h2 className="text-2xl font-bold text-gray-900 dark:text-white">料金プラン</h2>
          <p className="text-sm text-gray-500 dark:text-slate-400">まずは無料プランで試してみてください</p>
        </div>

        <div className="grid sm:grid-cols-2 gap-6 max-w-2xl mx-auto">
          <PricingCard
            plan="Free"
            price="¥0"
            period="/ 月"
            cta="無料で始める"
            href="/auth"
            features={[
              "毎日のシグナル（上位10件）",
              "シグナル確率表示",
              "バックテスト結果閲覧",
              "銘柄検索",
            ]}
          />
          <PricingCard
            plan="Pro"
            price="¥2,980"
            period="/ 月"
            cta="Pro を始める"
            href="/billing"
            highlighted
            features={[
              "毎日のシグナル（全件）",
              "AI説明 + 根拠チップ",
              "銘柄詳細 + 株価チャート",
              "四季報 AI サマリー",
              "シグナル履歴（無制限）",
              "いつでも解約可能",
            ]}
          />
        </div>
      </section>

      {/* ── FAQ ──────────────────────────────────────────────── */}
      <section className="space-y-6 max-w-2xl mx-auto">
        <h2 className="text-2xl font-bold text-center text-gray-900 dark:text-white">よくある質問</h2>
        <div className="space-y-3">
          {[
            {
              q: "投資初心者でも使えますか？",
              a: "はい。シグナルには「なぜ上昇と予測したか」をAIが日本語で説明するので、テクニカル分析の知識がなくても参考にできます。",
            },
            {
              q: "予測は必ず当たりますか？",
              a: "AIの予測であり、元本保証・利益保証は一切ありません。あくまで参考情報としてご利用ください。投資は自己責任でお願いします。",
            },
            {
              q: "どのくらいの頻度でシグナルが出ますか？",
              a: "東証の取引日（平日）の朝に、前日終値データを使って解析します。確度60%以上の銘柄のみ表示するため、日によって件数は異なります。",
            },
            {
              q: "解約はいつでもできますか？",
              a: "はい。Proプランはいつでも解約できます。解約後は月末まで引き続き利用可能で、翌月から課金されません。",
            },
            {
              q: "対象銘柄はどこですか？",
              a: "東証プライム・スタンダード・グロース上場の全銘柄（約3,900社）が対象です。J-Quantsのデータを使用しています。",
            },
          ].map(({ q, a }, i) => (
            <details key={i} className="group rounded-xl border border-gray-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-5 cursor-pointer">
              <summary className="flex items-center justify-between font-medium text-gray-900 dark:text-white list-none">
                {q}
                <ChevronRight className="w-4 h-4 text-gray-400 group-open:rotate-90 transition-transform shrink-0 ml-4" />
              </summary>
              <p className="mt-3 text-sm text-gray-600 dark:text-slate-400 leading-relaxed">{a}</p>
            </details>
          ))}
        </div>
      </section>

      {/* ── CTA ──────────────────────────────────────────────── */}
      <section className="text-center space-y-4 rounded-2xl bg-brand-600 dark:bg-brand-700 py-14 px-8">
        <h2 className="text-2xl font-bold text-white">今すぐ無料で始める</h2>
        <p className="text-brand-100 text-sm">クレジットカード不要。30秒で登録完了。</p>
        <Link
          href="/auth"
          className="inline-flex items-center gap-2 bg-white text-brand-700 hover:bg-brand-50 px-8 py-3.5 rounded-xl font-bold text-base transition-colors shadow"
        >
          無料アカウントを作成
          <ChevronRight className="w-4 h-4" />
        </Link>
      </section>

    </div>
  );
}
