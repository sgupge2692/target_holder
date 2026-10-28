"use client";
import { useEffect } from "react";
import { captureError } from "@/lib/monitoring";
import Link from "next/link";
import { AlertTriangle, RefreshCw } from "lucide-react";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    captureError(error, { digest: error.digest });
  }, [error]);

  return (
    <div className="min-h-[60vh] flex flex-col items-center justify-center gap-6 px-4 text-center">
      <div className="w-16 h-16 rounded-full bg-red-100 dark:bg-red-900/20 flex items-center justify-center">
        <AlertTriangle className="w-8 h-8 text-red-500" />
      </div>

      <div className="space-y-2">
        <h1 className="text-xl font-bold text-gray-900 dark:text-white">
          予期しないエラーが発生しました
        </h1>
        <p className="text-sm text-gray-500 dark:text-slate-400 max-w-sm">
          申し訳ありません。問題が発生しました。再試行するか、しばらく経ってからアクセスしてください。
        </p>
        {error.digest && (
          <p className="text-xs text-gray-400 font-mono">Error ID: {error.digest}</p>
        )}
      </div>

      <div className="flex gap-3">
        <button
          onClick={reset}
          className="inline-flex items-center gap-2 bg-brand-600 hover:bg-brand-700 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors"
        >
          <RefreshCw className="w-4 h-4" />
          再試行
        </button>
        <Link
          href="/"
          className="inline-flex items-center gap-2 border border-gray-200 dark:border-slate-700 text-gray-700 dark:text-slate-300 hover:bg-gray-50 dark:hover:bg-slate-800 px-4 py-2 rounded-lg text-sm font-medium transition-colors"
        >
          ホームへ戻る
        </Link>
      </div>
    </div>
  );
}
