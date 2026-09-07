import { useCallback, useEffect, useMemo, useState } from "react";
import AppShell from "@/components/AppShell";
import api from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { useBrand } from "@/context/BrandContext";
import { getCategoryQuestionNumber } from "@/lib/risk";
import { DOF } from "@/constants/testIds/dof";
import PhotoUploader from "@/components/PhotoUploader";
import DofApproveModal from "@/components/DofApproveModal";
import BranchHealthCard from "@/components/BranchHealthCard";
import DeadlineCountdown from "@/components/DeadlineCountdown";
import DofTimeline from "@/components/DofTimeline";
import RegulatoryInfoPanel from "@/components/RegulatoryInfoPanel";
import {
  filterDofs,
  buildUpdatePayload,
  validateKapatildiNotes,
  applyPutResponseToItem,
  computeKpis,
  formatUpdatedAt,
  isDirty,
  normalizeNotes,
  MAX_NOTES_LENGTH,
  STATUS_FILTER_OPTIONS,
  DOF_STATUSES,
} from "@/lib/dof";
import { toast } from "sonner";
import {
  AlertTriangle,
  Building2,
  CheckCircle2,
  FileText,
  Loader2,
  RefreshCw,
  Search,
  ShieldAlert,
  ScrollText,
  User as UserIcon,
  Wrench,
  CheckCheck,
  UserCheck,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { motion, AnimatePresence } from "framer-motion";

function cardKey(item) {
  return `${item.audit_id}_${item.question_id}`;
}

// Display precedence for the question number label:
//   1. ``category_question_no`` — backend-computed "1.3" form
//   2. ``getCategoryQuestionNumber(item)`` — frontend fallback for
//      legacy payloads / precomputed category numbering
//   3. ``item.question_no`` — legacy numeric value (int)
//   4. ``item.question_id`` — last-resort id-based fallback
function displayQuestionNo(item) {
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

function initialDraft(item) {
  return {
    status: item?.status ?? "AÇIK",
    notes: item?.notes ?? "",
  };
}

function statusFilterClasses(optValue, active) {
  // Tüm durum butonlarında aktif/pasif state arasında 1px border korunur
  // (1px border-transparent / 1px border-X) — geometri kayması yok.
  if (!active) {
    return "bg-surface-card text-ink-secondary border border-border-default hover:bg-surface-card-2 hover:text-ink-primary";
  }
  switch (optValue) {
    case "AÇIK":
      return "bg-risk-critical text-white border border-risk-critical shadow-sm";
    case "İŞLEMDE":
      return "bg-risk-moderate text-white border border-risk-moderate shadow-sm";
    case "KAPATILDI":
      return "bg-risk-compliant text-white border border-risk-compliant shadow-sm";
    case "HEPSİ":
      return "bg-ink-primary text-ink-inverse border border-border-strong shadow-sm";
    default:
      return "bg-ink-primary text-ink-inverse border border-border-strong shadow-sm";
  }
}

function statusControlClasses(s, active, disabled) {
  // DofCard içindeki durum kontrol butonları — geometri sabit.
  // inactive: border-transparent ile 1px yer kaplar → aktif/pasif geçişte
  //   left/top kenarı kaymaz.
  if (!active) {
    return disabled
      ? "text-ink-tertiary opacity-60 cursor-not-allowed border border-transparent"
      : "text-ink-secondary hover:text-ink-primary hover:bg-surface-card-2 border border-transparent";
  }
  switch (s) {
    case "AÇIK":
      return "bg-risk-critical text-white border border-risk-critical";
    case "İŞLEMDE":
      return "bg-risk-moderate text-white border border-risk-moderate";
    case "KAPATILDI":
      return "bg-risk-compliant text-white border border-risk-compliant";
    default:
      return "bg-ink-primary text-ink-inverse border border-border-strong";
  }
}

function IsolatedDofNoteBox({ item, initialNotes, onNotesChange, onSave, isSaving, updatedAt, canSaveBase, canCloseDof }) {
  const [val, setVal] = useState(initialNotes || "");

  useEffect(() => {
    setVal(initialNotes || "");
  }, [initialNotes]);

  const handleChange = (e) => {
    setVal(e.target.value);
  };

  const handleBlur = () => {
    if (val !== initialNotes) {
      onNotesChange(item, val);
    }
  };

  const handleSaveClick = () => {
    onNotesChange(item, val);
    onSave(item, val);
  };

  const trimmed = val.trim();
  const tooLong = trimmed.length > MAX_NOTES_LENGTH;
  const isDirtyLocal = trimmed !== (initialNotes || "").trim();
  const canSave = canSaveBase || isDirtyLocal;

  return (
    <div className="space-y-3 font-sans">
      <div className="space-y-1.5 font-sans">
        <span className="text-[11px] font-sans text-ink-secondary flex items-center gap-1.5 font-bold">
          <FileText className="w-3.5 h-3.5 text-risk-compliant" /> SAHA DÜZELTME AÇIKLAMASI:
        </span>
        <textarea
          rows={3}
          maxLength={MAX_NOTES_LENGTH + 50}
          placeholder="Düzeltici faaliyet açiklamasini ve saha notunu girin..."
          value={val}
          onChange={handleChange}
          onBlur={handleBlur}
          disabled={isSaving}
          data-testid={DOF.notesTextarea}
          className={`w-full bg-surface-card-2 border text-xs text-ink-primary p-3.5 rounded-control placeholder:text-ink-tertiary focus:outline-none transition-colors duration-standard ease-swift font-sans ${
            tooLong
              ? "border-risk-critical focus:border-risk-critical focus:ring-2 focus:ring-risk-critical/20 text-risk-critical"
              : "border-border-default focus:border-border-focus focus:ring-2 focus:ring-risk-critical/20"
          }`}
        />
        <div className="flex items-center justify-between text-[11px] font-sans text-ink-secondary">
          <span
            data-testid={DOF.notesCounter}
            className={
              tooLong
                ? "text-risk-critical font-bold"
                : trimmed.length > MAX_NOTES_LENGTH - 100
                ? "text-risk-moderate"
                : "text-ink-secondary font-mono"
            }
          >
            {trimmed.length}/{MAX_NOTES_LENGTH}
          </span>
          {updatedAt && (
            <span className="text-ink-secondary font-mono">
              Son güncelleme: {updatedAt}
            </span>
          )}
        </div>
      </div>

      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pt-1 font-sans">
        {!canCloseDof && (
          <span className="text-[10px] text-risk-moderate font-sans flex items-center gap-1">
            * Kanıt fotoğrafı yüklediğinizde DÖF otomatik 'İŞLEMDE' durumuna geçer ve İSG Uzmanı onayına sunulur.
          </span>
        )}
        <div className="flex items-center gap-2 ml-auto">
          <button
            type="button"
            onClick={handleSaveClick}
            disabled={!canSave || isSaving}
            data-testid={DOF.notesSave}
            className={`px-5 py-2.5 rounded-control text-xs font-sans font-semibold flex items-center gap-2 transition-colors duration-standard ease-swift border ${
              canSave && !isSaving
                ? "bg-action-primary hover:bg-action-primary-hover text-action-primary-foreground border border-transparent cursor-pointer"
                : "bg-surface-card-2 text-ink-tertiary border border-border-default cursor-not-allowed"
            }`}
          >
            {isSaving ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                <span>Kaydediliyor…</span>
              </>
            ) : (
              <span>Değişiklikleri Kaydet</span>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}

function draftFor(drafts, key, item) {
  return drafts[key] ?? initialDraft(item);
}

const ALL_SORT_OPTIONS = [
  { value: "risk_desc", label: "🔴 En Yüksek Risk (Skor: 25 → 1)" },
  { value: "risk_asc", label: "🟢 En Düşük Risk (Skor: 1 → 25)" },
  { value: "date_desc", label: "📅 En Yeni Tarihli DÖF'ler" },
  { value: "deadline_asc", label: "⏳ Termini Yaklaşanlar" },
  { value: "restaurant_asc", label: "🔤 Restoran Adı (A - Z)", requiresAllBranches: true },
  { value: "restaurant_desc", label: "🔤 Restoran Adı (Z - A)", requiresAllBranches: true },
];

export default function DofPage() {
  const { user, formatApiErrorDetail } = useAuth();
  const userRole = user?.role || "user";
  const canCloseDof = ["admin", "yönetici", "isg_uzmani"].includes(userRole);
  const isAdmin = userRole === "admin" || userRole === "yönetici";

  const [dofs, setDofs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [fetchError, setFetchError] = useState(null);

  const [statusFilter, setStatusFilter] = useState("HEPSİ");
  const [riskFilter, setRiskFilter] = useState("HEPSİ");
  const [selectedBranch, setSelectedBranch] = useState("HEPSİ");
  const [sortBy, setSortBy] = useState("risk_desc");
  const [search, setSearch] = useState("");

  const [drafts, setDrafts] = useState({});
  const [savingKeys, setSavingKeys] = useState(() => new Set());
  const [approveTargetItem, setApproveTargetItem] = useState(null);

  const fetchDofs = useCallback(async ({ silent = false } = {}) => {
    if (!silent) {
      setLoading(true);
      setFetchError(null);
    }
    try {
      const res = await api.get("/dofs");
      const list = Array.isArray(res?.data) ? res.data : [];
      setDofs(list);
      setDrafts((prev) => {
        const next = {};
        for (const item of list) {
          const key = cardKey(item);
          const serverDraft = initialDraft(item);
          const prevDraft = prev[key];
          // During a silent background refresh (save/approve) we must not
          // overwrite in-flight local edits. A prevDraft that diverges from
          // the server snapshot — typed-but-not-yet-saved notes, or a
          // status the user picked locally — is kept as-is so the
          // IsolatedDofNoteBox's ``initialNotes`` prop stays stable and
          // does not trigger its reset effect. Matching prevDrafts are
          // refreshed from the server (visually a no-op).
          if (
            silent &&
            prevDraft &&
            (prevDraft.status !== serverDraft.status ||
              prevDraft.notes !== serverDraft.notes)
          ) {
            next[key] = prevDraft;
          } else {
            next[key] = serverDraft;
          }
        }
        return next;
      });
    } catch (err) {
      const detail = formatApiErrorDetail ? formatApiErrorDetail(err) : null;
      const msg = detail || err?.message || "DÖF listesi yüklenemedi.";
      if (!silent) {
        setFetchError(msg);
      }
      toast.error(msg);
    } finally {
      if (!silent) {
        setLoading(false);
      }
    }
  }, [formatApiErrorDetail]);

  useEffect(() => {
    fetchDofs();
  }, [fetchDofs]);

  // Dynamic available sort options based on branch selection
  const availableSortOptions = useMemo(() => {
    if (selectedBranch === "HEPSİ") {
      return ALL_SORT_OPTIONS;
    }
    return ALL_SORT_OPTIONS.filter((opt) => !opt.requiresAllBranches);
  }, [selectedBranch]);

  // Fallback to risk_desc if selected branch changes and current sortBy is restaurant name
  useEffect(() => {
    if (selectedBranch !== "HEPSİ" && (sortBy === "restaurant_asc" || sortBy === "restaurant_desc")) {
      setSortBy("risk_desc");
    }
  }, [selectedBranch, sortBy]);

  // Unique branch list
  const branchOptions = useMemo(() => {
    const set = new Set();
    dofs.forEach((item) => {
      if (item.restaurant_name) set.add(item.restaurant_name);
    });
    return ["HEPSİ", ...Array.from(set)];
  }, [dofs]);

  const kpis = useMemo(() => computeKpis(dofs), [dofs]);

  const { selectedBrand } = useBrand();

  // Filter by status, risk, search, brand and branch
  const filteredDofs = useMemo(() => {
    let list = filterDofs(dofs, {
      status: statusFilter,
      riskLevel: riskFilter,
      search,
      brand: selectedBrand,
    });
    if (selectedBranch !== "HEPSİ") {
      list = list.filter(
        (x) => (x.restaurant_name || "").toLowerCase() === selectedBranch.toLowerCase()
      );
    }
    return list;
  }, [dofs, statusFilter, riskFilter, search, selectedBrand, selectedBranch]);

  // Sort DÖFs based on selected criteria
  const sortedDofs = useMemo(() => {
    const list = [...filteredDofs];
    switch (sortBy) {
      case "risk_desc":
        return list.sort(
          (a, b) => (b.risk_score ?? b.default_risk_score ?? 0) - (a.risk_score ?? a.default_risk_score ?? 0)
        );
      case "risk_asc":
        return list.sort(
          (a, b) => (a.risk_score ?? a.default_risk_score ?? 0) - (b.risk_score ?? b.default_risk_score ?? 0)
        );
      case "date_desc":
        return list.sort(
          (a, b) => new Date(b.audit_date || b.updated_at || 0) - new Date(a.audit_date || a.updated_at || 0)
        );
      case "deadline_asc": {
        const getDueMs = (item) => {
          // Backend "Sürekli" terminli sorular için due_date=null döner —
          // bunlar en yakın deadline (0) olmalı çünkü "anında müdahale"
          // edilmeli, deadline hesaplanmamalı.
          if (item.due_date) return new Date(item.due_date).getTime();
          // Deadline string "Sürekli" içeriyorsa veya due_date null ise
          // sıfır döndür (en yakın).
          const dStr = String(item.deadline || "").toLowerCase();
          if (dStr.includes("sürekli") || dStr.includes("surekli")) return 0;
          // Fallback: deadline string'den tahmin
          const created = new Date(item.created_at || item.audit_date || Date.now()).getTime();
          const days = dStr.includes("1") ? 30 : dStr.includes("2") ? 60 : 90;
          return created + days * 86400000;
        };
        return list.sort((a, b) => getDueMs(a) - getDueMs(b));
      }
      case "restaurant_asc":
        return list.sort((a, b) => (a.restaurant_name || "").localeCompare(b.restaurant_name || "", "tr"));
      case "restaurant_desc":
        return list.sort((a, b) => (b.restaurant_name || "").localeCompare(a.restaurant_name || "", "tr"));
      default:
        return list;
    }
  }, [filteredDofs, sortBy]);

  const handleStatusClick = useCallback(
    (item, nextStatus) => {
      // Mandatory photo check for İŞLEMDE
      if (nextStatus === "İŞLEMDE") {
        const totalPhotos = (item.photos?.finding?.length || 0) + (item.photos?.resolution?.length || 0);
        if (totalPhotos === 0) {
          toast.error("DÖF'ü İŞLEMDE durumuna almak için en az 1 adet saha düzeltme kanıt fotoğrafı yüklemeniz gerekmektedir.");
          return;
        }
      }

      // Authorization check for KAPATILDI
      if (nextStatus === "KAPATILDI") {
        if (!canCloseDof) {
          toast.error(
            "DÖF kapatma yetkisi yalnızca İSG Uzmanı / Admin hesaplarına aittir. Çözüm kanıt fotoğrafı ekleyerek İSG Uzmanı onayına sunabilirsiniz."
          );
          return;
        }
        setApproveTargetItem(item);
        return;
      }

      const key = cardKey(item);
      setDrafts((prev) => {
        const current = prev[key] ?? initialDraft(item);
        if (current.status === nextStatus) return prev;
        return {
          ...prev,
          [key]: { ...current, status: nextStatus },
        };
      });
    },
    [canCloseDof]
  );

  const handleNotesChange = useCallback((item, nextNotes) => {
    const key = cardKey(item);
    setDrafts((prev) => {
      const current = prev[key] ?? initialDraft(item);
      return {
        ...prev,
        [key]: { ...current, notes: nextNotes },
      };
    });
  }, []);

  const handleSave = useCallback(
    async (item, overrideNotes) => {
      const key = cardKey(item);
      const currentDraft = drafts[key] ?? initialDraft(item);
      const draft = {
        ...currentDraft,
        notes: overrideNotes !== undefined ? overrideNotes : currentDraft.notes,
      };

      const validation = validateKapatildiNotes(draft);
      if (!validation.ok) {
        toast.error(validation.message || "Doğrulama hatası");
        return;
      }

      setSavingKeys((prev) => new Set(prev).add(key));
      try {
        const payload = buildUpdatePayload(item, draft);
        const url = `/dofs/${item.audit_id}/${item.question_id}`;
        const res = await api.put(url, payload);

        // PUT response is wrapped: ``{status: "success", dof: {...}}``.
        // ``applyPutResponseToItem`` expects the inner ``dof`` object so
        // the canonical merged item carries the new status / notes;
        // passing the wrapper would have surfaced ``"success"`` as the
        // status and left notes at the previous (potentially empty)
        // value. ``?? res.data`` keeps backwards compat with any caller
        // that historically gets the dof object directly.
        const updatedItem = applyPutResponseToItem(
          item,
          res?.data?.dof ?? res?.data
        );

        setDofs((prevList) =>
          prevList.map((x) => (cardKey(x) === key ? updatedItem : x))
        );

        setDrafts((prevDrafts) => ({
          ...prevDrafts,
          [key]: initialDraft(updatedItem),
        }));

        toast.success(
          updatedItem.status === "KAPATILDI"
            ? "DÖF İSG Uzmanı tarafından ONAYLANDI ve KAPATILDI!"
            : `DÖF güncellendi (${updatedItem.status})`
        );

        // Background refresh — silent mode keeps existing cards rendered
        // and avoids flashing the full-page skeleton; the just-saved card
        // is already up-to-date via the optimistic update above.
        await fetchDofs({ silent: true });
      } catch (err) {
        const detail = formatApiErrorDetail ? formatApiErrorDetail(err) : null;
        const msg = detail || err?.response?.data?.detail || err?.message || "DÖF güncellenemedi.";
        toast.error(msg);
      } finally {
        setSavingKeys((prev) => {
          const next = new Set(prev);
          next.delete(key);
          return next;
        });
      }
    },
    [drafts, fetchDofs, formatApiErrorDetail]
  );

  const handleApproveConfirm = useCallback(
    async (item, resolutionNote) => {
      const key = cardKey(item);
      setSavingKeys((prev) => new Set(prev).add(key));
      try {
        // resolved_at / resolved_by server-controlled — client göndermez.
        const payload = {
          status: "KAPATILDI",
          notes: resolutionNote,
          resolution_note: resolutionNote,
        };
        const url = `/dofs/${item.audit_id}/${item.question_id}`;
        const res = await api.put(url, payload);

        // Server payload'unda resolved_at / resolved_by yok; server bunları
        // response ile dönmüyor (küçük payload). Card üzerindeki resolved_at
        // backend'in tutarlı response'u için reload'a bırakılır; burada
        // ``nowIso`` UI'ın optimistic update'i için kullanılır.
        const nowIso = new Date().toISOString();
        const updatedItem = {
          ...item,
          status: "KAPATILDI",
          notes: resolutionNote,
          resolution_note: resolutionNote,
          resolved_at: nowIso,
          updated_at: nowIso,
        };

        setDofs((prevList) =>
          prevList.map((x) => (cardKey(x) === key ? updatedItem : x))
        );

        setDrafts((prevDrafts) => ({
          ...prevDrafts,
          [key]: { status: "KAPATILDI", notes: resolutionNote },
        }));

        toast.success("DÖF aksiyonu İSG Uzmanı tarafından ONAYLANDI ve KAPATILDI!");
        setApproveTargetItem(null);

        // Background refresh — silent mode keeps cards visible and avoids
        // the skeleton flash; the approved card is already canonical via
        // the optimistic update above.
        await fetchDofs({ silent: true });
      } catch (err) {
        const detail = formatApiErrorDetail ? formatApiErrorDetail(err) : null;
        const msg = detail || err?.response?.data?.detail || err?.message || "DÖF kapatılamadı.";
        toast.error(msg);
      } finally {
        setSavingKeys((prev) => {
          const next = new Set(prev);
          next.delete(key);
          return next;
        });
      }
    },
    [formatApiErrorDetail, fetchDofs]
  );

  const handlePhotosChange = useCallback((item, updatedPhotos, type, nextModifyCount) => {
    const key = cardKey(item);
    setDofs((prevList) =>
      prevList.map((x) => {
        if (cardKey(x) === key) {
          const existingPhotos = x.photos || { finding: [], resolution: [] };
          return {
            ...x,
            photo_modify_count: nextModifyCount ?? (x.photo_modify_count || 0) + 1,
            photos: { ...existingPhotos, [type]: updatedPhotos },
          };
        }
        return x;
      })
    );
    if (type === "resolution") {
      handleStatusClick(item, "İŞLEMDE");
    }
  }, [handleStatusClick]);

  const updatedAtText = useCallback(
    (iso) => formatUpdatedAt(iso),
    []
  );

  return (
    <AppShell>
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
        className="space-y-6 font-sans"
        data-testid={DOF.page}
      >
        {/* HEADER TITLE */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-border-default pb-5">
          <div className="space-y-1 font-sans">
            <h1 className="text-2xl sm:text-3xl font-extrabold text-ink-primary tracking-tight font-sans flex items-center gap-2.5">
              <ShieldAlert className="w-7 h-7 text-risk-moderate" />
              DÖF Takip & Aksiyon Yönetimi
            </h1>
            <p className="text-xs text-ink-secondary font-sans leading-relaxed">
              Saha denetimi uygunsuzluk fotoğrafları, çözüm kanıt yüklemeleri ve İSG Uzmanı onaylı kapatma süreci.
            </p>
          </div>
          <button
            type="button"
            onClick={fetchDofs}
            disabled={loading}
            data-testid={DOF.refresh}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-control text-xs font-sans font-semibold bg-surface-card text-ink-primary border border-border-default hover:bg-surface-card-2 hover:text-ink-primary transition-colors duration-standard ease-swift self-start sm:self-auto cursor-pointer"
          >
            <RefreshCw className={`w-3.5 h-3.5 text-risk-compliant ${loading ? "animate-spin" : ""}`} />
            <span>Yenile</span>
          </button>
        </div>

        {/* VERCEL KPIS GRID */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4" data-testid="dof-kpis">
          <Kpi label="TOPLAM DÖF" value={kpis.total} testId={DOF.kpi.total} />
          <Kpi label="AÇIK / İŞLEMDE" value={kpis.acik} testId={DOF.kpi.acik} />
          <Kpi label="KAPATILDI" value={kpis.kapatildi} testId={DOF.kpi.kapatildi} />
          <Kpi label="KRİTİK RİSK (KABUL EDİLEMEZ)" value={kpis.kabulEdilemez} testId={DOF.kpi.kabulEdilemez} />
        </div>

        {/* FILTERS & SORTING CARD */}
        <div className="rounded-card border border-border-default bg-surface-card p-4 sm:p-5 space-y-4 font-sans">
          <div className="flex flex-col md:flex-row gap-4 items-stretch md:items-center justify-between">
            {/* SEARCH INPUT */}
            <div className="relative flex-1">
              <Search className="w-4 h-4 text-ink-tertiary absolute left-3.5 top-1/2 -translate-y-1/2" />
              <input
                type="search"
                placeholder="Restoran, soru, kategori veya sorumlu ara…"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="w-full bg-surface-card-2 border border-border-default rounded-control pl-10 pr-4 py-2.5 text-xs text-ink-primary placeholder:text-ink-tertiary focus:outline-none focus:border-border-focus focus:ring-2 focus:ring-risk-critical/20 transition-colors duration-standard ease-swift font-sans"
                data-testid={DOF.filters.search}
              />
            </div>

            {/* BRANCH SELECTOR DROPDOWN */}
            <div className="w-full md:w-56">
              <Select value={selectedBranch} onValueChange={setSelectedBranch}>
                <SelectTrigger className="bg-surface-card-2 border border-border-default text-xs text-ink-primary font-sans h-10 rounded-control focus:border-border-focus focus:ring-2 focus:ring-risk-critical/20">
                  <SelectValue placeholder="Tüm Şubeler" />
                </SelectTrigger>
                <SelectContent className="bg-surface-card border border-border-default text-ink-primary font-sans text-xs">
                  {branchOptions.map((b) => (
                    <SelectItem key={b} value={b} className="hover:bg-surface-card-2 focus:bg-surface-card-2">
                      {b === "HEPSİ" ? "Tüm Şubeler / Restoranlar" : b}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* ADVANCED SORTING DROPDOWN (GÖREV 2) */}
            <div className="w-full md:w-60 flex items-center gap-2">
              <Select value={sortBy} onValueChange={setSortBy}>
                <SelectTrigger className="bg-surface-card-2 border border-border-default text-xs text-ink-primary font-sans h-10 rounded-control focus:border-border-focus focus:ring-2 focus:ring-risk-critical/20 w-full">
                  <SelectValue placeholder="Sıralama ölçütü" />
                </SelectTrigger>
                <SelectContent className="bg-surface-card border border-border-default text-ink-primary font-sans text-xs">
                  {availableSortOptions.map((opt) => (
                    <SelectItem key={opt.value} value={opt.value} className="hover:bg-surface-card-2 focus:bg-surface-card-2 font-sans">
                      {opt.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          {/* STATUS BUTTONS */}
          <div className="flex flex-wrap items-center gap-2 pt-2 border-t border-border-default font-sans">
            <span className="text-xs font-sans text-ink-secondary mr-2 font-medium">Durum Filtresi:</span>
            {STATUS_FILTER_OPTIONS.map((opt) => (
              <button
                key={opt}
                type="button"
                onClick={() => setStatusFilter(opt)}
                data-testid={
                  opt === "HEPSİ"
                    ? DOF.filters.statusAll
                    : opt === "AÇIK"
                    ? DOF.filters.statusAcik
                    : opt === "İŞLEMDE"
                    ? DOF.filters.statusIslemde
                    : DOF.filters.statusKapatildi
                }
                className={`px-3.5 py-1.5 rounded-control text-xs font-sans font-bold transition-colors duration-standard ease-swift cursor-pointer active:scale-95 ${statusFilterClasses(opt, statusFilter === opt)}`}
              >
                {opt}
              </button>
            ))}
          </div>
        </div>

        {/* BRANCH HEALTH SUMMARY BANNER (IF SPECIFIC BRANCH IS SELECTED) */}
        {selectedBranch !== "HEPSİ" && (
          <BranchHealthCard branchName={selectedBranch} items={dofs} audits={[]} />
        )}

        {/* SORTED DOF LIST */}
        {loading ? (
          <DofListSkeleton />
        ) : fetchError ? (
          <ErrorBanner message={fetchError} onRetry={fetchDofs} testId={DOF.error} />
        ) : sortedDofs.length === 0 ? (
          <EmptyState testId={DOF.empty} />
        ) : (
          <motion.div layout className="space-y-4">
            <AnimatePresence>
              {sortedDofs.map((item) => (
                <DofCard
                  key={cardKey(item)}
                  item={item}
                  draft={draftFor(drafts, cardKey(item), item)}
                  isSaving={savingKeys.has(cardKey(item))}
                  canCloseDof={canCloseDof}
                  isAdmin={isAdmin}
                  onStatusClick={handleStatusClick}
                  onNotesChange={handleNotesChange}
                  onSave={handleSave}
                  onPhotosChange={handlePhotosChange}
                  formatDate={updatedAtText}
                />
              ))}
            </AnimatePresence>
          </motion.div>
        )}

        {/* İSG EXPERT APPROVAL MODAL */}
        <DofApproveModal
          item={approveTargetItem}
          isOpen={Boolean(approveTargetItem)}
          onClose={() => setApproveTargetItem(null)}
          onConfirm={handleApproveConfirm}
          isSaving={approveTargetItem ? savingKeys.has(cardKey(approveTargetItem)) : false}
        />
      </motion.div>
    </AppShell>
  );
}

function Kpi({ label, value, testId }) {
  return (
    <div
      className="rounded-card border border-border-default bg-surface-card p-5 transition-colors duration-standard ease-swift font-sans"
      data-testid={testId}
    >
      <div className="text-[11px] font-sans font-semibold uppercase tracking-wider text-ink-secondary">{label}</div>
      <div className="text-3xl md:text-4xl font-extrabold mt-2 font-mono tabular-nums text-ink-primary">
        {value}
      </div>
    </div>
  );
}

function EmptyState({ testId }) {
  return (
    <div data-testid={testId} className="py-16 text-center rounded-card border border-dashed border-border-default bg-surface-card-2 space-y-2 font-sans">
      <CheckCircle2 className="w-8 h-8 text-risk-compliant mx-auto opacity-80" />
      <p className="text-base font-bold text-ink-primary tracking-tight font-sans">Kayıtlı DÖF Bulunamadı</p>
      <p className="text-xs text-ink-secondary font-sans">Filtrelerle eşleşen bir uygunsuzluk kaydı bulunmuyor.</p>
    </div>
  );
}

function ErrorBanner({ message, onRetry, testId }) {
  return (
    <div data-testid={testId} className="rounded-card border border-risk-critical-border bg-risk-critical-bg p-4 flex items-center justify-between gap-3 font-sans">
      <div className="flex items-center gap-2 text-risk-critical text-xs font-sans">
        <AlertTriangle className="w-4 h-4 shrink-0" />
        <div>
          <div className="font-bold">DÖF Listesi Yüklenemedi</div>
          <div className="text-[11px] text-risk-critical/80">{message}</div>
        </div>
      </div>
      <Button size="sm" variant="outline" onClick={onRetry} className="border-risk-critical-border text-risk-critical hover:bg-risk-critical-bg rounded-control text-xs font-sans">
        Yeniden Dene
      </Button>
    </div>
  );
}

function DofListSkeleton() {
  return (
    <div className="space-y-4" data-testid={DOF.loading}>
      {[0, 1, 2].map((i) => (
        <div key={i} className="rounded-card border border-border-default bg-surface-card p-5 space-y-3 font-sans">
          <Skeleton className="h-4 w-1/3 bg-surface-card-2" />
          <Skeleton className="h-3 w-1/2 bg-surface-card-2" />
          <Skeleton className="h-16 w-full bg-surface-card-2" />
        </div>
      ))}
    </div>
  );
}

function DofCard({
  item,
  draft,
  isSaving,
  canCloseDof,
  isAdmin,
  onStatusClick,
  onNotesChange,
  onSave,
  onPhotosChange,
  formatDate,
}) {
  const key = cardKey(item);
  const dirty = isDirty(item, draft);
  const trimmed = normalizeNotes(draft.notes);
  const tooLong = trimmed.length > MAX_NOTES_LENGTH;
  const validation = validateKapatildiNotes(draft);
  const canSave = !isSaving && dirty && !tooLong && validation.ok;

  const updatedAt = formatDate(item.updated_at);
  const isKabulEdilemez = item.risk_level === "Kabul Edilemez" || (item.risk_score != null && item.risk_score >= 13);

  const questionText = item.question || item.soru || "";
  const categoryName = item.category || item.kategori || "İSG";
  const areaName = item.area || item.alan || categoryName;
  const responsiblePerson = item.responsible || item.sorumlu || "Restoran Sorumlusu";
  const deadlinePeriod = item.deadline || item.termin || (isKabulEdilemez ? "1 Ay" : "3 Ay");
  const correctiveActionText = item.corrective_action || item.tedbir || item.alinmasi_gereken_tedbir || "";

  const findingPhotos = item.photos?.finding || [];
  const resolutionPhotos = item.photos?.resolution || [];
  const modifyCount = item.photo_modify_count || 0;

  const legalBasis = useMemo(() => {
    if (Array.isArray(item.legal_basis)) return item.legal_basis.filter(Boolean);
    if (Array.isArray(item.mevzuat)) return item.mevzuat.filter(Boolean);
    if (typeof item.legal_basis === "string" && item.legal_basis.trim()) {
      return item.legal_basis.split(/\r?\n|;|\s*,\s*/).map((s) => s.trim()).filter(Boolean);
    }
    if (typeof item.mevzuat === "string" && item.mevzuat.trim()) {
      return item.mevzuat.split(/\r?\n|;|\s*,\s*/).map((s) => s.trim()).filter(Boolean);
    }
    return [];
  }, [item.legal_basis, item.mevzuat]);

  const showDocLevel =
    item.document_risk_level &&
    item.document_risk_level !== item.risk_level;

  // Save butonu IsolatedDofNoteBox içinde (editor altında) — local val
  // divergence + server draft divergence'yi "canSave" olarak kapsayan
  // contract (PR0 + S18 hardening) bu component ile korunur.
  // Tip: not tasarrufu esnasında card/page jump yok (1px border her zaman).

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, scale: 0.98 }}
      transition={{ duration: 0.25 }}
      className="rounded-card border border-border-default bg-surface-card shadow-sm p-5 md:p-6 space-y-4 transition-colors duration-standard ease-swift relative overflow-hidden font-sans"
      data-testid={DOF.card}
    >
      {/* Left indicator bar — flat risk-color stripe (neon glow kaldırıldı) */}
      <div
        aria-hidden="true"
        className={`absolute left-0 top-0 bottom-0 w-1.5 ${isKabulEdilemez ? "bg-risk-critical" : "bg-risk-moderate"}`}
      />

      {/* CARD MAIN FLEX LAYOUT (LEFT DETAILS + RIGHT ACTION RAIL) */}
      <div className="flex flex-col lg:flex-row gap-6 pl-2">

        {/* LEFT FLEX-1 MAIN SECTION */}
        <div className="flex-1 min-w-0 space-y-4 font-sans">

          {/* HEADER TAGS & QUESTION TITLE */}
          <div className="space-y-1.5 font-sans">
            <div className="flex flex-wrap items-center gap-2 text-xs font-sans">
              <span className="text-risk-critical font-bold flex items-center gap-1 font-mono">
                <Building2 className="w-3.5 h-3.5" /> {item.restaurant_name || "(restoran adı yok)"}
              </span>
              <span className="text-ink-tertiary">•</span>
              <span className="text-ink-secondary bg-surface-card-2 border border-border-default px-2 py-0.5 rounded-xs font-sans">
                [{categoryName}]
              </span>
              {areaName && areaName !== categoryName && (
                <>
                  <span className="text-ink-tertiary">•</span>
                  <span className="text-ink-secondary font-sans">Alan: {areaName}</span>
                </>
              )}
              <span className="text-ink-tertiary">•</span>
              <span className="text-ink-secondary font-mono text-[11px]">Tarih: {item.audit_date || "—"}</span>
            </div>

            <h3 className="text-base font-bold text-ink-primary tracking-tight leading-snug font-sans">
              Soru #{displayQuestionNo(item)}: {questionText}
            </h3>
          </div>

          {/* LEGAL BASIS MEVZUAT PILLS */}
          {legalBasis.length > 0 && (
            <div className="flex flex-wrap gap-1.5 font-mono text-xs">
              <span className="text-[10px] text-ink-secondary font-sans font-bold flex items-center gap-1 self-center mr-1">
                <ScrollText className="w-3 h-3 text-ink-tertiary" /> MEVZUAT:
              </span>
              {legalBasis.map((basis, idx) => (
                <span key={`${key}-lb-${idx}`} className="bg-surface-card-2 text-ink-secondary border border-border-default px-2.5 py-0.5 rounded-xs text-[11px] font-mono">
                  {basis}
                </span>
              ))}
            </div>
          )}

          {/* YASAL YAPTIRIM PANELİ (Phase 2B — U4) */}
          <RegulatoryInfoPanel questionId={item.question_id} variant="compact" />

          {/* HAZIR DÖF TEDBİR METNİ (CORRECTIVE ACTION BOX) */}
          {correctiveActionText && (
            <div className="p-3.5 rounded-control border border-risk-moderate-border bg-risk-moderate-bg space-y-1 font-sans">
              <div className="text-[10px] font-extrabold text-risk-moderate uppercase tracking-wider flex items-center gap-1.5 font-sans">
                <Wrench className="w-3.5 h-3.5 text-risk-moderate" /> ALINMASI GEREKEN TEDBİR (HAZIR DÖF AKSİYONU):
              </div>
              <div className="text-xs text-ink-primary leading-relaxed font-sans font-medium">
                {correctiveActionText}
              </div>
            </div>
          )}

          {/* ÖZEL İŞ YERİ BEYANI / İTİRAZ AÇIKLAMASI */}
          {item.workplace_declaration && (item.workplace_declaration.reason || item.workplace_declaration.decision || item.workplace_declaration.commitment) && (
            <div className="p-3.5 rounded-control border border-border-strong bg-risk-info-bg space-y-1.5 font-sans">
              <div className="text-[10px] font-extrabold text-risk-info uppercase tracking-wider flex items-center justify-between font-sans">
                <span className="flex items-center gap-1.5">
                  <FileText className="w-3.5 h-3.5 text-risk-info" />
                  📌 İŞ YERİ BEYANI ({item.workplace_declaration.decision === "DISPUTED" ? "İTİRAZ EDİLDİ" : "ONAYLANDI"}):
                </span>
                {item.workplace_declaration.saved_at && (
                  <span className="text-[10px] font-mono text-risk-info font-normal">
                    {formatDate(item.workplace_declaration.saved_at)}
                  </span>
                )}
              </div>
              {item.workplace_declaration.reason && (
                <div className="text-xs text-ink-primary leading-relaxed font-sans font-medium">
                  <strong>İtiraz / Gerekçe Notu:</strong> "{item.workplace_declaration.reason}"
                </div>
              )}
              {item.workplace_declaration.commitment && (
                <div className="text-xs text-ink-primary leading-relaxed font-sans font-normal pt-0.5">
                  <strong>İş Yeri Taahhüdü:</strong> "{item.workplace_declaration.commitment}"
                </div>
              )}
            </div>
          )}

          {/* RESPONSIBLE & DEADLINE COUNTDOWN ROW */}
          <div className="flex flex-wrap items-center justify-between gap-3 text-xs font-sans text-ink-secondary pt-1">
            <span className="flex items-center gap-1.5 font-semibold font-sans">
              <UserIcon className="w-3.5 h-3.5 text-ink-tertiary" /> SORUMLU: <strong className="text-ink-primary">{responsiblePerson}</strong>
            </span>
            <div className="flex items-center gap-2 font-sans">
              <span className="text-[11px] font-semibold text-ink-secondary">TERMİN:</span>
              <DeadlineCountdown
                dueDate={item.due_date}
                status={item.status}
                createdAt={item.created_at}
                resolvedAt={item.resolved_at}
              />
            </div>
          </div>

          {/* PHOTO EVIDENCE SECTION WITH 3/3 MODIFY LIMIT */}
          <div className="space-y-3 pt-3 border-t border-border-default font-sans">
            {findingPhotos.length > 0 && (
              <PhotoUploader
                auditId={item.audit_id}
                questionId={item.question_id}
                photoType="finding"
                photos={findingPhotos}
                onPhotosChange={(updated, t, m) => onPhotosChange(item, updated, t, m)}
                disabled={!isAdmin}
                isAdmin={isAdmin}
                modifyCount={modifyCount}
                maxModifyRights={3}
                label="Saha Tespit Fotoğrafları (Denetçi Kanıtı)"
              />
            )}

            <PhotoUploader
              auditId={item.audit_id}
              questionId={item.question_id}
              photoType="resolution"
              photos={resolutionPhotos}
              onPhotosChange={(updated, t, m) => onPhotosChange(item, updated, t, m)}
              disabled={isSaving}
              isAdmin={isAdmin}
              modifyCount={modifyCount}
              maxModifyRights={3}
              label="Çözüm & Düzeltme Kanıt Fotoğrafları"
            />
          </div>

          {/* UZMAN GERİ BİLDİRİMİ / RESOLUTION NOTE BOX (IF CLOSED) */}
          {item.resolution_note && (
            <div className="p-3.5 rounded-control border border-risk-compliant-border bg-risk-compliant-bg space-y-1 font-sans">
              <div className="text-[10px] font-extrabold text-risk-compliant uppercase tracking-wider flex items-center justify-between font-sans">
                <span className="flex items-center gap-1.5 font-sans">
                  <UserCheck className="w-3.5 h-3.5 text-risk-compliant" /> İSG UZMANI DEĞERLENDİRME & KAPANIS NOTU:
                </span>
                {item.resolved_at && (
                  <span className="text-[10px] font-mono text-risk-compliant/80 font-normal">
                    {formatDate(item.resolved_at)}
                  </span>
                )}
              </div>
              <div className="text-xs text-ink-primary leading-relaxed font-sans font-medium">
                "{item.resolution_note}"
              </div>
              {item.resolved_by && (
                <div className="text-[10px] text-risk-compliant/90 font-sans pt-1">
                  Onaylayan: <strong>{item.resolved_by}</strong>
                </div>
              )}
            </div>
          )}

          {/* STATUS SELECTOR & NOTES FORM
              (status + save spatially adjacent: status row → textarea → counter → save) */}
          <div className="space-y-3 pt-3 border-t border-border-default font-sans">
            {/* DÖF DURUMU STATUS CONTROLS — AÇIK / İŞLEMDE / KAPATILDI
                Right rail'den buraya taşındı; status seçimi ile Save butonu
                aynı dikey kolonda, editörün hemen üstünde komşu. */}
            <div className="space-y-2">
              <div className="text-[10px] font-bold uppercase tracking-wider text-ink-secondary">
                DÖF DURUMU
              </div>
              <div className="flex flex-row flex-wrap gap-1.5">
                {DOF_STATUSES.map((s) => {
                  const active = draft.status === s;
                  const isDisabledStatus = s === "KAPATILDI" && !canCloseDof;
                  return (
                    <button
                      key={s}
                      type="button"
                      disabled={isSaving}
                      onClick={() => onStatusClick(item, s)}
                      title={
                        isDisabledStatus
                          ? "DÖF kapatma yetkisi yalnızca İSG Uzmanı / Admin hesaplarına aittir"
                          : ""
                      }
                      data-testid={
                        s === "AÇIK"
                          ? DOF.statusButton.acik
                          : s === "İŞLEMDE"
                          ? DOF.statusButton.islemde
                          : DOF.statusButton.kapatildi
                      }
                      className={`px-3 py-1.5 rounded-control transition-colors duration-standard ease-swift font-bold cursor-pointer active:scale-95 ${statusControlClasses(
                        s,
                        active,
                        isDisabledStatus
                      )}`}
                    >
                      {s === "KAPATILDI" && canCloseDof ? (
                        <span className="flex items-center gap-1.5">
                          <CheckCheck className="w-3.5 h-3.5" /> Onayla & Kapat
                        </span>
                      ) : (
                        s
                      )}
                    </button>
                  );
                })}
              </div>
            </div>

            <IsolatedDofNoteBox
              item={item}
              initialNotes={draft.notes}
              onNotesChange={onNotesChange}
              onSave={onSave}
              isSaving={isSaving}
              updatedAt={updatedAt}
              canSaveBase={canSave}
              canCloseDof={canCloseDof}
            />
          </div>
        </div>

        {/* RIGHT SUMMARY RAIL — informational only (status badge, risk, deadline, sorumlu).
            İnteraktif status kontrolleri ana içerik kolonuna taşındı. */}
        <div className="w-full lg:w-72 shrink-0 p-4 rounded-card border border-border-default bg-surface-card-2 space-y-4 font-sans text-xs">
          {/* STATUS BADGE */}
          <div className="space-y-2">
            <div className="text-[10px] font-bold uppercase tracking-wider text-ink-secondary border-b border-border-default pb-2 flex items-center justify-between">
              <span>DÖF DURUMU</span>
              <span
                className={`px-2 py-0.5 rounded-pill font-sans text-[9px] font-extrabold tracking-wide ${
                  item.status === "KAPATILDI"
                    ? "bg-risk-compliant-bg text-risk-compliant border border-risk-compliant-border"
                    : item.status === "İŞLEMDE"
                    ? "bg-risk-moderate-bg text-risk-moderate border border-risk-moderate-border"
                    : "bg-risk-critical-bg text-risk-critical border border-risk-critical-border"
                }`}
              >
                {item.status || "AÇIK"}
              </span>
            </div>

            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-ink-secondary font-semibold">RİSK SKORU:</span>
                <span
                  className={`font-mono font-extrabold px-2.5 py-0.5 rounded-control text-[11px] ${
                    isKabulEdilemez
                      ? "bg-risk-critical-bg text-risk-critical border border-risk-critical-border"
                      : "bg-risk-moderate-bg text-risk-moderate border border-risk-moderate-border"
                  }`}
                >
                  {item.risk_score ?? (item.default_risk_score ?? "—")} Puan
                </span>
              </div>

              <div className="flex items-center justify-between">
                <span className="text-ink-secondary font-semibold">RİSK SINIFI:</span>
                <span
                  className={`font-bold ${isKabulEdilemez ? "text-risk-critical" : "text-risk-moderate"}`}
                >
                  {item.risk_level || (isKabulEdilemez ? "Kabul Edilemez" : "Dikkate Değer")}
                </span>
              </div>

              {showDocLevel && (
                <div className="flex items-center justify-between text-[11px]">
                  <span className="text-ink-secondary font-semibold">BELGE SEVİYESİ:</span>
                  <span className="text-ink-primary font-semibold">{item.document_risk_level}</span>
                </div>
              )}

              <div className="flex items-center justify-between pt-2 border-t border-border-default">
                <span className="text-ink-secondary font-semibold">TERMİN:</span>
                <span className="font-bold text-risk-moderate font-mono bg-risk-moderate-bg px-2 py-0.5 rounded-xs border border-risk-moderate-border">{deadlinePeriod}</span>
              </div>
            </div>
          </div>

          {/* SORUMLU BİRİM */}
          <div className="pt-3 border-t border-border-default text-[11px] space-y-1 font-sans">
            <div className="text-ink-secondary text-[10px] font-semibold uppercase tracking-wider">SORUMLU BİRİM</div>
            <div className="text-ink-primary font-bold font-sans">{responsiblePerson}</div>
          </div>

        </div>

      </div>

      {/* İŞLEM GEÇMİŞİ — full-width timeline beneath the two-column region.
          Tek DofTimeline render'ı; component'in kendi collapse başlığı
          (📜 İşlem Geçmişi) section başlığı olarak yeterli. */}
      <div className="pt-4 mt-2 border-t border-border-default">
        <DofTimeline
          logs={item.timeline_logs}
          status={item.status}
          createdAt={item.created_at}
          resolvedAt={item.resolved_at}
        />
      </div>
    </motion.div>
  );
}
