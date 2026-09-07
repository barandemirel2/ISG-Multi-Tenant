import React from "react";
import { useNavigate } from "react-router-dom";
import { useBrand, BRANDS_LIST } from "@/context/BrandContext";
import { getBrandLogo } from "@/components/BrandLogos";
import { motion } from "framer-motion";
import { Building2, Check, ArrowRight, ShieldCheck, Sparkles } from "lucide-react";

export default function BrandSelectionPage() {
  const { selectedBrand, setSelectedBrand } = useBrand();
  const navigate = useNavigate();

  const handleSelectBrand = (brandName) => {
    setSelectedBrand(brandName);
    navigate("/dashboard");
  };

  return (
    <div className="min-h-screen bg-surface-page-2 text-ink-primary flex flex-col justify-between p-4 sm:p-8 font-sans relative">
      {/* MAIN CONTAINER — master prompt: NO decorative glow blobs */}
      <div className="max-w-6xl mx-auto w-full flex-1 flex flex-col justify-center py-6 space-y-8">
        
        {/* TAB HERO HEADER */}
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="text-center space-y-4 font-sans"
        >
          {/* TAB BRAND LOGO GIANT HEADER */}
          <div className="inline-flex flex-col items-center">
            <h1 className="text-6xl sm:text-8xl font-black tracking-tighter text-[#0A58CA] dark:text-[#2563EB] font-sans">
              TAB
            </h1>
            {/* BLUE DIVIDER LINE — solid bar, no glow */}
            <div className="w-full max-w-[420px] h-1.5 bg-[#0A58CA] dark:bg-[#2563EB] rounded-full mt-1" />
          </div>

          <div className="space-y-1.5 pt-2">
            <h2 className="text-xl sm:text-2xl font-extrabold text-ink-primary tracking-tight flex items-center justify-center gap-2 font-sans">
              <Sparkles className="w-5 h-5 text-blue-600 dark:text-blue-400" />
              Restoran Zinciri Seçim Paneli
            </h2>
            <p className="text-xs sm:text-sm text-ink-secondary max-w-xl mx-auto leading-relaxed font-sans">
              Lütfen işlem yapmak istediğiniz marka zincirini seçiniz. Seçiminiz denetim oluşturma ve filtreleme süreçlerinize otomatik tanımlanacaktır.
            </p>
          </div>
        </motion.div>

        {/* TÜM MARKALAR (ABCD Tech Solutions GENEL) OPTION */}
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.4, delay: 0.1 }}
          className="max-w-md mx-auto w-full"
        >
          <button
            type="button"
            onClick={() => handleSelectBrand("Tüm Markalar")}
            className={`w-full p-4 rounded-2xl border-2 transition-all duration-300 flex items-center justify-between group cursor-pointer active:scale-98 ${
              selectedBrand === "Tüm Markalar" || !selectedBrand
                ? "bg-blue-500/10 dark:bg-blue-500/20 border-blue-500 text-ink-primary"
                : "bg-surface-card border-border-default hover:border-blue-500/50 text-ink-secondary hover:text-ink-primary"
            }`}
          >
            <div className="flex items-center gap-3.5">
              <div className="w-11 h-11 rounded-xl bg-blue-500/10 border border-blue-500/40 flex items-center justify-center shrink-0">
                <Building2 className="w-6 h-6 text-blue-600 dark:text-blue-400" />
              </div>
              <div className="text-left font-sans">
                <div className="text-sm font-extrabold text-ink-primary group-hover:text-blue-600 dark:group-hover:text-blue-400 transition-colors">
                  Tüm Markalar (ABCD Tech Solutions Genel)
                </div>
                <div className="text-[11px] text-ink-tertiary">
                  Tüm restoran zincirlerinde genel görünüm ve tam yetki
                </div>
              </div>
            </div>
            <div className="flex items-center gap-2">
              {selectedBrand === "Tüm Markalar" && (
                <span className="bg-blue-500 text-white p-1 rounded-full">
                  <Check className="w-4 h-4" />
                </span>
              )}
              <ArrowRight className="w-4 h-4 text-ink-tertiary group-hover:text-blue-600 dark:group-hover:text-blue-400 group-hover:translate-x-1 transition-all" />
            </div>
          </button>
        </motion.div>

        {/* 7 RESTAURANT CARDS GRID */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.2 }}
          className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-7 gap-3 sm:gap-4 pt-2"
        >
          {BRANDS_LIST.map((brand, index) => {
            const isSelected = selectedBrand === brand.name;
            return (
              <button
                key={brand.id}
                type="button"
                onClick={() => handleSelectBrand(brand.name)}
                className={`p-4 rounded-2xl border-2 transition-all duration-300 flex flex-col items-center justify-between text-center min-h-[170px] relative group cursor-pointer active:scale-95 ${
                  isSelected
                    ? "bg-surface-card border-amber-500 text-ink-primary ring-2 ring-amber-500/50"
                    : "bg-surface-card border-border-default hover:border-amber-500/50 text-ink-secondary hover:text-ink-primary"
                }`}
              >
                {/* BRAND LOGO DISPLAY */}
                <div className="w-full flex-1 flex items-center justify-center py-2">
                  <div className="w-16 h-16 sm:w-20 sm:h-20 flex items-center justify-center group-hover:scale-110 transition-transform duration-300">
                    {getBrandLogo(brand.name, "w-full h-full object-contain")}
                  </div>
                </div>

                {/* BRAND NAME & DESCRIPTION */}
                <div className="w-full space-y-1 pt-2 border-t border-border-default">
                  <div className="text-xs sm:text-sm font-extrabold text-ink-primary tracking-tight group-hover:text-amber-600 dark:group-hover:text-amber-400 transition-colors">
                    {brand.name}
                  </div>
                  <div className="text-[10px] text-ink-tertiary line-clamp-1 font-sans">
                    {brand.tag}
                  </div>
                </div>

                {/* SELECTED BADGE */}
                {isSelected && (
                  <div className="absolute top-2 right-2 bg-amber-500 text-white p-1 rounded-full shadow-card">
                    <Check className="w-3.5 h-3.5 stroke-[3]" />
                  </div>
                )}
              </button>
            );
          })}
        </motion.div>
      </div>

      {/* FOOTER ACCENT */}
      <div className="max-w-6xl mx-auto w-full pt-4 border-t border-border-default flex flex-col sm:flex-row items-center justify-between gap-2 text-xs text-ink-tertiary font-sans">
        <span className="flex items-center gap-1.5">
          <ShieldCheck className="w-4 h-4 text-risk-compliant" /> ABCD Tech Solutions İSG Risk & Denetim Yönetim Sistemi
        </span>
        <span>© {new Date().getFullYear()} ABCD Tech Solutions Sanayi ve Ticaret A.Ş.</span>
      </div>
    </div>
  );
}
