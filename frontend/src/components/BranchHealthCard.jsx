import React, { useMemo } from "react";
import { motion } from "framer-motion";
import { Building2, ShieldAlert, Activity, AlertOctagon, UserCheck } from "lucide-react";

export function BranchHealthCard({ branchName, items = [], audits = [] }) {
  // Compute branch metrics (hooks MUST be declared before any early return)
  const branchItems = useMemo(
    () => items.filter((x) => (x.restaurant_name || "").toLowerCase() === (branchName || "").toLowerCase()),
    [items, branchName]
  );

  const branchAudits = useMemo(
    () => audits.filter((a) => (a.restaurant_name || "").toLowerCase() === (branchName || "").toLowerCase()),
    [audits, branchName]
  );

  const openDofs = useMemo(
    () => branchItems.filter((x) => x.status !== "KAPATILDI").length,
    [branchItems]
  );

  const avgRiskScore = useMemo(() => {
    if (branchItems.length === 0) return "0.0";
    const total = branchItems.reduce((acc, curr) => acc + (curr.risk_score ?? curr.default_risk_score ?? 0), 0);
    return (total / branchItems.length).toFixed(1);
  }, [branchItems]);

  const topCategory = useMemo(() => {
    if (branchItems.length === 0) return "—";
    const counts = {};
    for (const item of branchItems) {
      const cat = item.category || item.kategori || "Genel";
      counts[cat] = (counts[cat] || 0) + 1;
    }
    let top = "—";
    let max = 0;
    for (const [cat, count] of Object.entries(counts)) {
      if (count > max) {
        max = count;
        top = cat;
      }
    }
    return `${top} (${max} Uygunsuzluk)`;
  }, [branchItems]);

  if (!branchName || branchName === "HEPSİ") return null;

  const latestAudit = branchAudits[0] || branchItems[0] || {};
  const managerName = latestAudit.restaurant_manager || latestAudit.sorumlu || "Atanmadı";

  const isHighRisk = Number(avgRiskScore) >= 13;

  return (
    <motion.div
      initial={{ opacity: 0, y: -10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -10 }}
      transition={{ duration: 0.25 }}
      className={`rounded-card border p-5 shadow-2xl space-y-4 font-sans transition-colors duration-standard ease-swift ${
        isHighRisk
          ? "bg-risk-critical-bg border-risk-critical-border"
          : "surface-card border-emerald-500/30"
      }`}
    >
      {/* CARD HEADER */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-200/80 dark:border-white/10 pb-3">
        <div className="flex items-center gap-2.5 font-sans">
          <div className="p-2 rounded-card bg-red-500/15 text-red-600 dark:text-red-400 border border-red-500/30">
            <Building2 className="w-5 h-5" />
          </div>
          <div>
            <div className="text-[10px] font-bold text-red-600 dark:text-red-500 uppercase tracking-widest font-sans">
              ŞUBE İSG SAĞLIK VE RİSK KARNESİ
            </div>
            <h2 className="text-lg sm:text-xl font-extrabold text-slate-900 dark:text-white tracking-tight font-sans">
              {branchName}
            </h2>
          </div>
        </div>

        <span
          className={`px-3 py-1 rounded-card text-xs font-sans font-extrabold flex items-center gap-1.5 self-start sm:self-auto ${
            isHighRisk
              ? "bg-red-500/20 text-red-700 dark:text-red-300 border border-red-500/40 animate-pulse"
              : "bg-emerald-500/20 text-emerald-700 dark:text-emerald-300 border border-emerald-500/40"
          }`}
        >
          <Activity className="w-3.5 h-3.5" />
          {isHighRisk ? "Yüksek Risk Seviyesi" : "Kontrol Altında"}
        </span>
      </div>

      {/* METRICS GRID */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 pt-1 font-sans">
        <div className="p-3.5 rounded-card bg-slate-100/80 dark:bg-slate-900/80 border border-slate-200/80 dark:border-white/5 space-y-1">
          <span className="text-[10px] font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider flex items-center gap-1">
            <ShieldAlert className="w-3 h-3 text-amber-500 dark:text-amber-400" /> AÇIK DÖF SAYISI
          </span>
          <div className="text-xl font-extrabold text-slate-900 dark:text-white tabular-nums">{openDofs} Adet</div>
        </div>

        <div className="p-3.5 rounded-card bg-slate-100/80 dark:bg-slate-900/80 border border-slate-200/80 dark:border-white/5 space-y-1">
          <span className="text-[10px] font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider flex items-center gap-1">
            <AlertOctagon className="w-3 h-3 text-red-500 dark:text-red-400" /> ORTALAMA RİSK SKORU
          </span>
          <div className={`text-xl font-extrabold tabular-nums ${isHighRisk ? "text-red-600 dark:text-red-400" : "text-emerald-600 dark:text-emerald-400"}`}>
            {avgRiskScore} / 25
          </div>
        </div>

        <div className="p-3.5 rounded-card bg-slate-100/80 dark:bg-slate-900/80 border border-slate-200/80 dark:border-white/5 space-y-1">
          <span className="text-[10px] font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider flex items-center gap-1">
            <Activity className="w-3 h-3 text-emerald-500 dark:text-emerald-400" /> EN ÇOK UYGUNSUZLUK
          </span>
          <div className="text-xs font-bold text-slate-800 dark:text-slate-200 truncate">{topCategory}</div>
        </div>

        <div className="p-3.5 rounded-card bg-slate-100/80 dark:bg-slate-900/80 border border-slate-200/80 dark:border-white/5 space-y-1">
          <span className="text-[10px] font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider flex items-center gap-1">
            <UserCheck className="w-3 h-3 text-slate-500 dark:text-slate-400" /> ŞUBE MÜDÜRÜ / UZMAN
          </span>
          <div className="text-xs font-bold text-slate-800 dark:text-slate-200 truncate">{managerName}</div>
        </div>
      </div>
    </motion.div>
  );
}

export default BranchHealthCard;
