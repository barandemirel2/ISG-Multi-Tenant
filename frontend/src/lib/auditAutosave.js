// ---------------------------------------------------------------------------
// Audit session draft key + legacy key cleanup
// ---------------------------------------------------------------------------

export const auditDraftKey = (userId, auditId) => `audit-draft:${userId}:${auditId}`;
const auditLegacyDraftKey = (auditId) => `audit-draft:${auditId}`;

// ---------------------------------------------------------------------------
// Pure helpers (state shape independent of React)
// ---------------------------------------------------------------------------

const cloneAnswers = (answers) => ({ ...(answers || {}) });

// risk_overrides değerleri primitive değil; içerde sadece {probability, severity}
// tutuyoruz, dolayısıyla referans karşılaştırması yeterli; fakat best practice:
// iki ayrı override nesnesi eşitse snapshot eşittir kararı için yüzeysel
// kontrol uyguluyoruz.
const cloneOverrides = (overrides) => {
  const out = {};
  if (!overrides || typeof overrides !== "object" || Array.isArray(overrides)) return out;
  for (const [qid, pair] of Object.entries(overrides)) {
    if (!pair || typeof pair !== "object") continue;
    const prob = pair.probability;
    const sev = pair.severity;
    if (!Number.isInteger(prob) || !Number.isInteger(sev)) continue;
    out[qid] = { probability: Number(prob), severity: Number(sev) };
  }
  return out;
};

const sameAnswers = (left, right) => {
  if (left === right) return true;
  if (!left || !right || typeof left !== "object" || typeof right !== "object") {
    return false;
  }
  const leftKeys = Object.keys(left);
  const rightKeys = Object.keys(right);
  if (leftKeys.length !== rightKeys.length) return false;
  for (const key of leftKeys) {
    if (!Object.prototype.hasOwnProperty.call(right, key)) return false;
    if (left[key] !== right[key]) return false;
  }
  return true;
};

const sameOverrides = (left, right) => {
  if (left === right) return true;
  if (!left || !right || typeof left !== "object" || typeof right !== "object") {
    return false;
  }
  const leftKeys = Object.keys(left);
  const rightKeys = Object.keys(right);
  if (leftKeys.length !== rightKeys.length) return false;
  for (const qid of leftKeys) {
    const a = left[qid];
    const b = right[qid];
    if (!a || !b) return false;
    if (a.probability !== b.probability || a.severity !== b.severity) return false;
  }
  return true;
};

const sameSnapshot = (a, b) =>
  sameAnswers(a.answers, b.answers) && sameOverrides(a.risk_overrides, b.risk_overrides);

const cleanupLegacyDraft = (storage, auditId) => {
  if (!storage || !auditId) return;
  try {
    storage.removeItem(auditLegacyDraftKey(auditId));
  } catch (_error) {
    // ignore storage failures
  }
};

// ---------------------------------------------------------------------------
// Public draft reader
//
// Draft shape (Phase 2B):
//   {
//     userId, auditId, baseVersion,
//     answers: { [qid]: "EVET" | "HAYIR" | "NA" },
//     risk_overrides: { [qid]: { probability: int, severity: int } },
//     timestamp
//   }
//
// Legacy drafts written before Phase 2B had no `risk_overrides` field. They
// are recovered as answers-only; the queue normalises them to an empty
// overrides map so callers downstream always see a consistent shape.
// ---------------------------------------------------------------------------

export function readAuditDraft(storage, userId, auditId, serverVersion) {
  if (!storage) return { status: "none", draft: null };
  if (!userId || !auditId || !Number.isInteger(serverVersion)) {
    return { status: "invalid", draft: null };
  }
  cleanupLegacyDraft(storage, auditId);
  try {
    const raw = storage.getItem(auditDraftKey(userId, auditId));
    if (!raw) return { status: "none", draft: null };
    const parsed = JSON.parse(raw);
    if (
      parsed.userId !== userId ||
      parsed.auditId !== auditId ||
      !Number.isInteger(parsed.baseVersion) ||
      !parsed.answers ||
      typeof parsed.answers !== "object" ||
      Array.isArray(parsed.answers)
    ) {
      return { status: "invalid", draft: null };
    }
    const normalized = {
      userId: parsed.userId,
      auditId: parsed.auditId,
      baseVersion: parsed.baseVersion,
      answers: cloneAnswers(parsed.answers),
      // Legacy draft → empty overrides map; UI görünümü default'a düşer.
      risk_overrides: cloneOverrides(parsed.risk_overrides),
      timestamp: parsed.timestamp || null,
    };
    return {
      status: parsed.baseVersion === serverVersion ? "compatible" : "incompatible",
      draft: normalized,
    };
  } catch (_error) {
    return { status: "invalid", draft: null };
  }
}

// ---------------------------------------------------------------------------
// BeforeUnload helper — referans davranışı korunuyor
// ---------------------------------------------------------------------------

export function createBeforeUnloadGuard(target) {
  let active = false;
  const isFunctionTarget = typeof target === "function";
  const winTarget = isFunctionTarget ? (typeof window !== "undefined" ? window : null) : target;

  const handler = (event) => {
    if (isFunctionTarget && !target()) return;
    event.preventDefault();
    event.returnValue = "";
  };

  const update = (nextActive) => {
    if (!winTarget || typeof winTarget.addEventListener !== "function") return;
    if (nextActive === active) return;
    active = nextActive;
    if (active) winTarget.addEventListener("beforeunload", handler);
    else winTarget.removeEventListener("beforeunload", handler);
  };

  const dispose = () => {
    if (winTarget && typeof winTarget.removeEventListener === "function" && active) {
      winTarget.removeEventListener("beforeunload", handler);
    }
    active = false;
  };

  if (isFunctionTarget && winTarget) {
    update(true);
  }

  const guardFn = function () {
    dispose();
  };
  guardFn.update = update;
  guardFn.dispose = dispose;

  return guardFn;
}

// ---------------------------------------------------------------------------
// Queue API — arayüz açıklamaları:
//   edit(snapshotOrAnswers)
//       yeni form: { answers, risk_overrides }  — iki state atomik günceller.
//       legacy  : { [qid]: "EVET" | "HAYIR" | "NA" } — risk_overrides'i
//       olduğu gibi bırakır; mevcut risk override'ları kaybetmez.
//
//   editState(state)
//       aynı yeni formun açık adı. Frontend tarafında okunabilirlik için
//       editState(state) tercih edilir; edit(answers) ise eski call-site'ların
//       boşuna değişmemesi için alias olarak yaşar.
//
//   restoreConflict(state | answers)
//       çakışma sonrası yerel taslağı kuyruğa bağlar; yeni form veya legacy
//       form kabul edilir.
//
//   reset(state | answers, version, clearDraft)
//       sunucudan gelen yeni sürümü/state'i kuyruğa yerleştirir.
//       Yeni form: reset({answers, risk_overrides}, version, clearDraft)
//       Legacy   : reset(answers, version, clearDraft) — risk_overrides'i
//       boş map'e çevirir.
//
//   save snapshot parametresi artık { answers, risk_overrides } şeklindedir.
// ---------------------------------------------------------------------------

export function createAuditAutosaveQueue({
  auditId,
  userId,
  initialVersion,
  save,
  saveFn,
  storage,
  debounceMs = 900,
  onState = () => {},
  onAcknowledged = () => {},
}) {
  const saveCallback = save || saveFn;
  if (typeof saveCallback !== "function") {
    throw new Error("createAuditAutosaveQueue requires a save or saveFn function");
  }
  if (!userId || typeof userId !== "string") {
    throw new Error("createAuditAutosaveQueue requires a non-empty userId");
  }
  if (!auditId || typeof auditId !== "string") {
    throw new Error("createAuditAutosaveQueue requires a non-empty auditId");
  }
  let active = true;
  let timer = null;
  let inFlight = null;
  let pending = null;
  let latest = { answers: {}, risk_overrides: {} };
  let acknowledgedVersion = initialVersion;
  let status = "saved";
  let error = null;
  let requestGeneration = 0;
  let waiters = [];

  const emptySnapshot = () => ({ answers: {}, risk_overrides: {} });

  const cloneSnapshot = (snap) => ({
    answers: cloneAnswers(snap.answers),
    risk_overrides: cloneOverrides(snap.risk_overrides),
  });

  // Legacy shape detection: { [qid]: "EVET"|"HAYIR"|"NA" } → answers map.
  // Yeni shape'de answers alanı düz bir primitive map; bunu ayırt etmek için
  // candidate değerlerinin tipine bakıyoruz; değerler "EVET"/"HAYIR"/"NA"
  // string'i ise legacy answers map kabul ediyoruz.
  const isLegacyAnswersPayload = (payload) => {
    if (!payload || typeof payload !== "object") return false;
    if (Array.isArray(payload)) return false;
    if (payload.answers || payload.risk_overrides) return false;
    for (const value of Object.values(payload)) {
      if (value === null || value === undefined) continue;
      const t = typeof value;
      if (t === "string") continue;
      if (t === "object") {
        if ("probability" in value || "severity" in value) return false;
      }
      return false;
    }
    return true;
  };

  const normaliseEdit = (payload) => {
    if (isLegacyAnswersPayload(payload)) {
      // legacy answers map → answers'ı güncelle, risk_overrides'i koru
      return { answers: cloneAnswers(payload), risk_overrides: cloneOverrides(latest.risk_overrides) };
    }
    const answers = payload && typeof payload === "object" && payload.answers ? cloneAnswers(payload.answers) : {};
    const overrides = payload && typeof payload === "object" && payload.risk_overrides ? cloneOverrides(payload.risk_overrides) : {};
    return { answers, risk_overrides: overrides };
  };

  const state = () => ({
    auditId,
    userId,
    version: acknowledgedVersion,
    status,
    error,
    dirty:
      pending !== null ||
      inFlight !== null ||
      status === "error" ||
      status === "validation" ||
      status === "conflict",
    saving: inFlight !== null,
  });

  const notify = () => onState(state());

  const writeDraft = (snap, baseVersion = acknowledgedVersion) => {
    if (!storage) return;
    storage.setItem(
      auditDraftKey(userId, auditId),
      JSON.stringify({
        userId,
        auditId,
        baseVersion,
        answers: cloneAnswers(snap.answers),
        risk_overrides: cloneOverrides(snap.risk_overrides),
        timestamp: new Date().toISOString(),
      }),
    );
  };

  const clearMatchingDraft = (snap, serverAnswers, serverOverrides) => {
    if (!storage) return;
    // Sunucu gönderdiğimiz snapshot'tan farklı veri döndürdüyse
    // (örn. validator nedeniyle boş döndü), kullanıcının orijinal
    // input'unu temsil eden draft'ı silmeyiz — server değişikliği
    // kabul etmedi, bizim local kopyamız hâlâ geçerli.
    if (
      !sameAnswers(serverAnswers, snap.answers) ||
      !sameOverrides(serverOverrides, snap.risk_overrides)
    ) {
      return;
    }
    // acknowledgedVersion hemen save öncesi snapshot'ın baseVersion'ıdır;
    // aynı şekilde dependency olarak ararız. baseVersion eşleşmiyorsa
    // storage daha yeni bir edit içeriyor demektir — silmeyiz.
    const recovered = readAuditDraft(storage, userId, auditId, acknowledgedVersion - 1);
    if (
      recovered.draft &&
      recovered.draft.baseVersion === acknowledgedVersion - 1 &&
      sameAnswers(recovered.draft.answers, snap.answers) &&
      sameOverrides(recovered.draft.risk_overrides, snap.risk_overrides)
    ) {
      storage.removeItem(auditDraftKey(userId, auditId));
    }
  };

  const settle = (failure) => {
    const current = waiters;
    waiters = [];
    for (const waiter of current) {
      if (failure) waiter.reject(failure);
      else waiter.resolve();
    }
  };

  const classifyError = (failure) => {
    const responseStatus = failure?.response?.status;
    if (responseStatus === 409) return "conflict";
    if (responseStatus === 422) return "validation";
    return "error";
  };

  const run = () => {
    if (!active || inFlight || !pending || status === "conflict") return inFlight?.promise;
    if (timer) {
      clearTimeout(timer);
      timer = null;
    }
    const snapshot = pending;
    pending = null;
    const expectedVersion = acknowledgedVersion;
    const generation = ++requestGeneration;
    const controller = new AbortController();
    status = "saving";
    error = null;
    const cloned = cloneSnapshot(snapshot);
    const promise = Promise.resolve().then(() => saveCallback(cloned, expectedVersion, controller.signal));
    inFlight = { snapshot: cloned, generation, promise, controller };
    notify();
    promise
      .then((result) => {
        if (!active || !inFlight || inFlight.generation !== generation) return;
        inFlight = null;
        acknowledgedVersion = result.version;
        const serverAnswers = result.answers || {};
        const serverOverrides = result.risk_overrides || {};
        const serverSnapshot = {
          answers: cloneAnswers(serverAnswers),
          risk_overrides: cloneOverrides(serverOverrides),
        };
        const newer = pending !== null && !sameSnapshot(pending, snapshot);
        if (pending !== null && !newer) pending = null;
        onAcknowledged(result, !newer);
        if (newer) {
          latest = cloneSnapshot(pending);
          writeDraft(latest);
          status = "dirty";
          notify();
          run();
        } else {
          latest = serverSnapshot;
          clearMatchingDraft(snapshot, serverSnapshot.answers, serverSnapshot.risk_overrides);
          status = "saved";
          notify();
          settle(null);
        }
      })
      .catch((failure) => {
        if (!active || !inFlight || inFlight.generation !== generation) return;
        inFlight = null;
        if (!pending) pending = snapshot;
        latest = cloneSnapshot(pending);
        writeDraft(latest);
        status = classifyError(failure);
        error = failure;
        notify();
        settle(failure);
      });
    return promise;
  };

  const schedule = () => {
    if (timer) clearTimeout(timer);
    timer = setTimeout(() => {
      timer = null;
      run();
    }, debounceMs);
  };

  const editInternal = (payload) => {
    if (!active) return;
    const next = normaliseEdit(payload);
    latest = next;
    pending = next;
    const conflictBaseVersion =
      status === "conflict"
        ? readAuditDraft(storage, userId, auditId, acknowledgedVersion).draft?.baseVersion
        : acknowledgedVersion;
    writeDraft(latest, conflictBaseVersion ?? acknowledgedVersion);
    if (status !== "conflict") {
      status = "dirty";
      error = null;
      schedule();
    }
    notify();
  };

  return {
    edit(payload) {
      editInternal(payload);
    },
    // Yeni açık API — frontend bu imzayı tercih edecek.
    editState(nextState) {
      editInternal(nextState);
    },
    enqueue(payload) {
      editInternal(payload);
    },
    flush() {
      if (!active) return Promise.reject(new Error("Autosave queue disposed"));
      if (status === "conflict") return Promise.reject(error || new Error("Audit version conflict"));
      if (status === "validation" || status === "error")
        return Promise.reject(error || new Error("Autosave save failed"));
      const completion = new Promise((resolve, reject) => waiters.push({ resolve, reject }));
      if (!pending && !inFlight && status === "saved") settle(null);
      else run();
      return completion;
    },
    retry() {
      if (!active || status === "conflict") return;
      status = "dirty";
      error = null;
      notify();
      run();
    },
    restoreConflict(payload) {
      if (!active) return;
      const next = normaliseEdit(payload);
      if (timer) clearTimeout(timer);
      timer = null;
      pending = next;
      latest = next;
      writeDraft(next, acknowledgedVersion);
      status = "conflict";
      error = new Error("Audit version conflict");
      notify();
    },
    reset(payload, version, clearDraft = true) {
      if (!active) return;
      let next;
      // Tek argümanlı legacy answers + version sürümü de desteklenir.
      if (typeof version === "undefined" && typeof payload === "object" && !Array.isArray(payload)) {
        // (answers, version, clearDraft) formunda legacy argüman sıralaması
        // korunur; burada payload = answers, version = version; bu durumu
        // isLegacyAnswersPayload ile yakalayız.
        if (isLegacyAnswersPayload(payload) && Number.isInteger(arguments[1])) {
          next = { answers: cloneAnswers(payload), risk_overrides: {} };
        } else {
          next = normaliseEdit(payload);
        }
      } else if (Number.isInteger(version)) {
        // payload, answers ya da {answers, risk_overrides} olabilir.
        if (isLegacyAnswersPayload(payload)) {
          next = { answers: cloneAnswers(payload), risk_overrides: {} };
        } else {
          next = normaliseEdit(payload);
        }
      } else {
        // eski imza: reset(answers, version, clearDraft)
        const args = arguments;
        next = { answers: cloneAnswers(args[0]), risk_overrides: {} };
        version = args[1];
        clearDraft = args[2] !== false;
      }
      if (timer) clearTimeout(timer);
      if (inFlight) inFlight.controller.abort();
      requestGeneration += 1;
      timer = null;
      inFlight = null;
      pending = null;
      latest = next;
      acknowledgedVersion = Number.isInteger(version) ? version : acknowledgedVersion;
      status = "saved";
      error = null;
      if (clearDraft && storage) storage.removeItem(auditDraftKey(userId, auditId));
      notify();
      settle(null);
    },
    dispose() {
      active = false;
      requestGeneration += 1;
      if (timer) clearTimeout(timer);
      if (inFlight) inFlight.controller.abort();
      timer = null;
      inFlight = null;
      settle(new Error("Autosave queue disposed"));
    },
    getState: state,
    // test-only introspection — production callers MUST not depend on this
    _latest: () => cloneSnapshot(latest),
    _emptySnapshot: emptySnapshot,
  };
}
