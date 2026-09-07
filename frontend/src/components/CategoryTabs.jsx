import React from "react";
import { motion } from "framer-motion";

export function CategoryTabs({ categories = [], selectedCategory, onSelectCategory, questions = [], answers = {} }) {
  const safeQuestions = (questions || []).filter(Boolean);
  const safeCategories = (categories || []).filter(Boolean);

  if (safeCategories.length === 0) return null;

  return (
    <div className="w-full overflow-x-auto pb-1 mb-6 border-b border-border scrollbar-thin scrollbar-thumb-slate-200 dark:scrollbar-thumb-slate-700 scrollbar-track-transparent">
      {/* Master prompt: NO glassmorphism. NO backdrop-blur. Flat surface. */}
      <div className="inline-flex items-center gap-1 p-1.5 surface-card">
        {safeCategories.map((cat, index) => {
          const catQuestions = safeQuestions.filter((q) => (q?.kategori || q?.category) === cat);
          const totalCatQ = catQuestions.length;
          const answeredCatQ = catQuestions.filter((q) => q?.id && answers[String(q.id)]).length;
          const hayirCount = catQuestions.filter((q) => q?.id && answers[String(q.id)] === "HAYIR").length;
          const isSelected = selectedCategory === cat;
          const catNumber = String(index + 1).padStart(2, "0");

          return (
            <button
              key={cat}
              type="button"
              onClick={() => onSelectCategory && onSelectCategory(cat)}
              className={`relative flex items-center gap-2 px-3 py-1.5 rounded-control text-xs font-sans font-bold whitespace-nowrap transition-colors duration-standard ease-swift active:scale-95 cursor-pointer ${
                isSelected
                  ? "bg-risk-critical text-white"
                  : "text-ink-secondary hover:text-ink-primary hover:bg-surface-card-2"
              }`}
            >
              {/* Master prompt: NO gradient, NO neon glow. Flat risk-critical fill. */}
              {isSelected && (
                <motion.div
                  layoutId="activeCategoryTab"
                  className="absolute inset-0 rounded-control bg-risk-critical"
                  transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
                />
              )}
              <span className="relative z-10 flex items-center gap-2">
                <span className={isSelected ? "text-white/70 MonoData text-[10px]" : "text-ink-tertiary MonoData text-[10px]"}>
                  [{catNumber}]
                </span>
                <span>{cat}</span>
                <span
                  className={`px-2 py-0.5 rounded text-[10px] MonoData font-bold ${
                    isSelected ? "bg-black/30 text-white" : "bg-surface-card-2 text-ink-secondary border border-border"
                  }`}
                >
                  {answeredCatQ}/{totalCatQ}
                </span>
                {hayirCount > 0 && (
                  <span className="relative z-10 bg-risk-critical text-white text-[9px] px-1.5 py-0.5 rounded MonoData font-extrabold">
                    {hayirCount}
                  </span>
                )}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}

export default CategoryTabs;
