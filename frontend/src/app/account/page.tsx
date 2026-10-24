"use client";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/hooks/useAuth";
import { createPortal } from "@/lib/api";
import { useState } from "react";

export default function AccountPage() {
  const { user, loading, signOut } = useAuth();
  const [portalLoading, setPortalLoading] = useState(false);
  const router = useRouter();

  if (loading) return <div className="text-center py-16 text-gray-400">読み込み中...</div>;
  if (!user) {
    router.push("/auth");
    return null;
  }

  const openPortal = async () => {
    setPortalLoading(true);
    try { const { url } = await createPortal(); window.location.href = url; }
    catch (e: unknown) { alert(e instanceof Error ? e.message : "エラー"); setPortalLoading(false); }
  };

  return (
    <div className="max-w-lg mx-auto space-y-6">
      <h1 className="text-2xl font-bold">アカウント</h1>

      <div className="bg-white dark:bg-slate-800 rounded-2xl border border-gray-200 dark:border-slate-700 divide-y divide-gray-100 dark:divide-slate-700">
        <div className="px-6 py-4 flex justify-between items-center">
          <span className="text-sm text-gray-500">メール</span>
          <span className="font-medium text-sm">{user.email}</span>
        </div>
        <div className="px-6 py-4 flex justify-between items-center">
          <span className="text-sm text-gray-500">プラン</span>
          <span className={`px-2.5 py-0.5 rounded-full text-xs font-semibold ${
            user.plan === "pro"
              ? "bg-brand-100 text-brand-700 dark:bg-brand-900/40 dark:text-brand-300"
              : "bg-gray-100 text-gray-600 dark:bg-slate-700 dark:text-slate-300"
          }`}>
            {user.plan === "pro" ? "Pro" : "無料"}
          </span>
        </div>
      </div>

      <div className="flex flex-col gap-3">
        {user.plan !== "pro" && (
          <Link
            href="/billing"
            className="w-full text-center bg-brand-600 hover:bg-brand-700 text-white py-2.5 rounded-lg font-medium transition-colors"
          >
            Pro プランにアップグレード
          </Link>
        )}
        {user.plan === "pro" && (
          <button
            onClick={openPortal} disabled={portalLoading}
            className="w-full border border-gray-300 dark:border-slate-600 hover:bg-gray-50 dark:hover:bg-slate-800 py-2.5 rounded-lg text-sm font-medium transition-colors disabled:opacity-60"
          >
            {portalLoading ? "処理中..." : "サブスクリプション管理（解約・カード変更）"}
          </button>
        )}
        <button
          onClick={signOut}
          className="w-full border border-red-200 dark:border-red-900 text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 py-2.5 rounded-lg text-sm font-medium transition-colors"
        >
          ログアウト
        </button>
      </div>
    </div>
  );
}
