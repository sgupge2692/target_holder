import Link from "next/link";
import { Home, TrendingUp } from "lucide-react";

export default function NotFound() {
  return (
    <div className="min-h-[65vh] flex flex-col items-center justify-center gap-6 px-4 text-center">
      {/* 大きな数字 */}
      <div className="relative">
        <p className="text-[9rem] font-black text-slate-800 leading-none select-none">
          404
        </p>
        <div className="absolute inset-0 flex items-center justify-center">
          <div className="w-16 h-16 rounded bg-teal-600 flex items-center justify-center shadow-lg">
            <TrendingUp size={32} className="text-white" />
          </div>
        </div>
      </div>

      <div className="space-y-1.5 -mt-2">
        <h1 className="text-2xl font-black tracking-tight">ページが見つかりません</h1>
        <p className="text-sm text-slate-400">
          お探しのページは移動または削除された可能性があります。
        </p>
      </div>

      <Link
        href="/"
        className="inline-flex items-center gap-2 bg-teal-600 hover:bg-teal-500 text-white px-6 py-2.5 rounded text-xs font-black tracking-widest uppercase transition-all"
      >
        <Home size={15} />
        ホームへ戻る
      </Link>
    </div>
  );
}
