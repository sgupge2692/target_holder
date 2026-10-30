"use client";
import Link from "next/link";
import useSWR from "swr";
import { getAccuracy, getBacktestChart, type AccuracyRow } from "@/lib/api";
import {
  TrendingUp, TrendingDown, Zap, Lock, BarChart2,
  CheckCircle2, ChevronRight, Star, Bell, Search, ArrowRight,
  Shield, Brain, Layers,
} from "lucide-react";

// ── 精度バッジ ─────────────────────────────────────────────────
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
        <div className={`text-3xl font-extrabold tabular-nums ${isUp ? "text-emerald-600" : "text-red-500"}`}>
          {row.accuracy_pct}%
        </div>
        <div className="text-xs text-gray-500 dark:text-slate-400 mt-0.5">
          {isUp ? "上昇" : "下落"}予測精度（n={row.total}）
        </div>
      </div>
    </div>
  );
}

// ── シグナルプレビューモック ────────────────────────────────────
function SignalPreview() {
  const items = [
    { code: "7203", name: "トヨタ自動車", prob: 84.2, signal: "UP" },
    { code: "9984", name: "ソフトバンクG", prob: 79.5, signal: "UP" },
    { code: "6758", name: "ソニーグループ", prob: 73.1, signal: "UP" },
    { code: "6367", name: "ダイキン工業", prob: 71.8, signal: "UP" },
  ];
  return (
    <div className="rounded-2xl border border-gray-200 dark:border-slate-700 bg-white dark:bg-slate-900 shadow-xl overflow-hidden">
      {/* ヘッダーバー */}
      <div className="bg-gray-50 dark:bg-slate-800/80 px-4 py-3 border-b border-gray-200 dark:border-slate-700 flex items-center gap-2">
        <span className="w-3 h-3 rounded-full bg-red-400" />
        <span className="w-3 h-3 rounded-full bg-yellow-400" />
        <span className="w-3 h-3 rounded-full bg-green-400" />
        <span className="ml-2 text-xs text-gray-400 font-mono">stock-intelligence.app</span>
        <span className="ml-auto flex items-center gap-1.5">
          <span className="live-dot" />
          <span className="text-xs text-gray-400">LIVE</span>
        </span>
      </div>
      {/* テーブルヘッダー */}
      <div className="grid grid-cols-3 px-4 py-2 bg-gray-50 dark:bg-slate-800/40 text-xs text-gray-400 font-semibold uppercase tracking-wide">
        <span>銘柄</span><span className="text-center">シグナル</span><span className="text-right">確率</span>
      </div>
      {/* 行 */}
      {items.map((item) => (
        <div key={item.code} className="grid grid-cols-3 items-center px-4 py-3 border-t border-gray-100 dark:border-slate-800 hover:bg-brand-50/30 dark:hover:bg-brand-900/10 transition-colors">
          <div>
            <div className="font-semibold text-sm text-gray-900 dark:text-white">{item.name}</div>
            <div className="text-xs text-gray-400">{item.code}</div>
          </div>
          <div className="text-center">
            <span className="px-2 py-0.5 rounded-full bg-emerald-100 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-400 text-xs font-bold">
              ↑ UP
            </span>
          </div>
          <div className="text-right">
            <div className="flex items-center justify-end gap-2">
              <div className="prob-bar-track w-12 hidden sm:block">
                <div className="prob-bar-fill bg-brand-500" style={{ width: `${item.prob}%` }} />
              </div>
              <span className="font-mono font-bold text-brand-600 dark:text-brand-400 text-sm">
                {item.prob}%
              </span>
            </div>
          </div>
        </div>
      ))}
      <div className="px-4 py-2.5 bg-gray-50 dark:bg-slate-800/40 border-t border-gray-200 dark:border-slate-700 text-xs text-gray-400 text-center">
        本日のシグナル 32件 — Proプランで全件表示
      </div>
    </div>
  );
}

// ── 機能カード ─────────────────────────────────────────────────
function FeatureCard({
  icon, title, desc, accent,
}: { icon: React.ReactNode; title: string; desc: string; accent?: string }) {
  return (
    <div className="group rounded-2xl border border-gray-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-6 hover:border-brand-300 dark:hover:border-brand-700 hover:shadow-md transition-all duration-200">
      <div className={`inline-flex items-center justify-center w-11 h-11 rounded-xl mb-4 ${accent ?? "bg-brand-50 dark:bg-brand-900/30 text-brand-600 dark:text-brand-400"}`}>
        {icon}
      </div>
      <h3 className="font-semibold text-gray-900 dark:text-white mb-1.5">{title}</h3>
      <p className="text-sm text-gray-500 dark:text-slate-400 leading-relaxed">{desc}</p>
    </div>
  );
}

// ── How it works ステップ ───────────────────────────────────────
function StepCard({ num, title, desc }: { num: number; title: string; desc: string }) {
  return (
    <div className="flex gap-4">
      <div className="flex flex-col items-center gap-1 shrink-0">
        <div className="w-9 h-9 rounded-full bg-brand-600 text-white flex items-center justify-center text-sm font-bold">{num}</div>
        {num < 3 && <div className="w-px flex-1 bg-brand-200 dark:bg-brand-800 min-h-[2rem]" />}
      </div>
      <div className="pb-6">
        <h3 className="font-semibold text-gray-900 dark:text-white mb-1">{title}</h3>
        <p className="text-sm text-gray-500 dark:text-slate-400 leading-relaxed">{desc}</p>
      </div>
    </div>
  );
}

// ── 料金カード ─────────────────────────────────────────────────
function PricingCard({
  plan, price, period, features, highlighted, cta, href, badge,
}: {
  plan: string; price: string; period: string;
  features: { text: string; included: boolean }[];
  highlighted?: boolean; cta: string; href: string; badge?: string;
}) {
  return (
    <div className={`rounded-2xl border p-7 flex flex-col gap-5 relative ${
      highlighted
        ? "border-brand-500 bg-gradient-to-b from-brand-50 to-white dark:from-brand-900/20 dark:to-slate-900 ring-2 ring-brand-400 shadow-lg"
        : "border-gray-200 dark:border-slate-700 bg-white dark:bg-slate-900"
    }`}>
      {badge && (
        <span className="absolute -top-3 left-1/2 -translate-x-1/2 px-3 py-1 rounded-full bg-brand-500 text-white text-xs font-bold shadow">
          {badge}
        </span>
      )}
      <div>
        <div className="text-sm font-semibold uppercase tracking-wide text-gray-500 dark:text-slate-400 mb-1">{plan}</div>
        <div className="flex items-end gap-1">
          <span className="text-4xl font-extrabold text-gray-900 dark:text-white">{price}</span>
          <span className="text-sm text-gray-500 dark:text-slate-400 mb-1">{period}</span>
        </div>
      </div>

      <ul className="space-y-2.5 flex-1">
        {features.map((f, i) => (
          <li key={i} className={`flex items-start gap-2 text-sm ${f.included ? "text-gray-700 dark:text-slate-300" : "text-gray-300 dark:text-slate-600 line-through"}`}>
            <CheckCircle2 className={`w-4 h-4 mt-0.5 shrink-0 ${f.included ? "text-brand-500" : "text-gray-200 dark:text-slate-700"}`} />
            {f.text}
          </li>
        ))}
      </ul>

      <Link
        href={href}
        className={`block text-center py-3 rounded-xl font-semibold text-sm transition-colors ${
          highlighted
            ? "bg-brand-600 hover:bg-brand-700 text-white shadow"
            : "bg-gray-100 dark:bg-slate-800 hover:bg-gray-200 dark:hover:bg-slate-700 text-gray-900 dark:text-white"
        }`}
      >
        {cta}
      </Link>
    </div>
  );
}

// ── メイン ─────────────────────────────────────────────────────
export function LandingPage() {
  const { data: accData } = useSWR("accuracy", getAccuracy, { revalidateOnFocus: false });
  const { data: btData }  = useSWR(["backtest", 12], () => getBacktestChart(12), { revalidateOnFocus: false });

  const accuracyRows: AccuracyRow[] = accData?.accuracy ?? [];
  const upRow   = accuracyRows.find(r => r.signal === "UP");
  const downRow = accuracyRows.find(r => r.signal === "DOWN");
  const lastCumReturn = btData?.cumulative_return?.at(-1)?.cumulative_return_pct ?? null;

  return (
    <div className="space-y-28 pb-24">

      {/* ── HERO ───────────────────────────────────────────────── */}
      <section className="pt-10 grid lg:grid-cols-2 gap-12 items-center">
        {/* 左: テキスト */}
        <div className="space-y-6">
          <div className="inline-flex items-center gap-2 rounded-full bg-brand-50 dark:bg-brand-900/30 border border-brand-200 dark:border-brand-700 px-4 py-1.5 text-xs font-medium text-brand-700 dark:text-brand-300">
            <Zap className="w-3.5 h-3.5" />
            LightGBM × XGBoost アンサンブル予測
          </div>

          <h1 className="text-4xl sm:text-5xl font-extrabold text-gray-900 dark:text-white leading-[1.15]">
            AIが毎朝、<br />
            <span className="text-brand-600 dark:text-brand-400">翌日の上昇銘柄</span>を<br />
            自動で選ぶ
          </h1>

          <p className="text-base text-gray-500 dark:text-slate-400 leading-relaxed">
            46種のテクニカル指標 × セクター相対分析 × ニュースセンチメント。
            毎営業日の朝、高確度な騰落シグナルを配信します。
          </p>

          <div className="flex flex-col sm:flex-row gap-3">
            <Link
              href="/auth"
              className="inline-flex items-center justify-center gap-2 bg-brand-600 hover:bg-brand-700 text-white px-7 py-3.5 rounded-xl font-semibold text-base transition-colors shadow-md"
            >
              無料で始める
              <ArrowRight className="w-4 h-4" />
            </Link>
            <Link
              href="/backtest"
              className="inline-flex items-center justify-center gap-2 bg-white dark:bg-slate-900 border border-gray-200 dark:border-slate-700 text-gray-700 dark:text-slate-300 hover:border-brand-400 px-6 py-3.5 rounded-xl font-medium text-sm transition-colors"
            >
              <BarChart2 className="w-4 h-4" />
              バックテスト実績を見る
            </Link>
          </div>

          {/* 実績バッジ */}
          <div className="flex flex-wrap gap-3 pt-2">
            {upRow   && <AccuracyBadge row={upRow} />}
            {downRow && <AccuracyBadge row={downRow} />}
            {lastCumReturn != null && (
              <div className="flex items-center gap-3 rounded-2xl px-5 py-4 bg-brand-50 dark:bg-brand-900/20 border border-brand-200 dark:border-brand-700">
                <TrendingUp className="w-7 h-7 text-brand-600 dark:text-brand-400 shrink-0" />
                <div>
                  <div className={`text-3xl font-extrabold tabular-nums ${lastCumReturn >= 0 ? "text-brand-600 dark:text-brand-400" : "text-red-500"}`}>
                    {lastCumReturn >= 0 ? "+" : ""}{lastCumReturn.toFixed(1)}%
                  </div>
                  <div className="text-xs text-gray-500 dark:text-slate-400 mt-0.5">
                    累積リターン（過去12ヶ月）
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* 右: シグナルプレビュー */}
        <div className="lg:pl-4">
          <SignalPreview />
        </div>
      </section>

      {/* ── 実績数字 ─────────────────────────────────────────── */}
      <section className="grid grid-cols-2 md:grid-cols-4 gap-6 text-center py-8 border-y border-gray-100 dark:border-slate-800">
        {[
          { num: "3,900+", label: "対象銘柄数" },
          { num: "46種", label: "テクニカル指標" },
          { num: "毎営業日", label: "シグナル更新" },
          { num: "2モデル", label: "アンサンブルAI" },
        ].map(({ num, label }) => (
          <div key={label}>
            <div className="text-2xl sm:text-3xl font-extrabold text-gray-900 dark:text-white">{num}</div>
            <div className="text-xs text-gray-500 dark:text-slate-400 mt-1">{label}</div>
          </div>
        ))}
      </section>

      {/* ── How it works ─────────────────────────────────────── */}
      <section className="grid md:grid-cols-2 gap-10 items-start">
        <div className="space-y-3">
          <h2 className="text-2xl font-bold text-gray-900 dark:text-white">どうやって予測するの？</h2>
          <p className="text-sm text-gray-500 dark:text-slate-400">
            毎日3ステップで、翌日上昇が期待される銘柄を自動で選び出します。
          </p>
        </div>
        <div className="space-y-0">
          <StepCard
            num={1}
            title="データ収集"
            desc="J-Quantsから全上場銘柄の株価・出来高・財務データを取得。ニュースセンチメントもリアルタイムで収集。"
          />
          <StepCard
            num={2}
            title="AIが46種の特徴量を解析"
            desc="RSI・MACD・ボリンジャーバンドなどテクニカル指標に加え、セクター相対強度・52週位置・出来高急増などを分析。"
          />
          <StepCard
            num={3}
            title="シグナル配信"
            desc="LightGBM × XGBoostのアンサンブルで翌日の騰落確率を算出。60%以上の銘柄を朝8時までに配信。"
          />
        </div>
      </section>

      {/* ── 機能 ─────────────────────────────────────────────── */}
      <section className="space-y-8">
        <div className="text-center space-y-2">
          <h2 className="text-2xl font-bold text-gray-900 dark:text-white">主な機能</h2>
          <p className="text-sm text-gray-500 dark:text-slate-400">投資判断をサポートするツールが揃っています</p>
        </div>
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-5">
          <FeatureCard
            icon={<Brain className="w-5 h-5" />}
            title="AIシグナル（毎朝配信）"
            desc="終値確定後に全銘柄を解析。60%以上の確度を持つUP/DOWNシグナルのみ表示。AI説明付き。"
            accent="bg-brand-50 dark:bg-brand-900/30 text-brand-600 dark:text-brand-400"
          />
          <FeatureCard
            icon={<BarChart2 className="w-5 h-5" />}
            title="バックテスト実績公開"
            desc="過去シグナルの的中率・平均リターンを月別グラフで公開。透明性のある実績開示。"
            accent="bg-emerald-50 dark:bg-emerald-900/20 text-emerald-600 dark:text-emerald-400"
          />
          <FeatureCard
            icon={<Search className="w-5 h-5" />}
            title="銘柄詳細ページ"
            desc="株価チャート・シグナル履歴・四季報AIサマリーをワンストップで確認できます。"
            accent="bg-blue-50 dark:bg-blue-900/20 text-blue-600 dark:text-blue-400"
          />
          <FeatureCard
            icon={<Layers className="w-5 h-5" />}
            title="セクター相対分析"
            desc="同セクター内での相対的な強さを分析。市場全体が下げても出遅れ銘柄を発掘。"
            accent="bg-violet-50 dark:bg-violet-900/20 text-violet-600 dark:text-violet-400"
          />
          <FeatureCard
            icon={<Bell className="w-5 h-5" />}
            title="メールアラート（Pro）"
            desc="毎日のシグナルをメールで受け取れます。見逃しゼロで投資機会をキャッチ。"
            accent="bg-amber-50 dark:bg-amber-900/20 text-amber-600 dark:text-amber-400"
          />
          <FeatureCard
            icon={<Shield className="w-5 h-5" />}
            title="安心のセキュリティ"
            desc="JWT認証 + Stripe決済。カード情報はStripeが保管し、当サービスには渡りません。"
            accent="bg-slate-50 dark:bg-slate-800 text-slate-600 dark:text-slate-400"
          />
        </div>
      </section>

      {/* ── 料金 ─────────────────────────────────────────────── */}
      <section className="space-y-8" id="pricing">
        <div className="text-center space-y-2">
          <h2 className="text-2xl font-bold text-gray-900 dark:text-white">料金プラン</h2>
          <p className="text-sm text-gray-500 dark:text-slate-400">まずは無料プランでお試しください。いつでもアップグレード・解約できます。</p>
        </div>

        <div className="grid sm:grid-cols-2 gap-6 max-w-2xl mx-auto">
          <PricingCard
            plan="Free"
            price="¥0"
            period="/ 月"
            cta="無料で始める"
            href="/auth"
            features={[
              { text: "毎日のシグナル（上位10件）", included: true },
              { text: "シグナル確率表示", included: true },
              { text: "バックテスト結果閲覧", included: true },
              { text: "銘柄検索", included: true },
              { text: "全件シグナル表示", included: false },
              { text: "メールアラート", included: false },
            ]}
          />
          <PricingCard
            plan="Pro"
            price="¥2,980"
            period="/ 月"
            cta="Pro を始める"
            href="/billing"
            highlighted
            badge="おすすめ"
            features={[
              { text: "毎日のシグナル（全件）", included: true },
              { text: "AI説明 + 根拠チップ", included: true },
              { text: "銘柄詳細 + 株価チャート", included: true },
              { text: "四季報AIサマリー", included: true },
              { text: "メールアラート（毎日配信）", included: true },
              { text: "いつでも解約可能", included: true },
            ]}
          />
        </div>
      </section>

      {/* ── FAQ ──────────────────────────────────────────────── */}
      <section className="space-y-5 max-w-2xl mx-auto">
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
            <details key={i} className="group rounded-xl border border-gray-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-5 cursor-pointer open:border-brand-300 dark:open:border-brand-700 transition-colors">
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
      <section className="relative overflow-hidden text-center rounded-3xl bg-gradient-to-br from-brand-600 to-brand-700 dark:from-brand-700 dark:to-brand-800 py-16 px-8 shadow-xl">
        <div className="absolute inset-0 opacity-10" style={{
          backgroundImage: "radial-gradient(circle at 20% 50%, white 0%, transparent 50%), radial-gradient(circle at 80% 20%, white 0%, transparent 40%)"
        }} />
        <div className="relative z-10 space-y-4">
          <h2 className="text-2xl sm:text-3xl font-bold text-white">今すぐ無料で始める</h2>
          <p className="text-brand-100 text-sm">クレジットカード不要。30秒で登録完了。</p>
          <Link
            href="/auth"
            className="inline-flex items-center gap-2 bg-white text-brand-700 hover:bg-brand-50 px-8 py-3.5 rounded-xl font-bold text-base transition-colors shadow"
          >
            無料アカウントを作成
            <ChevronRight className="w-4 h-4" />
          </Link>
        </div>
      </section>

    </div>
  );
}
