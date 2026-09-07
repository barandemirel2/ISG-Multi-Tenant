import React, { useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { X, Download, Trash2, Calendar, User } from "lucide-react";
import { BACKEND_ORIGIN } from "@/lib/api";
import { PHOTO } from "@/constants/testIds";

export function PhotoLightbox({ photo, onClose, onDelete, canDelete = true }) {
  // Escape → close.
  useEffect(() => {
    if (!photo) return undefined;
    const handler = (e) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [photo, onClose]);

  const fullUrl = photo.url.startsWith("http") ? photo.url : `${BACKEND_ORIGIN}${photo.url}`;

  // backdrop click → close (overlay only; toolbar/image clicks stopPropagation).
  const handleOverlayMouseDown = useCallback(
    (e) => {
      if (e.target === e.currentTarget) onClose();
    },
    [onClose]
  );

  // image click → close (per task spec).
  const handleImageClick = useCallback(() => {
    onClose();
  }, [onClose]);

  if (!photo) return null;

  return (
    <AnimatePresence>
      <motion.div
        key="overlay"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        transition={{ duration: 0.18 }}
        onMouseDown={handleOverlayMouseDown}
        className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6 bg-slate-950/80 font-sans"
        role="dialog"
        aria-modal="true"
        aria-label="Fotoğraf önizleme"
        data-testid={PHOTO.lightboxOverlay}
      >
        {/* VIEWER CARD: flex column with viewport-bounded geometry.
            max-h-[min(90vh,90dvh)] ensures that landscape/portrait/tall/wide
            images never push the toolbar off-screen. */}
        <motion.div
          key="viewer"
          initial={{ opacity: 0, scale: 0.96 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={{ opacity: 0, scale: 0.96 }}
          transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
          className="relative flex flex-col w-full max-w-5xl max-h-[min(90vh,90dvh)] bg-white border border-slate-200 rounded-card shadow-2xl overflow-hidden dark:bg-slate-950/95 dark:border-white/10"
          onMouseDown={(e) => e.stopPropagation()}
          data-testid={PHOTO.lightboxViewer}
        >
          {/* HEADER / TOOLBAR — fixed-height (flex-none), never scrolls away. */}
          <div
            data-testid={PHOTO.lightboxToolbar}
            className="flex-none flex items-center justify-between gap-3 px-4 sm:px-5 py-3 border-b border-slate-200 bg-slate-50 dark:border-white/10 dark:bg-slate-900/70"
          >
            <div className="flex items-center gap-3 min-w-0">
              <span
                data-testid={PHOTO.lightboxBadge}
                className={`px-2.5 py-0.5 rounded-lg text-[11px] font-bold uppercase tracking-wider border ${
                  photo.type === "resolution"
                    ? "bg-emerald-100 text-emerald-800 border-emerald-300 dark:bg-emerald-500/15 dark:text-emerald-300 dark:border-emerald-500/30"
                    : "bg-red-100 text-red-800 border-red-300 dark:bg-red-500/15 dark:text-red-300 dark:border-red-500/30"
                }`}
              >
                {photo.type === "resolution" ? "Çözüm Kanıtı" : "Tespit Fotoğrafı"}
              </span>
              {photo.created_at && (
                <span className="hidden sm:inline-flex items-center gap-1 text-xs text-slate-600 dark:text-slate-400 font-mono truncate">
                  <Calendar className="w-3.5 h-3.5 shrink-0" />
                  {new Date(photo.created_at).toLocaleString("tr-TR")}
                </span>
              )}
            </div>

            <div className="flex items-center gap-2 shrink-0">
              <a
                href={fullUrl}
                download
                target="_blank"
                rel="noreferrer"
                onClick={(e) => e.stopPropagation()}
                className="p-2 rounded-card bg-slate-100 hover:bg-slate-200 text-slate-700 hover:text-slate-900 border border-slate-200 transition-colors cursor-pointer dark:bg-slate-800 dark:hover:bg-slate-700 dark:text-slate-300 dark:hover:text-white dark:border-white/10"
                title="Resmi İndir"
                aria-label="Resmi İndir"
                data-testid={PHOTO.lightboxDownload}
              >
                <Download className="w-4 h-4" />
              </a>

              {canDelete && onDelete && (
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    onDelete(photo);
                  }}
                  className="p-2 rounded-card bg-red-50 hover:bg-red-100 text-red-700 border border-red-200 transition-colors cursor-pointer dark:bg-red-500/10 dark:hover:bg-red-500/20 dark:text-red-300 dark:border-red-500/30"
                  title="Fotoğrafı Sil"
                  aria-label="Fotoğrafı Sil"
                  data-testid={PHOTO.lightboxDelete}
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              )}

              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  onClose();
                }}
                className="p-2 rounded-card bg-slate-100 hover:bg-slate-200 text-slate-700 hover:text-slate-900 border border-slate-200 transition-colors cursor-pointer dark:bg-slate-800 dark:hover:bg-slate-700 dark:text-slate-300 dark:hover:text-white dark:border-white/10"
                title="Kapat"
                aria-label="Kapat"
                data-testid={PHOTO.lightboxClose}
              >
                <X className="w-5 h-5" />
              </button>
            </div>
          </div>

          {/* IMAGE AREA — flex: 1, min-h: 0 (overflow-bounded), object-contain.
              The image is constrained to viewport independently of its native
              aspect ratio, so toolbar/X never leaves the viewport. */}
          <div
            data-testid={PHOTO.lightboxImageWrap}
            className="flex-1 min-h-0 overflow-auto p-3 sm:p-4 flex items-center justify-center bg-slate-100 dark:bg-black/70"
          >
            <img
              src={fullUrl}
              alt="Denetim Fotoğrafı"
              onClick={handleImageClick}
              data-testid={PHOTO.lightboxImage}
              className="block max-w-full max-h-full w-auto h-auto rounded-lg object-contain select-none cursor-zoom-out"
            />
          </div>

          {/* FOOTER — fixed-height strip (flex-none) with helpful hint. */}
          <div
            data-testid={PHOTO.lightboxFooter}
            className="flex-none px-4 sm:px-5 py-2 border-t border-slate-200 bg-slate-50 text-[11px] text-slate-500 flex items-center justify-between dark:border-white/10 dark:bg-slate-900/70 dark:text-slate-400"
          >
            <span className="flex items-center gap-1.5 truncate">
              <User className="w-3.5 h-3.5 shrink-0" />
              <span className="truncate">
                {photo.created_by ? `ID: ${photo.created_by}` : "Denetim Fotoğrafı"}
              </span>
            </span>
            <span className="hidden sm:inline font-mono">
              ESC veya boşluğa tıkla → kapat
            </span>
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}

export default PhotoLightbox;
