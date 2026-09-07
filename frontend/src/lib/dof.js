// ---------------------------------------------------------------------------
// DÖF (Düzeltici ve Önleyici Faaliyet) pure logic helpers
// ---------------------------------------------------------------------------
// Backend contract reference (canonical English schema from PR2 DÖF backend):
//   GET  /api/dofs                        -> DofItem[]
//   PUT  /api/dofs/{audit_id}/{question_id} -> { status: "success", dof: PartialDofItem }
//
// DofItem shape (22 fields):
//   audit_id, audit_user_id, owner_name, restaurant_name, audit_date,
//   question_id, question_no, category, question, responsible,
//   probability, severity, risk_score, risk_level, document_risk_level,
//   deadline, legal_basis, corrective_action,
//   status, notes, updated_at, updated_by
//
// Status enum: "AÇIK" | "İŞLEMDE" | "KAPATILDI"
// Risk level enum: "Kabul Edilemez" | "Dikkate Değer" | "Kabul Edilebilir"
//   (canonical Turkish labels — do NOT recompute numeric thresholds on the client)
// Notes: str, max 2000 chars, server trims; KAPATILDI requires non-empty notes.
// ---------------------------------------------------------------------------

export const DOF_STATUSES = ["AÇIK", "İŞLEMDE", "KAPATILDI"];
export const STATUS_FILTER_OPTIONS = ["HEPSİ", ...DOF_STATUSES];

// Phase 2B — S7: "Sürekli" termin string'i için inline yardımcı.
// Backend ``_calculate_due_date`` artık "sürekli"/"surekli" içeren
// termin string'leri için ``None`` döndürür; frontend buna göre inline
// formda termin input'unu gizler ve özel uyarı gösterir.
export function isContinuousDeadline(deadlineStr) {
  if (!deadlineStr) return false;
  const lower = String(deadlineStr).toLowerCase();
  return lower.includes("sürekli") || lower.includes("surekli");
}

// Inline DÖF payload'ı oluştur (PUT /api/dofs/{audit_id}/{question_id})
export function buildInlineDofPayload({
  status = "AÇIK",
  notes = "",
  resolutionNote = "",
} = {}) {
  return {
    status,
    notes: normalizeNotes(notes),
    resolution_note: resolutionNote ? normalizeNotes(resolutionNote) : normalizeNotes(notes),
  };
}

// Inline form validasyonu. Hata varsa string mesaj, yoksa null.
export function validateInlineDofForm({
  status = "AÇIK",
  notes = "",
  deadline = "",
} = {}) {
  if (status === "KAPATILDI" && !normalizeNotes(notes)) {
    return "DÖF kapatılıyorsa not alanı zorunludur (min 20 karakter önerilir).";
  }
  if (status === "KAPATILDI" && normalizeNotes(notes).length < 20) {
    return "Kapatma notu en az 20 karakter olmalıdır (yasal iz için).";
  }
  if (normalizeNotes(notes).length > MAX_NOTES_LENGTH) {
    return `Not en fazla ${MAX_NOTES_LENGTH} karakter olabilir.`;
  }
  return null;
}

export const RISK_LEVELS_CANONICAL = [
  "Kabul Edilemez",
  "Dikkate Değer",
  "Kabul Edilebilir",
];
export const RISK_FILTER_OPTIONS = ["HEPSİ", ...RISK_LEVELS_CANONICAL];

export const MAX_NOTES_LENGTH = 2000;

// ---------------------------------------------------------------------------
// normalizeNotes
//   Mirrors backend `notes.strip()` validator. Client-side guard only;
//   the server remains the source of truth for validation.
// ---------------------------------------------------------------------------
export function normalizeNotes(value) {
  return (value ?? "").trim();
}

// ---------------------------------------------------------------------------
// filterDofs
//   Client-side filtering across the GET /api/dofs payload.
//   Pure; no side effects. Returns a new array; input is not mutated.
//
//   - status:   "HEPSİ" passes everything; otherwise must match item.status.
//   - riskLevel:"HEPSİ" passes everything; otherwise must match item.risk_level.
//   - search:   empty/whitespace passes everything; otherwise case-insensitive
//               substring match against restaurant_name, question, category,
//               responsible.
// ---------------------------------------------------------------------------
export function filterDofs(dofs, { status, riskLevel, search, brand } = {}) {
  if (!Array.isArray(dofs)) return [];
  const s = (status ?? "HEPSİ").toString();
  const r = (riskLevel ?? "HEPSİ").toString();
  const b = (brand ?? "HEPSİ").toString();
  const q = (search ?? "").toString().trim().toLowerCase();

  return dofs.filter((item) => {
    if (!item || typeof item !== "object") return false;
    // Skip malformed/empty entries that lack the canonical GET /dofs keys.
    // Server should never emit these, but defending the client against a
    // partial payload is cheap and keeps the page from crashing on render.
    if (!item.audit_id || !item.status) return false;

    if (s !== "HEPSİ" && item.status !== s) return false;
    if (r !== "HEPSİ" && item.risk_level !== r) return false;

    if (b !== "HEPSİ" && b !== "Tüm Markalar") {
      const restName = String(item.restaurant_name || "").toLowerCase();
      const brandName = String(item.brand || "").toLowerCase();
      const bLower = b.toLowerCase();
      if (!restName.includes(bLower) && !brandName.includes(bLower)) {
        return false;
      }
    }

    if (q.length > 0) {
      const haystacks = [
        item.restaurant_name,
        item.question,
        item.category,
        item.responsible,
      ];
      const hit = haystacks.some((field) => {
        if (typeof field !== "string") return false;
        return field.toLowerCase().includes(q);
      });
      if (!hit) return false;
    }
    return true;
  });
}

// ---------------------------------------------------------------------------
// buildUpdatePayload
//   Construct the PUT request body from a card draft + current server item.
//   - status defaults to currentItem.status if draft.status missing.
//   - notes is trimmed (mirrors backend validator).
//   The backend accepts { status, notes } only; do not add extra fields.
// ---------------------------------------------------------------------------
export function buildUpdatePayload(currentItem, draft) {
  const status = (draft?.status ?? currentItem?.status ?? "AÇIK").toString();
  const notes = normalizeNotes(draft?.notes ?? currentItem?.notes ?? "");
  return { status, notes };
}

// ---------------------------------------------------------------------------
// validateKapatildiNotes
//   Client-side guard for the "KAPATILDI requires notes" rule.
//   Returns { ok: true } or { ok: false, message }.
//   This is UX only — server still returns 422 if the client misses it.
//   Empty/whitespace notes are both rejected for KAPATILDI.
//   AÇIK and İŞLEMDE allow empty notes (user can clear the existing note).
// ---------------------------------------------------------------------------
export function validateKapatildiNotes(draft) {
  const status = (draft?.status ?? "").toString();
  const trimmed = normalizeNotes(draft?.notes ?? "");
  if (status === "KAPATILDI" && trimmed.length === 0) {
    return {
      ok: false,
      message: "KAPATILDI durumunda not zorunludur",
    };
  }
  return { ok: true };
}

// ---------------------------------------------------------------------------
// applyPutResponseToItem
//   After a successful PUT, merge the response.dof (6 fields) into the
//   existing item. Response only carries audit_id, question_id, status,
//   notes, updated_at, updated_by — all other fields (restaurant_name,
//   risk_level, etc.) are preserved from the original GET payload.
// ---------------------------------------------------------------------------
export function applyPutResponseToItem(item, responseDof) {
  if (!item || typeof item !== "object") return item;
  if (!responseDof || typeof responseDof !== "object") return item;
  return {
    ...item,
    status: responseDof.status ?? item.status,
    notes: typeof responseDof.notes === "string" ? responseDof.notes : item.notes,
    updated_at: responseDof.updated_at ?? item.updated_at ?? null,
    updated_by: responseDof.updated_by ?? item.updated_by ?? null,
  };
}

// ---------------------------------------------------------------------------
// computeKpis
//   Aggregate counts across the entire (unfiltered) DÖF payload for the
//   top KPI strip. Returns 0/0/0/0/total when input is empty.
// ---------------------------------------------------------------------------
export function computeKpis(dofs) {
  if (!Array.isArray(dofs) || dofs.length === 0) {
    return { total: 0, acik: 0, islemde: 0, kapatildi: 0 };
  }
  let acik = 0;
  let islemde = 0;
  let kapatildi = 0;
  for (const item of dofs) {
    if (!item || typeof item !== "object") continue;
    if (item.status === "AÇIK") acik += 1;
    else if (item.status === "İŞLEMDE") islemde += 1;
    else if (item.status === "KAPATILDI") kapatildi += 1;
  }
  return { total: dofs.length, acik, islemde, kapatildi };
}

// ---------------------------------------------------------------------------
// formatUpdatedAt
//   Best-effort Turkish-locale rendering for an ISO date string.
//   Falls back to the raw value if Date parsing fails (or input is empty).
//   Returns null when there is no update yet.
// ---------------------------------------------------------------------------
export function formatUpdatedAt(value) {
  if (value === null || value === undefined || value === "") return null;
  const s = String(value);
  const d = new Date(s);
  if (Number.isNaN(d.getTime())) return s;
  try {
    const date = d.toLocaleDateString("tr-TR", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
    });
    const time = d.toLocaleTimeString("tr-TR", {
      hour: "2-digit",
      minute: "2-digit",
    });
    return `${date} ${time}`;
  } catch (_e) {
    return s;
  }
}

// ---------------------------------------------------------------------------
// isDirty
//   True when the draft diverges from the server-side item.
//   Used to enable/disable the "Değişiklikleri Kaydet" button.
// ---------------------------------------------------------------------------
export function isDirty(item, draft) {
  if (!item || !draft) return false;
  const serverStatus = (item.status ?? "").toString();
  const serverNotes = (item.notes ?? "").toString();
  const draftStatus = (draft.status ?? "").toString();
  const draftNotes = (draft.notes ?? "").toString();
  return draftStatus !== serverStatus || draftNotes !== serverNotes;
}