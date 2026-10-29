"use client";
import { createContext, useCallback, useContext, useState, useEffect } from "react";
import { CheckCircle2, XCircle, Info, X } from "lucide-react";

type ToastType = "success" | "error" | "info";

interface Toast {
  id: number;
  type: ToastType;
  message: string;
}

interface ToastContextValue {
  toast: (message: string, type?: ToastType) => void;
}

const ToastContext = createContext<ToastContextValue>({ toast: () => {} });

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  let nextId = 0;

  const toast = useCallback((message: string, type: ToastType = "info") => {
    const id = ++nextId;
    setToasts(prev => [...prev, { id, type, message }]);
    setTimeout(() => setToasts(prev => prev.filter(t => t.id !== id)), 4000);
  }, []);

  const remove = (id: number) => setToasts(prev => prev.filter(t => t.id !== id));

  const icons = {
    success: <CheckCircle2 size={16} className="text-emerald-500 shrink-0" />,
    error:   <XCircle size={16} className="text-red-500 shrink-0" />,
    info:    <Info size={16} className="text-blue-500 shrink-0" />,
  };

  const colors = {
    success: "border-emerald-200 dark:border-emerald-700 bg-white dark:bg-slate-800",
    error:   "border-red-200 dark:border-red-700 bg-white dark:bg-slate-800",
    info:    "border-blue-200 dark:border-blue-700 bg-white dark:bg-slate-800",
  };

  return (
    <ToastContext.Provider value={{ toast }}>
      {children}
      {/* トースト表示エリア */}
      <div className="fixed bottom-4 right-4 z-[9999] flex flex-col gap-2 pointer-events-none">
        {toasts.map(t => (
          <div
            key={t.id}
            className={`pointer-events-auto flex items-center gap-2.5 px-4 py-3 rounded-xl border shadow-lg text-sm max-w-xs animate-slide-up ${colors[t.type]}`}
          >
            {icons[t.type]}
            <span className="flex-1 text-gray-800 dark:text-slate-100">{t.message}</span>
            <button
              onClick={() => remove(t.id)}
              className="text-gray-400 hover:text-gray-600 dark:hover:text-slate-300 transition-colors"
            >
              <X size={14} />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  return useContext(ToastContext);
}
