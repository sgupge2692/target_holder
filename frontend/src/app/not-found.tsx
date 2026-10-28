import Link from "next/link";
import { Search } from "lucide-react";

export default function NotFound() {
  return (
    <div className="min-h-[60vh] flex flex-col items-center justify-center gap-6 px-4 text-center">
      <div className="w-20 h-20 rounded-full bg-gray-100 dark:bg-slate-800 flex items-center justify-center">
        <Search className="w-10 h-10 text-gray-400" />
      </div>

      <div className="space-y-2">
        <p className="text-6xl font-extrabold text-gray-200 dark:text-slate-700">404</p>
        <h1 className="text-xl font-bold text-gray-900 dark:text-white -mt-4">
          ページが見つかりません
        </h1>
        <p className="text-sm text-gray-500 dark:text-slate-400">
          お探しのページは移動または削除された可能性があります。
        </p>
      </div>

      <Link
        href="/"
        className="bg-brand-600 hover:bg-brand-700 text-white px-6 py-2.5 rounded-lg text-sm font-medium transition-colors"
      >
        ホームへ戻る
      </Link>
    </div>
  );
}
