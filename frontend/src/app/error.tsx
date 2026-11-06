"use client";
import { useEffect } from "react";
import { AlertTriangle, RefreshCw, Home } from "lucide-react";
import Link from "next/link";

export default function ErrorPage({
  error, reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <div className="min-h-[65vh] flex flex-col items-center justify-center gap-6 px-4 text-center">
      <div className="w-16 h-16 rounded bg-red-900/20 border border-red-900/40 flex items-center justify-center">
        <AlertTriangle size={28} className="text-red-400" />
      </div>

      <div className="space-y-1.5">
        <h1 className="text-2xl font-black tracking-tight">エラーが発生しました</h1>
        <p className="text-sm text-slate-400">
          予期しないエラーが発生しました。もう一度お試しください。
        </p>
        {error.digest && (
          <p className="text-xs text-slate-600 font-mono mt-2">
            {error.digest}
          </p>
        )}
      </div>

      <div className="flex items-center gap-3">
        <button
          onClick={reset}
          className="inline-flex items-center gap-2 bg-teal-600 hover:bg-teal-500 text-white px-5 py-2.5 rounded text-xs font-black tracking-widest uppercase transition-all"
        >
          <RefreshCw size={14} />
          再試行
        </button>
        <Link
          href="/"
          className="inline-flex items-center gap-2 border border-slate-700/60 text-slate-400 hover:bg-slate-800/60 px-5 py-2.5 rounded text-xs font-black tracking-widest uppercase transition-colors"
        >
          <Home size={14} />
          ホームへ
        </Link>
      </div>
    </div>
  );
}
