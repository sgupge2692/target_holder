import { TrendingUp, TrendingDown } from "lucide-react";
import clsx from "clsx";

export function SignalBadge({ signal }: { signal: "UP" | "DOWN" }) {
  return (
    <span className={clsx(
      "inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold",
      signal === "UP"
        ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-400"
        : "bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-400"
    )}>
      {signal === "UP" ? <TrendingUp size={12} /> : <TrendingDown size={12} />}
      {signal}
    </span>
  );
}
