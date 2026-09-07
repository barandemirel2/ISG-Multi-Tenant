import React, { useState, useEffect, useMemo } from "react";
import AppShell from "@/components/AppShell";
import AuditStateBadge from "@/components/AuditStateBadge";
import { useBrand } from "@/context/BrandContext";
import { getCategoryQuestionNumber } from "@/lib/risk";
import api from "@/lib/api";
import { motion, AnimatePresence } from "framer-motion";
import {
  FileEdit,
  CheckCircle2,
  XCircle,
  Clock,
  ShieldCheck,
  Building2,
  Save,
  Search,
  Check,
  User,
  AlertTriangle,
  ChevronRight,
  ArrowLeft,
  PenLine,
  FileSignature,
  Sparkles,
  Download,
  Printer,
  Loader2,
} from "lucide-react";
import { toast } from "sonner";

// Karar enum: backend'de declarations.<qid>.decision alaninda tutulur
const DECISION = {
  PENDING: "PENDING",
  APPROVED: "APPROVED",
  DISPUTED: "DISPUTED",
};

const DISPUTE_MIN_CHARS = 20;
const COMMITMENT_MIN_CHARS = 10;

export default function UatChecklistPage() {
  const [audits, setAudits] = useState([]);
  const [loadingAudits, setLoadingAudits] = useState(true);
  const [selectedAuditId, setSelectedAuditId] = useState("");
  const [activeAuditDoc, setActiveAuditDoc] = useState(null);
  const [loadingAuditDetails, setLoadingAuditDetails] = useState(false);

  const [search, setSearch] = useState("");
  const [auditSearch, setAuditSearch] = useState("");
  const [savingItemMap, setSavingItemMap] = useState({});
  const [signing, setSigning] = useState(false);

  // METADATA: isveren vekili imza bloku
  const [metaForm, setMetaForm] = useState({
    rep_name: "",
    rep_title: "Restoran Müdürü / İşveren Vekili",
    declaration_date: new Date().toISOString().slice(0, 10),
  });

  // DECLARATIONS: { [qid]: { decision, reason, commitment, saved_at, saved_by } }
  const [declarations, setDeclarations] = useState({});

  // 1. Audit listesi
  useEffect(() => {
    async function fetchAudits() {
      setLoadingAudits(true);
      try {
        const { data } = await api.get("/audits");
        setAudits(Array.isArray(data) ? data : []);
      } catch (e) {
        console.error("Audits fetch error:", e);
        toast.error("Denetim listesi yüklenemedi.");
      } finally {
        setLoadingAudits(false);
      }
    }
    fetchAudits();
  }, []);

  // 2. Secilen audit detay + declarations restore
  useEffect(() => {
    if (!selectedAuditId) {
      setActiveAuditDoc(null);
      return;
    }
    async function loadAuditDetails() {
      setLoadingAuditDetails(true);
      try {
        const { data } = await api.get(`/audits/${selectedAuditId}`);
        setActiveAuditDoc(data);
        const dbDeclarations = data.declarations || {};
        const dbMeta = data.declarations_meta || {};
        if (Object.keys(dbMeta).length > 0) {
          setMetaForm((prev) => ({ ...prev, ...dbMeta }));
        }
        // Eski semadaki isyeri_beyani alanlarini PENDING karar olarak migrate et
        const migrated = {};
        Object.entries(dbDeclarations).forEach(([qid, dec]) => {
          if (dec && !dec.decision && dec.isyeri_beyani) {
            migrated[qid] = { ...dec, decision: DECISION.APPROVED };
          } else {
            migrated[qid] = dec;
          }
        });
        setDeclarations(migrated);
      } catch (e) {
        toast.error("Denetim detayları veritabanından yüklenemedi.");
      } finally {
        setLoadingAuditDetails(false);
      }
    }
    loadAuditDetails();
  }, [selectedAuditId]);

  // Karar metni guncelle (henuz kaydedilmedi)
  const updateDecisionDraft = (qid, patch) => {
    setDeclarations((prev) => ({
      ...prev,
      [qid]: {
        ...(prev[qid] || {}),
        ...patch,
        is_dirty: true,
      },
    }));
  };

  // Soru basina kaydet
  const handleSaveDecision = async (qid, questionTitle) => {
    if (!selectedAuditId) return;
    const dec = declarations[qid] || {};
    if (!dec.decision || dec.decision === DECISION.PENDING) {
      toast.error("Önce bir karar seçin (Onayla / İtiraz Et).");
      return;
    }
    if (dec.decision === DECISION.DISPUTED) {
      const reason = (dec.reason || "").trim();
      if (reason.length < DISPUTE_MIN_CHARS) {
        toast.error(`İtiraz sebebi en az ${DISPUTE_MIN_CHARS} karakter olmalı.`);
        return;
      }
    }
    if (dec.decision === DECISION.APPROVED) {
      const commit = (dec.commitment || "").trim();
      if (commit.length > 0 && commit.length < COMMITMENT_MIN_CHARS) {
        toast.error(`Taahhüt metni en az ${COMMITMENT_MIN_CHARS} karakter olmalı (ya da boş bırakın).`);
        return;
      }
    }
    setSavingItemMap((prev) => ({ ...prev, [qid]: true }));
    try {
      const itemToSave = {
        ...dec,
        decision: dec.decision,
        reason: (dec.reason || "").trim(),
        commitment: (dec.commitment || "").trim(),
        is_dirty: false,
        saved_at: new Date().toISOString(),
      };
      const payload = {
        declarations: { [qid]: itemToSave },
        meta: metaForm,
      };
      const { data } = await api.patch(`/audits/${selectedAuditId}/declarations`, payload);
      setActiveAuditDoc(data);
      if (data.declarations) setDeclarations(data.declarations);
      toast.success(`Soru #${qid} kararı kaydedildi.`, {
        description: questionTitle ? `"${questionTitle.slice(0, 50)}..."` : undefined,
      });
    } catch (e) {
      toast.error("Karar kaydedilirken hata oluştu.");
    } finally {
      setSavingItemMap((prev) => ({ ...prev, [qid]: false }));
    }
  };

  // Toplu kaydet (sadece dirty olanlari)
  const handleSaveAll = async () => {
    if (!selectedAuditId) return;
    const dirtyIds = Object.keys(declarations).filter((qid) => declarations[qid]?.is_dirty);
    if (dirtyIds.length === 0) {
      toast.info("Tüm kararlar zaten kaydedilmiş.");
      return;
    }
    let ok = 0, fail = 0;
    for (const qid of dirtyIds) {
      try {
        const dec = declarations[qid];
        if (!dec.decision || dec.decision === DECISION.PENDING) { fail++; continue; }
        if (dec.decision === DECISION.DISPUTED && (dec.reason || "").trim().length < DISPUTE_MIN_CHARS) { fail++; continue; }
        const itemToSave = { ...dec, is_dirty: false, saved_at: new Date().toISOString() };
        const { data } = await api.patch(`/audits/${selectedAuditId}/declarations`, {
          declarations: { [qid]: itemToSave },
          meta: metaForm,
        });
        setActiveAuditDoc(data);
        if (data.declarations) setDeclarations(data.declarations);
        ok++;
      } catch (e) { fail++; }
    }
    if (ok > 0) toast.success(`${ok} karar kaydedildi.`);
    if (fail > 0) toast.error(`${fail} karar kaydedilemedi (validasyon/API).`);
  };

  // Imzalama: tum kararlar PENDING degil, rep_name dolu
  const handleSign = async () => {
    if (!selectedAuditId) return;
    if (!metaForm.rep_name?.trim()) {
      toast.error("İşveren vekili adı zorunludur.");
      return;
    }
    const qs = activeAuditDoc?.questions || [];
    const answers = activeAuditDoc?.answers || {};
    const hayirQs = qs.filter((q) => answers[q.id] === "HAYIR");
    const undecided = hayirQs.filter((q) => {
      const d = declarations[q.id];
      return !d || !d.decision || d.decision === DECISION.PENDING || d.is_dirty;
    });
    if (undecided.length > 0) {
      toast.error(`${undecided.length} soru hâlâ karar bekliyor. Önce tüm kararları kaydedin.`);
      return;
    }
    setSigning(true);
    try {
      // Yeni /workplace-approval/sign endpoint'i:
      //  - signed_at server-side set edilir (idempotent)
      //  - audit_log yazılır
      //  - DOF_OPEN + tüm DÖF'ler kapalı → DOF_CLOSED transition uygular
      const decisionsPayload = {};
      Object.entries(declarations).forEach(([qid, dec]) => {
        if (dec && dec.decision && dec.decision !== DECISION.PENDING) {
          decisionsPayload[qid] = {
            decision: dec.decision,
            reason: (dec.reason || "").trim(),
            commitment: (dec.commitment || "").trim(),
            saved_at: dec.saved_at,
          };
        }
      });
      const { data } = await api.post(
        `/audits/${selectedAuditId}/workplace-approval/sign`,
        {
          decisions: decisionsPayload,
          rep_name: metaForm.rep_name.trim(),
          rep_title: (metaForm.rep_title || "").trim(),
          declaration_date: metaForm.declaration_date,
        }
      );
      setActiveAuditDoc(data);
      // Server meta'yı güncelledi (signed_at, signed_by_*, signed_by_user_*),
      // local metaForm'u data.declarations_meta ile senkronize et
      if (data.declarations_meta) {
        setMetaForm((prev) => ({ ...prev, ...data.declarations_meta }));
      }
      const newState = data.state;
      toast.success("İşveren Vekili Onayı imzalandı ve veritabanına kaydedildi.", {
        description: newState === "DOF_CLOSED"
          ? "Tüm DÖF'ler kapatıldı — denetim artık nihai rapor için hazır."
          : `Denetim durumu: ${newState}. Nihai rapor için tüm DÖF'ler kapatılmalı.`,
        duration: 5000,
      });
    } catch (e) {
      const detail = e?.response?.data?.detail || "İmzalama sırasında hata oluştu.";
      toast.error(detail);
    } finally {
      setSigning(false);
    }
  };

  // ---- Derived ----
  // activeAuditDoc referansı her render'da yeni olabilir; array/object türevlerini
  // useMemo ile stabilize ediyoruz ki alt useMemo'lar gereksiz re-render olmasın.
  // BUG FIX: Backend `_serialize_audit` snapshot'ı `template_snapshot.questions`
  // altında döner, üst seviyede `questions` yok. Önceki kod `activeAuditDoc.questions`
  // okuduğu için HAYIR filtreleri hep boş dönüyordu.
  const questions = useMemo(
    () => activeAuditDoc?.template_snapshot?.questions || activeAuditDoc?.questions || [],
    [activeAuditDoc]
  );
  const answers = useMemo(
    () => activeAuditDoc?.answers || {},
    [activeAuditDoc]
  );
  const dofDetails = useMemo(
    () => activeAuditDoc?.dof_details || {},
    [activeAuditDoc]
  );
  const hayirQuestions = useMemo(
    () =>
      questions.filter((q) => {
        const val = answers[q.id] ?? answers[String(q.id)] ?? answers[Number(q.id)];
        return val === "HAYIR";
      }),
    [questions, answers]
  );

  const filteredHayirQuestions = useMemo(() => {
    if (!search.trim()) return hayirQuestions;
    const q = search.toLowerCase().trim();
    return hayirQuestions.filter((x) =>
      (x.category || "").toLowerCase().includes(q) ||
      (x.question || "").toLowerCase().includes(q)
    );
  }, [hayirQuestions, search]);

  const { selectedBrand } = useBrand();

  const filteredAudits = useMemo(() => {
    let list = audits;
    if (selectedBrand && selectedBrand !== "Tüm Markalar") {
      const bLower = selectedBrand.toLowerCase();
      list = list.filter((a) =>
        (a.restaurant_name || "").toLowerCase().includes(bLower) ||
        (a.brand || "").toLowerCase().includes(bLower)
      );
    }
    if (!auditSearch.trim()) return list;
    const q = auditSearch.toLowerCase().trim();
    return list.filter((a) =>
      (a.restaurant_name || "").toLowerCase().includes(q) ||
      (a.denetci || "").toLowerCase().includes(q) ||
      (a.brand || "").toLowerCase().includes(q) ||
      (a.city || "").toLowerCase().includes(q)
    );
  }, [audits, auditSearch, selectedBrand]);

  const decisionStats = useMemo(() => {
    let approved = 0, disputed = 0, pending = 0, dirty = 0;
    hayirQuestions.forEach((q) => {
      const d = declarations[q.id];
      if (!d || !d.decision || d.decision === DECISION.PENDING) pending++;
      else if (d.decision === DECISION.APPROVED) approved++;
      else if (d.decision === DECISION.DISPUTED) disputed++;
      if (d?.is_dirty) dirty++;
    });
    return { approved, disputed, pending, dirty, total: hayirQuestions.length };
  }, [hayirQuestions, declarations]);

  const isSigned = !!metaForm.signed_at;
  const canSign = decisionStats.pending === 0 && decisionStats.dirty === 0 && decisionStats.total > 0;

  // ============ RENDER ============
  return (
    <AppShell>
      <div className="space-y-6 max-w-7xl mx-auto font-sans pb-16">

        {/* ============================================================ */}
        {/* STAGE 1: DENETIM SECIMI                                      */}
        {/* ============================================================ */}
        {!selectedAuditId && (
          <div className="space-y-6">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-200/80 dark:border-white/10 pb-5">
              <div>
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-[11px] font-bold text-red-600 dark:text-red-500 uppercase tracking-widest flex items-center gap-1">
                    <FileEdit className="w-3.5 h-3.5" /> 1. AŞAMA — DENETİM SEÇİMİ
                  </span>
                </div>
                <h1 className="text-3xl font-extrabold text-slate-900 dark:text-white tracking-tight">
                  İşveren Vekili Onayı İçin Denetim Seçin
                </h1>
                <p className="text-xs text-slate-600 dark:text-slate-400 mt-1 max-w-3xl leading-relaxed">
                  İşveren vekili onayı vermek istediğiniz denetimi seçin. Denetim seçildiğinde, o denetimdeki
                  <strong> "HAYIR" </strong>cevaplı sorular için onay/itiraz kararı verebileceğiniz form açılacak.
                </p>
              </div>
              <div className="relative shrink-0">
                <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
                <input
                  type="search"
                  placeholder="Restoran veya denetçi ara..."
                  value={auditSearch}
                  onChange={(e) => setAuditSearch(e.target.value)}
                  className="bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-800 rounded-xl pl-9 pr-3 py-2 text-xs text-slate-900 dark:text-slate-100 placeholder:text-slate-400 focus:outline-none focus:border-red-500 w-full sm:w-64"
                />
              </div>
            </div>

            {loadingAudits ? (
              <div className="p-12 text-center text-xs text-slate-500 font-sans flex items-center justify-center gap-2">
                <Loader2 className="w-4 h-4 animate-spin" /> Tamamlanmış ve kayıtlı denetimler yükleniyor...
              </div>
            ) : filteredAudits.length === 0 ? (
              <div className="p-12 rounded-2xl border border-dashed border-slate-300 dark:border-slate-800 text-center space-y-2 font-sans">
                <Building2 className="w-8 h-8 text-slate-400 mx-auto" />
                <div className="text-sm font-bold text-slate-900 dark:text-white">
                  Henüz Kayıtlı Denetim Bulunmamaktadır.
                </div>
                <div className="text-xs text-slate-500 dark:text-slate-400">
                  Ana panelden "Yeni Denetim Başlat" butonuna tıklayarak ilk denetimi oluşturabilirsiniz.
                </div>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {filteredAudits.map((audit) => {
                  const auditAnswers = audit.answers || {};
                  const hayirCount = Object.values(auditAnswers).filter((v) => v === "HAYIR").length;
                  const isSignedAudit = audit.declarations_meta?.signed_at;
                  return (
                    <div
                      key={audit.id}
                      onClick={() => setSelectedAuditId(audit.id)}
                      className="p-5 rounded-2xl border border-slate-200/80 dark:border-slate-800 bg-white dark:bg-slate-950/80 space-y-4 hover:border-red-500 transition-all cursor-pointer group shadow-sm flex flex-col justify-between"
                    >
                      <div className="space-y-2">
                        <div className="flex items-start justify-between gap-2">
                          <span className="text-[10px] font-bold text-slate-500 uppercase tracking-widest font-mono">
                            {audit.brand || "RESTORAN"}
                          </span>
                          <div className="flex flex-col items-end gap-1">
                            <span
                              className={`px-2.5 py-0.5 rounded-full text-[10px] font-bold border ${
                                hayirCount > 0
                                  ? "bg-red-500/10 text-red-600 dark:text-red-400 border-red-500/30"
                                  : "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/30"
                              }`}
                            >
                              {hayirCount > 0 ? `🚨 ${hayirCount} HAYIR` : "🟢 Uygun"}
                            </span>
                            {audit.state && <AuditStateBadge state={audit.state} />}
                          </div>
                        </div>
                        <h3 className="text-base font-extrabold text-slate-900 dark:text-white group-hover:text-red-600 dark:group-hover:text-red-400 transition-colors leading-tight">
                          {audit.restaurant_name}
                        </h3>
                        <div className="text-xs text-slate-600 dark:text-slate-400 space-y-1">
                          <div>📍 {audit.address || "Lokasyon belirtilmemiş"}</div>
                          {audit.city && <div>🌆 {audit.city} / {audit.district}</div>}
                          <div>👤 Denetçi: <strong>{audit.denetci || "Belirtilmedi"}</strong></div>
                          <div>📅 Tarih: <span className="font-mono">{audit.audit_date || "Tarihsiz"}</span></div>
                          {isSignedAudit && (
                            <div className="pt-1 text-emerald-600 dark:text-emerald-400 font-bold flex items-center gap-1">
                              <FileSignature className="w-3 h-3" /> Onay {new Date(isSignedAudit).toLocaleDateString("tr-TR")} tarihinde imzalanmış
                            </div>
                          )}
                        </div>
                      </div>
                      <div className="pt-3 border-t border-slate-100 dark:border-slate-900 flex items-center justify-between text-xs font-bold text-red-600 dark:text-red-400 group-hover:translate-x-1 transition-transform">
                        <span>{isSignedAudit ? "Onay Belgesini Görüntüle" : "Beyan Formunu Aç"}</span>
                        <ChevronRight className="w-4 h-4" />
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {/* ============================================================ */}
        {/* STAGE 2 + 3: SECILMIS DENETIME ONAY FORMU                    */}
        {/* ============================================================ */}
        {selectedAuditId && (
          <div className="space-y-6">
            {/* TOP BAR */}
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-200/80 dark:border-white/10 pb-5">
              <div>
                <button
                  type="button"
                  onClick={() => setSelectedAuditId("")}
                  className="inline-flex items-center gap-1.5 text-xs font-bold text-slate-600 dark:text-slate-400 hover:text-red-600 dark:hover:text-red-400 transition-colors cursor-pointer mb-2"
                >
                  <ArrowLeft className="w-4 h-4" />
                  <span>Farklı Denetim Seç</span>
                </button>
                <div className="flex items-center gap-2 mb-1 flex-wrap">
                  <span className="text-[11px] font-bold text-red-600 dark:text-red-500 uppercase tracking-widest flex items-center gap-1">
                    <FileEdit className="w-3.5 h-3.5" /> 2. AŞAMA — İŞVEREN VEKİLİ ONAY FORMU
                  </span>
                  {activeAuditDoc?.state && <AuditStateBadge state={activeAuditDoc.state} />}
                </div>
                <h1 className="text-3xl font-extrabold text-slate-900 dark:text-white tracking-tight">
                  {activeAuditDoc?.restaurant_name} — Onay Formu
                </h1>
                <p className="text-xs text-slate-600 dark:text-slate-400 mt-1 max-w-3xl leading-relaxed">
                  "HAYIR" cevaplı her soru için onay veya itiraz kararı verin. Tüm kararlar kaydedildikten sonra
                  sayfanın altındaki <strong>İmza Bloğu</strong>'ndan İşveren Vekili Onay Belgesi'ni imzalayabilirsiniz.
                </p>
              </div>

              {!isSigned && (
                <div className="flex items-center gap-2 shrink-0">
                  <button
                    type="button"
                    onClick={handleSaveAll}
                    disabled={decisionStats.dirty === 0}
                    className="inline-flex items-center justify-center gap-2 px-5 py-2.5 rounded-xl text-xs font-bold bg-emerald-600 hover:bg-emerald-500 text-white shadow-md transition-all active:scale-95 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    <Save className="w-4 h-4" />
                    <span>Kaydedilmemiş {decisionStats.dirty > 0 && `(${decisionStats.dirty})`} Kararı Kaydet</span>
                  </button>
                </div>
              )}
            </div>

            {/* AUDIT SUMMARY + PROGRESS — master prompt: flat surface, no gradient, no backdrop-blur */}
            <div className="p-5 rounded-2xl border border-risk-critical-border bg-risk-critical-bg flex flex-col md:flex-row items-stretch md:items-center justify-between gap-4 font-sans shadow-sm">
              <div className="flex items-center gap-3">
                <div className="w-12 h-12 rounded-2xl bg-risk-critical text-white flex items-center justify-center font-bold shrink-0 shadow-md">
                  <Building2 className="w-6 h-6" />
                </div>
                <div>
                  <div className="text-[10px] font-bold text-red-600 dark:text-red-400 uppercase tracking-widest">
                    SEÇİLİ DENETİM
                  </div>
                  <div className="text-base font-extrabold text-slate-900 dark:text-white">
                    {activeAuditDoc?.restaurant_name}
                  </div>
                  <div className="text-xs text-slate-600 dark:text-slate-400 flex items-center gap-2 mt-0.5 flex-wrap">
                    <span>📍 {activeAuditDoc?.address || "Lokasyon"}</span>
                    {activeAuditDoc?.brand && <span>• <strong className="text-red-600 dark:text-red-400">{activeAuditDoc.brand}</strong></span>}
                    {activeAuditDoc?.city && <span>• {activeAuditDoc.city} / {activeAuditDoc.district}</span>}
                    <span>• 👤 {activeAuditDoc?.denetci || "Denetçi yok"}</span>
                    <span>• 📅 {activeAuditDoc?.audit_date || "Tarih yok"}</span>
                  </div>
                </div>
              </div>

              {/* KARAR PROGRESS */}
              <div className="flex items-center gap-2 flex-wrap">
                <span className="px-2.5 py-1 rounded-full text-[10px] font-bold bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/30 font-mono">
                  ✅ {decisionStats.approved} Onay
                </span>
                <span className="px-2.5 py-1 rounded-full text-[10px] font-bold bg-amber-500/10 text-amber-700 dark:text-amber-400 border border-amber-500/30 font-mono">
                  ⚠ {decisionStats.disputed} İtiraz
                </span>
                <span className={`px-2.5 py-1 rounded-full text-[10px] font-bold font-mono border ${
                  decisionStats.pending > 0
                    ? "bg-slate-500/10 text-slate-600 dark:text-slate-400 border-slate-500/30"
                    : "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/30"
                }`}>
                  {decisionStats.pending > 0 ? `⏳ ${decisionStats.pending} Bekliyor` : "✓ Tüm Kararlar Verildi"}
                </span>
              </div>
            </div>

            {/* ISVEREN VEKILI BILGILERI */}
            <div className="p-5 border border-slate-200/80 dark:border-slate-800 rounded-2xl bg-white dark:bg-slate-950/80 space-y-4 font-sans">
              <div className="flex items-center justify-between border-b border-slate-100 dark:border-slate-900 pb-3">
                <h2 className="text-sm font-bold text-slate-900 dark:text-white flex items-center gap-2">
                  <User className="w-4 h-4 text-red-600 dark:text-red-400" /> İşveren Vekili Bilgileri
                </h2>
                {isSigned && (
                  <span className="text-[11px] text-emerald-600 dark:text-emerald-400 font-bold font-mono flex items-center gap-1 bg-emerald-500/10 px-2.5 py-1 rounded-xl border border-emerald-500/30">
                    <FileSignature className="w-3.5 h-3.5" /> İmzalı: {new Date(metaForm.signed_at).toLocaleString("tr-TR")}
                  </span>
                )}
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-xs">
                <div className="space-y-1">
                  <label className="font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider text-[10px]">
                    Ad Soyad <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="text"
                    value={metaForm.rep_name}
                    onChange={(e) => setMetaForm({ ...metaForm, rep_name: e.target.value })}
                    placeholder="Örn: Ahmet Yılmaz"
                    disabled={isSigned}
                    className="w-full bg-slate-50 dark:bg-slate-900 border border-slate-300 dark:border-slate-800 rounded-xl px-3 py-2 text-slate-900 dark:text-slate-100 disabled:opacity-60"
                  />
                </div>
                <div className="space-y-1">
                  <label className="font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider text-[10px]">
                    Görevi / Unvanı
                  </label>
                  <input
                    type="text"
                    value={metaForm.rep_title}
                    onChange={(e) => setMetaForm({ ...metaForm, rep_title: e.target.value })}
                    disabled={isSigned}
                    className="w-full bg-slate-50 dark:bg-slate-900 border border-slate-300 dark:border-slate-800 rounded-xl px-3 py-2 text-slate-900 dark:text-slate-100 disabled:opacity-60"
                  />
                </div>
                <div className="space-y-1">
                  <label className="font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider text-[10px]">
                    Onay Tarihi
                  </label>
                  <input
                    type="date"
                    value={metaForm.declaration_date}
                    onChange={(e) => setMetaForm({ ...metaForm, declaration_date: e.target.value })}
                    disabled={isSigned}
                    className="w-full bg-slate-50 dark:bg-slate-900 border border-slate-300 dark:border-slate-800 rounded-xl px-3 py-2 text-slate-900 dark:text-slate-100 font-mono disabled:opacity-60"
                  />
                </div>
              </div>
            </div>

            {/* SEARCH */}
            <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 bg-slate-100 dark:bg-slate-900/60 p-2.5 rounded-2xl border border-slate-200 dark:border-slate-800 font-sans">
              <div className="text-xs font-bold text-slate-900 dark:text-white flex items-center gap-2">
                <XCircle className="w-4 h-4 text-red-600 dark:text-red-400" />
                <span>HAYIR Cevaplı Soru Listesi ({hayirQuestions.length} Madde)</span>
              </div>
              <div className="relative">
                <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
                <input
                  type="search"
                  placeholder="Soru metni veya kategori ara..."
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  className="bg-white dark:bg-slate-950 border border-slate-300 dark:border-slate-800 rounded-xl pl-9 pr-3 py-1.5 text-xs text-slate-900 dark:text-slate-100 placeholder:text-slate-400 focus:outline-none focus:border-red-500 w-full sm:w-64"
                />
              </div>
            </div>

            {/* SORU KARTLARI */}
            {loadingAuditDetails ? (
              <div className="p-12 text-center text-xs text-slate-500 font-sans flex items-center justify-center gap-2">
                <Loader2 className="w-4 h-4 animate-spin" /> Denetim verileri yükleniyor...
              </div>
            ) : filteredHayirQuestions.length === 0 ? (
              <div className="p-12 rounded-2xl border border-dashed border-slate-300 dark:border-slate-800 text-center space-y-2 font-sans">
                <CheckCircle2 className="w-8 h-8 text-emerald-500 mx-auto" />
                <div className="text-sm font-bold text-slate-900 dark:text-white">
                  Bu Denetimde "HAYIR" Cevabı Verilmiş Soru Bulunmamaktadır.
                </div>
                <div className="text-xs text-slate-500 dark:text-slate-400">
                  Tüm sorular "EVET (Uygun)" veya "N/A" olarak yanıtlanmıştır.
                </div>
              </div>
            ) : (
              <div className="space-y-4 font-sans">
                {filteredHayirQuestions.map((q) => {
                  const dec = declarations[q.id] || {};
                  const terminSuresi = q.deadline || q.termin || "30 Gün";
                  const dof = dofDetails[q.id] || dofDetails[String(q.id)] || {};
                  const isSavingThis = !!savingItemMap[q.id];
                  const decision = dec.decision;
                  const dirty = !!dec.is_dirty;

                  return (
                    <div
                      key={q.id}
                      className={`p-5 rounded-2xl border bg-white dark:bg-slate-950/95 shadow-sm transition-all space-y-4 ${
                        decision === DECISION.APPROVED
                          ? "border-emerald-500/40"
                          : decision === DECISION.DISPUTED
                          ? "border-amber-500/40"
                          : "border-red-500/40 hover:border-red-500"
                      }`}
                    >
                      {/* HEADER */}
                      <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 border-b border-slate-100 dark:border-slate-900 pb-3">
                        <div className="space-y-1">
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="px-2.5 py-0.5 rounded bg-red-500/10 text-red-600 dark:text-red-400 font-mono text-xs font-extrabold border border-red-500/20">
                              {q.category || "İSG MADDE"} Soru #{getCategoryQuestionNumber(q, [], questions)}
                            </span>
                            <span className="px-2.5 py-0.5 rounded-full bg-red-500/10 text-red-600 dark:text-red-400 border border-red-500/30 text-[10px] font-extrabold flex items-center gap-1">
                              <XCircle className="w-3 h-3" /> UYGUN DEĞİL
                            </span>
                            <span className="px-3 py-0.5 rounded-full bg-amber-500/10 text-amber-700 dark:text-amber-400 border border-amber-500/30 text-[11px] font-mono font-bold flex items-center gap-1">
                              <Clock className="w-3.5 h-3.5 text-amber-500" />
                              <span>Termin: <strong className="underline">{terminSuresi}</strong></span>
                            </span>
                            {dof.status && (
                              <span className={`px-2.5 py-0.5 rounded-full text-[10px] font-bold border ${
                                dof.status === "KAPATILDI"
                                  ? "bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border-emerald-500/30"
                                  : dof.status === "İŞLEMDE"
                                  ? "bg-blue-500/10 text-blue-700 dark:text-blue-400 border-blue-500/30"
                                  : "bg-amber-500/10 text-amber-700 dark:text-amber-400 border-amber-500/30"
                              }`}>
                                DÖF: {dof.status}
                              </span>
                            )}
                          </div>
                          <h3 className="text-sm font-extrabold text-slate-900 dark:text-white leading-snug pt-0.5">
                            {q.question || q.soru}
                          </h3>
                        </div>
                        {/* KAYIT INDIKATORU */}
                        {dec.saved_at && !dirty && (
                          <span className="text-[11px] text-emerald-600 dark:text-emerald-400 font-bold font-mono flex items-center gap-1 shrink-0 bg-emerald-500/10 px-2.5 py-1 rounded-xl border border-emerald-500/30">
                            <Check className="w-3.5 h-3.5" /> Kaydedildi
                          </span>
                        )}
                        {dirty && (
                          <span className="text-[11px] text-amber-600 dark:text-amber-400 font-bold font-mono flex items-center gap-1 shrink-0 bg-amber-500/10 px-2.5 py-1 rounded-xl border border-amber-500/30">
                            <AlertTriangle className="w-3.5 h-3.5" /> Kaydedilmedi
                          </span>
                        )}
                      </div>

                      {/* KARAR SECIMI */}
                      <div className="space-y-2">
                        <label className="font-bold text-red-600 dark:text-red-400 uppercase tracking-wider text-[10px] flex items-center gap-1">
                          <Sparkles className="w-3 h-3" /> Soru #{q.id} İçin Kararınız *
                        </label>
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                          {/* ONAY */}
                          <button
                            type="button"
                            disabled={isSigned}
                            onClick={() => updateDecisionDraft(q.id, { decision: DECISION.APPROVED, reason: "" })}
                            className={`p-4 rounded-xl border-2 text-left transition-all ${
                              decision === DECISION.APPROVED
                                ? "border-emerald-500 bg-emerald-500/10 shadow-sm"
                                : "border-slate-200 dark:border-slate-800 hover:border-emerald-500/50"
                            } disabled:opacity-60 disabled:cursor-not-allowed`}
                          >
                            <div className="flex items-center gap-2 mb-1">
                              <div className={`w-5 h-5 rounded-full flex items-center justify-center ${
                                decision === DECISION.APPROVED ? "bg-emerald-500 text-white" : "border-2 border-slate-300"
                              }`}>
                                {decision === DECISION.APPROVED && <Check className="w-3.5 h-3.5" />}
                              </div>
                              <span className="font-extrabold text-sm text-slate-900 dark:text-white">✅ Onaylıyorum</span>
                            </div>
                            <div className="text-[11px] text-slate-600 dark:text-slate-400 leading-relaxed">
                              Bulgu yerindedir, DÖF termin süresinde kapatılacaktır.
                            </div>
                          </button>
                          {/* ITIRAZ */}
                          <button
                            type="button"
                            disabled={isSigned}
                            onClick={() => updateDecisionDraft(q.id, { decision: DECISION.DISPUTED })}
                            className={`p-4 rounded-xl border-2 text-left transition-all ${
                              decision === DECISION.DISPUTED
                                ? "border-amber-500 bg-amber-500/10 shadow-sm"
                                : "border-slate-200 dark:border-slate-800 hover:border-amber-500/50"
                            } disabled:opacity-60 disabled:cursor-not-allowed`}
                          >
                            <div className="flex items-center gap-2 mb-1">
                              <div className={`w-5 h-5 rounded-full flex items-center justify-center ${
                                decision === DECISION.DISPUTED ? "bg-amber-500 text-white" : "border-2 border-slate-300"
                              }`}>
                                {decision === DECISION.DISPUTED && <Check className="w-3.5 h-3.5" />}
                              </div>
                              <span className="font-extrabold text-sm text-slate-900 dark:text-white">⚠ İtiraz Ediyorum</span>
                            </div>
                            <div className="text-[11px] text-slate-600 dark:text-slate-400 leading-relaxed">
                              Bulguya katılmıyorum. Sebep aşağıda belirtilecektir.
                            </div>
                          </button>
                        </div>
                      </div>

                      {/* ITIRAZ SEBEBI (sadece DISPUTED) */}
                      <AnimatePresence>
                        {decision === DECISION.DISPUTED && (
                          <motion.div
                            initial={{ opacity: 0, height: 0 }}
                            animate={{ opacity: 1, height: "auto" }}
                            exit={{ opacity: 0, height: 0 }}
                            className="space-y-2 overflow-hidden"
                          >
                            <label className="font-bold text-amber-700 dark:text-amber-400 uppercase tracking-wider text-[10px] flex items-center gap-1">
                              <AlertTriangle className="w-3 h-3" /> İtiraz Sebebi * (en az {DISPUTE_MIN_CHARS} karakter)
                            </label>
                            <textarea
                              rows={3}
                              value={dec.reason || ""}
                              onChange={(e) => updateDecisionDraft(q.id, { reason: e.target.value })}
                              disabled={isSigned}
                              placeholder="Bu bulguya neden itiraz ettiğinizi, varsa ek kanıt/olay/durumu belirtin..."
                              className="w-full bg-amber-50/30 dark:bg-amber-950/20 border border-amber-500/30 rounded-xl p-3 text-xs text-slate-900 dark:text-slate-100 focus:border-amber-500 focus:outline-none shadow-inner disabled:opacity-60"
                            />
                            <div className="text-[10px] text-slate-500 font-mono flex items-center justify-between">
                              <span>Karakter: {(dec.reason || "").trim().length} / min {DISPUTE_MIN_CHARS}</span>
                              {(dec.reason || "").trim().length >= DISPUTE_MIN_CHARS && (
                                <span className="text-emerald-600 dark:text-emerald-400 flex items-center gap-1">
                                  <Check className="w-3 h-3" /> Yeterli
                                </span>
                              )}
                            </div>
                          </motion.div>
                        )}
                      </AnimatePresence>

                      {/* TAAHHUT (sadece APPROVED) */}
                      <AnimatePresence>
                        {decision === DECISION.APPROVED && (
                          <motion.div
                            initial={{ opacity: 0, height: 0 }}
                            animate={{ opacity: 1, height: "auto" }}
                            exit={{ opacity: 0, height: 0 }}
                            className="space-y-2 overflow-hidden"
                          >
                            <label className="font-bold text-emerald-700 dark:text-emerald-400 uppercase tracking-wider text-[10px] flex items-center gap-1">
                              <PenLine className="w-3 h-3" /> Taahhüt Metni (opsiyonel, en az {COMMITMENT_MIN_CHARS} karakter)
                            </label>
                            <textarea
                              rows={2}
                              value={dec.commitment || ""}
                              onChange={(e) => updateDecisionDraft(q.id, { commitment: e.target.value })}
                              disabled={isSigned}
                              placeholder="Örn: 'Bu bulgu 15 gün içinde giderilecek, fotoğraf kanıtı yüklenecektir.'"
                              className="w-full bg-emerald-50/30 dark:bg-emerald-950/20 border border-emerald-500/30 rounded-xl p-3 text-xs text-slate-900 dark:text-slate-100 focus:border-emerald-500 focus:outline-none shadow-inner disabled:opacity-60"
                            />
                          </motion.div>
                        )}
                      </AnimatePresence>

                      {/* KAYDET BUTONU */}
                      {!isSigned && (
                        <div className="flex items-center justify-between pt-1">
                          <div className="text-[11px] text-slate-500 dark:text-slate-400 font-medium">
                            Sorumlu: <strong className="text-slate-700 dark:text-slate-300">{activeAuditDoc?.denetci || "Restoran Müdürü"}</strong>
                            {" • "}Termin: <strong className="text-amber-600 font-mono">{terminSuresi}</strong>
                          </div>
                          <button
                            type="button"
                            disabled={isSavingThis || !decision}
                            onClick={() => handleSaveDecision(q.id, q.question || q.soru)}
                            className={`inline-flex items-center gap-1.5 px-4 py-1.5 rounded-xl text-xs font-bold transition-all active:scale-95 shadow-sm ${
                              dec.saved_at && !dirty
                                ? "bg-emerald-600/10 text-emerald-700 dark:text-emerald-400 border border-emerald-500/30 hover:bg-emerald-600/20"
                                : "bg-red-600 hover:bg-red-500 text-white"
                            } disabled:opacity-50 disabled:cursor-not-allowed`}
                          >
                            {isSavingThis ? (
                              <><Loader2 className="w-3.5 h-3.5 animate-spin" /> Kaydediliyor...</>
                            ) : dec.saved_at && !dirty ? (
                              <><Check className="w-3.5 h-3.5" /> Güncelle & Kaydet</>
                            ) : (
                              <><Save className="w-3.5 h-3.5" /> 💾 Kaydet</>
                            )}
                          </button>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}

            {/* ============================================================ */}
            {/* STAGE 3: IMZA BLOGU                                          */}
            {/* ============================================================ */}
            {hayirQuestions.length > 0 && (
              <div className={`p-6 rounded-2xl border-2 space-y-4 font-sans ${
                isSigned
                  ? "border-risk-compliant-border bg-risk-compliant-bg"
                  : canSign
                  ? "border-risk-critical-border bg-risk-critical-bg shadow-elevated"
                  : "border-border-default bg-surface-card"
              }`}>
                <div className="flex items-start justify-between gap-3 border-b border-slate-200/50 dark:border-slate-800 pb-3">
                  <div>
                    <h2 className="text-lg font-extrabold text-slate-900 dark:text-white flex items-center gap-2">
                      {isSigned ? (
                        <><FileSignature className="w-5 h-5 text-emerald-500" /> İşveren Vekili Onay Belgesi (İmzalı)</>
                      ) : (
                        <><FileSignature className="w-5 h-5 text-red-500" /> 3. AŞAMA — İşveren Vekili Onayı</>
                      )}
                    </h2>
                    <p className="text-xs text-slate-600 dark:text-slate-400 mt-1 leading-relaxed max-w-3xl">
                      İşveren Vekili olarak, denetimde tespit edilen bulguları (HAYIR cevaplı sorular) yukarıda
                      {isSigned
                        ? " onayladığımı/itiraz ettiğimi, işbu belge ile yasal olarak beyan ederim."
                        : " değerlendirip onay/itiraz kararı verdiğimde, sayfanın altındaki \"Onay Belgesini İmzala\" butonu ile bu belgeyi imzalayacağım."}
                    </p>
                  </div>
                  {isSigned && (
                    <span className="px-3 py-1 rounded-full text-[11px] font-bold bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border border-emerald-500/30 flex items-center gap-1">
                      <CheckCircle2 className="w-3.5 h-3.5" /> İMZALI
                    </span>
                  )}
                </div>

                {/* KARAR OZETI */}
                <div className="grid grid-cols-3 gap-3 text-center">
                  <div className="p-3 rounded-xl bg-emerald-500/5 border border-emerald-500/20">
                    <div className="text-2xl font-extrabold text-emerald-700 dark:text-emerald-400 font-mono">
                      {decisionStats.approved}
                    </div>
                    <div className="text-[10px] font-bold text-slate-600 dark:text-slate-400 uppercase tracking-wider mt-0.5">
                      Onaylanan
                    </div>
                  </div>
                  <div className="p-3 rounded-xl bg-amber-500/5 border border-amber-500/20">
                    <div className="text-2xl font-extrabold text-amber-700 dark:text-emerald-400 font-mono">
                      {decisionStats.disputed}
                    </div>
                    <div className="text-[10px] font-bold text-slate-600 dark:text-slate-400 uppercase tracking-wider mt-0.5">
                      İtiraz Edilen
                    </div>
                  </div>
                  <div className="p-3 rounded-xl bg-slate-500/5 border border-slate-500/20">
                    <div className="text-2xl font-extrabold text-slate-700 dark:text-slate-300 font-mono">
                      {decisionStats.pending}
                    </div>
                    <div className="text-[10px] font-bold text-slate-600 dark:text-slate-400 uppercase tracking-wider mt-0.5">
                      Bekleyen
                    </div>
                  </div>
                </div>

                {/* IMZALANABILIRLIK KONTROLU */}
                {!isSigned && (
                  <div className="space-y-2">
                    {decisionStats.pending > 0 && (
                      <div className="p-3 rounded-xl bg-amber-500/10 border border-amber-500/30 text-xs text-amber-700 dark:text-amber-400 flex items-center gap-2">
                        <AlertTriangle className="w-4 h-4 shrink-0" />
                        <span><strong>{decisionStats.pending}</strong> soru hâlâ karar bekliyor. İmzalamadan önce tüm kararlar verilmelidir.</span>
                      </div>
                    )}
                    {decisionStats.dirty > 0 && (
                      <div className="p-3 rounded-xl bg-amber-500/10 border border-amber-500/30 text-xs text-amber-700 dark:text-amber-400 flex items-center gap-2">
                        <AlertTriangle className="w-4 h-4 shrink-0" />
                        <span><strong>{decisionStats.dirty}</strong> karar kaydedilmemiş. Lütfen önce sayfanın üstündeki "Kaydet" butonlarını kullanın.</span>
                      </div>
                    )}
                    {!metaForm.rep_name?.trim() && (
                      <div className="p-3 rounded-xl bg-red-500/10 border border-red-500/30 text-xs text-red-700 dark:text-red-400 flex items-center gap-2">
                        <AlertTriangle className="w-4 h-4 shrink-0" />
                        <span>İşveren vekili adı zorunludur.</span>
                      </div>
                    )}
                  </div>
                )}

                {/* IMZALA / INDIR BUTONLARI */}
                <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 pt-2">
                  {isSigned ? (
                    <>
                      <div className="text-xs text-slate-600 dark:text-slate-400 flex items-center gap-2">
                        <ShieldCheck className="w-4 h-4 text-emerald-500" />
                        <span>İmza: <strong>{metaForm.signed_by_rep_name || metaForm.rep_name}</strong></span>
                        <span>•</span>
                        <span>{new Date(metaForm.signed_at).toLocaleString("tr-TR")}</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <button
                          type="button"
                          onClick={() => window.print()}
                          className="inline-flex items-center justify-center gap-2 px-4 py-2 rounded-xl text-xs font-bold bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-200 transition-all active:scale-95"
                        >
                          <Printer className="w-4 h-4" /> Yazdır
                        </button>
                        <button
                          type="button"
                          className="inline-flex items-center justify-center gap-2 px-4 py-2 rounded-xl text-xs font-bold bg-slate-100 dark:bg-slate-800 text-slate-500 cursor-not-allowed"
                          disabled
                          title="PDF indirme sonraki sprint'te"
                        >
                          <Download className="w-4 h-4" /> PDF
                        </button>
                      </div>
                    </>
                  ) : (
                    <button
                      type="button"
                      onClick={handleSign}
                      disabled={!canSign || !metaForm.rep_name?.trim() || signing}
                      className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-8 py-3 rounded-xl text-sm font-extrabold bg-risk-critical hover:bg-risk-critical-2 text-white shadow-card transition-all active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed disabled:bg-ink-tertiary"
                    >
                      {signing ? (
                        <><Loader2 className="w-4 h-4 animate-spin" /> İmzalanıyor...</>
                      ) : (
                        <><FileSignature className="w-5 h-5" /> Onay Belgesini İmzala</>
                      )}
                    </button>
                  )}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </AppShell>
  );
}
