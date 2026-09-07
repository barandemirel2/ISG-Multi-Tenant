/**
 * RiskDistributionChart — UI/UX P1
 *
 * DashboardPage'de tüm (filtrelenmiş) audit'lerin risk dağılımını
 * donut chart olarak gösterir. Recharts kullanır (package.json'da
 * yüklü).
 *
 * Girdi: array of audit (her biri summary.risk_counts içermeli)
 * Çıktı: 3 dilimli donut + toplam sayı + merkez metin
 */
import React, { useMemo } from "react";
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from "recharts";
import { ShieldCheck, AlertTriangle, AlertOctagon, PieChart as PieIcon } from "lucide-react";
import { cn } from "@/lib/utils";

const COLORS = {
  emerald: { color: "#10B981", bg: "bg-emerald-50 dark:bg-emerald-500/10", text: "text-emerald-700 dark:text-emerald-400", border: "border-emerald-200 dark:border-emerald-500/30" },
  amber:   { color: "#F59E0B", bg: "bg-amber-50 dark:bg-amber-500/10",     text: "text-amber-700 dark:text-amber-400",     border: "border-amber-200 dark:border-amber-500/30" },
  red:     { color: "#EF4444", bg: "bg-red-50 dark:bg-red-500/10",         text: "text-red-700 dark:text-red-400",         border: "border-red-200 dark:border-red-500/30" },
};

export default function RiskDistributionChart({ audits = [] }) {
  const { data, total, kabulEdilebilir, dikkateDeger, kabulEdilemez } = useMemo(() => {
    let kabulEdilebilir = 0;
    let dikkateDeger = 0;
    let kabulEdilemez = 0;
    for (const a of audits) {
      const counts = a.summary?.risk_counts || {};
      // Backend büyük harf (KABUL EDİLEMEZ) veya Title-case (Kabul Edilemez) gönderebilir
      kabulEdilebilir += counts["KABUL EDİLEBİLİR"] || counts["Kabul Edilebilir"] || 0;
      dikkateDeger += counts["DİKKATE DEĞER"] || counts["Dikkate Değer"] || 0;
      kabulEdilemez += counts["KABUL EDİLEMEZ"] || counts["Kabul Edilemez"] || 0;
    }
    const total = kabulEdilebilir + dikkateDeger + kabulEdilemez;
    const data = [
      { name: "Kabul Edilebilir", value: kabulEdilebilir, color: COLORS.emerald.color, key: "emerald" },
      { name: "Dikkate Değer", value: dikkateDeger, color: COLORS.amber.color, key: "amber" },
      { name: "Kabul Edilemez", value: kabulEdilemez, color: COLORS.red.color, key: "red" },
    ].filter((d) => d.value > 0);
    return { data, total, kabulEdilebilir, dikkateDeger, kabulEdilemez };
  }, [audits]);

  if (total === 0) {
    return (
      <div className="p-6 sm:p-8 rounded-card border border-slate-200/80 dark:border-white/10 surface-card shadow-sm dark:shadow-md font-sans text-center">
        <PieIcon className="w-8 h-8 text-slate-300 dark:text-slate-700 mx-auto mb-2" />
        <p className="text-sm font-semibold text-slate-700 dark:text-slate-300">
          Henüz risk verisi yok
        </p>
        <p className="text-[11px] text-slate-500 dark:text-slate-400 mt-1">
          Denetim tamamlandıkça burada risk dağılımı görünecek.
        </p>
      </div>
    );
  }

  return (
    <div className="p-5 sm:p-6 rounded-card border border-slate-200/80 dark:border-white/10 surface-card shadow-sm dark:shadow-md font-sans" data-testid="risk-distribution-chart">
      <div className="flex items-center justify-between mb-3">
        <div>
          <h3 className="text-sm font-extrabold text-slate-900 dark:text-white tracking-tight flex items-center gap-2">
            <PieIcon className="w-4 h-4 text-red-600 dark:text-red-400" />
            Risk Dağılımı
          </h3>
          <p className="text-[11px] text-slate-500 dark:text-slate-400 mt-0.5">
            Tüm filtrelenmiş denetimler
          </p>
        </div>
        <div className="text-right">
          <div className="text-2xl font-extrabold text-slate-900 dark:text-white tabular-nums font-mono">
            {total}
          </div>
          <div className="text-[10px] uppercase tracking-wider font-bold text-slate-500 dark:text-slate-400">
            Toplam Soru
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-[160px,1fr] gap-4 items-center">
        {/* DONUT CHART */}
        <div className="relative w-full" style={{ height: 160 }}>
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={data}
                cx="50%"
                cy="50%"
                innerRadius={48}
                outerRadius={72}
                paddingAngle={2}
                dataKey="value"
                stroke="none"
              >
                {data.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.color} />
                ))}
              </Pie>
              <Tooltip
                content={({ active, payload }) => {
                  if (!active || !payload?.[0]) return null;
                  const item = payload[0].payload;
                  const pct = total > 0 ? Math.round((item.value / total) * 100) : 0;
                  return (
                    <div className="bg-white dark:bg-slate-950 border border-slate-200 dark:border-white/10 rounded-lg shadow-lg p-2 text-xs font-sans">
                      <div className="font-bold text-slate-900 dark:text-white">{item.name}</div>
                      <div className="text-slate-600 dark:text-slate-400 tabular-nums">
                        {item.value} soru ({pct}%)
                      </div>
                    </div>
                  );
                }}
              />
            </PieChart>
          </ResponsiveContainer>
          {/* Center label */}
          <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
            <div className="text-[10px] uppercase tracking-wider font-bold text-slate-500 dark:text-slate-400">Oran</div>
            <div className="text-sm font-extrabold text-slate-900 dark:text-white tabular-nums">
              {total > 0 ? Math.round((kabulEdilemez / total) * 100) : 0}%
            </div>
            <div className="text-[9px] uppercase tracking-wider font-bold text-red-600 dark:text-red-400">Kritik</div>
          </div>
        </div>

        {/* LEGEND + BREAKDOWN */}
        <div className="space-y-2">
          <LegendRow
            icon={ShieldCheck}
            label="Kabul Edilebilir"
            value={kabulEdilebilir}
            total={total}
            colorKey="emerald"
          />
          <LegendRow
            icon={AlertTriangle}
            label="Dikkate Değer"
            value={dikkateDeger}
            total={total}
            colorKey="amber"
          />
          <LegendRow
            icon={AlertOctagon}
            label="Kabul Edilemez"
            value={kabulEdilemez}
            total={total}
            colorKey="red"
          />
        </div>
      </div>
    </div>
  );
}

function LegendRow({ icon: Icon, label, value, total, colorKey }) {
  const c = COLORS[colorKey];
  const pct = total > 0 ? Math.round((value / total) * 100) : 0;
  return (
    <div
      className={cn(
        "flex items-center gap-2 px-2.5 py-1.5 rounded-lg border",
        c.bg,
        c.border,
      )}
    >
      <Icon className={cn("w-4 h-4 shrink-0", c.text)} />
      <div className="flex-1 min-w-0">
        <div className={cn("text-xs font-bold", c.text)}>{label}</div>
      </div>
      <div className="text-right">
        <div className={cn("text-sm font-extrabold tabular-nums font-mono", c.text)}>
          {value}
        </div>
        <div className="text-[10px] text-slate-500 dark:text-slate-400 tabular-nums">
          {pct}%
        </div>
      </div>
    </div>
  );
}
