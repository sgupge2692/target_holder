/** シマーアニメーション付きのスケルトンブロック */
export function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`skeleton ${className}`} />;
}

/** シグナル一覧用スケルトン行 */
export function SignalRowSkeleton() {
  return (
    <tr>
      <td className="px-4 py-3.5">
        <Skeleton className="h-4 w-28 mb-1.5" />
        <Skeleton className="h-3 w-12" />
      </td>
      <td className="px-4 py-3.5"><Skeleton className="h-4 w-20" /></td>
      <td className="px-4 py-3.5 flex justify-center"><Skeleton className="h-5 w-14 rounded-full" /></td>
      <td className="px-4 py-3.5"><Skeleton className="h-4 w-12 ml-auto" /></td>
      <td className="px-4 py-3.5"><Skeleton className="h-4 w-14 ml-auto" /></td>
      <td className="px-4 py-3.5"><Skeleton className="h-4 w-6 mx-auto" /></td>
      <td className="px-4 py-3.5"><Skeleton className="h-4 w-10 mx-auto" /></td>
    </tr>
  );
}

/** シグナルカード用スケルトン（モバイル） */
export function SignalCardSkeleton() {
  return (
    <div className="rounded-xl border border-gray-200 dark:border-slate-700 bg-white dark:bg-slate-800 p-4 space-y-3">
      <div className="flex items-center justify-between">
        <div>
          <Skeleton className="h-4 w-28 mb-1.5" />
          <Skeleton className="h-3 w-12" />
        </div>
        <Skeleton className="h-6 w-14 rounded-full" />
      </div>
      <div className="flex justify-between">
        <Skeleton className="h-4 w-20" />
        <Skeleton className="h-4 w-16" />
      </div>
    </div>
  );
}

/** KPIカード用スケルトン */
export function StatCardSkeleton() {
  return (
    <div className="rounded-xl border border-gray-200 dark:border-slate-700 bg-white dark:bg-slate-800 p-4">
      <Skeleton className="h-3 w-20 mb-3" />
      <Skeleton className="h-8 w-24 mb-1.5" />
      <Skeleton className="h-3 w-32" />
    </div>
  );
}
