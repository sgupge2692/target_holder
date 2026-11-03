import { TrendingUp, TrendingDown } from "lucide-react";
import clsx from "clsx";

export function SignalBadge({ signal }: { signal: "UP" | "DOWN" }) {
  return (
    <span className={clsx(
      "inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-black tracking-wider uppercase",
      signal === "UP"
        ? "bg-teal-100 text-teal-700 dark:bg-teal-900/30 dark:text-teal-300"
        : "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400"
    )}>
      {signal === "UP" ? <TrendingUp size={10} strokeWidth={2.5} /> : <TrendingDown size={10} strokeWidth={2.5} />}
      {signal}
    </span>
  );
}
