"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { register, login } from "@/lib/api";
import { TrendingUp, Mail, Lock, Eye, EyeOff, ChevronRight, Shield } from "lucide-react";

type Mode = "login" | "register";

export default function AuthPage() {
  const [mode, setMode]       = useState<Mode>("login");
  const [email, setEmail]     = useState("");
  const [password, setPass]   = useState("");
  const [showPass, setShowP]  = useState(false);
  const [error, setError]     = useState("");
  const [loading, setLoading] = useState(false);
  const router = useRouter();

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(""); setLoading(true);
    try {
      const fn = mode === "login" ? login : register;
      const res = await fn(email, password);
      localStorage.setItem("token", res.access_token);
      router.push("/");
      router.refresh();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "エラーが発生しました");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex items-center justify-center min-h-[70vh] px-4">
      <div className="w-full max-w-sm">

        {/* ロゴ・タイトル */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-brand-600 mb-4 shadow-lg shadow-brand-500/30">
            <TrendingUp size={28} className="text-white" />
          </div>
          <h1 className="text-2xl font-black tracking-tight">
            {mode === "login" ? "おかえりなさい" : "アカウント作成"}
          </h1>
          <p className="text-sm text-gray-500 dark:text-slate-400 mt-1">
            {mode === "login"
              ? "AIシグナルにログイン"
              : "無料で始める · クレカ不要"}
          </p>
        </div>

        {/* フォームカード */}
        <form
          onSubmit={submit}
          className="bg-white dark:bg-slate-900 rounded-2xl border border-gray-200 dark:border-slate-700 p-7 shadow-xl shadow-gray-200/50 dark:shadow-none space-y-4"
        >

          {/* メール */}
          <div>
            <label className="block text-xs font-semibold text-gray-600 dark:text-slate-400 mb-1.5 uppercase tracking-wide">
              メールアドレス
            </label>
            <div className="relative">
              <Mail size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none" />
              <input
                type="email" required value={email} onChange={e => setEmail(e.target.value)}
                placeholder="you@example.com"
                className="w-full border border-gray-200 dark:border-slate-700 rounded-xl pl-9 pr-3 py-2.5 text-sm bg-gray-50 dark:bg-slate-800 outline-none focus:ring-2 focus:ring-brand-500 focus:bg-white dark:focus:bg-slate-700 transition-all"
              />
            </div>
          </div>

          {/* パスワード */}
          <div>
            <label className="block text-xs font-semibold text-gray-600 dark:text-slate-400 mb-1.5 uppercase tracking-wide">
              パスワード
            </label>
            <div className="relative">
              <Lock size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none" />
              <input
                type={showPass ? "text" : "password"} required value={password}
                onChange={e => setPass(e.target.value)}
                minLength={8}
                placeholder={mode === "register" ? "8文字以上" : "パスワード"}
                className="w-full border border-gray-200 dark:border-slate-700 rounded-xl pl-9 pr-10 py-2.5 text-sm bg-gray-50 dark:bg-slate-800 outline-none focus:ring-2 focus:ring-brand-500 focus:bg-white dark:focus:bg-slate-700 transition-all"
              />
              <button
                type="button"
                onClick={() => setShowP(v => !v)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 transition-colors"
              >
                {showPass ? <EyeOff size={14} /> : <Eye size={14} />}
              </button>
            </div>
          </div>

          {/* エラー */}
          {error && (
            <div className="flex items-center gap-2 text-sm text-red-600 bg-red-50 dark:bg-red-900/20 dark:text-red-400 rounded-xl px-3.5 py-2.5 border border-red-100 dark:border-red-900/40">
              <span className="shrink-0">⚠</span>
              {error}
            </div>
          )}

          {/* 送信ボタン */}
          <button
            type="submit" disabled={loading}
            className="w-full flex items-center justify-center gap-2 bg-brand-600 hover:bg-brand-700 active:bg-brand-800 disabled:opacity-60 text-white py-3 rounded-xl font-bold transition-all shadow-md shadow-brand-500/20 hover:shadow-brand-500/30 mt-1"
          >
            {loading ? (
              <span className="flex items-center gap-2">
                <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                処理中...
              </span>
            ) : (
              <>
                {mode === "login" ? "ログイン" : "無料で登録する"}
                <ChevronRight size={16} />
              </>
            )}
          </button>

          {/* モード切り替え */}
          <p className="text-center text-sm text-gray-500 dark:text-slate-400 pt-1">
            {mode === "login" ? "アカウントがない？" : "既にお持ちですか？"}{" "}
            <button
              type="button"
              onClick={() => { setMode(mode === "login" ? "register" : "login"); setError(""); }}
              className="text-brand-600 dark:text-brand-400 hover:underline font-semibold"
            >
              {mode === "login" ? "新規登録" : "ログイン"}
            </button>
          </p>

          {/* パスワードリセット */}
          {mode === "login" && (
            <p className="text-center text-xs text-gray-400 dark:text-slate-500">
              <Link href="/auth/reset-password" className="hover:text-brand-600 hover:underline">
                パスワードをお忘れですか？
              </Link>
            </p>
          )}
        </form>

        {/* セキュリティ注記 */}
        <p className="text-center text-xs text-gray-400 dark:text-slate-600 mt-5 flex items-center justify-center gap-1">
          <Shield size={11} />
          パスワードは暗号化して保存されます
        </p>
      </div>
    </div>
  );
}
