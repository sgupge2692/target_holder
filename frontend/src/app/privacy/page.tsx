import type { Metadata } from "next";
import { LegalPage, LegalSection, Todo } from "@/components/LegalPage";

export const metadata: Metadata = {
  title: "プライバシーポリシー",
  description: "かぶみにおける個人情報・利用データの取扱いについて。",
};

export default function PrivacyPage() {
  return (
    <LegalPage
      title="プライバシーポリシー"
      updatedAt="2026-11-08"
      lead="「かぶみ」（以下「本サービス」）は、利用者の個人情報を次のとおり取り扱います。"
    >
      <LegalSection heading="1. 取得する情報">
        <ul className="list-disc space-y-1.5 pl-5">
          <li>アカウント情報: メールアドレス、パスワード（ハッシュ化して保存し、平文では保持しません）。</li>
          <li>契約・決済に関する情報: プラン、Stripe上の顧客ID・サブスクリプションID、次回請求日。クレジットカード番号は Stripe が管理し、本サービスは保持しません。</li>
          <li>利用状況: ウォッチリスト、模擬売買の記録、通知設定、アクセスログ、エラー情報。</li>
          <li>ブラウザへの保存: ログイン状態を保持するための情報（localStorage 等）。</li>
        </ul>
      </LegalSection>

      <LegalSection heading="2. 利用目的">
        <ul className="list-disc space-y-1.5 pl-5">
          <li>本サービスの提供、本人確認、ログイン管理。</li>
          <li>料金の請求・決済、プランの管理。</li>
          <li>メールによる通知（パスワード再設定、シグナルのアラート、重要なお知らせ）。</li>
          <li>問い合わせへの対応、不正利用の防止、障害の調査と品質改善。</li>
          <li>個人を特定しない統計データとしての、サービス改善・精度検証。</li>
        </ul>
      </LegalSection>

      <LegalSection heading="3. 第三者への提供・外部サービスの利用">
        <p>法令に基づく場合を除き、本人の同意なく個人情報を第三者に提供しません。ただし、サービス運営のため、次の外部サービスに業務を委託しています。</p>
        <ul className="list-disc space-y-1.5 pl-5">
          <li>Stripe, Inc.: 決済処理。</li>
          <li>メール配信事業者（SMTP / SendGrid 等）: 通知メールの送信（メールアドレスを送信先として利用）。</li>
          <li>Sentry: エラー監視（エラー発生時の技術情報）。</li>
          <li>OpenAI: AIによる解説・分析の生成（銘柄・市場データを送信し、利用者のメールアドレス等の個人情報は送信しません）。</li>
          <li>ホスティング事業者: サーバー運用。</li>
        </ul>
        <p>これらの事業者の多くは海外に所在し、情報が日本国外で取り扱われる場合があります。</p>
      </LegalSection>

      <LegalSection heading="4. 保存期間">
        <p>アカウント情報は、退会またはアカウント削除の申し出があるまで保存します。法令上の保存義務があるもの（決済記録等）は、その期間保存します。</p>
      </LegalSection>

      <LegalSection heading="5. 安全管理">
        <p>通信の暗号化（HTTPS）、パスワードのハッシュ化、アクセス権限の管理などにより、個人情報の漏えい・滅失・毀損の防止に努めます。</p>
      </LegalSection>

      <LegalSection heading="6. 開示・訂正・削除の請求">
        <p>ご自身の個人情報の開示、訂正、利用停止、削除を希望される場合は、下記のお問い合わせ先までご連絡ください。ご本人であることを確認のうえ、法令に従い対応します。</p>
      </LegalSection>

      <LegalSection heading="7. 改定">
        <p>本ポリシーは、法令の変更やサービス内容の変更に応じて改定することがあります。重要な変更は本サービス上でお知らせします。</p>
      </LegalSection>

      <LegalSection heading="お問い合わせ先">
        <p>運営者: <Todo>運営者の氏名または名称</Todo></p>
        <p>連絡先: <Todo>連絡用メールアドレス</Todo></p>
      </LegalSection>
    </LegalPage>
  );
}
