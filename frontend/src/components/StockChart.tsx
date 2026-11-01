"use client";
import { useEffect, useRef, useState, useCallback } from "react";
import {
  createChart,
  CandlestickSeries,
  HistogramSeries,
  LineSeries,
  createSeriesMarkers,
  IChartApi,
  ISeriesApi,
  CandlestickData,
  HistogramData,
  LineData,
  Time,
  ColorType,
  CrosshairMode,
  SeriesMarker,
} from "lightweight-charts";
import type { Quote } from "@/lib/api";

// ── 型定義 ────────────────────────────────────────────────────────────────
interface SignalMarker {
  date: string;   // "YYYY-MM-DD"
  signal: "UP" | "DOWN";
  prob: number;   // 0–1
}

type Period = "1M" | "3M" | "6M" | "1Y" | "ALL";

interface Props {
  quotes: Quote[];
  signals?: SignalMarker[];
  isPro?: boolean;
}

// ── 日付フィルター ─────────────────────────────────────────────────────────
function cutoffDate(period: Period): string {
  const now = new Date();
  const map: Record<Period, number> = { "1M": 30, "3M": 90, "6M": 180, "1Y": 365, "ALL": 99999 };
  now.setDate(now.getDate() - map[period]);
  return now.toISOString().slice(0, 10);
}

// ── EMA 計算 ──────────────────────────────────────────────────────────────
function calcEMA(data: { time: Time; value: number }[], period: number) {
  const k = 2 / (period + 1);
  const result: LineData[] = [];
  let ema = data[0]?.value ?? 0;
  data.forEach(({ time, value }) => {
    ema = value * k + ema * (1 - k);
    result.push({ time, value: parseFloat(ema.toFixed(2)) });
  });
  return result.slice(period - 1);
}

// ── チェックボックス ───────────────────────────────────────────────────────
function Toggle({ label, checked, onChange }: { label: string; checked: boolean; onChange: () => void }) {
  return (
    <label className="flex items-center gap-1.5 text-xs cursor-pointer select-none">
      <input
        type="checkbox"
        className="w-3.5 h-3.5 accent-brand-500 cursor-pointer"
        checked={checked}
        onChange={onChange}
      />
      <span className="text-surface-500 dark:text-surface-400">{label}</span>
    </label>
  );
}

// ── メインコンポーネント ────────────────────────────────────────────────────
export function StockChart({ quotes, signals = [], isPro }: Props) {
  const containerRef  = useRef<HTMLDivElement>(null);
  const chartRef      = useRef<IChartApi | null>(null);
  const candleRef     = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const volumeRef     = useRef<ISeriesApi<"Histogram"> | null>(null);
  const ema25Ref      = useRef<ISeriesApi<"Line"> | null>(null);
  const ema75Ref      = useRef<ISeriesApi<"Line"> | null>(null);
  const tooltipRef    = useRef<HTMLDivElement>(null);

  const [period,     setPeriod]     = useState<Period>("3M");
  const [showVolume, setShowVolume] = useState(true);
  const [showEma25,  setShowEma25]  = useState(true);
  const [showEma75,  setShowEma75]  = useState(false);
  const [showSignal, setShowSignal] = useState(true);
  const [isDark,     setIsDark]     = useState(false);

  // ダークモード検出
  useEffect(() => {
    const el = document.documentElement;
    const check = () => setIsDark(el.classList.contains("dark"));
    check();
    const obs = new MutationObserver(check);
    obs.observe(el, { attributes: true, attributeFilter: ["class"] });
    return () => obs.disconnect();
  }, []);

  // フィルタ済みデータ
  const filteredQuotes = quotes.filter(q => q.Date >= cutoffDate(period));

  const candleData: CandlestickData[] = filteredQuotes.map(q => ({
    time: q.Date as Time,
    open:  Number(q.Open),
    high:  Number(q.High),
    low:   Number(q.Low),
    close: Number(q.AdjustmentClose),
  }));

  const volumeData: HistogramData[] = filteredQuotes.map(q => ({
    time:  q.Date as Time,
    value: Number(q.Volume),
    color: Number(q.AdjustmentClose) >= Number(q.Open)
      ? isDark ? "rgba(74,222,128,0.35)" : "rgba(22,163,74,0.3)"
      : isDark ? "rgba(251,113,133,0.35)" : "rgba(225,29,72,0.28)",
  }));

  const closeLine = filteredQuotes.map(q => ({
    time:  q.Date as Time,
    value: Number(q.AdjustmentClose),
  }));

  // チャート生成
  const buildChart = useCallback(() => {
    if (!containerRef.current) return;
    chartRef.current?.remove();
    chartRef.current = null;

    const bg    = isDark ? "#0f1a2e" : "#ffffff";
    const text  = isDark ? "#94a3b8" : "#64748b";
    const grid  = isDark ? "rgba(30,45,69,0.8)" : "rgba(226,232,240,0.6)";
    const up    = isDark ? "#4ade80" : "#16a34a";
    const down  = isDark ? "#fb7185" : "#e11d48";
    const border = isDark ? "#1e2d45" : "#e2e8f0";

    const chart = createChart(containerRef.current, {
      width:  containerRef.current.clientWidth,
      height: showVolume ? 340 : 260,
      layout: {
        background: { type: ColorType.Solid, color: bg },
        textColor: text,
        fontFamily: "'Inter var', Inter, ui-sans-serif, sans-serif",
        fontSize: 11,
      },
      grid: {
        vertLines:   { color: grid },
        horzLines:   { color: grid },
      },
      crosshair: {
        mode: CrosshairMode.Normal,
        vertLine: { color: isDark ? "#4ade80" : "#16a34a", labelBackgroundColor: isDark ? "#4ade80" : "#16a34a" },
        horzLine: { color: isDark ? "#4ade80" : "#16a34a", labelBackgroundColor: isDark ? "#4ade80" : "#16a34a" },
      },
      rightPriceScale: {
        borderColor: border,
        scaleMargins: showVolume ? { top: 0.08, bottom: 0.28 } : { top: 0.08, bottom: 0.05 },
      },
      timeScale: {
        borderColor: border,
        timeVisible: false,
      },
    });

    chartRef.current = chart;

    // ローソク足
    const candle = chart.addSeries(CandlestickSeries, {
      upColor:        up,
      downColor:      down,
      borderUpColor:  up,
      borderDownColor:down,
      wickUpColor:    up,
      wickDownColor:  down,
    });
    candle.setData(candleData);
    candleRef.current = candle;

    // 出来高
    if (showVolume) {
      const vol = chart.addSeries(HistogramSeries, {
        priceFormat:  { type: "volume" },
        priceScaleId: "volume",
      });
      chart.priceScale("volume").applyOptions({
        scaleMargins: { top: 0.78, bottom: 0 },
      });
      vol.setData(volumeData);
      volumeRef.current = vol;
    }

    // EMA25
    if (showEma25 && closeLine.length >= 25) {
      const ema = chart.addSeries(LineSeries, {
        color:       isDark ? "#fbbf24" : "#d97706",
        lineWidth:   1,
        crosshairMarkerVisible: false,
        priceLineVisible: false,
      });
      ema.setData(calcEMA(closeLine, 25));
      ema25Ref.current = ema;
    }

    // EMA75
    if (showEma75 && closeLine.length >= 75) {
      const ema = chart.addSeries(LineSeries, {
        color:       isDark ? "#c084fc" : "#9333ea",
        lineWidth:   1,
        crosshairMarkerVisible: false,
        priceLineVisible: false,
      });
      ema.setData(calcEMA(closeLine, 75));
      ema75Ref.current = ema;
    }

    // シグナルマーカー (v5: createSeriesMarkers)
    if (showSignal && signals.length > 0) {
      const visibleDates = new Set(filteredQuotes.map(q => q.Date));
      const markers: SeriesMarker<Time>[] = signals
        .filter(s => visibleDates.has(s.date))
        .map(s => ({
          time:     s.date as Time,
          position: s.signal === "UP" ? "belowBar" as const : "aboveBar" as const,
          color:    s.signal === "UP" ? up : down,
          shape:    s.signal === "UP" ? "arrowUp" as const : "arrowDown" as const,
          text:     `${Math.round(s.prob * 100)}%`,
          size:     1.2,
        }));
      createSeriesMarkers(candle, markers);
    }

    // カスタムツールチップ
    chart.subscribeCrosshairMove(param => {
      const tooltip = tooltipRef.current;
      if (!tooltip) return;
      if (!param.time || !param.point) {
        tooltip.style.display = "none";
        return;
      }
      const cd = param.seriesData.get(candle);
      if (!cd || !("open" in cd)) {
        tooltip.style.display = "none";
        return;
      }
      const { open, high, low, close } = cd as CandlestickData;
      const isGreen = close >= open;
      tooltip.innerHTML = `
        <div class="text-xs font-mono leading-relaxed">
          <div class="font-bold mb-1 ${isGreen ? "text-brand-500 dark:text-brand-400" : "text-danger-500 dark:text-danger-400"}">
            ${String(param.time)}
          </div>
          <div class="grid grid-cols-2 gap-x-3 text-surface-700 dark:text-surface-300">
            <span class="text-surface-400 dark:text-surface-500">始値</span><span>¥${open.toLocaleString()}</span>
            <span class="text-surface-400 dark:text-surface-500">高値</span><span class="${isGreen ? "text-brand-600 dark:text-brand-400" : ""}">¥${high.toLocaleString()}</span>
            <span class="text-surface-400 dark:text-surface-500">安値</span><span class="${!isGreen ? "text-danger-500 dark:text-danger-400" : ""}">¥${low.toLocaleString()}</span>
            <span class="text-surface-400 dark:text-surface-500">終値</span><span class="font-bold">¥${close.toLocaleString()}</span>
          </div>
        </div>
      `;
      const rect   = containerRef.current!.getBoundingClientRect();
      const tipW   = tooltip.offsetWidth;
      const tipH   = tooltip.offsetHeight;
      let left     = param.point.x + 12;
      if (left + tipW > rect.width) left = param.point.x - tipW - 12;
      let top      = param.point.y - tipH / 2;
      if (top < 0) top = 4;
      tooltip.style.left    = `${left}px`;
      tooltip.style.top     = `${top}px`;
      tooltip.style.display = "block";
    });

    // レスポンシブ
    const ro = new ResizeObserver(() => {
      chart.applyOptions({ width: containerRef.current?.clientWidth ?? 600 });
    });
    ro.observe(containerRef.current);

    chart.timeScale().fitContent();

    return () => { ro.disconnect(); chart.remove(); };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isDark, period, showVolume, showEma25, showEma75, showSignal,
      candleData.length, volumeData.length]);

  useEffect(() => {
    const cleanup = buildChart();
    return cleanup;
  }, [buildChart]);

  const periods: Period[] = ["1M", "3M", "6M", "1Y", "ALL"];

  return (
    <div className="space-y-3">
      {/* コントロールバー */}
      <div className="flex items-center justify-between flex-wrap gap-2">
        {/* 期間ボタン */}
        <div className="flex items-center gap-1 bg-surface-50 dark:bg-surface-800 rounded-xl p-1 border border-surface-100 dark:border-surface-700">
          {periods.map(p => (
            <button
              key={p}
              onClick={() => setPeriod(p)}
              className={`px-3 py-1 rounded-lg text-xs font-semibold transition-all ${
                period === p
                  ? "bg-white dark:bg-surface-700 text-brand-600 dark:text-brand-400 shadow-sm"
                  : "text-surface-400 dark:text-surface-500 hover:text-surface-700 dark:hover:text-surface-300"
              }`}
            >
              {p}
            </button>
          ))}
        </div>

        {/* トグル */}
        <div className="flex items-center gap-3 flex-wrap">
          <Toggle label="出来高"   checked={showVolume} onChange={() => setShowVolume(v => !v)} />
          <Toggle label="EMA25"   checked={showEma25}  onChange={() => setShowEma25(v  => !v)} />
          <Toggle label="EMA75"   checked={showEma75}  onChange={() => setShowEma75(v  => !v)} />
          {signals.length > 0 && (
            <Toggle label="シグナル" checked={showSignal} onChange={() => setShowSignal(v => !v)} />
          )}
        </div>
      </div>

      {/* チャート本体 */}
      <div className="relative overflow-hidden rounded-xl bg-white dark:bg-surface-900 border border-surface-100 dark:border-surface-800">
        <div ref={containerRef} className="w-full" />
        {/* カスタムツールチップ */}
        <div
          ref={tooltipRef}
          className="pointer-events-none absolute hidden z-10 bg-white dark:bg-surface-800 border border-surface-200 dark:border-surface-700 rounded-xl px-3 py-2.5 shadow-xl"
        />
      </div>

      {/* 凡例 */}
      <div className="flex items-center gap-4 text-xs text-surface-400 dark:text-surface-500 flex-wrap">
        {showEma25 && (
          <span className="flex items-center gap-1">
            <span className="inline-block w-4 h-0.5 bg-amber-500 rounded" />EMA25
          </span>
        )}
        {showEma75 && (
          <span className="flex items-center gap-1">
            <span className="inline-block w-4 h-0.5 bg-purple-500 rounded" />EMA75
          </span>
        )}
        {showSignal && signals.length > 0 && (
          <span className="flex items-center gap-1">
            <span className="text-brand-500">▲</span>UPシグナル
            <span className="text-danger-500 ml-2">▼</span>DOWNシグナル
          </span>
        )}
        {!isPro && (
          <span className="ml-auto text-amber-500 dark:text-amber-400 font-medium">
            ※ Freeプランは直近30日
          </span>
        )}
      </div>
    </div>
  );
}
