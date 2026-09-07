import React, { useState, useEffect } from "react";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Textarea } from "@/components/ui/textarea";
import { AlertTriangle } from "lucide-react";

/**
 * Tutarlı Onay Mekanizması (S19).
 *
 * Tek satırlık kullanım:
 *   <ConfirmDestructive
 *     open={deleteId !== null}
 *     onOpenChange={(o) => !o && setDeleteId(null)}
 *     title="Denetim silinecek"
 *     description="Bu denetim kaydını silmek istediğinizden emin misiniz?"
 *     action="Sil"
 *     onConfirm={handleDelete}
 *     reasonRequired={false}
 *   />
 *
 * Özellikler:
 *   * ``action`` kırmızı buton (Vercel/Linear aesthetic)
 *   * ``reasonRequired`` true ise kullanıcı en az 20 karakter sebep yazmalı
 *   * İptal veya X tıklanınca ``onOpenChange(false)`` çağrılır
 *   * Onaylanınca ``onConfirm(reason)`` çağrılır, dialog kapanır
 *   * Sebep audit_log'a yazılır (caller'ın sorumluluğu — backend'e göndermeli)
 *
 * Tema uyumu (U4 — Phase 2B):
 *   * Tüm renkler design token üzerinden (bg-surface-card, text-ink-primary, vs.)
 *   * Light/dark mode otomatik uyumlu (önceki sürüm hardcoded slate-900 idi)
 *   * Master prompt uyumlu: NO glassmorphism, NO backdrop-blur, NO glow
 */
export default function ConfirmDestructive({
  open,
  onOpenChange,
  title = "Bu işlem geri alınamaz",
  description = "",
  itemName = "",
  action = "Sil",
  actionVerb = "silmek", // "silmek", "kapatmak", "değiştirmek" vs.
  reasonRequired = false,
  reasonMinLength = 20,
  reasonPlaceholder = "Bu işlemi neden yapıyorsunuz? (en az N karakter)",
  destructive = true,
  onConfirm,
}) {
  const [reason, setReason] = useState("");
  const [error, setError] = useState("");

  // Dialog kapandığında state'i temizle
  useEffect(() => {
    if (!open) {
      setReason("");
      setError("");
    }
  }, [open]);

  const handleConfirm = (e) => {
    e?.preventDefault?.();
    if (reasonRequired) {
      const trimmed = (reason || "").trim();
      if (trimmed.length < reasonMinLength) {
        setError(`Sebep zorunlu (en az ${reasonMinLength} karakter).`);
        return;
      }
    }
    setError("");
    onConfirm?.((reason || "").trim());
  };

  // Tasarım token'ları — hem light hem dark mode'da otomatik uyumlu
  // (U4 öncesi hardcoded bg-slate-900 / text-white idi — light modda karanlık
  // görünüyordu, özellikle HAYIR→EVET popup'ı)
  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent className="bg-surface-card border-border-default text-ink-primary font-sans max-w-md">
        <AlertDialogHeader>
          <div className="flex items-start gap-3">
            <div
              className={`mt-0.5 w-10 h-10 rounded-full flex items-center justify-center shrink-0 ${
                destructive
                  ? "bg-risk-critical-bg text-risk-critical"
                  : "bg-risk-moderate-bg text-risk-moderate"
              }`}
            >
              <AlertTriangle className="w-5 h-5" />
            </div>
            <div className="flex-1 min-w-0">
              <AlertDialogTitle className="text-ink-primary text-base">
                {title}
              </AlertDialogTitle>
              {description && (
                <AlertDialogDescription className="text-ink-secondary text-xs mt-1.5">
                  {description}
                </AlertDialogDescription>
              )}
              {itemName && (
                <div className="mt-2 px-3 py-2 rounded-control bg-surface-card-2 border border-border-default text-xs text-ink-primary font-mono break-all">
                  {itemName}
                </div>
              )}
            </div>
          </div>
        </AlertDialogHeader>

        {/* Sebep notu (opsiyonel/required) */}
        {(reasonRequired || reasonPlaceholder) && (
          <div className="space-y-1.5 pt-1">
            <label className="text-[10px] font-bold text-ink-secondary uppercase tracking-wider flex items-center justify-between">
              <span>
                Sebep {reasonRequired && <span className="text-risk-critical">*</span>}
              </span>
              {reasonRequired && (
                <span className="font-mono text-ink-tertiary">
                  {(reason || "").trim().length} / {reasonMinLength}
                </span>
              )}
            </label>
            <Textarea
              rows={3}
              value={reason}
              onChange={(e) => {
                setReason(e.target.value);
                if (error) setError("");
              }}
              placeholder={reasonPlaceholder}
              className="bg-surface-card-2 border-border-default text-ink-primary text-xs placeholder:text-ink-tertiary focus:border-risk-critical focus:outline-none focus:ring-2 focus:ring-risk-critical/20"
            />
            {error && (
              <p className="text-[11px] text-risk-critical font-bold">{error}</p>
            )}
          </div>
        )}

        <AlertDialogFooter className="gap-2">
          <AlertDialogCancel className="bg-surface-card-2 text-ink-secondary border-border-default hover:bg-surface-page-2 hover:text-ink-primary">
            İptal
          </AlertDialogCancel>
          <AlertDialogAction
            onClick={handleConfirm}
            className={
              destructive
                ? "bg-risk-critical hover:bg-risk-critical-2 text-white font-bold"
                : "bg-risk-moderate hover:bg-risk-moderate-2 text-white font-bold"
            }
          >
            {action}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
