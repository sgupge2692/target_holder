"use client";
import Link from "next/link";
import { Lock } from "lucide-react";
import type { PeersResponse } from "@/lib/api";
import { SignalBadge } from "@/components/SignalBadge";

/** 同業種の中での位置づけ。順位と業種平均は全員、同業種の個別銘柄は Pro のみ。 */
export function PeersCard({ peers }: { peers: PeersResponse }) {
  if (!peers.sector_name || peers.stock_count === 0) return null;

  const own = peers.up_probability;
  const avg = peers.avg_up_probability;
  const diff = own != null && avg != null ? (own - avg) * 100 : null;

  return (
    <div className="bg-[#0c1424] rounded border border-slate-700/60 p-5 space-y-3">
      <p className="text-[10px] font-black tracking-widest uppercase text-slate-400">
        同業種内の位置づけ（{peers.sector_name}）
      </p>

      <div className="flex flex-wrap items-end gap-x-8 gap-y-2">
        <div>
          <div className="text-[10px] font-black tracking-widest uppercase text-slate-500">業種内順位</div>
          <div className="text-2xl font-black font-mono text-white">
            {peers.rank != null ? <>{peers.rank}<span className="text-sm text-slate-400"> / {peers.stock_count}</span></> : "—"}
          </div>
        </div>
        <div>
          <div className="text-[10px] font-black tracking-widest uppercase text-slate-500">業種平均との差</div>
          <div className={`text-2xl font-black font-mono ${
            diff == null ? "text-slate-500" : diff >= 0 ? "text-teal-400" : "text-red-400"
          }`}>
            {diff == null ? "—" : `${diff >= 0 ? "+" : ""}${diff.toFixed(1)}pt`}
          </div>
        </div>
        <div className="text-[11px] text-slate-500 leading-relaxed">
          「翌営業日に市場平均を上回る確率」を同業種の銘柄で比べたものです。
        </div>
      </div>

      {peers.peers_locked ? (
        <div className="flex items-center gap-2 rounded border border-slate-700/60 px-3 py-2.5 text-xs text-slate-400">
          <Lock size={13} />
          <span>同業種の上位銘柄は Pro プランで見られます。</span>
          <Link href="/billing" className="ml-auto font-black text-teal-400 hover:text-teal-300">Pro を見る</Link>
        </div>
      ) : peers.peers.length > 0 ? (
        <div className="divide-y divide-slate-700/40">
          {peers.peers.map((p) => (
            <Link
              key={p.code}
              href={`/stocks/${p.code}`}
              className="flex items-center gap-3 py-2 text-sm hover:text-teal-400 transition-colors"
            >
              <span className="font-mono text-xs text-slate-500 w-12">{p.code}</span>
              <span className="flex-1 truncate">{p.company_name}</span>
              <SignalBadge signal={p.signal as "UP" | "DOWN"} />
              <span className="font-mono text-xs w-14 text-right text-slate-300">{(p.up_probability * 100).toFixed(1)}%</span>
            </Link>
          ))}
        </div>
      ) : null}
    </div>
  );
}
