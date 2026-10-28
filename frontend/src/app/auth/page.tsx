"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { register, login } from "@/lib/api";
import { TrendingUp } from "lucide-react";

type Mode = "login" | "register";

export default function AuthPage() {
  const [mode, setMode]       = useState<Mode>("login");
  const [email, setEmail]     = useState("");
  const [password, setPass]   = useState("");
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
    <div className="flex items-center justify-center min-h-[60vh]">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <TrendingUp size={36} className="mx-auto text-brand-600 mb-3" />
          <h1 className="text-2xl font-bold">
            {mode === "login" ? "ログイン" : "アカウント作成"}
          </h1>
        </div>

        <form onSubmit={submit} className="bg-white dark:bg-slate-800 rounded-2xl border border-gray-200 dark:border-slate-700 p-8 space-y-4 shadow-sm">
          <div>
            <label className="block text-sm font-medium mb-1.5">メールアドレス</label>
            <input
              type="email" required value={email} onChange={e => setEmail(e.target.value)}
              className="w-full border border-gray-300 dark:border-slate-600 rounded-lg px-3 py-2 text-sm bg-transparent outline-none focus:ring-2 focus:ring-brand-500 transition-shadow"
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1.5">パスワード</label>
            <input
              type="password" required value={password} onChange={e => setPass(e.target.value)}
              minLength={8}
              className="w-full border border-gray-300 dark:border-slate-600 rounded-lg px-3 py-2 text-sm bg-transparent outline-none focus:ring-2 focus:ring-brand-500 transition-shadow"
            />
          </div>

          {error && (
            <p className="text-sm text-red-500 bg-red-50 dark:bg-red-900/20 rounded-lg px-3 py-2">{error}</p>
          )}

          <button
            type="submit" disabled={loading}
            className="w-full bg-brand-600 hover:bg-brand-700 disabled:opacity-60 text-white py-2.5 rounded-lg font-medium transition-colors"
          >
            {loading ? "処理中..." : mode === "login" ? "ログイン" : "登録"}
          </button>

          <p className="text-center text-sm text-gray-500 dark:text-slate-400">
            {mode === "login" ? "アカウントがない？" : "既にアカウントをお持ち？"}{" "}
            <button
              type="button"
              onClick={() => { setMode(mode === "login" ? "register" : "login"); setError(""); }}
              className="text-brand-600 hover:underline font-medium"
            >
              {mode === "login" ? "新規登録" : "ログイン"}
            </button>
          </p>
          {mode === "login" && (
            <p className="text-center text-xs text-gray-400 dark:text-slate-500">
              <Link href="/auth/reset-password" className="hover:text-brand-600 hover:underline">
                パスワードをお忘れですか？
              </Link>
            </p>
          )}
        </form>
      </div>
    </div>
  );
}
