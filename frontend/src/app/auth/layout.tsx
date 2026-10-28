import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "ログイン / 新規登録",
  description: "Stock Intelligence にログインまたは無料アカウントを作成してAI株価シグナルを受け取りましょう。",
};

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
