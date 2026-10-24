import Link from "next/link";
import { CheckCircle } from "lucide-react";

export default function BillingSuccess() {
  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] text-center gap-4">
      <CheckCircle size={56} className="text-brand-500" />
      <h1 className="text-2xl font-bold">Pro プランへのアップグレード完了！</h1>
      <p className="text-gray-500 dark:text-slate-400">全シグナルが閲覧できるようになりました。</p>
      <Link href="/" className="mt-4 bg-brand-600 hover:bg-brand-700 text-white px-6 py-2.5 rounded-lg font-medium transition-colors">
        シグナル一覧へ
      </Link>
    </div>
  );
}
