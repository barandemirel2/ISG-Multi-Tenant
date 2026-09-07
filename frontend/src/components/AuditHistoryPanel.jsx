/**
 * AuditHistoryPanel — Phase 2B — S20
 *
 * Audit'in tüm değişiklik geçmişini kronolojik olarak gösterir.
 * İki veri kaynağını birleştirir:
 *
 *   1. ``audit.state_history`` — S18 state machine geçişleri (DRAFT → SUBMITTED → ...)
 *   2. ``GET /api/audits/{id}/audit-log`` — S20 audit_log koleksiyonu
 *      (create, submit, update, export, delete, ...)
 *
 * Kullanım:
 *   <AuditHistoryPanel audit={audit} auditId={id} />
 *
 * "İbraz" use-case'i için kritik — savcılık/mahkeme talep ettiğinde
 * "bu denetimde kim ne yaptı?" sorusunu yanıtlar.
 */
import React, { useEffect, useState } from "react";
import { History, ChevronDown, ChevronUp, Download, ShieldCheck, AlertCircle } from "lucide-react";
import api from "@/lib/api";
import { cn } from "@/lib/utils";

const ACTION_LABELS = {
  create: { label: "Denetim Oluşturuldu", icon: ShieldCheck, color: "emerald" },
  submit: { label: "Denetim Gönderildi", icon: ShieldCheck, color: "blue" },
  answer_update: { label: "Cevaplar Güncellendi", icon: History, color: "slate" },
  meta_update: { label: "Metadata Güncellendi", icon: History, color: "slate" },
  declaration_update: { label: "İş Yeri Beyanı Güncellendi", icon: History, color: "slate" },
  dof_update: { label: "DÖF Güncellendi", icon: History, color: "amber" },
  dof_open: { label: "DÖF Açıldı", icon: History, color: "amber" },
  dof_close: { label: "DÖF Kapatıldı", icon: ShieldCheck, color: "emerald" },
  photo_upload: { label: "Fotoğraf Yüklendi", icon: History, color: "slate" },
  photo_delete: { label: "Fotoğraf Silindi", icon: History, color: "red" },
  export_pdf: { label: "PDF Rapor İndirildi", icon: Download, color: "blue" },
  export_excel: { label: "Excel Rapor İndirildi", icon: Download, color: "blue" },
  export_finalize: { label: "Nihai Rapor Verildi", icon: ShieldCheck, color: "emerald" },
  delete: { label: "Denetim Silindi", icon: AlertCircle, color: "red" },
  soft_delete: { label: "Denetim Arşivlendi (soft-delete)", icon: AlertCircle, color: "amber" },
  archive: { label: "Otomatik Arşivleme (6 yıl)", icon: History, color: "slate" },
  login: { label: "Giriş Yapıldı", icon: History, color: "slate" },
  logout: { label: "Çıkış Yapıldı", icon: History, color: "slate" },
};

const COLOR_CLASSES = {
  emerald: { bg: "bg-emerald-100 dark:bg-emerald-500/20", text: "text-emerald-700 dark:text-emerald-400" },
  blue: { bg: "bg-blue-100 dark:bg-blue-500/20", text: "text-blue-700 dark:text-blue-400" },
  amber: { bg: "bg-amber-100 dark:bg-amber-500/20", text: "text-amber-700 dark:text-amber-400" },
  red: { bg: "bg-red-100 dark:bg-red-500/20", text: "text-red-700 dark:text-red-400" },
  slate: { bg: "bg-slate-100 dark:bg-slate-800/80", text: "text-slate-700 dark:text-slate-300" },
};

export default function AuditHistoryPanel({ audit }) {
  const [expanded, setExpanded] = useState(false);
  const [logEntries, setLogEntries] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Audit yüklendiğinde activity log'u getir
  useEffect(() => {
    if (!audit?.id || !expanded) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    api.get(`/audits/${audit.id}/audit-log?limit=50`)
      .then(({ data }) => {
        if (cancelled) return;
        setLogEntries(data?.items || []);
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err.response?.data?.detail || err.message);
      })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [audit?.id, expanded]);

  // state_history + audit_log birleştir (state_history önce, sonra log)
  const timeline = React.useMemo(() => {
    const items = [];
    // S18 state history
    (audit?.state_history || []).forEach((h) => {
      items.push({
        type: "state",
        timestamp: h.at,
        from: h.from,
        to: h.to,
        actor: h.by,
        reason: h.reason,
      });
    });
    // S20 activity log
    logEntries.forEach((l) => {
      items.push({
        type: "action",
        timestamp: l.timestamp,
        action: l.action,
        actor: l.user_name,
        before: l.before,
        after: l.after,
      });
    });
    // Tarihe göre azalan sırada
    items.sort((a, b) => (b.timestamp || "").localeCompare(a.timestamp || ""));
    return items;
  }, [audit?.state_history, logEntries]);

  const totalCount = timeline.length;

  return (
    <div className="rounded-card surface-card shadow-sm dark:shadow-md font-sans" data-testid="audit-history-panel">
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        data-testid="audit-history-toggle"
        className="w-full flex items-center justify-between gap-3 p-4 hover:bg-slate-50 dark:hover:bg-slate-900/40 transition-colors rounded-card"
      >
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-card bg-slate-100 dark:bg-slate-800 flex items-center justify-center">
            <History className="w-4 h-4 text-slate-600 dark:text-slate-400" />
          </div>
          <div className="text-left">
            <h3 className="text-sm font-extrabold text-slate-900 dark:text-white tracking-tight">
              Geçmiş (Activity Log)
            </h3>
            <p className="text-[11px] text-slate-500 dark:text-slate-400 mt-0.5">
              {totalCount > 0
                ? `${totalCount} kayıt — kim, ne zaman, ne yaptı`
                : "Henüz kayıt yok"}
            </p>
          </div>
        </div>
        {expanded ? <ChevronUp className="w-4 h-4 text-slate-500" /> : <ChevronDown className="w-4 h-4 text-slate-500" />}
      </button>

      {expanded && (
        <div className="border-t border-slate-200 dark:border-white/10 p-4">
          {loading && (
            <div className="text-center text-xs text-slate-500 dark:text-slate-400 py-4">
              Yükleniyor…
            </div>
          )}
          {error && (
            <div className="flex items-start gap-2 p-3 border border-amber-200 dark:border-amber-500/30 bg-amber-50 dark:bg-amber-500/10 rounded-card text-xs text-amber-800 dark:text-amber-300">
              <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
              <div>
                <strong>Log yüklenemedi.</strong> State machine geçişleri (S18)
                aşağıda görünür; S20 activity log henüz mevcut olmayabilir.
                <div className="font-mono text-[10px] mt-1 opacity-70">{error}</div>
              </div>
            </div>
          )}
          {!loading && !error && timeline.length === 0 && (
            <div className="text-center text-xs text-slate-500 dark:text-slate-400 py-4">
              Henüz hiçbir değişiklik kaydı yok.
            </div>
          )}
          {!loading && timeline.length > 0 && (
            <ol className="relative space-y-3 pl-6 border-l-2 border-slate-200 dark:border-white/10">
              {timeline.map((item, idx) => (
                <TimelineEntry key={`${item.type}-${item.timestamp}-${idx}`} item={item} />
              ))}
            </ol>
          )}
        </div>
      )}
    </div>
  );
}

function TimelineEntry({ item }) {
  if (item.type === "state") {
    return (
      <li className="relative">
        <span className="absolute -left-[31px] top-1 w-4 h-4 rounded-full bg-slate-300 dark:bg-slate-700 border-2 border-white dark:border-slate-950" />
        <div className="text-xs space-y-0.5">
          <div className="flex items-center gap-1.5">
            <span className="text-slate-500 dark:text-slate-400 font-mono text-[10px]">
              {formatTimestamp(item.timestamp)}
            </span>
            <span className="text-slate-400 dark:text-slate-500">·</span>
            <span className="text-slate-600 dark:text-slate-400 text-[11px]">
              {item.actor || "system"}
            </span>
          </div>
          <div className="font-bold text-slate-800 dark:text-slate-200">
            Durum: <span className="text-slate-500">{item.from || "—"}</span>
            {" → "}
            <span className="text-emerald-600 dark:text-emerald-400">{item.to}</span>
          </div>
          {item.reason && (
            <div className="text-[11px] text-slate-500 dark:text-slate-400 italic">
              {item.reason}
            </div>
          )}
        </div>
      </li>
    );
  }

  // action type
  const config = ACTION_LABELS[item.action] || { label: item.action, icon: History, color: "slate" };
  const Icon = config.icon;
  const colors = COLOR_CLASSES[config.color] || COLOR_CLASSES.slate;

  return (
    <li className="relative">
      <span className={cn(
        "absolute -left-[31px] top-1 w-4 h-4 rounded-full border-2 border-white dark:border-slate-950 flex items-center justify-center",
        colors.bg,
      )}>
        <Icon className={cn("w-2.5 h-2.5", colors.text)} />
      </span>
      <div className="text-xs space-y-0.5">
        <div className="flex items-center gap-1.5">
          <span className="text-slate-500 dark:text-slate-400 font-mono text-[10px]">
            {formatTimestamp(item.timestamp)}
          </span>
          <span className="text-slate-400 dark:text-slate-500">·</span>
          <span className="text-slate-600 dark:text-slate-400 text-[11px]">
            {item.actor}
          </span>
        </div>
        <div className={cn("font-bold", colors.text)}>
          {config.label}
        </div>
        {(item.before || item.after) && (
          <div className="text-[10px] font-mono text-slate-500 dark:text-slate-400 space-y-0.5 mt-1">
            {item.before && <div>önce: {JSON.stringify(item.before)}</div>}
            {item.after && <div>sonra: {JSON.stringify(item.after)}</div>}
          </div>
        )}
      </div>
    </li>
  );
}

function formatTimestamp(iso) {
  if (!iso) return "—";
  try {
    const d = new Date(iso);
    return d.toLocaleString("tr-TR", {
      year: "numeric", month: "2-digit", day: "2-digit",
      hour: "2-digit", minute: "2-digit",
    });
  } catch {
    return iso;
  }
}
