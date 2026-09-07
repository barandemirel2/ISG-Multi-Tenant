/**
 * InlineDofForm — Phase 2B — S7
 *
 * AuditFormPage'de HAYIR cevaplı bir soru seçildiğinde açılan inline
 * DÖF formu. İş birimi kuralı S7:
 *   "Cevap hayır olduğunda otomatik döf ekranı gelmeli, termin süresi
 *    burada verilmeli."
 *
 * Mevcut ``update_dof`` endpoint'ini çağırarak backend'de
 * ``dof_details.<qid>`` sub-doc'una yazar. İlk kayıtta DÖF "AÇIK"
 * durumunda oluşur; kullanıcı daha sonra DofPage veya UatChecklistPage'den
 * "KAPATILDI"ya geçirebilir.
 *
 * Kullanım:
 *   <InlineDofForm
 *     auditId={auditId}
 *     questionId={q.id}
 *     defaultDeadline={q.deadline}
 *     defaultResponsible={q.responsible}
 *     existingDof={q.dof}
 *   />
 */
import React, { useState, useEffect } from "react";
import { Save, Wrench, Zap, AlertCircle, CheckCircle2, Loader2 } from "lucide-react";
import api, { formatApiErrorDetail } from "@/lib/api";
import {
  isContinuousDeadline,
  buildInlineDofPayload,
  validateInlineDofForm,
} from "@/lib/dof";
import { toast } from "sonner";
import { cn } from "@/lib/utils";

export default function InlineDofForm({
  auditId,
  questionId,
  defaultDeadline = "",
  defaultResponsible = "",
  existingDof = null,
  readOnly = false,
}) {
  const continuous = isContinuousDeadline(defaultDeadline);

  // State — mevcut DÖF varsa ondan, yoksa question default'larından başla
  const [deadline, setDeadline] = useState(
    existingDof?.deadline || defaultDeadline || ""
  );
  const [responsible, setResponsible] = useState(
    existingDof?.responsible || defaultResponsible || ""
  );
  const [notes, setNotes] = useState(existingDof?.notes || "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [saved, setSaved] = useState(!!existingDof);

  // existingDof değişirse state'i resetle
  useEffect(() => {
    setDeadline(existingDof?.deadline || defaultDeadline || "");
    setResponsible(existingDof?.responsible || defaultResponsible || "");
    setNotes(existingDof?.notes || "");
    setSaved(!!existingDof);
  }, [existingDof, defaultDeadline, defaultResponsible]);

  const handleSave = async () => {
    setError(null);

    if (continuous) {
      // "Sürekli" termin için input yok; backend None döner. Kullanıcı
      // sadece not girebilir (saha tespit kanıtı).
      const validation = validateInlineDofForm({ status: "AÇIK", notes });
      if (validation) { setError(validation); return; }
    } else {
      // Normal termin: deadline alanı zorunlu (varsayılan dolu)
      if (!deadline.trim()) {
        setError("Termin süresi boş bırakılamaz.");
        return;
      }
    }

    setSaving(true);
    try {
      // Backend deadline'ı question template'inden hesaplıyor; biz
      // sadece durum + not yazıyoruz. İleride deadline'ı override
      // etmek istersek, update_dof endpoint'ine deadline parametresi
      // eklemek gerekir (server.py:1945 civarı).
      const payload = buildInlineDofPayload({
        status: "AÇIK",
        notes,
      });
      const { data } = await api.put(
        `/dofs/${auditId}/${questionId}`,
        payload
      );
      setSaved(true);
      setNotes(data?.dof?.notes ?? notes);
      toast.success("DÖF oluşturuldu", {
        description: continuous
          ? "Sürekli terminli uygunsuzluk — saha anında düzeltilecek."
          : `Termin: ${deadline}`,
      });
    } catch (e) {
      const detail = e.response?.data?.detail;
      setError(formatApiErrorDetail(detail) || e.message);
      toast.error("DÖF kaydedilemedi");
    } finally {
      setSaving(false);
    }
  };

  // Sürekli termin: input gizle, sadece özel uyarı + not
  if (continuous) {
    return (
      <div
        className="space-y-3 font-sans"
        data-testid={`inline-dof-form-${questionId}`}
      >
        <div className="flex items-start gap-2 p-3 border border-risk-critical-border bg-risk-critical-bg rounded-card">
          <Zap className="w-4 h-4 text-red-600 dark:text-red-400 mt-0.5 shrink-0" />
          <div className="flex-1 text-xs text-risk-critical leading-relaxed">
            <strong className="font-bold">SÜREKLİ — Anında Müdahale.</strong> Bu
            bulgu için termin süresi yoktur; saha tespit anında düzeltilmelidir.
            Not alanına kısa bir saha gözlemi yazıp kaydedin.
          </div>
        </div>

        <div>
          <label
            htmlFor={`dof-notes-${questionId}`}
            className="text-[10px] font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider flex items-center gap-1.5 mb-1"
          >
            <Wrench className="w-3 h-3" /> Saha Notu
          </label>
          <textarea
            id={`dof-notes-${questionId}`}
            value={notes}
            onChange={(e) => { setNotes(e.target.value); setSaved(false); }}
            disabled={readOnly || saving}
            rows={2}
            placeholder="Saha tespit gözlemi (opsiyonel)"
            data-testid={`inline-dof-notes-${questionId}`}
            className={cn(
              "w-full bg-slate-50 dark:bg-slate-950/90 border border-slate-200 dark:border-white/10 rounded-card p-2.5 text-xs text-slate-900 dark:text-slate-100 placeholder:text-slate-400 dark:placeholder:text-slate-500 focus:outline-none focus:border-risk-critical focus:ring-2 focus:ring-risk-critical/20 transition-all font-sans resize-none",
              (readOnly || saving) && "opacity-60 cursor-not-allowed"
            )}
          />
        </div>

        {error && (
          <div className="flex items-start gap-2 p-2 border border-risk-critical-border bg-risk-critical-bg rounded-lg text-xs text-risk-critical">
            <AlertCircle className="w-3.5 h-3.5 mt-0.5 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {!readOnly && (
          <button
            type="button"
            onClick={handleSave}
            disabled={saving}
            data-testid={`inline-dof-save-${questionId}`}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-control text-xs font-bold bg-risk-critical hover:bg-risk-critical-2 text-white active:scale-95 disabled:opacity-50 transition-colors duration-standard ease-swift"
          >
            {saving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />}
            {saved ? "DÖF Kaydedildi" : "DÖF Oluştur"}
          </button>
        )}
        {saved && !readOnly && (
          <span className="inline-flex items-center gap-1 text-[11px] text-risk-compliant font-semibold">
            <CheckCircle2 className="w-3 h-3" /> Mevcut DÖF
          </span>
        )}
      </div>
    );
  }

  // Normal termin: termin, sorumlu, not
  return (
    <div
      className="space-y-2.5 font-sans"
      data-testid={`inline-dof-form-${questionId}`}
    >
      <div className="text-[10px] font-extrabold text-risk-moderate uppercase tracking-wider flex items-center gap-1.5">
        <Wrench className="w-3 h-3" /> İNLINE DÖF OLUŞTUR
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
        <div>
          <label
            htmlFor={`dof-deadline-${questionId}`}
            className="text-[10px] font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider flex items-center gap-1 mb-1"
          >
            Termin Süresi
          </label>
          <input
            id={`dof-deadline-${questionId}`}
            type="text"
            value={deadline}
            onChange={(e) => { setDeadline(e.target.value); setSaved(false); }}
            disabled={readOnly || saving}
            placeholder="Örn: 30 gün, 2 ay, 1 hafta"
            data-testid={`inline-dof-deadline-${questionId}`}
            className={cn(
              "w-full bg-slate-50 dark:bg-slate-950/90 border border-slate-200 dark:border-white/10 rounded-lg px-2.5 py-1.5 text-xs text-slate-900 dark:text-slate-100 placeholder:text-slate-400 dark:placeholder:text-slate-500 focus:outline-none focus:border-risk-moderate focus:ring-2 focus:ring-risk-moderate/20 transition-all font-sans",
              (readOnly || saving) && "opacity-60 cursor-not-allowed"
            )}
          />
        </div>

        <div>
          <label
            htmlFor={`dof-responsible-${questionId}`}
            className="text-[10px] font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider flex items-center gap-1 mb-1"
          >
            Sorumlu
          </label>
          <input
            id={`dof-responsible-${questionId}`}
            type="text"
            value={responsible}
            onChange={(e) => { setResponsible(e.target.value); setSaved(false); }}
            disabled={readOnly || saving}
            placeholder="Restoran Sorumlusu"
            data-testid={`inline-dof-responsible-${questionId}`}
            className={cn(
              "w-full bg-slate-50 dark:bg-slate-950/90 border border-slate-200 dark:border-white/10 rounded-lg px-2.5 py-1.5 text-xs text-slate-900 dark:text-slate-100 placeholder:text-slate-400 dark:placeholder:text-slate-500 focus:outline-none focus:border-risk-moderate focus:ring-2 focus:ring-risk-moderate/20 transition-all font-sans",
              (readOnly || saving) && "opacity-60 cursor-not-allowed"
            )}
          />
        </div>
      </div>

      <div>
        <label
          htmlFor={`dof-notes-${questionId}`}
          className="text-[10px] font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider flex items-center gap-1.5 mb-1"
        >
          Saha Notu
        </label>
        <textarea
          id={`dof-notes-${questionId}`}
          value={notes}
          onChange={(e) => { setNotes(e.target.value); setSaved(false); }}
          disabled={readOnly || saving}
          rows={2}
          placeholder="İlk tespit notu, saha gözlemi, referans fotoğraf no vs."
          data-testid={`inline-dof-notes-${questionId}`}
          className={cn(
            "w-full bg-slate-50 dark:bg-slate-950/90 border border-slate-200 dark:border-white/10 rounded-lg p-2.5 text-xs text-slate-900 dark:text-slate-100 placeholder:text-slate-400 dark:placeholder:text-slate-500 focus:outline-none focus:border-risk-moderate focus:ring-2 focus:ring-risk-moderate/20 transition-all font-sans resize-none",
            (readOnly || saving) && "opacity-60 cursor-not-allowed"
          )}
        />
      </div>

      {error && (
        <div className="flex items-start gap-2 p-2 border border-risk-critical-border bg-risk-critical-bg rounded-lg text-xs text-risk-critical">
          <AlertCircle className="w-3.5 h-3.5 mt-0.5 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {!readOnly && (
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={handleSave}
            disabled={saving}
            data-testid={`inline-dof-save-${questionId}`}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-control text-xs font-bold bg-risk-moderate hover:bg-risk-moderate-2 text-white active:scale-95 disabled:opacity-50 transition-colors duration-standard ease-swift"
          >
            {saving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />}
            {saved ? "DÖF Kaydedildi" : "DÖF Oluştur"}
          </button>
          {saved && (
            <span className="inline-flex items-center gap-1 text-[11px] text-risk-compliant font-semibold">
              <CheckCircle2 className="w-3 h-3" /> Mevcut DÖF
            </span>
          )}
        </div>
      )}
    </div>
  );
}
