import React, { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { CheckCheck, X, AlertTriangle, ShieldCheck, FileText, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { getCategoryQuestionNumber } from "@/lib/risk";

// Display precedence for the question number shown in the modal:
//   1. ``category_question_no`` — backend-computed "1.3" form
//   2. ``getCategoryQuestionNumber(item)`` — frontend fallback helper
//   3. ``item.question_no`` — legacy numeric value (int)
//   4. ``item.question_id`` — last-resort id fallback.
//
// This avoids the historic bug where the modal silently fell back to
// the raw ``question_no`` integer, hiding the category-based numbering
// from the İSG uzmanı who approves the DÖF.
function resolveDisplayQuestionNo(item) {
  if (!item) return "";
  const fromBackend = item.category_question_no;
  if (typeof fromBackend === "string" && fromBackend.includes(".")) {
    return fromBackend;
  }
  const helper = getCategoryQuestionNumber(item);
  if (helper) {
    return helper;
  }
  if (item.question_no !== undefined && item.question_no !== null) {
    return String(item.question_no);
  }
  return String(item.question_id ?? "");
}

export function DofApproveModal({ item, isOpen, onClose, onConfirm, isSaving }) {
  // ``useState(item?.resolution_note ...)`` initial değeri yalnız mount'ta
  // okunur. Aynı modal instance farklı ``item`` ile yeniden kullanılırsa
  // (örn. birinciyi kapatmadan ikinciyi açmak), input içeriği eski item'dan
  // kalır — UX hatası + yanlış confirmation payload. ``item`` değiştiğinde
  // state'i senkronlamak için ``useEffect`` ile mirror yapıyoruz; ``isOpen``
  // açılışta reset için ana tetikleyici.
  const [resolutionNote, setResolutionNote] = useState("");
  useEffect(() => {
    if (!isOpen) return;
    setResolutionNote(item?.resolution_note || item?.notes || "");
  }, [isOpen, item]);

  if (!isOpen || !item) return null;

  const handleConfirmSubmit = (e) => {
    e.preventDefault();
    if (!resolutionNote.trim()) {
      toast.error("Lütfen düzeltmenin uygunluğunu teyit eden uzman görüşünü / açıklamasını giriniz.");
      return;
    }
    onConfirm(item, resolutionNote.trim());
  };

  return (
    <AnimatePresence>
      {/* Modal scrim (``bg-black/80``) bilinçli olarak her iki temada sabit —
          modal backdrop contract (görsel katman karartması) repodaki diğer
          shadcn ``DialogOverlay``'le uyumlu. */}
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 font-sans">
        <motion.div
          initial={{ opacity: 0, scale: 0.95, y: 10 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.95, y: 10 }}
          transition={{ type: "spring", stiffness: 300, damping: 25 }}
          className="relative max-w-lg w-full bg-white dark:bg-slate-950/95 border border-emerald-500/30 rounded-card overflow-hidden shadow-2xl flex flex-col p-6 space-y-5"
        >
          {/* HEADER */}
          <div className="flex items-start justify-between border-b border-slate-200 dark:border-white/10 pb-4">
            <div className="flex items-center gap-3">
              <div className="p-2.5 rounded-card bg-emerald-50 text-emerald-700 border border-emerald-300 dark:bg-emerald-500/20 dark:text-emerald-400 dark:border-emerald-500/30">
                <ShieldCheck className="w-6 h-6" />
              </div>
              <div>
                <h3 className="text-lg font-extrabold text-slate-900 dark:text-white tracking-tight font-sans">
                  DÖF Kapatma ve Aksiyon Onayı
                </h3>
                <p className="text-xs text-slate-600 dark:text-slate-400 font-sans mt-0.5">
                  İSG Uzmanı Değerlendirmesi ve Kapanış Onayı
                </p>
              </div>
            </div>
            <button
              type="button"
              onClick={onClose}
              disabled={isSaving}
              className="p-1.5 rounded-card bg-slate-100 text-slate-600 hover:bg-slate-200 hover:text-slate-900 dark:bg-slate-900 dark:text-slate-400 dark:hover:text-white transition-colors cursor-pointer"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* DESCRIPTION */}
          <div className="bg-slate-50 border border-slate-200 dark:bg-slate-900/80 dark:border-white/5 p-4 rounded-card space-y-2 text-xs font-sans">
            <p className="text-slate-700 dark:text-slate-300 leading-relaxed font-medium">
              Bu DÖF aksiyonunu kalıcı olarak <strong className="text-emerald-700 dark:text-emerald-400">KAPATILDI</strong> durumuna getirmek üzeresiniz. Lütfen yapılan düzeltmenin uygunluğunu teyit eden uzman görüşünüzü giriniz.
            </p>
            <div className="text-[11px] text-slate-600 dark:text-slate-400 pt-1 border-t border-slate-200 dark:border-white/5 flex items-center justify-between font-mono">
              <span>Restoran: <strong className="text-slate-900 dark:text-white">{item.restaurant_name}</strong></span>
              <span>Soru #{resolveDisplayQuestionNo(item)}</span>
            </div>
          </div>

          {/* EXPERT RESOLUTION NOTE FORM */}
          <form onSubmit={handleConfirmSubmit} className="space-y-4">
            <div className="space-y-1.5">
              <label htmlFor="expert-note" className="text-xs font-bold text-emerald-700 dark:text-emerald-400 font-sans uppercase tracking-wider flex items-center gap-1.5">
                <FileText className="w-3.5 h-3.5" /> UZMAN GÖRÜŞÜ / SAHA GERİ BİLDİRİMİ *
              </label>
              <textarea
                id="expert-note"
                rows={3}
                required
                placeholder="Örn: Saha düzeltme kanıt fotoğrafı ve fiziksel önlemler yerinde incelendi. Düzeltici faaliyet mevzuata uygundur."
                value={resolutionNote}
                onChange={(e) => setResolutionNote(e.target.value)}
                disabled={isSaving}
                className="w-full bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 text-xs text-slate-900 dark:text-slate-100 p-3.5 rounded-card placeholder:text-slate-400 dark:placeholder:text-slate-500 focus:outline-none focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/20 font-sans leading-relaxed"
              />
            </div>

            {/* ACTION BUTTONS */}
            <div className="flex items-center justify-end gap-3 pt-2">
              <button
                type="button"
                onClick={onClose}
                disabled={isSaving}
                className="px-4 py-2.5 rounded-card text-xs font-sans font-semibold bg-slate-100 border border-slate-300 text-slate-700 hover:bg-slate-200 hover:text-slate-900 dark:bg-slate-900 dark:border-slate-700 dark:text-slate-300 dark:hover:text-white transition-all active:scale-95 cursor-pointer"
              >
                İptal
              </button>
              <button
                type="submit"
                disabled={isSaving}
                className="px-5 py-2.5 rounded-card text-xs font-sans font-bold bg-risk-compliant hover:bg-risk-compliant-2 text-white transition-all active:scale-95 flex items-center gap-2 cursor-pointer"
              >
                {isSaving ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin text-white" />
                    <span>Onaylanıyor…</span>
                  </>
                ) : (
                  <>
                    <CheckCheck className="w-4 h-4" />
                    <span>Onayla ve DÖF'ü Kapat</span>
                  </>
                )}
              </button>
            </div>
          </form>
        </motion.div>
      </div>
    </AnimatePresence>
  );
}

export default DofApproveModal;
