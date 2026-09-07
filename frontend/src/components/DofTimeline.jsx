import React, { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { History, ChevronDown, ChevronUp, CheckCircle2, Clock, Camera, ShieldCheck, User } from "lucide-react";

export function DofTimeline({ logs = [], status, createdAt, resolvedAt }) {
  const [isOpen, setIsOpen] = useState(false);

  if (!logs || logs.length === 0) return null;

  const formatDate = (isoStr) => {
    if (!isoStr) return "—";
    try {
      const d = new Date(isoStr);
      return d.toLocaleString("tr-TR", {
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch (e) {
      return isoStr;
    }
  };

  return (
    <div className="pt-2 border-t border-slate-200 dark:border-white/5 font-sans">
      <button
        type="button"
        onClick={() => setIsOpen((prev) => !prev)}
        className="inline-flex items-center gap-1.5 text-xs font-bold text-slate-700 hover:text-slate-900 dark:text-slate-400 dark:hover:text-white transition-colors cursor-pointer py-1 font-sans"
      >
        <History className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400" />
        <span>📜 İşlem Geçmişi (Timeline - {logs.length} Adım)</span>
        {isOpen ? <ChevronUp className="w-3.5 h-3.5 ml-1" /> : <ChevronDown className="w-3.5 h-3.5 ml-1" />}
      </button>

      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden mt-3 p-4 rounded-card bg-slate-50 border border-slate-200 dark:bg-slate-900/90 dark:border-white/10 space-y-4 font-sans"
          >
            <div className="relative pl-6 space-y-4 border-l-2 border-slate-300 dark:border-slate-700 font-sans">
              {logs.map((log, idx) => {
                const isLast = idx === logs.length - 1;
                const isClosedAction = log.action?.includes("Kapatıldı") || log.action?.includes("Onaylandı");
                const isPhotoAction = log.action?.includes("Fotoğraf") || log.action?.includes("İşlemde");

                return (
                  <div key={idx} className="relative group font-sans">
                    {/* TIMELINE DOT */}
                    <div
                      className={`absolute -left-[31px] top-0.5 w-4 h-4 rounded-full border-2 flex items-center justify-center font-sans ${
                        isClosedAction
                          ? "bg-emerald-500 border-emerald-400"
                          : isPhotoAction
                          ? "bg-amber-500 border-amber-400"
                          : "bg-slate-500 border-slate-400 dark:bg-slate-700 dark:border-slate-500"
                      }`}
                    >
                      {isClosedAction ? (
                        <CheckCircle2 className="w-2.5 h-2.5 text-white" />
                      ) : isPhotoAction ? (
                        <Camera className="w-2.5 h-2.5 text-white" />
                      ) : (
                        <Clock className="w-2.5 h-2.5 text-white" />
                      )}
                    </div>

                    <div className="space-y-0.5 font-sans">
                      <div className="text-xs font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
                        <span>{log.action}</span>
                      </div>

                      <div className="text-[11px] text-slate-600 dark:text-slate-400 flex items-center gap-3 font-mono">
                        <span className="flex items-center gap-1">
                          <User className="w-3 h-3 text-slate-500 dark:text-slate-500" /> {log.user || "Kullanıcı"}
                        </span>
                        <span>•</span>
                        <span>{formatDate(log.timestamp)}</span>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

export default DofTimeline;
