"use client";
import { useState, useRef, useEffect } from "react";
import { useRouter } from "next/navigation";
import { searchStocks, type Stock } from "@/lib/api";
import { Search } from "lucide-react";

export function StockSearch() {
  const [query, setQuery]       = useState("");
  const [results, setResults]   = useState<Stock[]>([]);
  const [open, setOpen]         = useState(false);
  const router = useRouter();
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (query.length < 1) { setResults([]); return; }
    const t = setTimeout(async () => {
      try { const r = await searchStocks(query); setResults(r.stocks); setOpen(true); }
      catch { /* ignore */ }
    }, 300);
    return () => clearTimeout(t);
  }, [query]);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const go = (code: string) => {
    setOpen(false); setQuery("");
    router.push(`/stocks/${code}`);
  };

  return (
    <div ref={ref} className="relative w-full max-w-sm">
      <div className="flex items-center border border-gray-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-800 px-3 gap-2">
        <Search size={16} className="text-gray-400" />
        <input
          type="text"
          value={query}
          onChange={e => setQuery(e.target.value)}
          placeholder="銘柄コード・企業名で検索..."
          className="flex-1 py-2 text-sm bg-transparent outline-none placeholder-gray-400"
        />
      </div>

      {open && results.length > 0 && (
        <ul className="absolute z-50 mt-1 w-full bg-white dark:bg-slate-800 border border-gray-200 dark:border-slate-600 rounded-lg shadow-lg overflow-hidden">
          {results.map(s => (
            <li key={s.code}>
              <button
                onClick={() => go(s.code)}
                className="w-full text-left px-4 py-2.5 text-sm hover:bg-gray-50 dark:hover:bg-slate-700 transition-colors flex justify-between items-center"
              >
                <span className="font-medium">{s.company_name}</span>
                <span className="text-gray-400 text-xs ml-4">{s.code}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
