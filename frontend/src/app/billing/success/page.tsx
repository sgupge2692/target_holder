import Link from "next/link";
import { CheckCircle } from "lucide-react";

export default function BillingSuccess() {
  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] text-center gap-4">
      <CheckCircle size={56} className="text-teal-500" />
      <h1 className="text-2xl font-bold">Pro プランへのアップグレード完了！</h1>
      <p className="text-slate-400">全シグナルが閲覧できるようになりました。</p>
      <Link href="/" className="mt-4 bg-teal-600 hover:bg-teal-500 text-white px-6 py-2.5 rounded font-black text-xs tracking-widest uppercase transition-colors">
        シグナル一覧へ
      </Link>
    </div>
  );
}
