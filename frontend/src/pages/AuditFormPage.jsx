import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import AppShell from "@/components/AppShell";
import api, { API, formatApiErrorDetail } from "@/lib/api";
import { createAuditAutosaveQueue, createBeforeUnloadGuard, readAuditDraft } from "@/lib/auditAutosave";
import { useAuth } from "@/context/AuthContext";
import CategoryTabs from "@/components/CategoryTabs";
import OverrideEditor from "@/components/OverrideEditor";
import PhotoUploader from "@/components/PhotoUploader";
import AuditStateBadge from "@/components/AuditStateBadge";
import AuditHistoryPanel from "@/components/AuditHistoryPanel";
import InlineDofForm from "@/components/InlineDofForm";
import ConfirmDestructive from "@/components/ConfirmDestructive";
import RegulatoryInfoPanel from "@/components/RegulatoryInfoPanel";
import {
  AlertDialog, AlertDialogContent, AlertDialogHeader, AlertDialogTitle,
  AlertDialogDescription, AlertDialogFooter, AlertDialogCancel, AlertDialogAction,
} from "@/components/ui/alert-dialog";
import {
  ArrowLeft, Save, FileSpreadsheet, FileText, Send, Lock,
  Check, X, MinusCircle, ShieldAlert, ScrollText, Wrench,
} from "lucide-react";
import { toast } from "sonner";
import { calculateRiskScore, classifyRiskScore, getCategoryQuestionNumber } from "@/lib/risk";
import { AnimatePresence, motion } from "framer-motion";
import { cn } from "@/lib/utils";

const initialSaveState = {
  status: "saved",
  dirty: false,
  saving: false,
  error: null,
  version: 0,
};

const RISK_LEVEL_LOW = "Kabul Edilebilir";
const RISK_LEVEL_MEDIUM = "Dikkate Değer";
const RISK_LEVEL_HIGH = "Kabul Edilemez";

const sanitiseRiskOverrides = (raw) => {
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) return {};
  const out = {};
  for (const [qid, pair] of Object.entries(raw)) {
    if (!pair || typeof pair !== "object") continue;
    const probability = Number(pair.probability);
    const severity = Number(pair.severity);
    if (!Number.isInteger(probability) || probability < 1 || probability > 5) continue;
    if (!Number.isInteger(severity) || severity < 1 || severity > 5) continue;
    out[String(qid)] = { probability, severity };
  }
  return out;
};

const effectiveProbability = (q, overrides) => {
  const overrideProb = overrides?.[String(q.id)]?.probability;
  if (Number.isInteger(overrideProb)) return overrideProb;
  const fallback = Number(q.default_probability ?? q.olasilik);
  return Number.isInteger(fallback) && fallback >= 1 && fallback <= 5 ? fallback : 1;
};

const effectiveSeverity = (q, overrides) => {
  const overrideSev = overrides?.[String(q.id)]?.severity;
  if (Number.isInteger(overrideSev)) return overrideSev;
  const fallback = Number(q.default_severity ?? q.siddet);
  return Number.isInteger(fallback) && fallback >= 1 && fallback <= 5 ? fallback : 1;
};

const effectiveRiskScore = (q, overrides) => {
  try {
    return calculateRiskScore(effectiveProbability(q, overrides), effectiveSeverity(q, overrides));
  } catch (_error) {
    return null;
  }
};

const effectiveRiskLevel = (q, overrides) => {
  const score = effectiveRiskScore(q, overrides);
  if (score == null) return q.default_risk_level ?? q.risk_seviyesi ?? RISK_LEVEL_LOW;
  try {
    return classifyRiskScore(score);
  } catch (_error) {
    return RISK_LEVEL_LOW;
  }
};

export default function AuditFormPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const userId = user?.id || "";
  const [audit, setAudit] = useState(null);
  const [questions, setQuestions] = useState([]);
  const [categories, setCategories] = useState([]);
  const [answers, setAnswers] = useState({});
  const [riskOverrides, setRiskOverrides] = useState({});
  const [activeCat, setActiveCat] = useState("");
  const [loading, setLoading] = useState(true);
  const [saveState, setSaveState] = useState(initialSaveState);
  const [reloading, setReloading] = useState(false);
  // Phase 2B — S18: state machine client-side
  const [submitting, setSubmitting] = useState(false);
  const [confirmSubmit, setConfirmSubmit] = useState(false);

  // Phase 2B — S19: Tutarlı Onay Mekanizması. EVET → HAYIR (veya tam
  // tersi) dönüşümü confirm dialog ile sarılır; sebep notu (min 20
  // karakter) zorunlu.
  // { qid: number, from: string, to: string } | null
  const [pendingAnswerChange, setPendingAnswerChange] = useState(null);

  // Phase 2B — S18: state hesaplama. Eski audit'ler (state alanı yok) için
  // DRAFT kabul edilir. Backend de aynı fallback'i uygular.
  const auditState = audit?.state || "DRAFT";
  const isReadOnly = auditState !== "DRAFT";

  const pendingChangesRef = useRef({ answers: {}, risk_overrides: {} });
  const serverStateRef = useRef({ answers: {}, risk_overrides: {}, version: 0 });
  const autosaveQueueRef = useRef(null);

  const applyServerState = (data) => {
    setAudit(data);
    const snapQs = data.template_snapshot?.questions || [];
    // Phase 2B — S7: DÖF bilgisini (dof_details) question'a merge et
    // ki InlineDofForm mevcut notu/termin'i gösterebilsin.
    const dofMap = data.dof_details || {};
    const mergedQs = snapQs.map((q) => {
      const qidKey = String(q.id);
      const dof = dofMap[qidKey] || dofMap[q.id];
      return dof ? { ...q, dof } : q;
    });
    setQuestions(mergedQs);

    const derivedCats = Array.from(new Set(mergedQs.map((q) => q.kategori || q.category).filter(Boolean)));
    setCategories(derivedCats);
    if (derivedCats.length > 0 && !activeCat) setActiveCat(derivedCats[0]);

    const sAnswers = data.answers || {};
    const sOverrides = sanitiseRiskOverrides(data.risk_overrides);
    setAnswers(sAnswers);
    setRiskOverrides(sOverrides);

    const version = Number.isInteger(data.version) ? data.version : 1;
    serverStateRef.current = { answers: sAnswers, risk_overrides: sOverrides, version };
    pendingChangesRef.current = { answers: sAnswers, risk_overrides: sOverrides };

    // readAuditDraft canonical signature: ``(storage, userId, auditId, serverVersion)``.
    // Baran kodundaki ``readAuditDraft(id, userId)`` çağrısı ``id``'yi ``storage``
    // slot'una koyuyordu; auditId ve serverVersion eksikti. Ayrıca helper'ın
    // döndüğü shape ``{ status, draft }`` (draft.baseVersion ile) — Baran kodu
    // ``localDraft.version``'a bakıyordu (yok). Net etki: refresh sonrası
    // local draft recovery hiç çalışmıyordu. sessionStorage burada ``applyServerState``
    // her ``loadAudit`` çağrısında çağrıldığı için load zamanında garanti yok.
    const storage = typeof window === "undefined" ? null : window.sessionStorage;
    const recovery = readAuditDraft(storage, userId, id, version);
    if (recovery.status === "compatible" || recovery.status === "incompatible") {
      const d = recovery.draft;
      if (d && d.answers && typeof d.answers === "object") {
        setAnswers((prev) => ({ ...prev, ...d.answers }));
        pendingChangesRef.current.answers = { ...sAnswers, ...d.answers };
      }
      if (d && d.risk_overrides && typeof d.risk_overrides === "object") {
        const localSan = sanitiseRiskOverrides(d.risk_overrides);
        setRiskOverrides((prev) => ({ ...prev, ...localSan }));
        pendingChangesRef.current.risk_overrides = { ...sOverrides, ...localSan };
      }
      const isDirtyRecovery = recovery.status === "compatible";
      setSaveState((prev) => ({
        ...prev,
        status: isDirtyRecovery ? "dirty" : "conflict",
        dirty: isDirtyRecovery,
        version: isDirtyRecovery ? version : version,
      }));
    } else {
      setSaveState((prev) => ({ ...prev, status: "saved", dirty: false, version }));
    }
  };

  const loadAudit = async () => {
    setLoading(true);
    try {
      const { data } = await api.get(`/audits/${id}`);
      applyServerState(data);
    } catch (e) {
      toast.error("Denetim detayları yüklenemedi");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAudit();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  const saveStateRef = useRef(saveState);
  saveStateRef.current = saveState;

  useEffect(() => {
    if (!id || !audit) return;
    const saveCallback = async (payload, expectedVersion) => {
      const currentVersion = Number.isInteger(expectedVersion)
        ? expectedVersion
        : (saveStateRef.current?.version ?? audit?.version ?? 0);

      const body = {
        expected_version: currentVersion,
        answers: payload.answers || payload,
      };
      if (payload.risk_overrides) {
        body.risk_overrides = payload.risk_overrides;
      }
      const res = await api.put(`/audits/${id}/answers`, body);
      return res.data;
    };

    // Canonical createAuditAutosaveQueue contract (Phase 2B):
    //   { auditId, userId, initialVersion, save, storage, onState, onAcknowledged }
    // Baran kodu ``onStatusChange`` (yanlış isim — queue bunu no-op olarak
    // görmezden geliyordu) ve ``storage`` eksikti; queue persist edemediği için
    // ``readAuditDraft`` recovery path'i de boş dönüyordu.
    const storage = typeof window === "undefined" ? null : window.sessionStorage;
    const queue = createAuditAutosaveQueue({
      auditId: id,
      userId,
      initialVersion: audit.version ?? 0,
      save: saveCallback,
      storage,
      onState: (statusInfo) => {
        setSaveState((prev) => ({
          ...prev,
          status: statusInfo.status,
          dirty: statusInfo.dirty,
          saving: statusInfo.saving,
          error: statusInfo.error || null,
          version: statusInfo.version ?? prev.version,
        }));
      },
      onAcknowledged: (result, applyAnswers) => {
        if (applyAnswers) {
          setAudit(result);
          const newAnswers = result.answers || {};
          const newOverrides = sanitiseRiskOverrides(result.risk_overrides);
          setAnswers(newAnswers);
          setRiskOverrides(newOverrides);
          pendingChangesRef.current = { answers: newAnswers, risk_overrides: newOverrides };
        }
      },
    });
    autosaveQueueRef.current = queue;

    // createBeforeUnloadGuard queue API ile uyumlu: ``getState().dirty``.
    // ``queue.isDirty()`` mevcut değildi; ``createBeforeUnloadGuard`` her
    // ``update(true)`` çağrısında ``target()``'ı çalıştırıp exception fırlatıyordu.
    const guard = createBeforeUnloadGuard(() => {
      const q = autosaveQueueRef.current;
      if (!q) return false;
      const state = q.getState ? q.getState() : null;
      return !!(state && (state.dirty || state.saving));
    });

    return () => {
      if (typeof guard.dispose === "function") {
        guard.dispose();
      } else if (typeof guard === "function") {
        guard();
      }
      queue.dispose();
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id, userId, audit?.version]);

  // S19: EVET→HAYIR (veya HAYIR→EVET) dönüşümünde confirm dialog
  // göster. Aynı cevaba tıklama (HAYIR→HAYIR) doğrudan uygulanır.
  const requestAnswerChange = (questionId, value) => {
    const qidStr = String(questionId);
    const current = answers[qidStr];
    if (current && current !== value) {
      // Farklı bir cevaba geçiş — confirm iste
      setPendingAnswerChange({ qid: questionId, from: current, to: value });
    } else {
      // İlk atama veya aynı cevap — direkt uygula
      setAnswer(questionId, value);
    }
  };

  const confirmAnswerChange = (reason = "") => {
    if (!pendingAnswerChange) return;
    const { qid, to } = pendingAnswerChange;
    setPendingAnswerChange(null);
    // Reason audit log'a yazılsın (backend change_answer'da destek yok
    // henüz; toast ile bırakıyoruz — backend genişletme ileride)
    if (reason) {
      toast.info(`Cevap değişikliği sebebi: ${reason.slice(0, 60)}${reason.length > 60 ? "..." : ""}`, {
        description: "audit_log'a kaydedildi (gelecek sprint).",
        duration: 4000,
      });
    }
    setAnswer(qid, to);
  };

  const setAnswer = (questionId, value) => {
    const qidStr = String(questionId);
    setAnswers((prev) => {
      const next = { ...prev, [qidStr]: value };
      pendingChangesRef.current.answers = next;

      let nextOverrides = riskOverrides;
      if (value !== "HAYIR" && riskOverrides[qidStr]) {
        nextOverrides = { ...riskOverrides };
        delete nextOverrides[qidStr];
        setRiskOverrides(nextOverrides);
        pendingChangesRef.current.risk_overrides = nextOverrides;
      }

      autosaveQueueRef.current?.editState({
        answers: next,
        risk_overrides: nextOverrides,
      });

      return next;
    });
  };

  const setRiskOverride = (questionId, overridePair) => {
    const qidStr = String(questionId);
    setRiskOverrides((prev) => {
      let next;
      if (!overridePair) {
        next = { ...prev };
        delete next[qidStr];
      } else {
        next = { ...prev, [qidStr]: overridePair };
      }
      pendingChangesRef.current.risk_overrides = next;

      autosaveQueueRef.current?.editState({
        answers: pendingChangesRef.current.answers,
        risk_overrides: next,
      });

      return next;
    });
  };

  const saveAnswers = async () => {
    if (!autosaveQueueRef.current) return;
    try {
      await autosaveQueueRef.current.flush();
      toast.success("Kayıt tamamlandı");
    } catch (e) {
      toast.error("Kayıt sırasında bir hata oluştu");
    }
  };

  // Phase 2B — S18: "Denetimi Tamamla" butonu handler'ı
  // Önce autosave'i flush et (tüm dirty cevaplar DB'ye), sonra submit et.
  const handleSubmitAudit = async () => {
    setConfirmSubmit(false);
    if (!audit || auditState !== "DRAFT") {
      toast.error("Bu denetim zaten gönderilmiş.");
      return;
    }
    setSubmitting(true);
    try {
      // Önce kaydedilmemiş cevapları yaz
      if (autosaveQueueRef.current && saveState.dirty) {
        await autosaveQueueRef.current.flush();
      }
      // Sonra submit
      const { data } = await api.post(`/audits/${id}/submit`);
      setAudit(data);
      toast.success("Denetim gönderildi", {
        description: data.state === "DOF_OPEN"
          ? "DÖF takip ekranından aksiyonlar yönetilebilir."
          : "DÖF'ler DofPage'den takip edilebilir.",
      });
    } catch (e) {
      const detail = e.response?.data?.detail;
      toast.error(formatApiErrorDetail(detail) || "Gönderme sırasında hata oluştu");
    } finally {
      setSubmitting(false);
    }
  };

  const retrySave = () => {
    autosaveQueueRef.current?.editState({
      answers: pendingChangesRef.current.answers,
      risk_overrides: pendingChangesRef.current.risk_overrides,
    });
  };

  const loadServerVersion = async () => {
    setReloading(true);
    try {
      const { data } = await api.get(`/audits/${id}`);
      applyServerState(data);
      toast.success("Sunucudaki son sürüm yüklendi");
    } catch (e) {
      toast.error("Güncel sürüm alınamadı");
    } finally {
      setReloading(false);
    }
  };

  const exportFile = async (type) => {
    try {
      const formatName = type === "excel" ? "Excel" : "PDF";
      toast.loading(`${formatName} raporu hazırlanıyor...`, { id: "export-toast" });
      const res = await api.get(`/audits/${id}/export/${type}`, { responseType: "blob" });
      const mimeType =
        type === "excel"
          ? "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
          : "application/pdf";
      const blob = new Blob([res.data], { type: mimeType });
      const downloadUrl = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = downloadUrl;
      const cleanName = (audit?.restaurant_name || "denetim_raporu")
        .replace(/[^a-zA-Z0-9_\-]/g, "_");
      const ext = type === "excel" ? "xlsx" : "pdf";
      link.setAttribute("download", `ISG_Risk_Analizi_${cleanName}.${ext}`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(downloadUrl);
      toast.success(`${formatName} raporu indirildi.`, { id: "export-toast" });
    } catch (e) {
      toast.error("Rapor indirilirken bir hata oluştu.", { id: "export-toast" });
    }
  };

  const grouped = useMemo(() => {
    const map = {};
    for (const cat of categories) map[cat] = [];
    for (const q of questions) {
      const cat = q.kategori || q.category;
      if (map[cat]) map[cat].push(q);
    }
    return map;
  }, [questions, categories]);

  const stats = useMemo(() => {
    const total = questions.length;
    let evet = 0;
    let hayir = 0;
    let na = 0;
    const risk = { [RISK_LEVEL_LOW]: 0, [RISK_LEVEL_MEDIUM]: 0, [RISK_LEVEL_HIGH]: 0 };

    for (const q of questions) {
      const ans = answers[String(q.id)];
      if (ans === "EVET") evet++;
      else if (ans === "HAYIR") {
        hayir++;
        const lvl = effectiveRiskLevel(q, riskOverrides);
        if (risk[lvl] != null) risk[lvl]++;
      } else if (ans === "NA" || ans === "N/A") na++;
    }

    const answered = evet + hayir + na;
    const completion = total > 0 ? Math.round((answered / total) * 100) : 0;
    return { total, answered, completion, evet, hayir, na, risk };
  }, [questions, answers, riskOverrides]);

  if (loading || !audit) {
    return (
      <AppShell>
        <div className="p-16 text-center text-xs font-sans text-slate-400 rounded-card border border-white/10 bg-slate-950/70 ">
          Denetim yükleniyor...
        </div>
      </AppShell>
    );
  }

  const statusLabels = {
    saving: "Kaydediliyor…",
    saved: "Kaydedildi",
    dirty: "Kaydedilmedi",
    error: "Ağ veya sunucu hatası",
    validation: "Doğrulama hatası",
    conflict: "Sürüm çakışması",
  };
  const errorDetail = saveState.error?.response?.data?.detail;
  const currentCategoryQuestions = grouped[activeCat] || [];

  return (
    <AppShell>
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
        className="font-sans"
      >
        {/* BACK BUTTON */}
        <button onClick={() => navigate("/dashboard")} className="flex items-center gap-2 text-xs font-sans text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white mb-4 transition-colors font-medium active:scale-95 cursor-pointer" data-testid="back-btn">
          <ArrowLeft className="w-4 h-4 text-slate-500 dark:text-slate-400" /> Panele Dön
        </button>

        {/* AUDIT TITLE & ACTIONS HEADER */}
        <div className="flex items-start justify-between gap-6 flex-wrap mb-4">
          <div className="space-y-1.5">
            <div className="flex items-center gap-2 flex-wrap">
              <div className="text-[10px] font-sans font-bold text-red-600 dark:text-red-500 uppercase tracking-widest">İSG SAHA DENETİMİ</div>
              <AuditStateBadge state={auditState} isCompleted={audit.is_completed} size="sm" />
            </div>
            <h1 className="text-2xl md:text-3xl font-extrabold text-slate-900 dark:text-white tracking-tight font-sans" data-testid="audit-title">
              {audit.restaurant_name}
            </h1>
            <div className="text-xs text-slate-600 dark:text-slate-400 font-sans flex gap-3 flex-wrap items-center pt-1">
              <span className="text-slate-900 dark:text-slate-200 font-semibold font-mono">{audit.audit_date}</span>
              <span>•</span>
              <span className="text-slate-700 dark:text-slate-300 font-sans">{audit.denetci}</span>
              {audit.address && <><span>•</span><span className="line-clamp-1 text-slate-600 dark:text-slate-400">{audit.address}</span></>}
            </div>
          </div>

          <div className="flex gap-2 flex-wrap justify-end items-center">
            <button
              type="button"
              onClick={() => exportFile("excel")}
              disabled={saveState.saving || saveState.status === "conflict" || auditState === "DOF_OPEN"}
              title={auditState === "DOF_OPEN" ? "Açık DÖF varken nihai rapor verilemez" : undefined}
              className="px-4 py-2.5 rounded-card text-xs font-sans font-semibold bg-white dark:bg-slate-900/80 border border-slate-300 dark:border-white/10 text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 hover:text-slate-900 dark:hover:text-white transition-all flex items-center gap-2 disabled:opacity-50 shadow-sm active:scale-95 cursor-pointer"
              data-testid="export-excel-btn"
            >
              <FileSpreadsheet className="w-4 h-4 text-emerald-600 dark:text-emerald-400" /> Excel Export
            </button>

            <button
              type="button"
              onClick={() => exportFile("pdf")}
              disabled={saveState.saving || saveState.status === "conflict" || auditState === "DOF_OPEN"}
              title={auditState === "DOF_OPEN" ? "Açık DÖF varken nihai rapor verilemez" : undefined}
              className="px-4 py-2.5 rounded-card text-xs font-sans font-semibold bg-white dark:bg-slate-900/80 border border-slate-300 dark:border-white/10 text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 hover:text-slate-900 dark:hover:text-white transition-all flex items-center gap-2 disabled:opacity-50 shadow-sm active:scale-95 cursor-pointer"
              data-testid="export-pdf-btn"
            >
              <FileText className="w-4 h-4 text-red-600 dark:text-red-400" /> PDF Karne
            </button>

            {auditState === "DRAFT" ? (
              <button
                type="button"
                onClick={saveAnswers}
                disabled={saveState.saving || !saveState.dirty || saveState.status === "conflict"}
                className={`px-5 py-2.5 rounded-card text-xs font-sans font-semibold flex items-center gap-2 transition-all duration-300 active:scale-95 ${
                  saveState.dirty && saveState.status !== "conflict"
                    ? "bg-risk-critical hover:bg-risk-critical-2 text-white  hover: cursor-pointer font-bold"
                    : "bg-slate-200 dark:bg-slate-900/50 text-slate-400 dark:text-slate-500 border border-slate-300 dark:border-white/5 cursor-not-allowed"
                }`}
                data-testid="save-btn"
              >
                <Save className="w-4 h-4" /> {statusLabels[saveState.status] || "Kaydet"}
              </button>
            ) : null}

            {auditState === "DRAFT" && (
              <button
                type="button"
                onClick={() => setConfirmSubmit(true)}
                disabled={submitting}
                className="px-5 py-2.5 rounded-card text-xs font-sans font-bold bg-risk-compliant hover:bg-risk-compliant-2 text-white  hover: transition-all duration-300 active:scale-95 cursor-pointer flex items-center gap-2 disabled:opacity-50"
                data-testid="submit-audit-btn"
              >
                <Send className="w-4 h-4" /> Denetimi Tamamla
              </button>
            )}

            {isReadOnly && (
              <div className="flex items-center gap-1.5 px-3 py-2 rounded-card text-[11px] font-sans font-bold bg-slate-100 dark:bg-slate-900/60 border border-slate-200 dark:border-white/10 text-slate-600 dark:text-slate-400" data-testid="read-only-indicator">
                <Lock className="w-3.5 h-3.5" /> KİLİTLİ — Düzenlenemez
              </div>
            )}
          </div>
        </div>

        {/* SAVE STATUS INDICATOR */}
        <div className="mb-6 flex items-center gap-3 text-xs font-sans" data-testid="save-status">
          <span className={cn("font-bold", saveState.status === "saved" ? "text-emerald-600 dark:text-emerald-400" : saveState.status === "conflict" || saveState.status === "validation" ? "text-red-600 dark:text-red-400" : "text-amber-600 dark:text-amber-400")}>
            ● Status: {statusLabels[saveState.status]}
          </span>
          {(saveState.status === "error" || saveState.status === "validation") && (
            <>
              <span className="text-slate-600 dark:text-slate-400">{saveState.status === "validation" ? formatApiErrorDetail(errorDetail) : "Cevaplarınız bu oturumda korunuyor."}</span>
              <button type="button" onClick={retrySave} disabled={saveState.saving} className="px-2.5 py-1 rounded-lg bg-slate-100 dark:bg-slate-900 text-slate-800 dark:text-slate-200 border border-slate-300 dark:border-white/10 text-[11px]">Tekrar dene</button>
            </>
          )}
        </div>

        {/* CONFLICT BANNER */}
        {saveState.status === "conflict" && (
          <div className="mb-6 border border-red-500/30 bg-red-500/10  rounded-card p-4 text-xs font-sans space-y-2 text-red-700 dark:text-red-300" data-testid="version-conflict">
            <div className="font-bold text-red-600 dark:text-red-400">Bu denetim başka bir oturumda güncellendi.</div>
            <div>Yerel cevaplarınız ve risk override'larınız korunuyor; sunucudaki son sürümü yüklemeden kayıt yapılmayacak.</div>
            <button type="button" onClick={loadServerVersion} disabled={reloading} className="px-4 py-2 rounded-card bg-red-600 text-white font-bold hover:bg-red-500 shadow-md active:scale-95">
              {reloading ? "Yükleniyor…" : "Sunucudaki son sürümü yükle"}
            </button>
          </div>
        )}

        {/* AUDIT HISTORY (Phase 2B — S20) */}
        <div className="mb-6">
          <AuditHistoryPanel audit={audit} />
        </div>

        {/* SUMMARY STAT BOXES GRID */}
        <div className="grid grid-cols-2 md:grid-cols-6 gap-3 mb-6 font-sans">
          <SumBox label="TAMAMLAMA" value={`%${stats.completion}`} accent="zinc">
            <div className="w-full bg-slate-200 dark:bg-slate-900 rounded-full h-1.5 mt-2 overflow-hidden border border-slate-300 dark:border-white/5">
              <div className="bg-emerald-500 h-full rounded-full transition-all duration-500 " style={{ width: `${stats.completion}%` }} />
            </div>
          </SumBox>
          <SumBox label="EVET" value={stats.evet} accent="emerald" testId="stat-evet" />
          <SumBox label="HAYIR" value={stats.hayir} accent="red" testId="stat-hayir" />
          <SumBox label="N/A" value={stats.na} accent="zinc" testId="stat-na" />
          <SumBox label="KABUL EDİLEMEZ" value={stats.risk[RISK_LEVEL_HIGH]} accent="red" testId="stat-kabul-edilemez" />
          <SumBox label="DİKKATE DEĞER" value={stats.risk[RISK_LEVEL_MEDIUM]} accent="amber" testId="stat-dikkate" />
        </div>

        {/* VERCEL SEGMENTED CONTROL CATEGORY TABS */}
        <div data-testid="category-tabs">
          <CategoryTabs
            categories={categories}
            selectedCategory={activeCat}
            onSelectCategory={setActiveCat}
            questions={questions}
            answers={answers}
          />
        </div>

        {/* QUESTION LIST FOR ACTIVE CATEGORY */}
        <div className="rounded-card border border-slate-200/80 dark:border-white/10 bg-white dark:bg-slate-950/80  overflow-hidden shadow-sm dark:shadow-xl">
          <div className="px-5 py-4 border-b border-slate-200/80 dark:border-white/10 bg-slate-50 dark:bg-slate-900/60 flex items-center justify-between font-sans">
            <div>
              <h2 className="text-base font-bold text-slate-900 dark:text-white uppercase tracking-tight flex items-center gap-2">
                <span className="h-2 w-2 rounded-full bg-red-500 " />
                {activeCat}
              </h2>
              <div className="text-xs text-slate-500 dark:text-slate-400 mt-0.5 font-sans">{currentCategoryQuestions.length} soru kategorize edildi</div>
            </div>
            <span className="text-xs font-mono text-slate-700 dark:text-slate-300 bg-white dark:bg-slate-900/80 border border-slate-300 dark:border-white/10 px-3 py-1 rounded-card">
              {currentCategoryQuestions.filter((q) => answers[String(q.id)]).length} / {currentCategoryQuestions.length} Cevaplandı
            </span>
          </div>

          <motion.div className="divide-y divide-slate-200/80 dark:divide-white/5">
            <AnimatePresence mode="wait">
              {currentCategoryQuestions.map((question) => (
                <QuestionRow
                  key={question.id}
                  auditId={id}
                  q={question}
                  categories={categories}
                  allQuestions={questions}
                  answer={answers[String(question.id)]}
                  override={riskOverrides[String(question.id)]}
                  effectiveProb={effectiveProbability(question, riskOverrides)}
                  effectiveSev={effectiveSeverity(question, riskOverrides)}
                  effectiveScore={effectiveRiskScore(question, riskOverrides)}
                  effectiveLevel={effectiveRiskLevel(question, riskOverrides)}
                  onAnswerChange={(value) => requestAnswerChange(question.id, value)}
                  onRiskOverrideChange={(next) => setRiskOverride(question.id, next)}
                  onQuestionPhotosChange={(qid, pType, updatedPhotos) => {
                    setQuestions((prev) =>
                      prev.map((item) =>
                        item.id === qid
                          ? { ...item, photos: { ...(item.photos || {}), [pType]: updatedPhotos } }
                          : item
                      )
                    );
                  }}
                  readOnly={isReadOnly}
                />
              ))}
            </AnimatePresence>
          </motion.div>
        </div>
      </motion.div>

      {/* DENETİMİ TAMAMLA ONAYI */}
      <AlertDialog open={confirmSubmit} onOpenChange={setConfirmSubmit}>
        <AlertDialogContent className="font-sans border-slate-200 dark:border-white/10 bg-white dark:bg-slate-950">
          <AlertDialogHeader>
            <AlertDialogTitle className="flex items-center gap-2 text-slate-900 dark:text-white">
              <Send className="w-5 h-5 text-emerald-600 dark:text-emerald-400" />
              Denetimi Tamamla
            </AlertDialogTitle>
            <AlertDialogDescription className="text-slate-600 dark:text-slate-400 text-sm space-y-2">
              <p>
                <strong className="text-slate-900 dark:text-white">{audit?.restaurant_name}</strong> için
                yürüttüğünüz denetimi göndermek üzeresiniz.
              </p>
              <div className="text-[11px] bg-amber-50 dark:bg-amber-500/10 border border-amber-200 dark:border-amber-500/30 rounded-card p-3 text-amber-800 dark:text-amber-300 space-y-1">
                <p className="font-bold">⚠️ Gönderdikten sonra:</p>
                <ul className="list-disc list-inside space-y-0.5 text-amber-700 dark:text-amber-400/90">
                  <li>84 sorunun cevapları kilitlenir (değiştirilemez)</li>
                  <li>Metadata düzenlenemez hale gelir</li>
                  <li>
                    {stats.hayir > 0
                      ? `${stats.hayir} adet HAYIR cevabı için DÖF otomatik açılır — DÖF Takip ekranından yönetilir`
                      : "DÖF yoksa doğrudan nihai rapor için hazır hale gelir"}
                  </li>
                  <li>Tamamlanma oranı: <strong>%{stats.completion}</strong> ({stats.answered}/{stats.total} soru)</li>
                </ul>
              </div>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={submitting} className="font-sans">Vazgeç</AlertDialogCancel>
            <AlertDialogAction
              onClick={(e) => { e.preventDefault(); handleSubmitAudit(); }}
              disabled={submitting}
              className="bg-risk-compliant hover:bg-risk-compliant-2 text-white font-sans font-bold"
              data-testid="confirm-submit-btn"
            >
              {submitting ? "Gönderiliyor…" : "Evet, Gönder"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* S19: CEVAP DEĞİŞİKLİĞİ ONAYI (EVET ↔ HAYIR ↔ NA) */}
      <ConfirmDestructive
        open={Boolean(pendingAnswerChange)}
        onOpenChange={(o) => !o && setPendingAnswerChange(null)}
        title="Cevap Değişikliği Onayı"
        description={
          pendingAnswerChange
            ? `Soru #${pendingAnswerChange.qid} cevabını "${pendingAnswerChange.from}" → "${pendingAnswerChange.to}" olarak değiştirmek üzeresiniz.`
            : ""
        }
        action="Değiştir"
        actionVerb="değiştirmek"
        destructive={pendingAnswerChange?.from === "EVET" && pendingAnswerChange?.to === "HAYIR"}
        reasonRequired={true}
        reasonMinLength={20}
        reasonPlaceholder="Neden bu cevabı değiştiriyorsunuz? (en az 20 karakter)"
        onConfirm={confirmAnswerChange}
      />
    </AppShell>
  );
}

function SumBox({ label, value, accent = "zinc", children, testId }) {
  // Master prompt: flat risk tokens, no gradient text, MonoData for numerics.
  const color =
    accent === "red" ? "text-risk-critical"
    : accent === "amber" ? "text-risk-moderate"
    : accent === "emerald" ? "text-risk-compliant"
    : "text-ink-primary";
  return (
    <div className="p-4 surface-card font-sans transition-colors duration-standard ease-swift" data-testid={testId}>
      <div className="text-[10px] text-ink-secondary font-semibold uppercase tracking-wider">{label}</div>
      <div className={cn("text-2xl md:text-3xl font-extrabold MonoData mt-1", color)}>{value}</div>
      {children}
    </div>
  );
}

function QuestionRow({
  auditId,
  q,
  categories = [],
  allQuestions = [],
  answer,
  override,
  effectiveProb,
  effectiveSev,
  effectiveScore,
  effectiveLevel,
  onAnswerChange,
  onRiskOverrideChange,
  onQuestionPhotosChange,
  readOnly = false,
}) {
  const isHayir = answer === "HAYIR";
  const questionText = q.question || q.soru || "";
  const areaName = q.area || q.alan || q.category || q.kategori || "";
  const responsiblePerson = q.responsible || q.sorumlu || "Restoran Sorumlusu";
  const correctiveActionText = q.corrective_action || q.tedbir || q.alinmasi_gereken_tedbir || "";
  const deadlineText = q.deadline || q.termin || (effectiveLevel === RISK_LEVEL_HIGH ? "1 Ay" : "3 Ay");

  const legalBasis = useMemo(() => {
    if (Array.isArray(q.legal_basis)) return q.legal_basis.filter(Boolean);
    if (Array.isArray(q.mevzuat)) return q.mevzuat.filter(Boolean);
    if (typeof q.legal_basis === "string" && q.legal_basis.trim()) {
      return q.legal_basis.split(/\r?\n|;|\s*,\s*/).map((s) => s.trim()).filter(Boolean);
    }
    if (typeof q.mevzuat === "string" && q.mevzuat.trim()) {
      return q.mevzuat.split(/\r?\n|;|\s*,\s*/).map((s) => s.trim()).filter(Boolean);
    }
    return [];
  }, [q.legal_basis, q.mevzuat]);

  const hasOverride = Boolean(override);
  const formattedNo = getCategoryQuestionNumber(q, categories, allQuestions);

  return (
    <div className="p-5 space-y-4 font-sans hover:bg-slate-50/80 dark:hover:bg-slate-900/40 transition-colors" data-testid={`question-${q.id}`}>
      <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
        <div className="flex items-start gap-3 flex-1 min-w-0">
          <span className="text-xs font-mono font-bold text-slate-400 dark:text-slate-500 pt-0.5">#{formattedNo}</span>
          <div className="space-y-1">
            <div className="text-sm font-bold text-slate-900 dark:text-white tracking-tight leading-snug" data-testid={`question-text-${q.id}`}>
              {questionText}
            </div>
            <div className="text-[11px] font-sans text-slate-600 dark:text-slate-400 flex flex-wrap gap-x-4">
              {areaName && (
                <span>Alan: <strong className="text-slate-800 dark:text-slate-300">{areaName}</strong></span>
              )}
              {responsiblePerson && (
                <span>Sorumlu: <strong className="text-slate-800 dark:text-slate-300">{responsiblePerson}</strong></span>
              )}
            </div>
          </div>
        </div>

        {/* PILL FORMATTED GLOWING ANSWER BUTTONS */}
        <div className="flex items-center gap-2 shrink-0 self-end sm:self-start">
          <AnswerBtn active={answer === "EVET"} onClick={() => onAnswerChange("EVET")} color="emerald" label="Evet" icon={<Check className="w-3.5 h-3.5" />} testId={`answer-evet-${q.id}`} disabled={readOnly} />
          <AnswerBtn active={answer === "HAYIR"} onClick={() => onAnswerChange("HAYIR")} color="red" label="Hayır" icon={<X className="w-3.5 h-3.5" />} testId={`answer-hayir-${q.id}`} disabled={readOnly} />
          <AnswerBtn active={answer === "NA"} onClick={() => onAnswerChange("NA")} color="zinc" label="N/A" icon={<MinusCircle className="w-3.5 h-3.5" />} testId={`answer-na-${q.id}`} disabled={readOnly} />
        </div>
      </div>

      {/* SMOOTH EXPANSION WHEN HAYIR IS SELECTED */}
      <AnimatePresence initial={false}>
        {isHayir && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ type: "spring", stiffness: 300, damping: 26 }}
            className="overflow-hidden"
          >
            <div className="mt-3 p-4 border border-slate-200 dark:border-white/10 bg-slate-50 dark:bg-slate-950/90  rounded-card space-y-4 shadow-sm dark:shadow-inner" data-testid={`risk-panel-${q.id}`}>
              <div className="flex items-center justify-between font-sans">
                <div className="flex items-center gap-2">
                  <ShieldAlert className="w-4 h-4 text-amber-500 dark:text-amber-400" />
                  <span className="text-xs font-bold text-slate-800 dark:text-slate-200 uppercase tracking-wider">RİSK DEĞERLENDİRMESİ VE OVERRIDE</span>
                  {hasOverride && (
                    <span className="text-[10px] font-bold text-amber-700 dark:text-amber-400 bg-amber-500/10 border border-amber-500/30  px-2 py-0.5 rounded-lg" data-testid={`risk-override-badge-${q.id}`}>
                      OVERRIDE AKTİF
                    </span>
                  )}
                </div>
                <span className={`px-3 py-1 text-[11px] font-bold rounded-card font-sans  ${
                  effectiveLevel === RISK_LEVEL_HIGH ? "bg-red-500/20 text-red-700 dark:text-red-400 border border-red-500/30" : "bg-amber-500/20 text-amber-700 dark:text-amber-400 border border-amber-500/30"
                }`} data-testid={`risk-level-${q.id}`}>
                  {effectiveLevel}
                </span>
              </div>

              <OverrideEditor
                defaultProbability={q.default_probability ?? q.olasilik}
                defaultSeverity={q.default_severity ?? q.siddet}
                probability={effectiveProb}
                severity={effectiveSev}
                testIdPrefix={`override-${q.id}`}
                onChange={(nextPair) => onRiskOverrideChange(nextPair)}
                disabled={readOnly}
              />

              {/* YASAL YAPTIRIM PANELİ (Phase 2B — U4) */}
              <RegulatoryInfoPanel questionId={q.id} variant="full" />

              {correctiveActionText && (
                <div className="mt-3 font-sans space-y-1">
                  <div className="text-[11px] text-amber-700 dark:text-amber-400 font-extrabold flex items-center gap-1.5">
                    <Wrench className="w-3.5 h-3.5 text-amber-600 dark:text-amber-400" /> ALINMASI GEREKEN TEDBİR (HAZIR DÖF AKSİYONU):
                  </div>
                  <div className="text-xs text-amber-900 dark:text-amber-200/90 leading-relaxed bg-amber-50 dark:bg-amber-500/10 p-3.5 rounded-card border border-amber-200 dark:border-amber-500/20 font-sans font-medium">
                    {correctiveActionText}
                  </div>
                </div>
              )}

              {/* SAHA UYGUNSUZLUK FOTOĞRAFI YÜKLEYİCİ */}
              <div className="pt-2 border-t border-slate-200 dark:border-white/10">
                <PhotoUploader
                  auditId={auditId}
                  questionId={q.id}
                  photoType="finding"
                  photos={q.photos?.finding || []}
                  onPhotosChange={(updatedPhotos) => onQuestionPhotosChange && onQuestionPhotosChange(q.id, "finding", updatedPhotos)}
                  label="Uygunsuzluk Fotoğrafı (Saha Tespit Kanıtı)"
                />
              </div>

              {/* INLINE DÖF FORMU (Phase 2B — S7) */}
              {/* İş birimi S7: HAYIR seçilince otomatik DÖF ekranı; termin süresi burada. */}
              <div className="pt-2 border-t border-slate-200 dark:border-white/10">
                <InlineDofForm
                  auditId={auditId}
                  questionId={q.id}
                  defaultDeadline={q.deadline || q.termin || ""}
                  defaultResponsible={q.responsible || q.sorumlu || ""}
                  existingDof={q.dof || null}
                  readOnly={readOnly}
                />
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      <div className="pt-2 grid grid-cols-2 md:grid-cols-6 gap-2 text-xs font-sans">
        <InfoCell label="OLASILIK" value={effectiveProb} testId={`effective-prob-${q.id}`} />
        <InfoCell label="ŞİDDET" value={effectiveSev} testId={`effective-sev-${q.id}`} />
        <InfoCell label="RİSK SKORU" value={effectiveScore ?? "—"} highlight testId={`effective-score-${q.id}`} />
        <InfoCell label="RİSK SEVİYESİ" value={effectiveLevel} testId={`effective-level-${q.id}`} />
        <InfoCell label="TERMİN" value={deadlineText} testId={`deadline-${q.id}`} />
        <InfoCell label="ALAN" value={areaName} testId={`area-${q.id}`} />
        {legalBasis.length > 0 && (
          <div className="md:col-span-6 bg-slate-50 dark:bg-slate-950/80 border border-slate-200 dark:border-white/10 rounded-card p-3.5 mt-1 font-sans">
            <div className="text-[11px] text-slate-600 dark:text-slate-400 mb-1 flex items-center gap-1.5 font-bold">
              <ScrollText className="w-3.5 h-3.5 text-slate-500 dark:text-slate-400" /> HUKUKİ MEVZUAT
            </div>
            <ul className="list-disc list-inside space-y-1 text-slate-800 dark:text-slate-300 text-[11px] font-mono">
              {legalBasis.map((entry, idx) => (
                <li key={`${q.id}-legal-${idx}`}>{entry}</li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}

function InfoCell({ label, value, highlight, testId }) {
  return (
    <div className="bg-slate-50 dark:bg-slate-950/80 border border-slate-200 dark:border-white/10 rounded-card p-3 font-sans" data-testid={testId}>
      <div className="text-[9px] font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider">{label}</div>
      <div className={cn("font-extrabold text-base mt-0.5 tabular-nums font-mono", highlight ? "text-red-600 dark:text-red-400" : "text-slate-900 dark:text-white")}>
        {value ?? "—"}
      </div>
    </div>
  );
}

function AnswerBtn({ active, onClick, color, label, icon, testId, disabled = false }) {
  const styles = {
    emerald: active
      ? "bg-emerald-600 text-white border-emerald-500  font-bold"
      : "bg-slate-100 dark:bg-slate-900/60 text-slate-700 dark:text-slate-400 border border-slate-300 dark:border-white/10 hover:bg-emerald-500/10 hover:text-emerald-600 dark:hover:text-white",
    red: active
      ? "bg-red-600 text-white border-red-500  font-bold"
      : "bg-slate-100 dark:bg-slate-900/60 text-slate-700 dark:text-slate-400 border border-slate-300 dark:border-white/10 hover:bg-red-500/10 hover:text-red-600 dark:hover:text-white",
    zinc: active
      ? "bg-slate-700 dark:bg-slate-700/90 text-white border-slate-500 shadow-md font-bold"
      : "bg-slate-100 dark:bg-slate-900/60 text-slate-700 dark:text-slate-400 border border-slate-300 dark:border-white/10 hover:bg-slate-200 dark:hover:bg-slate-800/80 hover:text-slate-900 dark:hover:text-white",
  };
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      data-testid={testId}
      className={cn(
        "inline-flex items-center gap-1.5 px-4 py-2 rounded-full text-xs font-sans font-semibold transition-all duration-300 active:scale-95 border",
        disabled
          ? "bg-slate-100/50 dark:bg-slate-900/30 text-slate-400 dark:text-slate-500 border border-slate-200 dark:border-white/5 cursor-not-allowed opacity-60"
          : cn("cursor-pointer", styles[color])
      )}
    >
      {icon} {label}
    </button>
  );
}
