"use client";
import { useState, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { TrendingUp, CheckCircle } from "lucide-react";
import { apiFetch } from "@/lib/api";

function ResetPasswordForm() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const token = searchParams.get("token") ?? "";

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [done, setDone] = useState(false);

  const requestReset = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(""); setLoading(true);
    try {
      await apiFetch("/api/auth/password-reset/request", {
        method: "POST",
        body: JSON.stringify({ email }),
      });
      setDone(true);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "エラーが発生しました");
    } finally {
      setLoading(false);
    }
  };

  const confirmReset = async (e: React.FormEvent) => {
    e.preventDefault();
    if (password !== confirm) { setError("パスワードが一致しません"); return; }
    setError(""); setLoading(true);
    try {
      await apiFetch("/api/auth/password-reset/confirm", {
        method: "POST",
        body: JSON.stringify({ token, new_password: password }),
      });
      setDone(true);
      setTimeout(() => router.push("/auth"), 2500);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "エラーが発生しました");
    } finally {
      setLoading(false);
    }
  };

  const inputCls = "w-full border border-slate-700/60 rounded px-3 py-2 text-sm bg-[#060b16] text-slate-200 outline-none focus:ring-1 focus:ring-teal-500/50 placeholder-slate-600 transition-all";
  const btnCls = "w-full bg-teal-600 hover:bg-teal-500 disabled:opacity-60 text-white py-2.5 rounded font-black text-xs tracking-widest uppercase transition-colors";

  if (done) {
    return (
      <div className="text-center py-8">
        <CheckCircle className="w-12 h-12 text-teal-500 mx-auto mb-3" />
        <p className="font-semibold text-white">
          {token ? "パスワードを変更しました" : "リセットメールを送信しました"}
        </p>
        <p className="text-sm text-slate-400 mt-1">
          {token ? "ログインページへ移動します..." : "メールをご確認ください（迷惑メールフォルダもご確認を）"}
        </p>
      </div>
    );
  }

  return token ? (
    <form onSubmit={confirmReset} className="space-y-4">
      <h1 className="text-xl font-black text-white">新しいパスワードを設定</h1>
      <div>
        <label className="block text-[10px] font-black tracking-widest uppercase text-slate-500 mb-1.5">新しいパスワード（8文字以上）</label>
        <input
          type="password" required minLength={8} value={password}
          onChange={e => setPassword(e.target.value)}
          className={inputCls}
        />
      </div>
      <div>
        <label className="block text-[10px] font-black tracking-widest uppercase text-slate-500 mb-1.5">確認（再入力）</label>
        <input
          type="password" required value={confirm}
          onChange={e => setConfirm(e.target.value)}
          className={inputCls}
        />
      </div>
      {error && <p className="text-sm text-red-400 bg-red-900/20 rounded px-3 py-2 border border-red-900/40">{error}</p>}
      <button type="submit" disabled={loading} className={btnCls}>
        {loading ? "処理中..." : "パスワードを変更"}
      </button>
    </form>
  ) : (
    <form onSubmit={requestReset} className="space-y-4">
      <h1 className="text-xl font-black text-white">パスワードをお忘れですか？</h1>
      <p className="text-sm text-slate-400">
        登録済みのメールアドレスを入力してください。リセット用のリンクをお送りします。
      </p>
      <div>
        <label className="block text-[10px] font-black tracking-widest uppercase text-slate-500 mb-1.5">メールアドレス</label>
        <input
          type="email" required value={email}
          onChange={e => setEmail(e.target.value)}
          className={inputCls}
        />
      </div>
      {error && <p className="text-sm text-red-400 bg-red-900/20 rounded px-3 py-2 border border-red-900/40">{error}</p>}
      <button type="submit" disabled={loading} className={btnCls}>
        {loading ? "送信中..." : "リセットメールを送信"}
      </button>
    </form>
  );
}

export default function ResetPasswordPage() {
  return (
    <div className="flex items-center justify-center min-h-[60vh]">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <TrendingUp size={36} className="mx-auto text-teal-500 mb-3" />
        </div>
        <div className="bg-[#0c1424] rounded border border-slate-700/60 p-8 shadow-sm">
          <Suspense fallback={<div className="text-center text-slate-500">読み込み中...</div>}>
            <ResetPasswordForm />
          </Suspense>
        </div>
      </div>
    </div>
  );
}
