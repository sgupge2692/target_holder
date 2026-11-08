"use client";
import Link from "next/link";
import useSWR from "swr";
import { getAccuracy, getBacktestChart, type AccuracyRow } from "@/lib/api";
import {
  TrendingUp, TrendingDown, Zap, BarChart2,
  CheckCircle2, ChevronRight, Star, Bell, Search, ArrowRight,
  Shield, Brain, Layers, Sparkles,
} from "lucide-react";

// ── シグナルプレビュー（モック）────────────────────────────────────────────
function SignalPreview() {
  const items = [
    { code: "7203", name: "トヨタ自動車",   prob: 84.2, signal: "UP" },
    { code: "9984", name: "ソフトバンクG",  prob: 79.5, signal: "UP" },
    { code: "6758", name: "ソニーグループ", prob: 73.1, signal: "UP" },
    { code: "8306", name: "三菱UFJ",        prob: 78.4, signal: "DOWN" },
    { code: "6367", name: "ダイキン工業",   prob: 71.8, signal: "DOWN" },
  ];
  return (
    <div className="relative">
      {/* 背景グロー */}
      <div className="absolute -inset-4 bg-gradient-to-r from-teal-500/10 to-teal-600/5 rounded-3xl blur-2xl" />

      <div className="relative rounded border border-slate-700/60 bg-[#0c1424] overflow-hidden shadow-2xl">
        {/* ウィンドウ風ヘッダー */}
        <div className="flex items-center gap-2 px-4 py-3 bg-[#060b16] border-b border-slate-700/40">
          <span className="w-2.5 h-2.5 rounded-full bg-red-400" />
          <span className="w-2.5 h-2.5 rounded-full bg-yellow-400" />
          <span className="w-2.5 h-2.5 rounded-full bg-green-400" />
          <span className="ml-2 text-xs text-slate-500 font-mono">kabumi.app</span>
          <div className="ml-auto flex items-center gap-1.5 px-2 py-0.5 rounded border border-teal-700/40 bg-teal-900/20">
            <span className="live-dot w-1.5 h-1.5" />
            <span className="text-xs font-black tracking-widest uppercase text-teal-400">LIVE</span>
          </div>
        </div>

        {/* テーブルヘッダー */}
        <div className="grid grid-cols-3 px-4 py-2.5 text-[10px] text-slate-500 font-black uppercase tracking-widest bg-[#060b16]">
          <span>銘柄</span>
          <span className="text-center">シグナル</span>
          <span className="text-right">確率</span>
        </div>

        {/* 行 */}
        {items.map((item, i) => {
          const isDown = item.signal === "DOWN";
          return (
            <div
              key={item.code}
              className="grid grid-cols-3 items-center px-4 py-3 border-t border-slate-700/40 hover:bg-slate-800/20 transition-colors"
              style={{ animationDelay: `${i * 80}ms` }}
            >
              <div>
                <div className="font-semibold text-sm text-white leading-tight">{item.name}</div>
                <div className="text-xs text-slate-500 mt-0.5 font-mono">{item.code}</div>
              </div>
              <div className="flex justify-center">
                <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-black tracking-widest uppercase ${
                  isDown
                    ? "bg-red-900/30 text-red-400 border border-red-700/40"
                    : "bg-teal-900/30 text-teal-400 border border-teal-700/40"
                }`}>
                  {isDown ? "↓ DOWN" : "↑ UP"}
                </span>
              </div>
              <div className="flex items-center justify-end gap-2">
                <div className="prob-bar-track w-12 hidden sm:block">
                  <div
                    className={`prob-bar-fill ${isDown ? "bg-red-500" : "bg-teal-500"}`}
                    style={{ width: `${item.prob}%` }}
                  />
                </div>
                <span className={`font-mono font-bold text-sm tabular-nums ${
                  isDown ? "text-red-400" : "text-teal-400"
                }`}>
                  {item.prob}%
                </span>
              </div>
            </div>
          );
        })}

        <div className="px-4 py-3 border-t border-slate-700/40 bg-[#060b16] text-xs text-slate-500 text-center">
          本日のシグナル <span className="font-bold text-slate-300">32件</span> — Proプランで全件表示
        </div>
      </div>
    </div>
  );
}

// ── 実績バッジ ─────────────────────────────────────────────────────────────
function StatBadge({ value, label, isUp }: { value: string; label: string; isUp?: boolean }) {
  return (
    <div className={`flex items-center gap-3 rounded px-4 py-3.5 border ${
      isUp === false
        ? "border-red-700/40 bg-red-900/20"
        : "border-teal-700/40 bg-teal-900/20"
    }`}>
      {isUp === false
        ? <TrendingDown className="w-6 h-6 text-red-400 shrink-0" />
        : <TrendingUp className="w-6 h-6 text-teal-500 shrink-0" />
      }
      <div>
        <div className={`text-2xl font-black tabular-nums leading-none font-mono ${
          isUp === false ? "text-red-400" : "text-teal-400"
        }`}>{value}</div>
        <div className="text-xs text-slate-500 mt-0.5 leading-tight">{label}</div>
      </div>
    </div>
  );
}

// ── 機能カード ─────────────────────────────────────────────────────────────
function FeatureCard({
  icon, title, desc,
}: { icon: React.ReactNode; title: string; desc: string; color: string }) {
  return (
    <div className="group relative rounded border border-slate-700/60 bg-[#0c1424] p-6 overflow-hidden hover:border-teal-700/50 transition-all duration-200 hover:shadow-lg hover:-translate-y-0.5">
      <div className="relative">
        <div className="inline-flex items-center justify-center w-10 h-10 rounded mb-4 bg-[#060b16] border border-slate-700/60">
          {icon}
        </div>
        <h3 className="font-black text-sm text-white mb-1.5">{title}</h3>
        <p className="text-xs text-slate-500 leading-relaxed">{desc}</p>
      </div>
    </div>
  );
}

// ── ステップ ────────────────────────────────────────────────────────────────
function Step({ num, title, desc, last }: { num: number; title: string; desc: string; last?: boolean }) {
  return (
    <div className="flex gap-4">
      <div className="flex flex-col items-center shrink-0">
        <div className="w-9 h-9 rounded bg-teal-600 text-white flex items-center justify-center text-sm font-black font-mono">
          {num}
        </div>
        {!last && <div className="w-px flex-1 mt-1 bg-gradient-to-b from-teal-700 to-teal-900 min-h-[2.5rem]" />}
      </div>
      <div className="pb-7">
        <h3 className="font-black text-white mb-1 text-sm">{title}</h3>
        <p className="text-sm text-slate-500 leading-relaxed">{desc}</p>
      </div>
    </div>
  );
}

// ── 料金カード ─────────────────────────────────────────────────────────────
function PricingCard({
  plan, price, period, features, highlighted, cta, href, badge,
}: {
  plan: string; price: string; period: string;
  features: { text: string; included: boolean }[];
  highlighted?: boolean; cta: string; href: string; badge?: string;
}) {
  return (
    <div className={`relative rounded p-7 flex flex-col gap-5 transition-all border ${
      highlighted
        ? "bg-teal-900/20 border-teal-600/60"
        : "bg-[#0c1424] border-slate-700/60"
    }`}>
      {badge && (
        <span className="absolute -top-3 left-1/2 -translate-x-1/2 flex items-center gap-1 px-3 py-1 rounded bg-amber-500 text-black text-xs font-black shadow">
          <Star className="w-3 h-3" />{badge}
        </span>
      )}

      <div>
        <div className={`text-[10px] font-black uppercase tracking-widest mb-2 ${highlighted ? "text-teal-400" : "text-slate-500"}`}>
          {plan}
        </div>
        <div className="flex items-end gap-1.5">
          <span className="text-4xl font-black text-white font-mono">{price}</span>
          <span className={`text-sm mb-1 ${highlighted ? "text-teal-400" : "text-slate-500"}`}>{period}</span>
        </div>
      </div>

      <ul className="space-y-2.5 flex-1">
        {features.map((f, i) => (
          <li key={i} className={`flex items-start gap-2 text-sm ${
            f.included
              ? "text-slate-200"
              : "text-slate-600 line-through"
          }`}>
            <CheckCircle2 className={`w-4 h-4 mt-0.5 shrink-0 ${
              f.included
                ? highlighted ? "text-teal-400" : "text-teal-500"
                : "text-slate-700"
            }`} />
            {f.text}
          </li>
        ))}
      </ul>

      <Link
        href={href}
        className={`block text-center py-3 rounded font-black text-xs tracking-widest uppercase transition-all ${
          highlighted
            ? "bg-teal-600 hover:bg-teal-500 text-white"
            : "bg-[#060b16] hover:bg-slate-800 border border-slate-700/60 text-slate-300"
        }`}
      >
        {cta}
      </Link>
    </div>
  );
}

// ── メイン ─────────────────────────────────────────────────────────────────
export function LandingPage() {
  const { data: accData } = useSWR("accuracy", getAccuracy, { revalidateOnFocus: false });
  const { data: btData  } = useSWR(["backtest", 12], () => getBacktestChart(12), { revalidateOnFocus: false });

  const accuracyRows: AccuracyRow[] = accData?.accuracy ?? [];
  const upRow   = accuracyRows.find(r => r.signal === "UP");
  const downRow = accuracyRows.find(r => r.signal === "DOWN");
  const lastCumReturn = btData?.cumulative_return?.at(-1)?.cumulative_return_pct ?? null;

  return (
    <div className="space-y-28 pb-24">

      {/* ── HERO ───────────────────────────────────────────────────────────── */}
      <section className="pt-8 grid lg:grid-cols-2 gap-14 items-center">
        {/* 左: テキスト */}
        <div className="space-y-7">
          {/* バッジ */}
          <div className="inline-flex items-center gap-2 rounded border border-teal-700/40 bg-teal-900/20 px-4 py-1.5 text-xs font-black tracking-widest uppercase text-teal-400">
            <Sparkles className="w-3.5 h-3.5" />
            LightGBM × XGBoost アンサンブルAI
          </div>

          {/* 見出し */}
          <h1 className="text-5xl sm:text-6xl font-black text-white leading-[1.08] tracking-tight">
            株の<br />
            <span className="relative inline-block">
              <span className="relative z-10 text-teal-400">上がる・下がる</span>
              <span className="absolute bottom-1 left-0 right-0 h-3 bg-teal-900/40 -z-10 rounded" />
            </span>
            <br />をAIが予測
          </h1>

          <p className="text-base text-slate-400 leading-relaxed max-w-md">
            毎営業日の朝、46種のテクニカル指標 × セクター分析 × ニュースセンチメントで
            翌日の騰落シグナルを自動配信。
          </p>

          {/* CTA ボタン */}
          <div className="flex flex-col sm:flex-row gap-3">
            <Link
              href="/auth"
              className="inline-flex items-center justify-center gap-2 bg-teal-600 hover:bg-teal-500 active:scale-95 text-white px-8 py-4 rounded font-black text-sm tracking-widest uppercase transition-all"
            >
              無料で始める
              <ArrowRight className="w-4 h-4" />
            </Link>
            <Link
              href="/backtest"
              className="inline-flex items-center justify-center gap-2 bg-[#0c1424] border border-slate-700/60 text-slate-400 hover:border-teal-700/50 hover:text-slate-200 px-6 py-4 rounded font-black text-xs tracking-widest uppercase transition-all"
            >
              <BarChart2 className="w-4 h-4" />
              実績を確認する
            </Link>
          </div>

          {/* 実績バッジ */}
          <div className="flex flex-wrap gap-3 pt-1">
            {upRow && (
              <StatBadge value={`${upRow.accuracy_pct}%`} label={`UP 的中率・対市場 (n=${upRow.total})`} isUp={true} />
            )}
            {downRow && (
              <StatBadge value={`${downRow.accuracy_pct}%`} label={`DOWN 的中率・対市場 (n=${downRow.total})`} isUp={false} />
            )}
            {lastCumReturn != null && (
              <StatBadge
                value={`${lastCumReturn >= 0 ? "+" : ""}${lastCumReturn.toFixed(1)}%`}
                label="累積リターン（12ヶ月）"
              />
            )}
          </div>
        </div>

        {/* 右: プレビュー */}
        <div className="lg:pl-6">
          <SignalPreview />
        </div>
      </section>

      {/* ── スタッツ ────────────────────────────────────────────────────────── */}
      <section className="grid grid-cols-2 md:grid-cols-4 gap-4 py-10 border-y border-slate-700/40">
        {[
          { num: "3,900+", label: "対象銘柄" },
          { num: "46種",   label: "テクニカル指標" },
          { num: "毎朝",   label: "シグナル更新" },
          { num: "2 AI",   label: "アンサンブルモデル" },
        ].map(({ num, label }) => (
          <div key={label} className="text-center">
            <div className="text-3xl font-black text-white tabular-nums font-mono">{num}</div>
            <div className="text-[10px] font-black tracking-widest uppercase text-slate-500 mt-1.5">{label}</div>
          </div>
        ))}
      </section>

      {/* ── How it works ────────────────────────────────────────────────────── */}
      <section className="grid md:grid-cols-2 gap-12 items-start">
        <div className="space-y-4 md:sticky md:top-24">
          <div className="inline-flex items-center gap-2 text-[10px] font-black text-teal-400 uppercase tracking-widest">
            <Zap className="w-3.5 h-3.5" />
            How it works
          </div>
          <h2 className="text-3xl font-black text-white leading-tight">
            どうやって<br />予測するの？
          </h2>
          <p className="text-sm text-slate-500 leading-relaxed">
            毎日3ステップで、翌日に市場平均を上回る・下回ると予測される銘柄を自動選定します。
          </p>
        </div>
        <div>
          <Step
            num={1}
            title="データ収集"
            desc="J-Quantsから全上場銘柄の株価・出来高・財務データを取得。ニュースセンチメントもリアルタイムで収集。"
          />
          <Step
            num={2}
            title="46種の特徴量を解析"
            desc="RSI・MACD・ボリンジャーバンドなどテクニカル指標に加え、セクター相対強度・52週高値位置・出来高急増などを分析。"
          />
          <Step
            num={3}
            title="シグナル配信"
            desc="LightGBM × XGBoostのアンサンブルで翌日の騰落確率を算出。60%以上を毎朝8時までに配信。"
            last
          />
        </div>
      </section>

      {/* ── 機能 ────────────────────────────────────────────────────────────── */}
      <section className="space-y-10">
        <div className="text-center space-y-3">
          <div className="inline-flex items-center gap-2 text-[10px] font-black text-teal-400 uppercase tracking-widest">
            <Star className="w-3.5 h-3.5" />
            Features
          </div>
          <h2 className="text-3xl font-black text-white">主な機能</h2>
          <p className="text-sm text-slate-500">投資判断をサポートするツールが揃っています</p>
        </div>
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
          <FeatureCard
            icon={<Brain className="w-4 h-4 text-teal-400" />}
            title="AIシグナル（毎朝配信）"
            desc="終値確定後に全銘柄を解析。60%以上の確度を持つUP/DOWNシグナルのみ表示。AI説明付き。"
            color=""
          />
          <FeatureCard
            icon={<BarChart2 className="w-4 h-4 text-teal-400" />}
            title="バックテスト実績公開"
            desc="過去シグナルの的中率・平均リターンを月別グラフで公開。透明性のある実績開示。"
            color=""
          />
          <FeatureCard
            icon={<Search className="w-4 h-4 text-blue-400" />}
            title="銘柄詳細ページ"
            desc="株価チャート・シグナル履歴・四季報AIサマリーをワンストップで確認。"
            color=""
          />
          <FeatureCard
            icon={<Layers className="w-4 h-4 text-violet-400" />}
            title="セクター相対分析"
            desc="同セクター内での相対強度を分析。市場全体が下げても出遅れ銘柄を発掘。"
            color=""
          />
          <FeatureCard
            icon={<Bell className="w-4 h-4 text-amber-400" />}
            title="メールアラート（Pro）"
            desc="毎日のシグナルをメールで受け取れます。見逃しゼロで投資機会をキャッチ。"
            color=""
          />
          <FeatureCard
            icon={<Shield className="w-4 h-4 text-slate-400" />}
            title="安心のセキュリティ"
            desc="JWT認証 + Stripe決済。カード情報はStripeが保管し、当サービスには渡りません。"
            color=""
          />
        </div>
      </section>

      {/* ── 料金 ────────────────────────────────────────────────────────────── */}
      <section className="space-y-10" id="pricing">
        <div className="text-center space-y-3">
          <div className="text-[10px] font-black text-teal-400 uppercase tracking-widest">
            Pricing
          </div>
          <h2 className="text-3xl font-black text-white">料金プラン</h2>
          <p className="text-sm text-slate-500">まずは無料でお試し。いつでも解約できます。</p>
        </div>

        <div className="grid sm:grid-cols-2 gap-5 max-w-2xl mx-auto">
          <PricingCard
            plan="Free"
            price="¥0"
            period="/ 月"
            cta="無料で始める"
            href="/auth"
            features={[
              { text: "毎日のシグナル（上位3件）", included: true },
              { text: "シグナル確率表示",          included: true },
              { text: "バックテスト結果閲覧",       included: true },
              { text: "銘柄検索",                  included: true },
              { text: "全件シグナル表示",           included: false },
              { text: "スイング/長期/信用売りモード",included: false },
              { text: "メールアラート",             included: false },
            ]}
          />
          <PricingCard
            plan="Pro"
            price="¥2,980"
            period="/ 月"
            cta="Proを始める"
            href="/billing"
            highlighted
            badge="おすすめ"
            features={[
              { text: "毎日のシグナル（全件）",      included: true },
              { text: "AI説明 + 根拠チップ",         included: true },
              { text: "スイング/長期/信用売りモード", included: true },
              { text: "銘柄詳細 + 株価チャート",      included: true },
              { text: "メールアラート（毎日配信）",   included: true },
              { text: "CSVダウンロード",              included: true },
              { text: "いつでも解約可能",             included: true },
            ]}
          />
        </div>
      </section>

      {/* ── FAQ ─────────────────────────────────────────────────────────────── */}
      <section className="space-y-6 max-w-2xl mx-auto">
        <h2 className="text-3xl font-black text-center text-white">よくある質問</h2>
        <div className="space-y-2.5">
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
            <details
              key={i}
              className="group rounded border border-slate-700/60 bg-[#0c1424] px-5 py-4 cursor-pointer open:border-teal-700/50 transition-colors"
            >
              <summary className="flex items-center justify-between font-black text-sm text-white list-none select-none">
                {q}
                <ChevronRight className="w-4 h-4 text-slate-500 group-open:rotate-90 transition-transform duration-200 shrink-0 ml-4" />
              </summary>
              <p className="mt-3 text-sm text-slate-500 leading-relaxed">{a}</p>
            </details>
          ))}
        </div>
      </section>

      {/* ── BottomCTA ───────────────────────────────────────────────────────── */}
      <section className="relative overflow-hidden text-center rounded border border-teal-700/40 py-20 px-8 bg-teal-900/20">
        {/* グリッドテクスチャ */}
        <div className="absolute inset-0 opacity-5" style={{
          backgroundImage: "linear-gradient(rgba(45,212,191,0.3) 1px, transparent 1px), linear-gradient(90deg, rgba(45,212,191,0.3) 1px, transparent 1px)",
          backgroundSize: "32px 32px"
        }} />

        <div className="relative z-10 space-y-5">
          <div className="inline-flex items-center gap-2 bg-teal-900/40 border border-teal-700/40 px-4 py-1.5 rounded text-teal-400 text-xs font-black tracking-widest uppercase">
            <Zap className="w-3.5 h-3.5" />
            30秒で登録完了
          </div>
          <h2 className="text-3xl sm:text-4xl font-black text-white">今すぐ無料で始める</h2>
          <p className="text-teal-300/70 text-sm">クレジットカード不要。いつでも解約できます。</p>
          <Link
            href="/auth"
            className="inline-flex items-center gap-2 bg-teal-600 hover:bg-teal-500 active:scale-95 text-white px-8 py-4 rounded font-black text-sm tracking-widest uppercase transition-all shadow-lg mt-2"
          >
            無料アカウントを作成
            <ArrowRight className="w-4 h-4" />
          </Link>
        </div>
      </section>

    </div>
  );
}
