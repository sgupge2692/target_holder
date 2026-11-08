import type { ReactNode } from "react";

/** 法務ページ共通レイアウト（利用規約・プライバシー・特商法表記） */
export function LegalPage({
  title,
  updatedAt,
  lead,
  children,
}: {
  title: string;
  updatedAt: string;
  lead?: string;
  children: ReactNode;
}) {
  return (
    <article className="mx-auto max-w-3xl space-y-8">
      <header className="space-y-2 border-b border-slate-200 pb-5 dark:border-[#1a2740]">
        <h1 className="text-xl font-black tracking-tight text-slate-900 dark:text-white">{title}</h1>
        <p className="font-mono text-[11px] tracking-wider text-slate-400 dark:text-slate-500">
          最終更新日: {updatedAt}
        </p>
        {lead && <p className="pt-2 text-sm leading-relaxed text-slate-600 dark:text-slate-300">{lead}</p>}
      </header>
      <div className="space-y-8">{children}</div>
    </article>
  );
}

export function LegalSection({
  heading,
  children,
}: {
  heading: string;
  children: ReactNode;
}) {
  return (
    <section className="space-y-2.5">
      <h2 className="text-sm font-black tracking-wide text-teal-700 dark:text-teal-400">{heading}</h2>
      <div className="space-y-2 text-sm leading-relaxed text-slate-700 dark:text-slate-300">{children}</div>
    </section>
  );
}

/** 運営者情報など、公開前に必ず埋める必要がある項目の目印 */
export function Todo({ children }: { children: ReactNode }) {
  return (
    <span className="rounded bg-amber-100 px-1.5 py-0.5 font-bold text-amber-800 dark:bg-amber-900/30 dark:text-amber-300">
      【要入力：{children}】
    </span>
  );
}
