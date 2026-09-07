import React from "react";
import AppShell from "@/components/AppShell";
import { useBrand } from "@/context/BrandContext";
import { getBrandLogo } from "@/components/BrandLogos";
import { motion } from "framer-motion";
import { AlertTriangle, Clock } from "lucide-react";

const ACCENT_STYLES = {
  amber: {
    heroBadgeText: "text-amber-100",
    heroBadgeIcon: "text-amber-200",
    heroDescText: "text-amber-100",
    brandLabel: "text-amber-200",
    cardBg: "bg-amber-500/10 dark:bg-amber-500/15",
    cardBorder: "border-amber-500/40",
    cardText: "text-amber-950 dark:text-amber-100",
    iconBg: "bg-amber-500 text-slate-950",
    statusBadgeBg: "bg-amber-500/20 text-amber-700 dark:text-amber-400",
    statusClockText: "text-amber-600 dark:text-amber-400",
    titleText: "text-amber-900 dark:text-amber-300",
    noticeBg: "bg-amber-500/10 border-amber-500/30 text-amber-900/90 dark:text-amber-200",
    previewBorder: "border-amber-500/20",
    previewIconColor: "text-amber-500",
    previewBadgeBg: "bg-amber-500/20 text-amber-700 dark:text-amber-300",
  },
  blue: {
    heroBadgeText: "text-blue-100",
    heroBadgeIcon: "text-blue-200",
    heroDescText: "text-blue-100",
    brandLabel: "text-blue-200",
    cardBg: "bg-blue-500/10 dark:bg-blue-500/15",
    cardBorder: "border-blue-500/40",
    cardText: "text-blue-950 dark:text-blue-100",
    iconBg: "bg-blue-600 text-white",
    statusBadgeBg: "bg-blue-500/20 text-blue-700 dark:text-blue-400",
    statusClockText: "text-blue-600 dark:text-blue-400",
    titleText: "text-blue-900 dark:text-blue-300",
    noticeBg: "bg-blue-500/10 border-blue-500/30 text-blue-900/90 dark:text-blue-200",
    previewBorder: "border-blue-500/20",
    previewIconColor: "text-blue-500",
    previewBadgeBg: "bg-blue-500/20 text-blue-700 dark:text-blue-300",
  },
  violet: {
    heroBadgeText: "text-violet-100",
    heroBadgeIcon: "text-violet-200",
    heroDescText: "text-violet-100",
    brandLabel: "text-violet-200",
    cardBg: "bg-violet-500/10 dark:bg-violet-500/15",
    cardBorder: "border-violet-500/40",
    cardText: "text-violet-950 dark:text-violet-100",
    iconBg: "bg-violet-600 text-white",
    statusBadgeBg: "bg-violet-500/20 text-violet-700 dark:text-violet-400",
    statusClockText: "text-violet-600 dark:text-violet-400",
    titleText: "text-violet-900 dark:text-violet-300",
    noticeBg: "bg-violet-500/10 border-violet-500/30 text-violet-900/90 dark:text-violet-200",
    previewBorder: "border-violet-500/20",
    previewIconColor: "text-violet-500",
    previewBadgeBg: "bg-violet-500/20 text-violet-700 dark:text-violet-300",
  },
  rose: {
    heroBadgeText: "text-rose-100",
    heroBadgeIcon: "text-rose-200",
    heroDescText: "text-rose-100",
    brandLabel: "text-rose-200",
    cardBg: "bg-rose-500/10 dark:bg-rose-500/15",
    cardBorder: "border-rose-500/40",
    cardText: "text-rose-950 dark:text-rose-100",
    iconBg: "bg-rose-600 text-white",
    statusBadgeBg: "bg-rose-500/20 text-rose-700 dark:text-rose-400",
    statusClockText: "text-rose-600 dark:text-rose-400",
    titleText: "text-rose-900 dark:text-rose-300",
    noticeBg: "bg-rose-500/10 border-rose-500/30 text-rose-900/90 dark:text-rose-200",
    previewBorder: "border-rose-500/20",
    previewIconColor: "text-rose-500",
    previewBadgeBg: "bg-rose-500/20 text-rose-700 dark:text-rose-300",
  },
  emerald: {
    heroBadgeText: "text-emerald-100",
    heroBadgeIcon: "text-emerald-200",
    heroDescText: "text-emerald-100",
    brandLabel: "text-emerald-200",
    cardBg: "bg-emerald-500/10 dark:bg-emerald-500/15",
    cardBorder: "border-emerald-500/40",
    cardText: "text-emerald-950 dark:text-emerald-100",
    iconBg: "bg-emerald-600 text-white",
    statusBadgeBg: "bg-emerald-500/20 text-emerald-700 dark:text-emerald-400",
    statusClockText: "text-emerald-600 dark:text-emerald-400",
    titleText: "text-emerald-900 dark:text-emerald-300",
    noticeBg: "bg-emerald-500/10 border-emerald-500/30 text-emerald-900/90 dark:text-emerald-200",
    previewBorder: "border-emerald-500/20",
    previewIconColor: "text-emerald-500",
    previewBadgeBg: "bg-emerald-500/20 text-emerald-700 dark:text-emerald-300",
  },
};

export default function ModulePageLayout({
  moduleName = "İSG Modülü",
  moduleBadge = "İSG Modülü — Faz 2",
  moduleGradient = "from-emerald-600 via-teal-600 to-cyan-600",
  moduleIcon: ModuleIcon,
  moduleDescription = "",
  pageTitle = "",
  noticeText = "",
  themeAccent = "emerald",
  previewCards = [],
}) {
  const { selectedBrand } = useBrand();
  const styles = ACCENT_STYLES[themeAccent] || ACCENT_STYLES.emerald;

  return (
    <AppShell>
      <div className="space-y-6 max-w-7xl mx-auto font-sans pb-16">
        {/* HEADER HERO BANNER */}
        <div
          className={`relative overflow-hidden rounded-2xl bg-gradient-to-r ${moduleGradient} p-6 sm:p-8 text-white shadow-xl`}
        >
          <div className="absolute top-0 right-0 -translate-y-1/2 translate-x-1/4 w-96 h-96 bg-white/10 rounded-full blur-3xl pointer-events-none" />

          <div className="relative z-10 flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
            <div className="space-y-2">
              <div
                className={`inline-flex items-center gap-2 px-3 py-1 rounded-full bg-white/20 backdrop-blur-md text-xs font-black uppercase tracking-wider ${styles.heroBadgeText} border border-white/30`}
              >
                {ModuleIcon && <ModuleIcon className={`w-4 h-4 ${styles.heroBadgeIcon}`} />}
                <span>{moduleBadge}</span>
              </div>
              <h1 className="text-2xl sm:text-4xl font-extrabold tracking-tight font-sans">
                {moduleName}
              </h1>
              <p className={`text-xs sm:text-sm ${styles.heroDescText} max-w-xl leading-relaxed`}>
                {moduleDescription}
              </p>
            </div>

            {/* ACTIVE BRAND BADGE */}
            {selectedBrand && selectedBrand !== "Tüm Markalar" && (
              <div className="bg-white/10 backdrop-blur-md border border-white/20 p-3.5 rounded-xl flex items-center gap-3 shrink-0">
                <div className="w-10 h-10 rounded-lg bg-white/20 flex items-center justify-center">
                  {getBrandLogo(selectedBrand, "w-7 h-7 object-contain")}
                </div>
                <div>
                  <div className={`text-[10px] uppercase font-bold ${styles.brandLabel}`}>
                    Seçili Restoran Zinciri
                  </div>
                  <div className="text-sm font-black text-white">{selectedBrand}</div>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* MAIN WARNING CARD */}
        <motion.div
          initial={{ opacity: 0, y: 15 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
          className={`p-8 rounded-2xl ${styles.cardBg} border-2 ${styles.cardBorder} ${styles.cardText} shadow-lg space-y-6`}
        >
          <div className="flex items-start gap-4">
            <div
              className={`w-12 h-12 rounded-2xl ${styles.iconBg} flex items-center justify-center shrink-0 shadow-md`}
            >
              <AlertTriangle className="w-7 h-7 stroke-[2.5]" />
            </div>
            <div className="space-y-2 flex-1">
              <div className="flex items-center gap-2">
                <span
                  className={`text-xs font-black uppercase tracking-widest ${styles.statusBadgeBg} px-2.5 py-0.5 rounded-md`}
                >
                  Geliştirme Aşamasında
                </span>
                <span
                  className={`text-xs ${styles.statusClockText} flex items-center gap-1 font-mono`}
                >
                  <Clock className="w-3.5 h-3.5" /> Güncelleme Yakında
                </span>
              </div>
              <h2 className={`text-xl sm:text-2xl font-black ${styles.titleText} tracking-tight font-sans`}>
                {pageTitle}
              </h2>
              {noticeText && (
                <p
                  className={`text-sm sm:text-base font-bold leading-relaxed font-sans p-4 rounded-xl border ${styles.noticeBg}`}
                >
                  {noticeText}
                </p>
              )}
            </div>
          </div>

          {/* PREVIEW MODULE CARDS */}
          {previewCards.length > 0 && (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-2">
              {previewCards.map((card, idx) => {
                const CardIcon = card.icon || AlertTriangle;
                return (
                  <div
                    key={idx}
                    className={`p-4 rounded-xl bg-white/60 dark:bg-slate-900/60 border ${styles.previewBorder} space-y-2`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold text-slate-700 dark:text-slate-300 flex items-center gap-1.5">
                        <CardIcon className={`w-4 h-4 ${styles.previewIconColor}`} /> {card.title}
                      </span>
                      <span
                        className={`text-[10px] ${styles.previewBadgeBg} font-bold px-2 py-0.5 rounded-full`}
                      >
                        {card.badge || "v2.0"}
                      </span>
                    </div>
                    <p className="text-xs text-slate-500 dark:text-slate-400">
                      {card.description}
                    </p>
                  </div>
                );
              })}
            </div>
          )}
        </motion.div>
      </div>
    </AppShell>
  );
}
