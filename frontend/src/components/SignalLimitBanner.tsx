"use client";

import Link from "next/link";
import { ArrowRight, Lock } from "lucide-react";

interface SignalLimitBannerProps {
  /** 実際に表示されたシグナル数 */
  shown: number;
  /** 制限前の全シグナル数 */
  totalAvailable: number;
  /** 無料プランの閲覧上限 */
  freeLimit: number;
}

/**
 * 無料ユーザーがシグナル閲覧上限に達したときに一覧の末尾へ出すアップグレード誘導。
 * 件数は API の値をそのまま使う（上限を変えてもここは修正不要）。
 */
export function SignalLimitBanner({
  shown,
  totalAvailable,
  freeLimit,
}: SignalLimitBannerProps) {
  const hiddenCount = Math.max(totalAvailable - shown, 0);
  if (hiddenCount === 0) return null;

  return (
    <div className="relative overflow-hidden rounded border border-teal-500/30 bg-teal-50/60 dark:bg-[#0c1424]">
      <div className="flex flex-col items-center gap-3 px-4 py-6 text-center">
        <span className="inline-flex items-center gap-1.5 rounded bg-teal-500/10 px-3 py-1 text-[11px] font-black tracking-widest uppercase text-teal-600 dark:text-teal-400">
          <Lock size={12} />
          あと <span className="font-mono">{hiddenCount}</span> 件のシグナルが非表示
        </span>

        <p className="max-w-xs text-sm leading-relaxed text-slate-600 dark:text-slate-300">
          無料プランは確度の高い上位{" "}
          <span className="font-mono font-bold text-slate-900 dark:text-white">{freeLimit}</span>{" "}
          件まで閲覧できます。
          <br />
          <span className="font-semibold text-teal-600 dark:text-teal-400">Pro</span>{" "}
          にすると全シグナル・ICT分析・CSV出力が使えます。
        </p>

        <Link
          href="/billing"
          className="inline-flex items-center gap-2 rounded bg-teal-500 px-5 py-2.5 text-sm font-bold text-black transition hover:bg-teal-400 active:scale-95"
        >
          Proにアップグレード
          <ArrowRight size={16} />
        </Link>

        <p className="text-[11px] text-slate-500">
          投資助言ではなく参考情報です · いつでも解約できます
        </p>
      </div>
    </div>
  );
}
