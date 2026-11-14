"use client";
import useSWR from "swr";
import Link from "next/link";
import { getSectorHeatmap, SectorStrength } from "@/lib/api";

// 確率(0.5 が中立)を色の濃さに変える。±8pt で最大濃度（校正後の確率は 50% 付近に寄るため狭い幅にしている）
function cellStyle(prob: number): React.CSSProperties {
  const diff = Math.max(-0.08, Math.min(0.08, prob - 0.5)) / 0.08; // -1 〜 1
  const alpha = 0.12 + Math.abs(diff) * 0.55;
  const rgb = diff >= 0 ? "13,148,136" : "239,68,68";
  return { background: `rgba(${rgb},${alpha.toFixed(2)})` };
}

function SectorCell({ s }: { s: SectorStrength }) {
  const pct = (s.avg_up_probability * 100).toFixed(1);
  const diff = (s.avg_up_probability - 0.5) * 100;
  return (
    <div
      className="rounded border border-slate-300 dark:border-slate-700/60 p-3 flex flex-col gap-1"
      style={cellStyle(s.avg_up_probability)}
    >
      <div className="text-xs font-black text-slate-900 dark:text-white leading-tight">{s.sector_name}</div>
      <div className="text-lg font-black tabular-nums font-mono text-slate-900 dark:text-white">
        {pct}%
        <span className="ml-1 text-[10px] font-bold text-slate-600 dark:text-slate-300">
          ({diff >= 0 ? "+" : ""}{diff.toFixed(1)}pt)
        </span>
      </div>
      <div className="text-[10px] text-slate-700 dark:text-slate-300">
        {s.stock_count}銘柄 ・ 強 {s.up_count} / 弱 {s.down_count}
      </div>
    </div>
  );
}

export default function SectorsPage() {
  const { data, isLoading, error } = useSWR("sector-heatmap", getSectorHeatmap, { refreshInterval: 300_000 });
  const sectors = data?.sectors ?? [];

  return (
    <div className="max-w-5xl mx-auto px-4 py-6 space-y-5">
      <div>
        <h1 className="text-xl font-black tracking-tight text-slate-900 dark:text-white uppercase">Sector Strength</h1>
        <p className="text-xs text-slate-600 dark:text-slate-400 mt-1 leading-relaxed">
          業種ごとの「翌営業日に市場平均を上回る確率」の平均です。緑が市場より強い、赤が弱いと予測された業種です
          （50% が中立）。{data?.date && <>基準日: {data.date}</>}
        </p>
      </div>

      {isLoading && <div className="text-sm text-slate-500 py-10 text-center">読み込み中...</div>}
      {error && <div className="text-sm text-red-500 py-10 text-center">データを取得できませんでした。</div>}

      {data && sectors.length === 0 && (
        <div className="text-sm text-slate-500 py-16 text-center">
          まだ集計できるシグナルがありません。
        </div>
      )}

      {sectors.length > 0 && (
        <>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2">
            {sectors.map((s) => <SectorCell key={s.sector_code} s={s} />)}
          </div>
          <p className="text-[11px] text-slate-500 leading-relaxed">
            銘柄数が{data?.min_stocks}件未満の業種は、平均がぶれるため表示していません。
            業種の強弱は翌営業日の相対的な予測であり、将来の成果を保証するものではありません。
            情報提供を目的としたもので、投資助言・売買の推奨ではありません。
          </p>
        </>
      )}

      <div className="rounded border border-teal-600/30 bg-teal-50 dark:bg-teal-900/10 p-5 text-center space-y-2">
        <p className="text-sm text-slate-700 dark:text-slate-300">業種の中で、どの銘柄が強いと予測されているかはシグナル一覧で確認できます。</p>
        <Link href="/" className="inline-block rounded bg-teal-600 px-5 py-2 text-xs font-black tracking-widest uppercase text-white hover:bg-teal-500">
          シグナルを見る
        </Link>
      </div>
    </div>
  );
}
