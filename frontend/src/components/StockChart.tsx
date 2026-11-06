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
        className="w-3.5 h-3.5 accent-teal-500 cursor-pointer"
        checked={checked}
        onChange={onChange}
      />
      <span className="text-slate-500">{label}</span>
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
      ? "rgba(45,212,191,0.35)"
      : "rgba(251,113,133,0.35)",
  }));

  const closeLine = filteredQuotes.map(q => ({
    time:  q.Date as Time,
    value: Number(q.AdjustmentClose),
  }));

  // チャート生成
  const buildChart = useCallback(() => {
    if (!containerRef.current) return;
    if (chartRef.current) {
      try { chartRef.current.remove(); } catch {}
      chartRef.current = null;
    }

    const bg    = "#0c1424";
    const text  = "#64748b";
    const grid  = "rgba(30,45,69,0.8)";
    const up    = "#2dd4bf";   // teal-400
    const down  = "#fb7185";   // rose-400
    const border = "#1e2d45";

    const chart = createChart(containerRef.current, {
      width:  containerRef.current.clientWidth,
      height: showVolume ? 340 : 260,
      layout: {
        background: { type: ColorType.Solid, color: bg },
        textColor: text,
        fontFamily: "'JetBrains Mono', 'Fira Code', 'Cascadia Code', ui-monospace, monospace",
        fontSize: 11,
      },
      grid: {
        vertLines:   { color: grid },
        horzLines:   { color: grid },
      },
      crosshair: {
        mode: CrosshairMode.Normal,
        vertLine: { color: up, labelBackgroundColor: up },
        horzLine: { color: up, labelBackgroundColor: up },
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
        color:       "#fbbf24",   // amber-400
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
        color:       "#c084fc",   // purple-400
        lineWidth:   1,
        crosshairMarkerVisible: false,
        priceLineVisible: false,
      });
      ema.setData(calcEMA(closeLine, 75));
      ema75Ref.current = ema;
    }

    // シグナルマーカー
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

    let disposed = false;

    // カスタムツールチップ
    chart.subscribeCrosshairMove(param => {
      if (disposed) return;
      const tooltip = tooltipRef.current;
      if (!tooltip) return;
      if (!param.time || !param.point) {
        tooltip.style.display = "none";
        return;
      }
      try {
        const cd = param.seriesData.get(candle);
        if (!cd || !("open" in cd)) {
          tooltip.style.display = "none";
          return;
        }
        const { open, high, low, close } = cd as CandlestickData;
        const isGreen = close >= open;
        tooltip.innerHTML = `
          <div class="text-xs font-mono leading-relaxed">
            <div class="font-bold mb-1 ${isGreen ? "text-teal-400" : "text-red-400"}">
              ${String(param.time)}
            </div>
            <div class="grid grid-cols-2 gap-x-3 text-slate-300">
              <span class="text-slate-500">始値</span><span>¥${open.toLocaleString()}</span>
              <span class="text-slate-500">高値</span><span class="${isGreen ? "text-teal-400" : ""}">¥${high.toLocaleString()}</span>
              <span class="text-slate-500">安値</span><span class="${!isGreen ? "text-red-400" : ""}">¥${low.toLocaleString()}</span>
              <span class="text-slate-500">終値</span><span class="font-bold">¥${close.toLocaleString()}</span>
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
      } catch {}
    });

    // レスポンシブ
    const ro = new ResizeObserver(() => {
      if (disposed) return;
      try {
        chart.applyOptions({ width: containerRef.current?.clientWidth ?? 600 });
      } catch {}
    });
    ro.observe(containerRef.current);

    chart.timeScale().fitContent();

    return () => {
      disposed = true;
      ro.disconnect();
      try { chart.remove(); } catch {}
      chartRef.current = null;
    };
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
        <div className="flex items-center gap-1 bg-[#060b16] rounded p-1 border border-slate-700/60">
          {periods.map(p => (
            <button
              key={p}
              onClick={() => setPeriod(p)}
              className={`px-3 py-1 rounded text-xs font-black tracking-widest uppercase transition-all ${
                period === p
                  ? "bg-[#0c1424] text-teal-400 shadow-sm border border-slate-700/60"
                  : "text-slate-600 hover:text-slate-400"
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
      <div className="relative overflow-hidden rounded bg-[#0c1424] border border-slate-700/60">
        <div ref={containerRef} className="w-full" />
        {/* カスタムツールチップ */}
        <div
          ref={tooltipRef}
          className="pointer-events-none absolute hidden z-10 bg-[#060b16] border border-slate-700/60 rounded px-3 py-2.5 shadow-xl"
        />
      </div>

      {/* 凡例 */}
      <div className="flex items-center gap-4 text-xs text-slate-600 flex-wrap">
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
            <span className="text-teal-500">▲</span>UPシグナル
            <span className="text-red-400 ml-2">▼</span>DOWNシグナル
          </span>
        )}
        {!isPro && (
          <span className="ml-auto text-amber-500 font-medium">
            ※ Freeプランは直近30日
          </span>
        )}
      </div>
    </div>
  );
}
