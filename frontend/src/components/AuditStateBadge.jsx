/**
 * AuditStateBadge — Phase 2B — S18
 *
 * Audit'in yaşam döngüsü durumunu görsel olarak gösteren pill component.
 * Backend'deki 5 state machine ile birebir eşleşir:
 *
 *   DRAFT       → gri   "Taslak"
 *   SUBMITTED   → mavi  "Gönderildi"
 *   DOF_OPEN    → sarı  "DÖF Açık"
 *   DOF_CLOSED  → mor   "DÖF Kapalı"
 *   FINAL       → yeşil "Tamamlandı"
 *
 * Backend response audit objesinde `state` alanı gelir; burada olduğu gibi
 * gösterilir. Eski audit'ler için backend fallback olarak `DRAFT` döner.
 *
 * Kullanım:
 *   <AuditStateBadge state={audit.state} size="sm" />
 *   <AuditStateBadge state={audit.state} isCompleted={audit.is_completed} />
 */
import React from "react";
import { cn } from "@/lib/utils";
import { FileEdit, Send, AlertTriangle, Lock, CheckCircle2 } from "lucide-react";

const STATE_CONFIG = {
  DRAFT: {
    label: "Taslak",
    color: "slate",
    icon: FileEdit,
    description: "Denetçi tarafından dolduruluyor; düzenlenebilir.",
  },
  SUBMITTED: {
    label: "Gönderildi",
    color: "blue",
    icon: Send,
    description: "Denetçi tarafından gönderildi; cevaplar kilitli.",
  },
  DOF_OPEN: {
    label: "DÖF Açık",
    color: "amber",
    icon: AlertTriangle,
    description: "Açık DÖF var; takip ediliyor. Nihai rapor verilemez.",
  },
  DOF_CLOSED: {
    label: "DÖF Kapalı",
    color: "purple",
    icon: Lock,
    description: "Tüm DÖF'ler kapatıldı; nihai rapor export edilebilir.",
  },
  FINAL: {
    label: "Tamamlandı",
    color: "emerald",
    icon: CheckCircle2,
    description: "Nihai rapor verildi; düzenlenemez.",
  },
};

const COLOR_CLASSES = {
  slate: {
    bg: "bg-slate-100 dark:bg-slate-800/80",
    text: "text-slate-700 dark:text-slate-300",
    border: "border-slate-200 dark:border-slate-700",
    ring: "ring-slate-300/40",
  },
  blue: {
    bg: "bg-blue-100 dark:bg-blue-500/20",
    text: "text-blue-700 dark:text-blue-300",
    border: "border-blue-200 dark:border-blue-500/40",
    ring: "ring-blue-300/40",
  },
  amber: {
    bg: "bg-amber-100 dark:bg-amber-500/20",
    text: "text-amber-700 dark:text-amber-300",
    border: "border-amber-200 dark:border-amber-500/40",
    ring: "ring-amber-300/40",
  },
  purple: {
    bg: "bg-purple-100 dark:bg-purple-500/20",
    text: "text-purple-700 dark:text-purple-300",
    border: "border-purple-200 dark:border-purple-500/40",
    ring: "ring-purple-300/40",
  },
  emerald: {
    bg: "bg-emerald-100 dark:bg-emerald-500/20",
    text: "text-emerald-700 dark:text-emerald-300",
    border: "border-emerald-200 dark:border-emerald-500/40",
    ring: "ring-emerald-300/40",
  },
};

const SIZE_CLASSES = {
  xs: "text-[10px] px-1.5 py-0.5 gap-0.5",
  sm: "text-[11px] px-2 py-0.5 gap-1",
  md: "text-xs px-2.5 py-1 gap-1.5",
  lg: "text-sm px-3 py-1.5 gap-2",
};

const ICON_SIZE = {
  xs: "w-2.5 h-2.5",
  sm: "w-3 h-3",
  md: "w-3.5 h-3.5",
  lg: "w-4 h-4",
};

export default function AuditStateBadge({
  state,
  isCompleted,
  size = "sm",
  showIcon = true,
  className,
  title,
}) {
  // Bilinmeyen state → fallback (gri, "Bilinmiyor")
  const config = STATE_CONFIG[state] || {
    label: state || "Bilinmiyor",
    color: "slate",
    icon: null,
    description: "Bilinmeyen audit durumu.",
  };
  const colors = COLOR_CLASSES[config.color];
  const Icon = config.icon;

  // Eğer state None/undefined ama is_completed geliyorsa (geriye uyumluluk),
  // FINAL'e çevir ki UI doğru göstersin.
  const effectiveState =
    state ||
    (isCompleted ? "FINAL" : "DRAFT");

  return (
    <span
      className={cn(
        "inline-flex items-center font-bold rounded-md border",
        "font-sans uppercase tracking-wider whitespace-nowrap",
        colors.bg,
        colors.text,
        colors.border,
        SIZE_CLASSES[size],
        className,
      )}
      title={title || config.description}
      data-testid={`audit-state-badge-${effectiveState.toLowerCase()}`}
      data-state={effectiveState}
    >
      {showIcon && Icon && <Icon className={ICON_SIZE[size]} />}
      <span>{config.label}</span>
    </span>
  );
}
