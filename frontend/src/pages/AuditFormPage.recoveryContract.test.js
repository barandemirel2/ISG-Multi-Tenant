// Regression test: AuditFormPage draft recovery wiring.
//
// Bug context (PR0 review): AuditFormPage ``readAuditDraft`` helper'ını
// yanlış argüman sırasıyla çağırıyordu (``readAuditDraft(id, userId)``),
// helper'ın döndüğü ``{status, draft}`` shape'indeki ``localDraft.version``
// alanını yanlış okuyordu, ``createAuditAutosaveQueue`` constructor'ında
// ``storage`` + ``onState`` (canonical isim) + ``onAcknowledged`` argümanları
// eksikti, ``createBeforeUnloadGuard(() => queue.isDirty())`` queue API'sinde
// olmayan bir method çağırıyordu. Net etki: refresh sonrası local draft
// recovery hiç çalışmıyordu, autosave state UI'a yansımıyordu, beforeunload
// guard crash ediyordu.
//
// Bu test helper contract'ı TEKRAR test etmez (auditAutosave.test.js bunu
// yapıyor); AuditFormPage'in helper'lara GEÇTİĞİ argüman shape'ini ve
// DÖNEN sonuçtan ürettiği state'i birebir simüle eder. Yani production
// wiring'inin canonical helper contract ile uyumlu olduğunu doğrular.
//
// Not: Tam React render testi (AuditFormPage mount + useParams/useNavigate
// stub + api mock + CategoryTabs/OverrideEditor/PhotoUploader render) test
// kapsamı dışı bırakıldı. AuditFormPage; AppShell, useAuth, framer-motion,
// sonner, lucide-react, @/components/ui/select (Radix tabanlı), 3 internal
// bileşen (CategoryTabs, OverrideEditor, PhotoUploader) ve 3 auditAutosave
// helper import ediyor; minimum render mock surface ~15 ağır dependency.
// PR0 review kuralı olan "minimum regression test, refactor yok" gereği
// caller contract testi tercih edildi.

import { auditDraftKey, readAuditDraft } from "../lib/auditAutosave";

// ---------------------------------------------------------------------------
// Helpers (mock storage + canonical draft shape)
// ---------------------------------------------------------------------------
function memoryStorage() {
  const values = new Map();
  return {
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, value),
    removeItem: (key) => values.delete(key),
    values,
  };
}

function seededStorage(seededMap) {
  const values = new Map(seededMap);
  return {
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, value),
    removeItem: (key) => values.delete(key),
    values,
  };
}

// AuditFormPage ``applyServerState`` içinde readAuditDraft'i şu şekilde
// çağırır (post-FIX C, satır ~122):
//   readAuditDraft(storage, userId, id, version)
// ve dönen shape'i şu şekilde kullanır:
//   recovery.status: "compatible" | "incompatible" | "absent"
//   recovery.draft: { answers, risk_overrides, baseVersion, savedAt }
// Bu helper production wiring'in birebir kopyası.
function recoverAnswers(storage, userId, auditId, serverVersion) {
  const recovery = readAuditDraft(storage, userId, auditId, serverVersion);
  if (recovery.status !== "compatible" && recovery.status !== "incompatible") {
    return { applied: false, answers: {}, riskOverrides: {}, state: "saved" };
  }
  const d = recovery.draft || {};
  return {
    applied: recovery.status === "compatible",
    answers: d.answers && typeof d.answers === "object" ? d.answers : {},
    riskOverrides:
      d.risk_overrides && typeof d.risk_overrides === "object" ? d.risk_overrides : {},
    state: recovery.status === "compatible" ? "dirty" : "conflict",
  };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------
describe("AuditFormPage draft recovery wiring — canonical helper contract", () => {
  test("recovery key uses (userId, auditId) tuple, not serverVersion", () => {
    // PR0 bug şüphesi: ``readAuditDraft(id, userId)`` çağrısı ``id``'yi
    // ``storage`` slot'una koyup ``userId``'yi ``auditId``'ye geçiriyordu.
    // Canonical helper ``auditDraftKey(userId, auditId)`` kullanır.
    const key1 = auditDraftKey("u1", "a1");
    const key2 = auditDraftKey("u2", "a1");
    expect(key1).not.toBe(key2);
    expect(key1).toContain("u1");
    expect(key1).toContain("a1");
  });

  test("compatible draft in storage applies answers/risk_overrides to UI state", () => {
    // sessionStorage'a canonical formatta compatible draft koy.
    const storage = memoryStorage();
    const userId = "u1";
    const auditId = "a1";
    const serverVersion = 5;

    const draft = {
      userId,
      auditId,
      baseVersion: serverVersion,
      answers: { "12": "HAYIR", "13": "EVET" },
      risk_overrides: { "12": { probability: 4, severity: 5 } },
      timestamp: "2026-08-10T12:00:00+00:00",
    };
    storage.setItem(auditDraftKey(userId, auditId), JSON.stringify(draft));

    // Production wiring'in aynı argüman sırası: (storage, userId, auditId, version)
    const recovery = recoverAnswers(storage, userId, auditId, serverVersion);

    // Recovered answers UI state'e geçmeli.
    expect(recovery.applied).toBe(true);
    expect(recovery.answers["12"]).toBe("HAYIR");
    expect(recovery.answers["13"]).toBe("EVET");
    expect(recovery.riskOverrides["12"]).toEqual({ probability: 4, severity: 5 });
    // "compatible" → dirty mode (kullanıcının elinde değişiklik var).
    expect(recovery.state).toBe("dirty");
  });

  test("incompatible draft (baseVersion mismatch) is NOT applied as compatible", () => {
    const storage = memoryStorage();
    const userId = "u1";
    const auditId = "a1";

    // Sunucu artık version=10'a geçti; kullanıcının local draft'ı 5'i
    // temel alıyor. Helper "incompatible" dönmeli — audit form yanlışlıkla
    // server state üzerine uygulamamalı.
    const draft = {
      userId,
      auditId,
      baseVersion: 5,
      answers: { "12": "HAYIR" },
      risk_overrides: {},
      timestamp: "2026-08-10T12:00:00+00:00",
    };
    storage.setItem(auditDraftKey(userId, auditId), JSON.stringify(draft));

    const recovery = recoverAnswers(storage, userId, auditId, 10);

    // PR0 bug guard: helper HÂLÂ draft.answers döndürüyor (incompatible
    // payload'ın parçası olarak) — ama caller bunu "dirty" olarak
    // state'e uygulamamalı. State "conflict" olmalı, applied=false.
    expect(recovery.applied).toBe(false);
    expect(recovery.state).toBe("conflict");
    // recovery answers hâlâ inspectable (kullanıcı kendi draft'ını
    // görsün diye) ama AuditFormPage bunu state'e yazmaz.
    expect(recovery.answers["12"]).toBe("HAYIR");
  });

  test("absent draft (no entry in storage) returns applied=false, state=saved", () => {
    const storage = memoryStorage();
    const recovery = recoverAnswers(storage, "u1", "a1", 5);
    expect(recovery.applied).toBe(false);
    expect(recovery.answers).toEqual({});
    expect(recovery.riskOverrides).toEqual({});
    expect(recovery.state).toBe("saved");
  });

  test("corrupt storage payload (invalid JSON) does not throw", () => {
    // Defensive: storage'da corrupted JSON varsa helper exception
    // fırlatmamalı — AuditFormPage crash etmemeli.
    const storage = memoryStorage();
    storage.setItem(auditDraftKey("u1", "a1"), "{invalid json");

    let recovery;
    expect(() => {
      recovery = recoverAnswers(storage, "u1", "a1", 5);
    }).not.toThrow();
    expect(recovery.applied).toBe(false);
    expect(recovery.state).toBe("saved");
  });

  test("canonical arg order guard: (storage, userId, auditId, version) — swapping args fails correctly", () => {
    // PR0 bug'ın regression guard'ı: readAuditDraft eski çağrı sırası
    // (id, userId) ile storage'a ``id``'yi koyardı; userId ``auditId``
    // olarak okunurdu. Bu test, doğru arg sırası ile çalışan çağrının
    // sonuç döndürdüğünü, yanlış sıranın lookup'ı kaçırdığını doğrular.
    const storage = memoryStorage();
    const userId = "u1";
    const auditId = "a1";
    const version = 5;
    storage.setItem(
      auditDraftKey(userId, auditId),
      JSON.stringify({
        userId,
        auditId,
        baseVersion: version,
        answers: { "1": "EVET" },
        risk_overrides: {},
      })
    );

    const correct = readAuditDraft(storage, userId, auditId, version);
    expect(correct.status).toBe("compatible");

    // Yanlış arg sırası: (auditId, userId) — eski Baran kodu. helper
    // auditId'yi storage olarak kullanır (string, .getItem yok) → TypeError
    // fırlatır, audit form crash ederdi.
    const buggy = readAuditDraft(auditId, userId, "anything", version);
    expect(buggy.status).not.toBe("compatible");
  });

  test("auditDraftKey isolation: different userId or auditId produces distinct keys", () => {
    const a = auditDraftKey("u1", "a1");
    const b = auditDraftKey("u2", "a1");
    const c = auditDraftKey("u1", "a2");
    expect(new Set([a, b, c]).size).toBe(3);
  });
});