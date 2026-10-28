import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "バックテスト実績",
  description: "Stock Intelligence のAIシグナル過去実績。月別UP/DOWN精度・平均リターン・累積リターン推移をグラフで確認できます。",
};

export default function BacktestLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
