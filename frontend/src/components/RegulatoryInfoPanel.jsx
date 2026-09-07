/**
 * RegulatoryInfoPanel — 84 soru için mevzuat + yaptırım paneli.
 *
 * AuditFormPage (HAYIR expansion) ve DofPage (DÖF kartı) tarafından kullanılır.
 *
 * Data source: frontend/src/data/question_regulatory_map.json
 *   Schema: { questions: { [id]: { topic, primary, secondary, ipc, ipc_short,
 *                                criminal, criminal_short, civil, consequence, severity } } }
 *
 * Presentation Safety:
 *   - Dataset status = "UNVERIFIED" durumunda kesin TL tutarları ve kesin hapis cezası
 *     iddiaları render edilmez; yerine nötr ve yetkili kaynak doğrulama uyarıları gösterilir.
 *   - Hem full hem de compact varyantlarında görünür mevzuat bilgilendirme feragatnamesi yer alır.
 *
 * Master prompt uyumlu: NO glassmorphism, NO backdrop-blur, NO gradient,
 * NO neon glow. Flat risk tokens + rounded-control/card.
 */
import React, { useMemo } from "react";
import { Scale, AlertTriangle, Gavel, FileWarning, ScrollText, Info } from "lucide-react";
import regulatoryData from "@/data/question_regulatory_map.json";

export const DISCLAIMER_TEXT =
  "Mevzuat, idari para cezası ve cezai sorumluluk bilgileri bilgilendirme amaçlıdır. Güncel tutar ve uygulama yetkili/resmî kaynaktan doğrulanmalıdır.";

export const UNVERIFIED_IPC_TEXT =
  "Güncel idari para cezası tutarı resmî kaynaktan doğrulanmalıdır.";

export const UNVERIFIED_CRIMINAL_TEXT =
  "İlgili TCK hükümleri kapsamında cezai sorumluluk doğabilir; kapsam ve yaptırım güncel resmî kaynaktan doğrulanmalıdır.";

export const UNVERIFIED_CRIMINAL_COMPACT_TEXT =
  "İlgili TCK hükümleri kapsamında cezai sorumluluk doğabilir (doğrulanmalı)";

const isDatasetVerified = (regulatoryData?.status || "").toUpperCase() === "VERIFIED";

const SEVERITY_CONFIG = {
  high: {
    label: "YÜKSEK RİSK",
    border: "border-risk-critical-border",
    bg: "bg-risk-critical-bg",
    text: "text-risk-critical",
    icon: AlertTriangle,
    iconClass: "text-risk-critical",
  },
  medium: {
    label: "ORTA RİSK",
    border: "border-risk-moderate-border",
    bg: "bg-risk-moderate-bg",
    text: "text-risk-moderate",
    icon: FileWarning,
    iconClass: "text-risk-moderate",
  },
  low: {
    label: "DÜŞÜK RİSK",
    border: "border-border-default",
    bg: "bg-surface-card-2",
    text: "text-ink-secondary",
    icon: Info,
    iconClass: "text-ink-tertiary",
  },
};

/**
 * @param {object} props
 * @param {number|string} props.questionId - Soru ID (1-84)
 * @param {"compact"|"full"} [props.variant="compact"] - compact = inline panel (DÖF için);
 *                                                      full = detaylı panel (audit form için)
 * @param {boolean} [props.isVerified] - Opsiyonel doğrulama durumu override (varsayılan: dataset status)
 * @param {string} [props.className] - ek class
 */
export function RegulatoryInfoPanel({
  questionId,
  variant = "compact",
  isVerified = undefined,
  className = "",
}) {
  const data = useMemo(() => {
    if (!questionId) return null;
    return regulatoryData.questions?.[String(questionId)] || null;
  }, [questionId]);

  if (!data) {
    return null;
  }

  const verified = isVerified !== undefined ? isVerified : isDatasetVerified;
  const sev = SEVERITY_CONFIG[data.severity] || SEVERITY_CONFIG.low;
  const SevIcon = sev.icon;

  if (variant === "full") {
    // Detaylı versiyon — AuditFormPage HAYIR expansion içinde
    return (
      <div
        className={`rounded-control border ${sev.border} ${sev.bg} p-4 space-y-3 font-sans ${className}`}
        data-testid={`regulatory-panel-${questionId}`}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <SevIcon className={`w-4 h-4 ${sev.iconClass}`} />
            <span className={`text-[10px] font-extrabold ${sev.text} uppercase tracking-wider`}>
              {sev.label}
            </span>
            {!verified && (
              <span
                data-testid="unverified-status-badge"
                className="text-[9px] font-semibold text-ink-tertiary uppercase tracking-wider bg-surface-card px-2 py-0.5 rounded-xs border border-border-default"
              >
                DOĞRULAMA BEKLENİYOR
              </span>
            )}
          </div>
          <Scale className={`w-3.5 h-3.5 ${sev.iconClass} opacity-70`} />
        </div>

        {/* YASAL BİLGİLENDİRME VE DOĞRULAMA UYARISI */}
        <div
          data-testid="regulatory-disclaimer-full"
          className="text-[10px] text-ink-secondary bg-surface-card border border-border-default rounded-control p-2.5 flex items-start gap-2 leading-relaxed"
        >
          <Info className="w-3.5 h-3.5 text-ink-tertiary shrink-0 mt-0.5" />
          <span>{DISCLAIMER_TEXT}</span>
        </div>

        <div className="text-xs font-bold text-ink-primary leading-snug">
          {data.topic}
        </div>

        {/* MEVZUAT */}
        <div className="space-y-1.5">
          <div className="text-[10px] font-extrabold text-ink-secondary uppercase tracking-wider flex items-center gap-1.5">
            <ScrollText className="w-3 h-3" /> MEVZUAT
          </div>
          <div className="text-[11px] text-ink-primary leading-relaxed font-mono bg-surface-card border border-border-default px-2.5 py-1.5 rounded-control">
            {data.primary}
          </div>
          {data.secondary && (
            <div className="text-[10px] text-ink-tertiary leading-relaxed font-mono">
              {data.secondary}
            </div>
          )}
        </div>

        {/* İDARİ PARA CEZASI */}
        {data.ipc_short && (
          <div className="space-y-1">
            <div className="text-[10px] font-extrabold text-ink-secondary uppercase tracking-wider flex items-center gap-1.5">
              <FileWarning className="w-3 h-3" /> İDARİ PARA CEZASI
            </div>
            <div
              data-testid="ipc-content"
              className={`text-[11px] rounded-control px-2.5 py-1.5 border border-border-default bg-surface-card leading-relaxed ${
                verified ? "text-ink-primary font-mono font-bold" : "text-ink-secondary font-sans font-medium italic"
              }`}
            >
              {verified ? data.ipc_short : UNVERIFIED_IPC_TEXT}
            </div>
          </div>
        )}

        {/* CEZAİ SORUMLULUK */}
        {data.criminal_short && (
          <div className="space-y-1">
            <div className="text-[10px] font-extrabold text-ink-secondary uppercase tracking-wider flex items-center gap-1.5">
              <Gavel className="w-3 h-3" /> CEZAİ SORUMLULUK
            </div>
            <div
              data-testid="criminal-content"
              className={`text-[11px] font-medium leading-relaxed ${sev.text}`}
            >
              {verified ? data.criminal_short : UNVERIFIED_CRIMINAL_TEXT}
            </div>
          </div>
        )}

        {/* HUKUKİ SORUMLULUK */}
        {data.civil && (
          <div className="space-y-1">
            <div className="text-[10px] font-extrabold text-ink-secondary uppercase tracking-wider">
              HUKUKİ SORUMLULUK
            </div>
            <div
              data-testid="civil-content"
              className="text-[10px] text-ink-secondary leading-relaxed"
            >
              {verified
                ? data.civil
                : `${data.civil} (Hukuki sorumluluk ve tazminat kapsamı somut olaya göre yetkili kaynaktan doğrulanmalıdır)`}
            </div>
          </div>
        )}

        {/* SONUÇ (consequence) — Sadece doğrulanmış veride gösterilir */}
        {verified && data.consequence && (
          <div className="pt-2 border-t border-border-default">
            <div className="text-[10px] text-ink-tertiary leading-relaxed italic">
              {data.consequence}
            </div>
          </div>
        )}
      </div>
    );
  }

  // COMPACT — DÖF kartı için
  return (
    <div
      className={`rounded-control border ${sev.border} ${sev.bg} p-2.5 space-y-2 font-sans ${className}`}
      data-testid={`regulatory-compact-${questionId}`}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1.5">
          <SevIcon className={`w-3 h-3 ${sev.iconClass}`} />
          <span className={`text-[9px] font-extrabold ${sev.text} uppercase tracking-wider`}>
            {sev.label}
          </span>
        </div>
        {!verified && (
          <span
            data-testid="unverified-status-badge-compact"
            className="text-[8px] font-semibold text-ink-tertiary uppercase tracking-wider bg-surface-card px-1.5 py-0.5 rounded-xs border border-border-default"
          >
            DOĞRULAMA BEKLENİYOR
          </span>
        )}
      </div>

      <div className="text-[10px] text-ink-primary font-mono leading-snug">
        {data.primary}
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-2 gap-y-1.5 text-[10px]">
        {data.ipc_short && (
          <div>
            <div className="text-ink-tertiary font-bold uppercase tracking-wider text-[8.5px]">İPC</div>
            <div
              data-testid="ipc-content-compact"
              className={`text-[9.5px] leading-tight ${
                verified ? "text-ink-primary font-mono font-bold" : "text-ink-secondary italic"
              }`}
            >
              {verified ? data.ipc_short : UNVERIFIED_IPC_TEXT}
            </div>
          </div>
        )}
        {data.criminal_short && (
          <div>
            <div className="text-ink-tertiary font-bold uppercase tracking-wider text-[8.5px]">Cezai</div>
            <div
              data-testid="criminal-content-compact"
              className={`text-[9.5px] font-medium leading-tight ${sev.text}`}
            >
              {verified ? data.criminal_short : UNVERIFIED_CRIMINAL_COMPACT_TEXT}
            </div>
          </div>
        )}
      </div>

      {/* YASAL BİLGİLENDİRME VE DOĞRULAMA UYARISI */}
      <div
        data-testid="regulatory-disclaimer-compact"
        className="text-[8.5px] text-ink-tertiary leading-relaxed pt-1.5 border-t border-border-default flex items-start gap-1"
      >
        <Info className="w-2.5 h-2.5 shrink-0 mt-0.5" />
        <span>{DISCLAIMER_TEXT}</span>
      </div>
    </div>
  );
}

export default RegulatoryInfoPanel;
