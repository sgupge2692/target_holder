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
    <div className="bg-[#0c1424] rounded border border-slate-700/60 p-5">
      {/* ヘッダー */}
      <button
        className="w-full flex items-center justify-between"
        onClick={() => setOpen(o => !o)}
      >
        <div className="flex items-center gap-2">
          <Sparkles size={16} className="text-amber-400" />
          <span className="text-sm font-semibold text-slate-200">四季報 AI 要約</span>
          {summary && (
            <span className="text-xs text-slate-500 ml-1 font-mono">{summary.year_label}</span>
          )}
        </div>
        {open ? <ChevronUp size={16} className="text-slate-500" /> : <ChevronDown size={16} className="text-slate-500" />}
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
                <div className="flex items-center gap-2 rounded bg-amber-900/20 border border-amber-700/40 px-3 py-2 text-xs text-amber-400">
                  <Lock size={12} />
                  業績・リスク詳細は Pro プランで閲覧できます
                </div>
              )}
              <p className="text-xs text-slate-700 text-right font-mono">
                生成: {summary.created_at?.slice(0, 10)} · {summary.model}
              </p>
            </div>
          ) : (
            <p className="text-sm text-slate-500">まだ要約が生成されていません</p>
          )}

          {/* テキスト入力フォーム */}
          <div>
            <button
              onClick={() => setInput(v => !v)}
              className="text-xs text-teal-500 hover:text-teal-400 transition-colors flex items-center gap-1"
            >
              {inputOpen ? "▲ 閉じる" : "▼ 四季報テキストを貼り付けて生成"}
            </button>

            {inputOpen && (
              <div className="mt-3 space-y-3">
                <div className="flex gap-2 items-center">
                  <label className="text-[10px] font-black tracking-widest uppercase text-slate-500 shrink-0">年号:</label>
                  <select
                    value={yearLabel}
                    onChange={e => setYear(e.target.value)}
                    className="text-xs border border-slate-700/60 rounded px-2 py-1 bg-[#060b16] text-slate-300 focus:outline-none focus:ring-1 focus:ring-teal-500/50"
                  >
                    {YEAR_OPTIONS.map(y => <option key={y} value={y}>{y}</option>)}
                  </select>
                </div>
                <textarea
                  value={text}
                  onChange={e => setText(e.target.value)}
                  rows={6}
                  placeholder="四季報の本文テキストをここにペーストしてください（Web 版・PDF からコピー可）"
                  className="w-full text-xs border border-slate-700/60 rounded px-3 py-2 bg-[#060b16] text-slate-300 resize-none outline-none focus:ring-1 focus:ring-teal-500/50 font-mono"
                />
                <div className="flex gap-2">
                  <button
                    onClick={() => onGenerate(text, yearLabel)}
                    disabled={!hasText || loading}
                    className={clsx(
                      "flex items-center gap-1.5 px-4 py-1.5 rounded text-xs font-black tracking-widest uppercase transition-colors",
                      hasText && !loading
                        ? "bg-teal-600 hover:bg-teal-500 text-white"
                        : "bg-slate-800 text-slate-600 cursor-not-allowed"
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
                        "flex items-center gap-1.5 px-4 py-1.5 rounded text-xs font-black tracking-widest uppercase transition-colors border",
                        hasText && !loading
                          ? "border-teal-600/60 text-teal-400 hover:bg-teal-900/20"
                          : "border-slate-700/60 text-slate-600 cursor-not-allowed"
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
        "text-[10px] font-black uppercase tracking-widest mb-1",
        color === "red" ? "text-red-400" : "text-slate-500"
      )}>{title}</p>
      <p className="text-sm leading-relaxed text-slate-300">{text}</p>
    </div>
  );
}
