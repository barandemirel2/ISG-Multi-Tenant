import React, { useEffect, useState } from "react";
import { Clock, AlertTriangle, CheckCircle2, ShieldAlert, Zap } from "lucide-react";

export function calculateTimeRemaining(dueDateStr, status, created_at, resolved_at) {
  if (status === "KAPATILDI") {
    let durationText = "Tamamlandı";
    if (created_at && resolved_at) {
      const c = new Date(created_at).getTime();
      const r = new Date(resolved_at).getTime();
      const diffMs = Math.max(0, r - c);
      const days = Math.floor(diffMs / (1000 * 60 * 60 * 24));
      const hours = Math.floor((diffMs % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
      durationText = days > 0 ? `Çözüm Süresi: ${days} Gün ${hours} Saat` : `Çözüm Süresi: ${hours} Saat`;
    }
    return { isClosed: true, durationText };
  }

  // "Sürekli" termin string'i: deadline yok, müdahale anında olmalı.
  // Backend ``None`` döndürür; frontend bu durumu kırmızı pulse ile gösterir.
  if (!dueDateStr) {
    return { isContinuous: true, text: "SÜREKLİ — Anında Müdahale" };
  }

  const due = new Date(dueDateStr).getTime();
  const now = Date.now();
  const diffMs = due - now;

  if (diffMs <= 0) {
    const overdueMs = Math.abs(diffMs);
    const days = Math.floor(overdueMs / (1000 * 60 * 60 * 24));
    const hours = Math.floor((overdueMs % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
    return {
      isOverdue: true,
      days,
      hours,
      text: days > 0 ? `SÜRESİ GEÇTİ: ${days} Gün Gecikti` : `SÜRESİ GEÇTİ: ${hours} Saat Gecikti`,
    };
  }

  const days = Math.floor(diffMs / (1000 * 60 * 60 * 24));
  const hours = Math.floor((diffMs % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));

  if (days <= 3) {
    return {
      isCritical: true,
      days,
      hours,
      text: `Kritik Süre: ${days} Gün ${hours} Saat`,
    };
  }

  return {
    isNormal: true,
    days,
    hours,
    text: `Termine Kalan: ${days} Gün ${hours} Saat`,
  };
}

export function DeadlineCountdown({ dueDate, status, createdAt, resolvedAt, className = "" }) {
  const [timeState, setTimeState] = useState(() =>
    calculateTimeRemaining(dueDate, status, createdAt, resolvedAt)
  );

  useEffect(() => {
    const interval = setInterval(() => {
      setTimeState(calculateTimeRemaining(dueDate, status, createdAt, resolvedAt));
    }, 60000); // refresh every minute

    return () => clearInterval(interval);
  }, [dueDate, status, createdAt, resolvedAt]);

  if (timeState.isClosed) {
    return (
      <span
        className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-card text-xs font-sans font-extrabold bg-emerald-100 text-emerald-800 border border-emerald-300 dark:bg-emerald-500/15 dark:text-emerald-400 dark:border-emerald-500/30 font-sans ${className}`}
      >
        <CheckCircle2 className="w-3.5 h-3.5 text-emerald-700 dark:text-emerald-400" />
        <span>{timeState.durationText}</span>
      </span>
    );
  }

  // "Sürekli" termin — anında müdahale gereken bulgular için özel gösterim.
  // İSG mevzuatı: bu tür bulgular denetim anında düzeltilmelidir; 90 gün
  // gibi yapay deadline atanamaz (eski kod bug'ı).
  if (timeState.isContinuous) {
    return (
      <span
        className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-card text-xs font-sans font-extrabold bg-red-100 text-red-800 border border-red-300 dark:bg-red-500/20 dark:text-red-300 dark:border-red-500/40 dark: animate-pulse font-sans ${className}`}
        data-testid="deadline-continuous"
        title="Bu bulgu için termin yoktur; saha tespit anında düzeltilmelidir."
      >
        <Zap className="w-3.5 h-3.5 text-red-700 dark:text-red-400" />
        <span>{timeState.text}</span>
      </span>
    );
  }

  if (timeState.isOverdue) {
    return (
      <span
        className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-card text-xs font-sans font-extrabold bg-red-100 text-red-800 border border-red-300 dark:bg-red-500/20 dark:text-red-400 dark:border-red-500/40 dark: animate-pulse font-sans ${className}`}
      >
        <ShieldAlert className="w-3.5 h-3.5 text-red-700 dark:text-red-400" />
        <span>{timeState.text}</span>
      </span>
    );
  }

  if (timeState.isCritical) {
    return (
      <span
        className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-card text-xs font-sans font-extrabold bg-amber-100 text-amber-800 border border-amber-300 dark:bg-amber-500/20 dark:text-amber-300 dark:border-amber-500/40 dark: animate-pulse font-sans ${className}`}
      >
        <AlertTriangle className="w-3.5 h-3.5 text-amber-700 dark:text-amber-400" />
        <span>{timeState.text}</span>
      </span>
    );
  }

  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-card text-xs font-sans font-extrabold bg-slate-100 text-slate-700 border border-slate-300 dark:bg-slate-900/80 dark:text-slate-300 dark:border-white/10 font-sans ${className}`}
    >
      <Clock className="w-3.5 h-3.5 text-slate-600 dark:text-slate-400" />
      <span>{timeState.text}</span>
    </span>
  );
}

export default DeadlineCountdown;
