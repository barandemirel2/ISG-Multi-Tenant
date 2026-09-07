import { useMemo } from "react";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { RotateCcw } from "lucide-react";
import {
  calculateRiskScore,
  classifyRiskScore,
  riskBadgeClass,
} from "@/lib/risk";
import { cn } from "@/lib/utils";

const SCALE_VALUES = [1, 2, 3, 4, 5];

const safeLevel = (score) => {
  try {
    return classifyRiskScore(score);
  } catch (_error) {
    return "—";
  }
};

const cellClass =
  "bg-white dark:bg-slate-900/90 border border-slate-200 dark:border-white/10 rounded-card p-3 flex flex-col gap-1 shadow-sm font-sans transition-all duration-200 hover:border-slate-300 dark:hover:border-white/20";
const labelClass = "text-slate-600 dark:text-slate-400 text-[10px] uppercase font-bold tracking-wider font-sans";
const valueClass = "font-sans font-extrabold tabular-nums text-xl text-slate-900 dark:text-white";

export default function OverrideEditor({
  defaultProbability,
  defaultSeverity,
  probability,
  severity,
  onChange,
  testIdPrefix = "override",
  disabled = false,
}) {
  const score = useMemo(() => {
    try {
      return calculateRiskScore(probability, severity);
    } catch (_error) {
      return null;
    }
  }, [probability, severity]);

  const level = useMemo(() => (score == null ? "—" : safeLevel(score)), [score]);
  const hasOverride =
    Number(probability) !== Number(defaultProbability) ||
    Number(severity) !== Number(defaultSeverity);

  const isKabulEdilemez = level === "Kabul Edilemez" || (score != null && score >= 13);
  const isDikkateDeger = level === "Dikkate Değer" || (score != null && score >= 5 && score < 13);

  const glowBorderClass = isKabulEdilemez
    ? "border-red-300 dark:border-red-500/50 bg-red-50/80 dark:bg-red-950/30 text-red-900 dark:text-red-300"
    : isDikkateDeger
    ? "border-amber-300 dark:border-amber-500/50 bg-amber-50/80 dark:bg-amber-950/30 text-amber-900 dark:text-amber-300"
    : "border-emerald-300 dark:border-emerald-500/50 bg-emerald-50/80 dark:bg-emerald-950/30 text-emerald-900 dark:text-emerald-300";

  const handleProbability = (raw) => {
    const next = Number(raw);
    if (!Number.isInteger(next)) return;
    onChange({ probability: next, severity: Number(severity) });
  };

  const handleSeverity = (raw) => {
    const next = Number(raw);
    if (!Number.isInteger(next)) return;
    onChange({ probability: Number(probability), severity: next });
  };

  const handleReset = () => {
    onChange(null);
  };

  return (
    <div
      className="grid grid-cols-2 md:grid-cols-4 gap-2 font-sans"
      data-testid={testIdPrefix}
    >
      <div className={cn(cellClass, glowBorderClass)}>
        <span className={labelClass}>Olasılık (1-5)</span>
        <Select
          value={String(probability)}
          onValueChange={handleProbability}
          disabled={disabled}
        >
          <SelectTrigger
            className="h-9 w-full text-xs font-extrabold tabular-nums bg-slate-50 dark:bg-slate-950/90 border-slate-300 dark:border-slate-700 text-slate-900 dark:text-white focus:border-amber-500 font-sans"
            data-testid={`${testIdPrefix}-probability`}
          >
            <SelectValue />
          </SelectTrigger>
          <SelectContent className="bg-white dark:bg-slate-950 border-slate-200 dark:border-slate-800 text-slate-900 dark:text-white font-sans text-xs">
            {SCALE_VALUES.map((v) => (
              <SelectItem key={v} value={String(v)} className="text-xs hover:bg-slate-100 dark:hover:bg-slate-900 focus:bg-slate-100 dark:focus:bg-slate-800">
                <span className="tabular-nums font-bold">{v} Puan</span>
                {v === Number(defaultProbability) && (
                  <span
                    className="ml-2 text-[10px] uppercase tracking-wider text-amber-600 dark:text-amber-400 font-sans"
                    data-testid={`${testIdPrefix}-probability-default-${v}`}
                  >
                    (varsayılan)
                  </span>
                )}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className={cn(cellClass, glowBorderClass)}>
        <span className={labelClass}>Şiddet (1-5)</span>
        <Select
          value={String(severity)}
          onValueChange={handleSeverity}
          disabled={disabled}
        >
          <SelectTrigger
            className="h-9 w-full text-xs font-extrabold tabular-nums bg-slate-50 dark:bg-slate-950/90 border-slate-300 dark:border-slate-700 text-slate-900 dark:text-white focus:border-amber-500 font-sans"
            data-testid={`${testIdPrefix}-severity`}
          >
            <SelectValue />
          </SelectTrigger>
          <SelectContent className="bg-white dark:bg-slate-950 border-slate-200 dark:border-slate-800 text-slate-900 dark:text-white font-sans text-xs">
            {SCALE_VALUES.map((v) => (
              <SelectItem key={v} value={String(v)} className="text-xs hover:bg-slate-100 dark:hover:bg-slate-900 focus:bg-slate-100 dark:focus:bg-slate-800">
                <span className="tabular-nums font-bold">{v} Puan</span>
                {v === Number(defaultSeverity) && (
                  <span
                    className="ml-2 text-[10px] uppercase tracking-wider text-amber-600 dark:text-amber-400 font-sans"
                    data-testid={`${testIdPrefix}-severity-default-${v}`}
                  >
                    (varsayılan)
                  </span>
                )}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className={cn(cellClass, glowBorderClass)} data-testid={`${testIdPrefix}-score`}>
        <span className={labelClass}>Hesaplanan Risk Skoru</span>
        <span className={valueClass}>{score ?? "—"} Puan</span>
      </div>

      <div className={cn(cellClass, glowBorderClass)} data-testid={`${testIdPrefix}-level`}>
        <div className="flex items-center justify-between">
          <span className={labelClass}>Risk Sınıfı</span>
          {hasOverride && (
            <button
              type="button"
              onClick={handleReset}
              className="text-[10px] text-amber-600 dark:text-amber-400 hover:text-amber-700 dark:hover:text-amber-300 font-sans flex items-center gap-1 cursor-pointer font-bold"
              title="Varsayılana sıfırla"
              data-testid={`${testIdPrefix}-reset`}
            >
              <RotateCcw className="w-3 h-3" /> Sıfırla
            </button>
          )}
        </div>
        <span
          className={`inline-block w-fit px-2.5 py-1 text-xs font-extrabold rounded-lg font-sans ${
            isKabulEdilemez
              ? "bg-red-100 dark:bg-red-500/20 text-red-800 dark:text-red-300 border border-red-300 dark:border-red-500/40"
              : isDikkateDeger
              ? "bg-amber-100 dark:bg-amber-500/20 text-amber-800 dark:text-amber-300 border border-amber-300 dark:border-amber-500/40"
              : "bg-emerald-100 dark:bg-emerald-500/20 text-emerald-800 dark:text-emerald-300 border border-emerald-300 dark:border-emerald-500/40"
          }`}
        >
          {level}
        </span>
      </div>
    </div>
  );
}
