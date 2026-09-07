import {
  auditDraftKey,
  createAuditAutosaveQueue,
  createBeforeUnloadGuard,
  readAuditDraft,
} from "./auditAutosave";

const deferred = () => {
  let resolve;
  let reject;
  const promise = new Promise((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
};

const memoryStorage = () => {
  const values = new Map();
  return {
    getItem: jest.fn((key) => values.get(key) ?? null),
    setItem: jest.fn((key, value) => values.set(key, value)),
    removeItem: jest.fn((key) => values.delete(key)),
    clear: jest.fn(() => values.clear()),
    values,
  };
};

const tick = async () => {
  for (let index = 0; index < 8; index += 1) await Promise.resolve();
};

// Snapshot'un {answers, risk_overrides} halini çağrı argümanlarına göre
// karşılaştırırken kullanılan ortak helper.
const expectSnapshotShape = (actual) => {
  expect(actual).toEqual(
    expect.objectContaining({
      answers: expect.any(Object),
      risk_overrides: expect.any(Object),
    }),
  );
};

const lastCallArgs = (save, callIndex = 0) => {
  const call = save.mock.calls[callIndex];
  expectSnapshotShape(call[0]);
  return [call[0], call[1]];
};

const setup = (overrides = {}) => {
  const storage = overrides.storage || memoryStorage();
  const save = overrides.save || jest.fn();
  const states = [];
  const acknowledgements = [];
  const queue = createAuditAutosaveQueue({
    auditId: overrides.auditId || "audit-a",
    userId: overrides.userId || "user-a",
    initialVersion: overrides.initialVersion ?? 4,
    save,
    storage,
    debounceMs: overrides.debounceMs ?? 900,
    onState: (state) => states.push(state),
    onAcknowledged: (result, applyAnswers) => acknowledgements.push({ result, applyAnswers }),
  });
  return { queue, save, storage, states, acknowledgements };
};

beforeEach(() => {
  jest.useFakeTimers();
});

afterEach(() => {
  jest.useRealTimers();
});

// ---------------------------------------------------------------------------
// Core queue behaviour — snapshot = { answers, risk_overrides }
// ---------------------------------------------------------------------------

test("multiple rapid edits create one initial request with the latest snapshot", async () => {
  const request = deferred();
  const { queue, save } = setup({ save: jest.fn(() => request.promise) });
  queue.edit({ "1": "EVET" });
  queue.edit({ "1": "HAYIR" });
  queue.edit({ "1": "NA" });
  jest.advanceTimersByTime(899);
  await tick();
  expect(save).not.toHaveBeenCalled();
  jest.advanceTimersByTime(1);
  await tick();
  expect(save).toHaveBeenCalledTimes(1);
  const [snapshot, version] = lastCallArgs(save);
  expect(snapshot.answers).toEqual({ "1": "NA" });
  expect(snapshot.risk_overrides).toEqual({});
  expect(version).toBe(4);
  queue.dispose();
});

test("in-flight edits are coalesced and sent after success with the acknowledged version", async () => {
  const first = deferred();
  const second = deferred();
  const save = jest
    .fn()
    .mockReturnValueOnce(first.promise)
    .mockReturnValueOnce(second.promise);
  const { queue } = setup({ save });
  queue.edit({ "1": "EVET" });
  jest.advanceTimersByTime(900);
  await tick();
  queue.edit({ "1": "HAYIR" });
  queue.edit({ "1": "NA", "2": "EVET" });
  jest.advanceTimersByTime(900);
  await tick();
  expect(save).toHaveBeenCalledTimes(1);
  first.resolve({ version: 5, answers: { "1": "EVET" }, risk_overrides: {} });
  await tick();
  expect(save).toHaveBeenCalledTimes(2);
  const [snapshot, version] = lastCallArgs(save, 1);
  expect(snapshot.answers).toEqual({ "1": "NA", "2": "EVET" });
  expect(snapshot.risk_overrides).toEqual({});
  expect(version).toBe(5);
  second.resolve({
    version: 6,
    answers: { "1": "NA", "2": "EVET" },
    risk_overrides: {},
  });
  await tick();
});

test("an old response cannot replace a newer pending local snapshot", async () => {
  const first = deferred();
  const second = deferred();
  const { queue, acknowledgements } = setup({
    save: jest.fn().mockReturnValueOnce(first.promise).mockReturnValueOnce(second.promise),
  });
  queue.edit({ "1": "EVET" });
  jest.advanceTimersByTime(900);
  await tick();
  queue.edit({ "1": "HAYIR" });
  first.resolve({ version: 5, answers: { "1": "EVET" }, risk_overrides: {} });
  await tick();
  expect(acknowledgements[0].applyAnswers).toBe(false);
  second.resolve({ version: 6, answers: { "1": "HAYIR" }, risk_overrides: {} });
  await tick();
  expect(acknowledgements[1].applyAnswers).toBe(true);
});

test("HTTP 409 stops automatic saving and preserves the local draft", async () => {
  const conflict = { response: { status: 409 } };
  const save = jest.fn(() => Promise.reject(conflict));
  const { queue, storage } = setup({ save });
  queue.edit({ "1": "HAYIR" });
  jest.advanceTimersByTime(900);
  await tick();
  expect(queue.getState().status).toBe("conflict");
  const draftAfterConflict = JSON.parse(storage.getItem(auditDraftKey("user-a", "audit-a")));
  expect(draftAfterConflict.answers).toEqual({ "1": "HAYIR" });
  expect(draftAfterConflict.risk_overrides).toEqual({});
  queue.edit({ "1": "NA" });
  jest.advanceTimersByTime(5000);
  await tick();
  expect(save).toHaveBeenCalledTimes(1);
  const editedDraft = JSON.parse(storage.getItem(auditDraftKey("user-a", "audit-a")));
  expect(editedDraft.answers).toEqual({ "1": "NA" });
  expect(editedDraft.risk_overrides).toEqual({});
  expect(editedDraft.baseVersion).toBe(4);
});

test("network failure remains dirty and retry sends the preserved snapshot", async () => {
  const failure = new Error("offline");
  const save = jest
    .fn()
    .mockRejectedValueOnce(failure)
    .mockResolvedValueOnce({ version: 5, answers: { "1": "EVET" }, risk_overrides: {} });
  const { queue } = setup({ save });
  queue.edit({ "1": "EVET" });
  jest.advanceTimersByTime(900);
  await tick();
  expect(queue.getState()).toMatchObject({ status: "error", dirty: true });
  queue.retry();
  await tick();
  expect(save).toHaveBeenCalledTimes(2);
  const [snapshot, version] = lastCallArgs(save, 1);
  expect(snapshot.answers).toEqual({ "1": "EVET" });
  expect(snapshot.risk_overrides).toEqual({});
  expect(version).toBe(4);
  expect(queue.getState()).toMatchObject({ status: "saved", dirty: false, version: 5 });
});

test("successful acknowledgement clears the matching session draft", async () => {
  const { queue, storage } = setup({
    save: jest.fn().mockResolvedValue({
      version: 5,
      answers: { "1": "EVET" },
      risk_overrides: {},
    }),
  });
  queue.edit({ "1": "EVET" });
  expect(storage.getItem(auditDraftKey("user-a", "audit-a"))).not.toBeNull();
  jest.advanceTimersByTime(900);
  await tick();
  expect(storage.getItem(auditDraftKey("user-a", "audit-a"))).toBeNull();
});

test("acknowledging an older snapshot does not clear a newer draft", async () => {
  const first = deferred();
  const second = deferred();
  const { queue, storage } = setup({
    save: jest.fn().mockReturnValueOnce(first.promise).mockReturnValueOnce(second.promise),
  });
  queue.edit({ "1": "EVET" });
  jest.advanceTimersByTime(900);
  await tick();
  queue.edit({ "1": "HAYIR" });
  first.resolve({ version: 5, answers: { "1": "EVET" }, risk_overrides: {} });
  await tick();
  const draft = JSON.parse(storage.getItem(auditDraftKey("user-a", "audit-a")));
  expect(draft.answers).toEqual({ "1": "HAYIR" });
  expect(draft.risk_overrides).toEqual({});
  expect(draft.baseVersion).toBe(5);
  second.resolve({ version: 6, answers: { "1": "HAYIR" }, risk_overrides: {} });
  await tick();
});

test("audit route change disposes and aborts the previous queue", async () => {
  const request = deferred();
  const acknowledged = jest.fn();
  const save = jest.fn((snapshot, version, signal) => {
    expectSnapshotShape(snapshot);
    expect(signal.aborted).toBe(false);
    return request.promise;
  });
  const queue = createAuditAutosaveQueue({
    auditId: "audit-a",
    userId: "user-a",
    initialVersion: 0,
    save,
    storage: memoryStorage(),
    debounceMs: 900,
    onAcknowledged: acknowledged,
  });
  queue.edit({ "1": "EVET" });
  jest.advanceTimersByTime(900);
  await tick();
  const signal = save.mock.calls[0][2];
  queue.dispose();
  expect(signal.aborted).toBe(true);
  request.resolve({ version: 1, answers: { "1": "EVET" }, risk_overrides: {} });
  await tick();
  expect(acknowledged).not.toHaveBeenCalled();
});

test("draft storage keys are isolated per user and audit", () => {
  const storage = memoryStorage();
  const first = setup({ auditId: "audit-a", userId: "user-a", storage }).queue;
  const second = setup({ auditId: "audit-a", userId: "user-b", storage }).queue;
  const third = setup({ auditId: "audit-b", userId: "user-a", storage }).queue;
  first.edit({ "1": "EVET" });
  second.edit({ "2": "HAYIR" });
  third.edit({ "3": "NA" });
  expect(JSON.parse(storage.getItem(auditDraftKey("user-a", "audit-a"))).answers).toEqual({ "1": "EVET" });
  expect(JSON.parse(storage.getItem(auditDraftKey("user-b", "audit-a"))).answers).toEqual({ "2": "HAYIR" });
  expect(JSON.parse(storage.getItem(auditDraftKey("user-a", "audit-b"))).answers).toEqual({ "3": "NA" });
  first.dispose();
  second.dispose();
  third.dispose();
});

test("compatible refresh draft is restorable", () => {
  const storage = memoryStorage();
  storage.setItem(
    auditDraftKey("user-a", "audit-a"),
    JSON.stringify({
      userId: "user-a",
      auditId: "audit-a",
      baseVersion: 4,
      answers: { "1": "HAYIR" },
      risk_overrides: { "1": { probability: 4, severity: 5 } },
      timestamp: "2026-07-23T10:00:00.000Z",
    }),
  );
  expect(readAuditDraft(storage, "user-a", "audit-a", 4)).toMatchObject({
    status: "compatible",
    draft: {
      answers: { "1": "HAYIR" },
      risk_overrides: { "1": { probability: 4, severity: 5 } },
    },
  });
});

test("incompatible refresh draft is not marked compatible or auto-submittable", () => {
  const storage = memoryStorage();
  storage.setItem(
    auditDraftKey("user-a", "audit-a"),
    JSON.stringify({
      userId: "user-a",
      auditId: "audit-a",
      baseVersion: 4,
      answers: { "1": "HAYIR" },
      risk_overrides: { "1": { probability: 4, severity: 5 } },
      timestamp: "2026-07-23T10:00:00.000Z",
    }),
  );
  expect(readAuditDraft(storage, "user-a", "audit-a", 5).status).toBe("incompatible");
});

test("beforeunload is active only while dirty or saving", () => {
  const target = {
    addEventListener: jest.fn(),
    removeEventListener: jest.fn(),
  };
  const guard = createBeforeUnloadGuard(target);
  guard.update(false);
  expect(target.addEventListener).not.toHaveBeenCalled();
  guard.update(true);
  expect(target.addEventListener).toHaveBeenCalledWith("beforeunload", expect.any(Function));
  guard.update(false);
  expect(target.removeEventListener).toHaveBeenCalledWith("beforeunload", expect.any(Function));
  guard.dispose();
});

// ---------------------------------------------------------------------------
// Direct recovery-state coverage
// ---------------------------------------------------------------------------

test("flush() awaits the in-flight save and clears the matching draft on success", async () => {
  const request = deferred();
  const save = jest.fn(() => request.promise);
  const { queue, storage } = setup({ save });
  queue.edit({ "1": "EVET" });
  const flushPromise = queue.flush();
  await tick();
  expect(save).toHaveBeenCalledTimes(1);
  const secondFlush = queue.flush();
  await tick();
  expect(save).toHaveBeenCalledTimes(1);
  request.resolve({ version: 5, answers: { "1": "EVET" }, risk_overrides: {} });
  await flushPromise;
  await secondFlush;
  expect(save).toHaveBeenCalledTimes(1);
  expect(queue.getState()).toMatchObject({ status: "saved", dirty: false, version: 5 });
  expect(storage.getItem(auditDraftKey("user-a", "audit-a"))).toBeNull();
});

test("flush() reports 422 as a validation error without starting automatic retry", async () => {
  const validation = { response: { status: 422, data: { detail: "Geçersiz" } } };
  const save = jest.fn(() => Promise.reject(validation));
  const { queue, storage } = setup({ save });
  queue.edit({ "1": "EVET" });
  jest.advanceTimersByTime(900);
  await tick();
  let caught = null;
  try {
    await queue.flush();
  } catch (failure) {
    caught = failure;
  }
  expect(caught).toBe(validation);
  expect(queue.getState()).toMatchObject({ status: "validation", dirty: true });
  jest.advanceTimersByTime(5000);
  await tick();
  expect(save).toHaveBeenCalledTimes(1);
  expect(storage.getItem(auditDraftKey("user-a", "audit-a"))).not.toBeNull();
});

test("reset() cancels timer, aborts in-flight, clears state and matching draft", async () => {
  const request = deferred();
  const save = jest.fn(() => request.promise);
  const { queue, storage } = setup({ save });
  queue.edit({ "1": "EVET" });
  queue.edit({ "1": "HAYIR" });
  jest.advanceTimersByTime(900);
  await tick();
  const signal = save.mock.calls[0][2];
  queue.reset({ "1": "EVET" }, 9, true);
  expect(signal.aborted).toBe(true);
  expect(queue.getState()).toMatchObject({
    status: "saved",
    dirty: false,
    version: 9,
  });
  expect(storage.getItem(auditDraftKey("user-a", "audit-a"))).toBeNull();
  request.resolve({ version: 8, answers: { "1": "HAYIR" } });
  await tick();
});

test("reset() preserves and applies both answers and risk_overrides", async () => {
  const { queue } = setup({ save: jest.fn() });
  queue.reset(
    {
      answers: { "21": "EVET" },
      risk_overrides: { "21": { probability: 4, severity: 5 } },
    },
    11,
    true,
  );
  expect(queue.getState()).toMatchObject({ status: "saved", version: 11 });
  expect(queue._latest()).toEqual({
    answers: { "21": "EVET" },
    risk_overrides: { "21": { probability: 4, severity: 5 } },
  });
});

test("restoreConflict() leaves the queue stuck in conflict until reset", () => {
  const { queue, storage } = setup({ save: jest.fn() });
  queue.restoreConflict({
    answers: { "1": "HAYIR" },
    risk_overrides: { "1": { probability: 3, severity: 2 } },
  });
  expect(queue.getState().status).toBe("conflict");
  const draft = JSON.parse(storage.getItem(auditDraftKey("user-a", "audit-a")));
  expect(draft.answers).toEqual({ "1": "HAYIR" });
  expect(draft.risk_overrides).toEqual({ "1": { probability: 3, severity: 2 } });
});

test("two queues on the same key do not fight over the acknowledgement handshake", async () => {
  const { storage } = { storage: memoryStorage() };
  const requests = [deferred(), deferred()];
  const saveA = jest.fn(() => requests[0].promise);
  const queueA = createAuditAutosaveQueue({
    auditId: "audit-a",
    userId: "user-a",
    initialVersion: 4,
    save: saveA,
    storage,
  });
  const saveB = jest.fn(() => Promise.reject(new Error("network")));
  const queueB = createAuditAutosaveQueue({
    auditId: "audit-a",
    userId: "user-a",
    initialVersion: 4,
    save: saveB,
    storage,
  });
  queueA.edit({ "1": "EVET" });
  jest.advanceTimersByTime(900);
  await tick();
  expect(saveA).toHaveBeenCalledTimes(1);
  requests[0].resolve({ version: 5, answers: { "1": "EVET" }, risk_overrides: {} });
  await tick();
  expect(saveB).not.toHaveBeenCalled();
  queueA.dispose();
  queueB.dispose();
});

test("same user + same audit + same baseVersion can read the draft", () => {
  const storage = memoryStorage();
  storage.setItem(
    auditDraftKey("user-a", "audit-a"),
    JSON.stringify({
      userId: "user-a",
      auditId: "audit-a",
      baseVersion: 7,
      answers: { "1": "EVET" },
      timestamp: "2026-07-23T10:00:00.000Z",
    }),
  );
  expect(readAuditDraft(storage, "user-b", "audit-a", 7)).toEqual({
    status: "none",
    draft: null,
  });
});

test("same user + different audit cannot read the draft", () => {
  const storage = memoryStorage();
  storage.setItem(
    auditDraftKey("user-a", "audit-a"),
    JSON.stringify({
      userId: "user-a",
      auditId: "audit-a",
      baseVersion: 7,
      answers: { "1": "EVET" },
      timestamp: "2026-07-23T10:00:00.000Z",
    }),
  );
  expect(readAuditDraft(storage, "user-a", "audit-b", 7).draft).toBeNull();
});

// ---------------------------------------------------------------------------
// Phase 2B — answers + risk_overrides atomic snapshot contract
// ---------------------------------------------------------------------------

// E. Autosave payload: answers ve risk_overrides aynı snapshot içinde gider.
test("save() receives answers and risk_overrides atomically in one snapshot", async () => {
  const { queue, save } = setup({
    save: jest.fn().mockResolvedValue({
      version: 5,
      answers: { "1": "HAYIR", "21": "EVET" },
      risk_overrides: { "21": { probability: 4, severity: 5 } },
    }),
  });
  queue.editState({
    answers: { "1": "HAYIR", "21": "EVET" },
    risk_overrides: { "21": { probability: 4, severity: 5 } },
  });
  jest.advanceTimersByTime(900);
  await tick();
  expect(save).toHaveBeenCalledTimes(1);
  const [snapshot, version] = lastCallArgs(save);
  expect(snapshot).toEqual({
    answers: { "1": "HAYIR", "21": "EVET" },
    risk_overrides: { "21": { probability: 4, severity: 5 } },
  });
  expect(version).toBe(4);
});

// F. Answer edit: mevcut risk_overrides kaybolmaz.
test("edit(answers) preserves the existing risk_overrides state", async () => {
  const { queue, save, storage } = setup({
    save: jest.fn().mockResolvedValue({
      version: 5,
      answers: { "1": "EVET" },
      risk_overrides: { "21": { probability: 4, severity: 5 } },
    }),
  });
  queue.editState({
    answers: { "21": "EVET" },
    risk_overrides: { "21": { probability: 4, severity: 5 } },
  });
  jest.advanceTimersByTime(900);
  await tick();
  expect(save).toHaveBeenCalledTimes(1);

  // şimdi legacy answers payload ile düzenleme
  queue.edit({ "1": "EVET" });
  jest.advanceTimersByTime(900);
  await tick();
  expect(save).toHaveBeenCalledTimes(2);
  const [snapshot] = lastCallArgs(save, 1);
  expect(snapshot.answers).toEqual({ "1": "EVET" });
  expect(snapshot.risk_overrides).toEqual({ "21": { probability: 4, severity: 5 } });

  // localStorage draft da aynı şekilde güncel olmalı
  const draft = JSON.parse(storage.getItem(auditDraftKey("user-a", "audit-a")));
  expect(draft.answers).toEqual({ "1": "EVET" });
  expect(draft.risk_overrides).toEqual({ "21": { probability: 4, severity: 5 } });
});

// G. Override edit: mevcut answers kaybolmaz.
test("edit({answers, risk_overrides}) preserves the existing answers", async () => {
  const { queue, save, storage } = setup({
    save: jest.fn().mockResolvedValue({
      version: 5,
      answers: { "1": "EVET" },
      risk_overrides: { "21": { probability: 4, severity: 5 } },
    }),
  });
  queue.edit({ "1": "EVET" });
  jest.advanceTimersByTime(900);
  await tick();
  expect(save).toHaveBeenCalledTimes(1);

  // Yalnız risk override güncelleniyor; answers aynen korunmalı.
  queue.editState({
    answers: { "1": "EVET" },
    risk_overrides: { "21": { probability: 3, severity: 5 } },
  });
  jest.advanceTimersByTime(900);
  await tick();
  expect(save).toHaveBeenCalledTimes(2);
  const [snapshot] = lastCallArgs(save, 1);
  expect(snapshot.answers).toEqual({ "1": "EVET" });
  expect(snapshot.risk_overrides).toEqual({ "21": { probability: 3, severity: 5 } });
  const draft = JSON.parse(storage.getItem(auditDraftKey("user-a", "audit-a")));
  expect(draft.risk_overrides).toEqual({ "21": { probability: 3, severity: 5 } });
});

// Eski kuyruk davranışı: edit(payload) override'ı korur.
test("edit() with the legacy answers payload keeps the existing risk_overrides intact", async () => {
  const { queue, save } = setup({
    save: jest.fn().mockResolvedValue({
      version: 5,
      answers: {},
      risk_overrides: {},
    }),
  });
  // İlk override'ı yerleştir.
  queue.editState({
    answers: {},
    risk_overrides: { "21": { probability: 4, severity: 5 } },
  });
  // Sonra legacy shape ile answer-only güncelleme yap.
  queue.edit({ "1": "HAYIR" });
  expect(queue._latest()).toEqual({
    answers: { "1": "HAYIR" },
    risk_overrides: { "21": { probability: 4, severity: 5 } },
  });
  jest.advanceTimersByTime(900);
  await tick();
  const [snapshot] = lastCallArgs(save);
  expect(snapshot.answers).toEqual({ "1": "HAYIR" });
  expect(snapshot.risk_overrides).toEqual({ "21": { probability: 4, severity: 5 } });
});

// H. Legacy draft: eksik risk_overrides crash etmemeli, answers-only olarak geri dönmeli.
test("readAuditDraft() recovers a legacy answers-only draft without crashing", () => {
  const storage = memoryStorage();
  // Eski format — risk_overrides yok.
  storage.setItem(
    auditDraftKey("user-a", "audit-a"),
    JSON.stringify({
      userId: "user-a",
      auditId: "audit-a",
      baseVersion: 4,
      answers: { "1": "HAYIR" },
      timestamp: "2026-07-23T10:00:00.000Z",
    }),
  );
  const recovered = readAuditDraft(storage, "user-a", "audit-a", 4);
  expect(recovered).toMatchObject({
    status: "compatible",
    draft: { answers: { "1": "HAYIR" }, risk_overrides: {} },
  });
});

// Legacy draft komşu test: aynı hook'a sahip 'invalid' shape için invalid dönmeli.
test("readAuditDraft() returns invalid on a corrupted JSON payload", () => {
  const storage = memoryStorage();
  storage.setItem(auditDraftKey("user-a", "audit-a"), "{not-json");
  expect(readAuditDraft(storage, "user-a", "audit-a", 4).status).toBe("invalid");
});

// I. Conflict recovery: answers + risk_overrides birlikte geri yüklenir.
test("readAuditDraft() restores both answers and risk_overrides for compatible recovery", () => {
  const storage = memoryStorage();
  storage.setItem(
    auditDraftKey("user-a", "audit-a"),
    JSON.stringify({
      userId: "user-a",
      auditId: "audit-a",
      baseVersion: 4,
      answers: { "1": "HAYIR", "21": "EVET" },
      risk_overrides: { "21": { probability: 4, severity: 5 } },
      timestamp: "2026-07-23T10:00:00.000Z",
    }),
  );
  const recovered = readAuditDraft(storage, "user-a", "audit-a", 4);
  expect(recovered.status).toBe("compatible");
  expect(recovered.draft.answers).toEqual({ "1": "HAYIR", "21": "EVET" });
  expect(recovered.draft.risk_overrides).toEqual({
    "21": { probability: 4, severity: 5 },
  });
});

test("readAuditDraft() flags an incompatible draft (different baseVersion) but keeps the data", () => {
  const storage = memoryStorage();
  storage.setItem(
    auditDraftKey("user-a", "audit-a"),
    JSON.stringify({
      userId: "user-a",
      auditId: "audit-a",
      baseVersion: 3,
      answers: { "1": "HAYIR" },
      risk_overrides: { "21": { probability: 4, severity: 5 } },
      timestamp: "2026-07-23T10:00:00.000Z",
    }),
  );
  const recovered = readAuditDraft(storage, "user-a", "audit-a", 7);
  expect(recovered.status).toBe("incompatible");
  expect(recovered.draft.answers).toEqual({ "1": "HAYIR" });
  expect(recovered.draft.risk_overrides).toEqual({
    "21": { probability: 4, severity: 5 },
  });
});

test("restoreConflict({answers, risk_overrides}) writes both into session storage", () => {
  const { queue, storage } = setup({ save: jest.fn() });
  queue.restoreConflict({
    answers: { "1": "HAYIR", "21": "EVET" },
    risk_overrides: { "21": { probability: 4, severity: 5 } },
  });
  const draft = JSON.parse(storage.getItem(auditDraftKey("user-a", "audit-a")));
  expect(draft.answers).toEqual({ "1": "HAYIR", "21": "EVET" });
  expect(draft.risk_overrides).toEqual({ "21": { probability: 4, severity: 5 } });
  expect(queue.getState().status).toBe("conflict");
});

test("invalid risk_overrides values are dropped (non-integer factors cannot enter storage)", async () => {
  const { queue, save, storage } = setup({
    save: jest.fn().mockResolvedValue({ version: 5, answers: {}, risk_overrides: {} }),
  });
  queue.editState({
    answers: {},
    risk_overrides: {
      "1": { probability: 4, severity: 5 },
      "bogus": { probability: 3.5, severity: 4 },
      "wrong": "string",
    },
  });
  jest.advanceTimersByTime(900);
  await tick();
  const [snapshot] = lastCallArgs(save);
  expect(snapshot.risk_overrides).toEqual({ "1": { probability: 4, severity: 5 } });
  const draft = JSON.parse(storage.getItem(auditDraftKey("user-a", "audit-a")));
  expect(draft.risk_overrides).toEqual({ "1": { probability: 4, severity: 5 } });
});
