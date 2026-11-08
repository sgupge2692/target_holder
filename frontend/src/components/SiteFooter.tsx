import Link from "next/link";

/** 全ページ共通フッター。投資に関する注意書きと法務ページへのリンク。 */
export function SiteFooter() {
  return (
    <footer className="mx-auto max-w-6xl space-y-3 border-t border-slate-200 px-4 py-6 has-bottom-nav md:pb-8 dark:border-[#1a2740]">
      <p className="text-[11px] leading-relaxed text-slate-500 dark:text-slate-500">
        当サービスが提供するシグナル・予測・AI解説は、統計モデルによる参考情報であり、特定の銘柄の売買を推奨・勧誘するものではありません。
        予測の的中や利益を保証するものではなく、過去の成績は将来の結果を示すものではありません。
        投資に関する最終判断はご自身の責任で行ってください。
      </p>
      <nav className="flex flex-wrap gap-x-5 gap-y-1 text-[11px] font-bold text-slate-500 dark:text-slate-400">
        <Link href="/terms" className="hover:text-teal-600 dark:hover:text-teal-400">利用規約・免責事項</Link>
        <Link href="/privacy" className="hover:text-teal-600 dark:hover:text-teal-400">プライバシーポリシー</Link>
        <Link href="/legal" className="hover:text-teal-600 dark:hover:text-teal-400">特定商取引法に基づく表記</Link>
      </nav>
      <p className="font-mono text-[10px] text-slate-400 dark:text-slate-600">© かぶみ</p>
    </footer>
  );
}
