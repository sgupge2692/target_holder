"use client";
import { useState } from "react";
import { Lock, RefreshCw, Sparkles, ChevronDown, ChevronUp } from "lucide-react";
import clsx from "clsx";

interface Summary {
  overview: string | null;
  performance: string | null;
  risks: string | null;
  year_label: string;
  model: string | null;
  created_at: string;
  plan: string;
}

interface Props {
  code: string;
  isPro: boolean;
  onGenerate: (text: string, yearLabel: string) => Promise<void>;
  onRegenerate: (text: string, yearLabel: string) => Promise<void>;
  summary: Summary | null;
  loading: boolean;
}

const YEAR_OPTIONS = [`${new Date().getFullYear()}秋`, `${new Date().getFullYear()}春`, `${new Date().getFullYear() - 1}秋`];

export function SummaryCard({ isPro, onGenerate, onRegenerate, summary, loading }: Props) {
  const [text, setText]         = useState("");
  const [yearLabel, setYear]    = useState(YEAR_OPTIONS[0]);
  const [open, setOpen]         = useState(false);
  const [inputOpen, setInput]   = useState(false);

  const hasText = text.trim().length > 50;

  return (
    <div className="bg-white dark:bg-slate-800 rounded-2xl border border-gray-200 dark:border-slate-700 p-5">
      {/* ヘッダー */}
      <button
        className="w-full flex items-center justify-between"
        onClick={() => setOpen(o => !o)}
      >
        <div className="flex items-center gap-2">
          <Sparkles size={16} className="text-amber-500" />
          <span className="text-sm font-medium">四季報 AI 要約</span>
          {summary && (
            <span className="text-xs text-gray-400 dark:text-slate-500 ml-1">{summary.year_label}</span>
          )}
        </div>
        {open ? <ChevronUp size={16} className="text-gray-400" /> : <ChevronDown size={16} className="text-gray-400" />}
      </button>

      {open && (
        <div className="mt-4 space-y-4">
          {/* 要約表示 */}
          {summary ? (
            <div className="space-y-3 text-sm">
              <Section title="会社概要" text={summary.overview} />
              {isPro ? (
                <>
                  <Section title="業績・見通し" text={summary.performance} />
                  <Section title="リスク・懸念点" text={summary.risks} color="red" />
                </>
              ) : (
                <div className="flex items-center gap-2 rounded-lg bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-700 px-3 py-2 text-xs text-amber-700 dark:text-amber-300">
                  <Lock size={12} />
                  業績・リスク詳細は Pro プランで閲覧できます
                </div>
              )}
              <p className="text-xs text-gray-300 dark:text-slate-600 text-right">
                生成: {summary.created_at?.slice(0, 10)} · {summary.model}
              </p>
            </div>
          ) : (
            <p className="text-sm text-gray-400 dark:text-slate-500">まだ要約が生成されていません</p>
          )}

          {/* テキスト入力フォーム */}
          <div>
            <button
              onClick={() => setInput(v => !v)}
              className="text-xs text-brand-600 dark:text-brand-400 hover:underline flex items-center gap-1"
            >
              {inputOpen ? "▲ 閉じる" : "▼ 四季報テキストを貼り付けて生成"}
            </button>

            {inputOpen && (
              <div className="mt-3 space-y-3">
                <div className="flex gap-2 items-center">
                  <label className="text-xs text-gray-500 shrink-0">年号:</label>
                  <select
                    value={yearLabel}
                    onChange={e => setYear(e.target.value)}
                    className="text-xs border border-gray-300 dark:border-slate-600 rounded px-2 py-1 bg-transparent"
                  >
                    {YEAR_OPTIONS.map(y => <option key={y} value={y}>{y}</option>)}
                  </select>
                </div>
                <textarea
                  value={text}
                  onChange={e => setText(e.target.value)}
                  rows={6}
                  placeholder="四季報の本文テキストをここにペーストしてください（Web 版・PDF からコピー可）"
                  className="w-full text-xs border border-gray-300 dark:border-slate-600 rounded-lg px-3 py-2 bg-transparent resize-none outline-none focus:ring-2 focus:ring-brand-500 font-mono"
                />
                <div className="flex gap-2">
                  <button
                    onClick={() => onGenerate(text, yearLabel)}
                    disabled={!hasText || loading}
                    className={clsx(
                      "flex items-center gap-1.5 px-4 py-1.5 rounded-lg text-xs font-medium transition-colors",
                      hasText && !loading
                        ? "bg-brand-600 hover:bg-brand-700 text-white"
                        : "bg-gray-100 dark:bg-slate-700 text-gray-400 cursor-not-allowed"
                    )}
                  >
                    <Sparkles size={12} />
                    {loading ? "生成中..." : "要約を生成"}
                  </button>

                  {isPro && summary && (
                    <button
                      onClick={() => onRegenerate(text, yearLabel)}
                      disabled={!hasText || loading}
                      className={clsx(
                        "flex items-center gap-1.5 px-4 py-1.5 rounded-lg text-xs font-medium transition-colors border",
                        hasText && !loading
                          ? "border-brand-400 text-brand-600 dark:text-brand-400 hover:bg-brand-50 dark:hover:bg-brand-900/20"
                          : "border-gray-200 dark:border-slate-700 text-gray-400 cursor-not-allowed"
                      )}
                    >
                      <RefreshCw size={12} />
                      再生成（Pro）
                    </button>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function Section({ title, text, color = "gray" }: { title: string; text: string | null; color?: "gray" | "red" }) {
  if (!text) return null;
  return (
    <div>
      <p className={clsx(
        "text-xs font-semibold uppercase tracking-wide mb-1",
        color === "red" ? "text-red-500" : "text-gray-400 dark:text-slate-500"
      )}>{title}</p>
      <p className="text-sm leading-relaxed text-gray-700 dark:text-slate-300">{text}</p>
    </div>
  );
}
