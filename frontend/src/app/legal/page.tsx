import type { Metadata } from "next";
import { LegalPage, Todo } from "@/components/LegalPage";

export const metadata: Metadata = {
  title: "特定商取引法に基づく表記",
  description: "かぶみの特定商取引法に基づく表記。",
};

const ROWS: { label: string; value: React.ReactNode }[] = [
  { label: "販売業者", value: <Todo>氏名または事業者名</Todo> },
  { label: "運営責任者", value: <Todo>氏名</Todo> },
  { label: "所在地", value: <Todo>住所（請求があれば遅滞なく開示する旨に変更可。弁護士等に要確認）</Todo> },
  { label: "電話番号", value: <Todo>電話番号（請求があれば遅滞なく開示する旨に変更可。要確認）</Todo> },
  { label: "メールアドレス", value: <Todo>連絡用メールアドレス</Todo> },
  { label: "サイトURL", value: <Todo>サービスのURL</Todo> },
  {
    label: "販売価格",
    value: "Proプラン: 月額 2,980円（税込）／年額 29,800円（税込・年払いの提供開始後）。無料プランは0円。最新の価格は料金ページに表示します。",
  },
  { label: "商品代金以外の必要料金", value: "インターネット接続にかかる通信料等は利用者の負担となります。" },
  { label: "お支払い方法", value: "クレジットカード（Stripeによる決済）" },
  { label: "お支払い時期", value: "お申込み時に初回決済、以降は選択した期間（月払いは毎月、年払いは毎年）の更新日に自動で決済されます。" },
  { label: "サービスの提供時期", value: "決済完了後、ただちにProプランの機能をご利用いただけます。" },
  {
    label: "解約・返金について",
    value:
      "解約はアカウント管理画面（Stripeカスタマーポータル）からいつでも可能です。解約後も、支払い済みの期間の末日（年払いは1年分の期間の末日）までご利用いただけます。デジタルサービスの性質上、法令に定める場合を除き、支払い済みの料金の返金・日割り計算は行いません。",
  },
  { label: "動作環境", value: "最新版の主要ブラウザ（Chrome / Safari / Edge / Firefox）。" },
  {
    label: "投資に関する注意",
    value:
      "本サービスは情報提供を目的としたものであり、投資の勧誘・助言ではありません。利益や的中を保証するものではなく、元本割れのリスクがあります。",
  },
];

export default function LegalNoticePage() {
  return (
    <LegalPage title="特定商取引法に基づく表記" updatedAt="2026-11-08">
      <dl className="divide-y divide-slate-200 rounded border border-slate-200 dark:divide-[#1a2740] dark:border-[#1a2740]">
        {ROWS.map(({ label, value }) => (
          <div key={label} className="grid gap-1 px-4 py-3 text-sm sm:grid-cols-[12rem_1fr] sm:gap-4">
            <dt className="text-[11px] font-black uppercase tracking-widest text-slate-500">{label}</dt>
            <dd className="leading-relaxed text-slate-700 dark:text-slate-300">{value}</dd>
          </div>
        ))}
      </dl>
    </LegalPage>
  );
}
