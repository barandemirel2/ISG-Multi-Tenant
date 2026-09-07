// Unit tests for frontend/src/lib/dof.js — pure DÖF helpers.
// No DOM, no React, no network. Mocks are not required.
//
// Test runner: craco test (Jest + jsdom from react-scripts).
import {
  DOF_STATUSES,
  STATUS_FILTER_OPTIONS,
  RISK_LEVELS_CANONICAL,
  RISK_FILTER_OPTIONS,
  MAX_NOTES_LENGTH,
  normalizeNotes,
  filterDofs,
  buildUpdatePayload,
  validateKapatildiNotes,
  applyPutResponseToItem,
  computeKpis,
  formatUpdatedAt,
  isDirty,
} from "./dof";

// ---------------------------------------------------------------------------
// Fixture: representative GET /api/dofs payload covering status, risk_level,
// legal_basis, optional fields (updated_at / updated_by), and admin scope.
// ---------------------------------------------------------------------------
function makeFixture() {
  return [
    {
      audit_id: "a1",
      audit_user_id: "u1",
      owner_name: "Ali Yılmaz",
      restaurant_name: "Merkez Şube",
      audit_date: "2026-07-15",
      question_id: 1,
      question_no: 3,
      category: "Hijyen",
      question: "Mutfak sıcaklık takibi yapılıyor mu?",
      responsible: "Şef",
      probability: 5,
      severity: 5,
      risk_score: 25,
      risk_level: "Kabul Edilemez",
      document_risk_level: "Kabul Edilemez",
      deadline: "2026-08-01",
      legal_basis: ["Yönetmelik Madde 5", "Yönetmelik Madde 12"],
      corrective_action: "Sıcaklık ölçer temin edilecek",
      status: "AÇIK",
      notes: "",
      updated_at: null,
      updated_by: null,
    },
    {
      audit_id: "a1",
      audit_user_id: "u1",
      owner_name: "Ali Yılmaz",
      restaurant_name: "Merkez Şube",
      audit_date: "2026-07-15",
      question_id: 7,
      question_no: 14,
      category: "Eğitim",
      question: "Personel hijyen eğitimi aldı mı?",
      responsible: "İK",
      probability: 3,
      severity: 4,
      risk_score: 12,
      risk_level: "Dikkate Değer",
      document_risk_level: "Dikkate Değer",
      deadline: "2026-09-01",
      legal_basis: [],
      corrective_action: "Eğitim planı hazırlanacak",
      status: "İŞLEMDE",
      notes: "Tedarikçi ile görüşüldü",
      updated_at: "2026-08-01T10:00:00Z",
      updated_by: "u1",
    },
    {
      audit_id: "a2",
      audit_user_id: "u2",
      owner_name: "Ayşe Demir",
      restaurant_name: "Cadde Şube",
      audit_date: "2026-06-10",
      question_id: 2,
      question_no: 5,
      category: "Hijyen",
      question: "El yıkama talimatı asılı mı?",
      responsible: "Müdür",
      probability: 2,
      severity: 3,
      risk_score: 6,
      risk_level: "Kabul Edilebilir",
      document_risk_level: "Kabul Edilebilir",
      deadline: "2026-07-01",
      legal_basis: ["Yönetmelik Madde 3"],
      corrective_action: "",
      status: "KAPATILDI",
      notes: "Talimat asıldı ve fotoğraflandı",
      updated_at: "2026-07-02T09:30:00Z",
      updated_by: "u2",
    },
  ];
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------
describe("constants", () => {
  test("DOF_STATUSES contains exactly the three canonical statuses", () => {
    expect(DOF_STATUSES).toEqual(["AÇIK", "İŞLEMDE", "KAPATILDI"]);
  });

  test("STATUS_FILTER_OPTIONS leads with HEPSİ then DOF_STATUSES", () => {
    expect(STATUS_FILTER_OPTIONS).toEqual(["HEPSİ", ...DOF_STATUSES]);
  });

  test("RISK_LEVELS_CANONICAL contains the three canonical Turkish labels", () => {
    expect(RISK_LEVELS_CANONICAL).toEqual([
      "Kabul Edilemez",
      "Dikkate Değer",
      "Kabul Edilebilir",
    ]);
  });

  test("RISK_FILTER_OPTIONS leads with HEPSİ", () => {
    expect(RISK_FILTER_OPTIONS[0]).toBe("HEPSİ");
    expect(RISK_FILTER_OPTIONS).toHaveLength(4);
  });

  test("MAX_NOTES_LENGTH is 2000 (matches backend Pydantic constraint)", () => {
    expect(MAX_NOTES_LENGTH).toBe(2000);
  });
});

// ---------------------------------------------------------------------------
// normalizeNotes
// ---------------------------------------------------------------------------
describe("normalizeNotes", () => {
  test("returns empty string for null/undefined", () => {
    expect(normalizeNotes(null)).toBe("");
    expect(normalizeNotes(undefined)).toBe("");
  });

  test("strips leading and trailing whitespace", () => {
    expect(normalizeNotes("  hello  ")).toBe("hello");
  });

  test("preserves internal whitespace", () => {
    expect(normalizeNotes("  a b  c  ")).toBe("a b  c");
  });

  test("returns empty string when input is only whitespace", () => {
    expect(normalizeNotes("   \t  \n ")).toBe("");
  });
});

// ---------------------------------------------------------------------------
// filterDofs
// ---------------------------------------------------------------------------
describe("filterDofs", () => {
  const dofs = makeFixture();

  test("returns empty array for non-array input", () => {
    expect(filterDofs(null)).toEqual([]);
    expect(filterDofs(undefined)).toEqual([]);
    expect(filterDofs("nope")).toEqual([]);
  });

  test("returns empty array for empty input", () => {
    expect(filterDofs([])).toEqual([]);
  });

  test("with HEPSİ status and HEPSİ risk and empty search returns all", () => {
    expect(filterDofs(dofs)).toHaveLength(3);
  });

  test("status filter keeps only matching status", () => {
    expect(filterDofs(dofs, { status: "AÇIK" })).toHaveLength(1);
    expect(filterDofs(dofs, { status: "İŞLEMDE" })).toHaveLength(1);
    expect(filterDofs(dofs, { status: "KAPATILDI" })).toHaveLength(1);
  });

  test("risk filter keeps only matching risk_level", () => {
    expect(filterDofs(dofs, { riskLevel: "Kabul Edilemez" })).toHaveLength(1);
    expect(filterDofs(dofs, { riskLevel: "Dikkate Değer" })).toHaveLength(1);
    expect(filterDofs(dofs, { riskLevel: "Kabul Edilebilir" })).toHaveLength(1);
  });

  test("status + risk combine with AND", () => {
    expect(
      filterDofs(dofs, { status: "AÇIK", riskLevel: "Kabul Edilemez" })
    ).toHaveLength(1);
    expect(
      filterDofs(dofs, { status: "KAPATILDI", riskLevel: "Kabul Edilebilir" })
    ).toHaveLength(1);
    expect(
      filterDofs(dofs, { status: "KAPATILDI", riskLevel: "Kabul Edilemez" })
    ).toHaveLength(0);
  });

  test("search is case-insensitive substring on restaurant_name", () => {
    expect(filterDofs(dofs, { search: "merkez" })).toHaveLength(2);
    expect(filterDofs(dofs, { search: "MERKEZ" })).toHaveLength(2);
    expect(filterDofs(dofs, { search: "cadde" })).toHaveLength(1);
  });

  test("search matches question, category, and responsible too", () => {
    expect(filterDofs(dofs, { search: "eğitim" })).toHaveLength(1);
    expect(filterDofs(dofs, { search: "hijyen" })).toHaveLength(3);
    expect(filterDofs(dofs, { search: "müdür" })).toHaveLength(1);
  });

  test("search trims whitespace; whitespace-only is no-op", () => {
    expect(filterDofs(dofs, { search: "   " })).toHaveLength(3);
    expect(filterDofs(dofs, { search: "" })).toHaveLength(3);
  });

  test("search with no match returns empty", () => {
    expect(filterDofs(dofs, { search: "yok böyle bir şey" })).toEqual([]);
  });

  test("does not mutate input array", () => {
    const before = [...dofs];
    filterDofs(dofs, { status: "AÇIK" });
    expect(dofs).toEqual(before);
  });

  test("filters out non-object entries", () => {
    expect(filterDofs([null, undefined, 0, {}, ...dofs])).toHaveLength(3);
  });

  // -------------------------------------------------------------------------
  // Brand filter (PR2 contract): workspace / UI filter, not a security
  // boundary. The function exposes a substring-based filter against
  // ``restaurant_name`` and ``brand``. Behavior pinned:
  //
  //   * brand omitted / falsy → no-op
  //   * "Tüm Markalar" / "HEPSİ" → no-op
  //   * matching brand substring on either field → included
  //   * non-matching brand → excluded
  //   * case-insensitive matching (lower / upper / mixed)
  //   * fallback to ``brand`` field if ``restaurant_name`` lacks the term
  // -------------------------------------------------------------------------
  describe("filterDofs — brand filter", () => {
    const branded = [
      {
        audit_id: "a1",
        restaurant_name: "Burger King Kadıköy",
        brand: "Burger King",
        status: "AÇIK",
        risk_level: "Kabul Edilemez",
      },
      {
        audit_id: "a2",
        restaurant_name: "Popeyes Bağdat Cad.",
        brand: "Popeyes",
        status: "AÇIK",
        risk_level: "Dikkate Değer",
      },
      {
        audit_id: "a3",
        restaurant_name: "Subway Mecidiyeköy",
        brand: "Subway",
        status: "KAPATILDI",
        risk_level: "Kabul Edilebilir",
      },
      {
        audit_id: "a4",
        // No brand field — only restaurant_name substring is available.
        restaurant_name: "Usta Dönerci Beşiktaş",
        status: "AÇIK",
        risk_level: "Dikkate Değer",
      },
    ];

    test("omitted brand preserves existing behavior", () => {
      expect(filterDofs(branded)).toHaveLength(4);
    });

    test("empty-string brand is treated as no filter", () => {
      expect(filterDofs(branded, { brand: "" })).toHaveLength(4);
    });

    test("'HEPSİ' brand is treated as no filter", () => {
      expect(filterDofs(branded, { brand: "HEPSİ" })).toHaveLength(4);
    });

    test("'Tüm Markalar' brand is treated as no filter", () => {
      // BrandSelectionPage's "Tüm Markalar" pseudo-brand must NOT
      // filter anything out — it's the workspace all-markets view.
      expect(filterDofs(branded, { brand: "Tüm Markalar" })).toHaveLength(4);
    });

    test("matching brand returns matching items", () => {
      expect(
        filterDofs(branded, { brand: "Burger King" })
      ).toHaveLength(1);
      expect(filterDofs(branded, { brand: "Popeyes" }).map((x) => x.audit_id)).toEqual(["a2"]);
    });

    test("non-matching brand excludes unrelated items", () => {
      // Asking for Burger King should NOT return Popeyes / Subway / Usta.
      const result = filterDofs(branded, { brand: "Burger King" });
      const auditIds = result.map((x) => x.audit_id);
      expect(auditIds).toEqual(["a1"]);
    });

    test("case normalization: lower-case input matches mixed-case data", () => {
      expect(
        filterDofs(branded, { brand: "burger king" })
      ).toHaveLength(1);
      expect(
        filterDofs(branded, { brand: "BURGER KING" })
      ).toHaveLength(1);
    });

    test("brand field fallback when restaurant_name lacks the term", () => {
      // Restaurant is "Usta Dönerci Beşiktaş" (no "Usta Dönerci" prefix).
      // We don't expect a match here, since "Usta Dönerci" isn't a
      // substring of "Usta Dönerci Beşiktaş"... actually it IS. The
      // substring match is exact: "Usta Dönerci" ⊂ "Usta Dönerci Beşiktaş".
      expect(
        filterDofs(branded, { brand: "Usta Dönerci" })
      ).toHaveLength(1);
    });

    test("combined brand + status filter uses AND", () => {
      // The brand filter is AND-composed with status + risk_level.
      expect(
        filterDofs(branded, {
          brand: "Burger King",
          status: "AÇIK",
        })
      ).toHaveLength(1);

      // Burger King AÇIK ∩ KAPATILDI = ∅ (no closed Burger King entries).
      expect(
        filterDofs(branded, {
          brand: "Burger King",
          status: "KAPATILDI",
        })
      ).toHaveLength(0);
    });

    test("brand filter does not mutate input", () => {
      const before = branded.map((x) => ({ ...x }));
      filterDofs(branded, { brand: "Burger King" });
      expect(branded).toEqual(before);
    });
  });
});

// ---------------------------------------------------------------------------
// buildUpdatePayload
// ---------------------------------------------------------------------------
describe("buildUpdatePayload", () => {
  const item = { status: "AÇIK", notes: "önceki not" };

  test("uses draft status when provided", () => {
    expect(buildUpdatePayload(item, { status: "KAPATILDI", notes: "bitti" })).toEqual({
      status: "KAPATILDI",
      notes: "bitti",
    });
  });

  test("falls back to currentItem.status when draft.status missing", () => {
    expect(buildUpdatePayload(item, { notes: "sadece not" })).toEqual({
      status: "AÇIK",
      notes: "sadece not",
    });
  });

  test("falls back to currentItem.notes when draft.notes missing", () => {
    expect(buildUpdatePayload(item, { status: "İŞLEMDE" })).toEqual({
      status: "İŞLEMDE",
      notes: "önceki not",
    });
  });

  test("falls back to AÇIK when neither draft nor item has a status", () => {
    expect(buildUpdatePayload({}, { notes: "x" })).toEqual({
      status: "AÇIK",
      notes: "x",
    });
  });

  test("trims notes (mirrors backend validator)", () => {
    expect(
      buildUpdatePayload(item, { status: "KAPATILDI", notes: "  bitti  " })
    ).toEqual({ status: "KAPATILDI", notes: "bitti" });
  });

  test("preserves whitespace-only as empty string (server treats same)", () => {
    expect(buildUpdatePayload(item, { status: "AÇIK", notes: "   " })).toEqual({
      status: "AÇIK",
      notes: "",
    });
  });
});

// ---------------------------------------------------------------------------
// validateKapatildiNotes
// ---------------------------------------------------------------------------
describe("validateKapatildiNotes", () => {
  test("KAPATILDI + empty notes is rejected", () => {
    expect(validateKapatildiNotes({ status: "KAPATILDI", notes: "" })).toEqual({
      ok: false,
      message: "KAPATILDI durumunda not zorunludur",
    });
  });

  test("KAPATILDI + whitespace-only notes is rejected", () => {
    expect(validateKapatildiNotes({ status: "KAPATILDI", notes: "   \n  " })).toEqual({
      ok: false,
      message: "KAPATILDI durumunda not zorunludur",
    });
  });

  test("KAPATILDI + non-empty notes passes", () => {
    expect(validateKapatildiNotes({ status: "KAPATILDI", notes: "bitti" })).toEqual({
      ok: true,
    });
  });

  test("AÇIK + empty notes is allowed (user can clear the note)", () => {
    expect(validateKapatildiNotes({ status: "AÇIK", notes: "" })).toEqual({ ok: true });
  });

  test("İŞLEMDE + empty notes is allowed", () => {
    expect(validateKapatildiNotes({ status: "İŞLEMDE", notes: "" })).toEqual({ ok: true });
  });
});

// ---------------------------------------------------------------------------
// applyPutResponseToItem
// ---------------------------------------------------------------------------
describe("applyPutResponseToItem", () => {
  const item = {
    audit_id: "a1",
    question_id: 7,
    restaurant_name: "Merkez Şube",
    risk_level: "Dikkate Değer",
    status: "İŞLEMDE",
    notes: "eski",
    updated_at: null,
    updated_by: null,
    category: "Eğitim",
  };

  test("merges 6 response.dof fields into the existing item", () => {
    const result = applyPutResponseToItem(item, {
      audit_id: "a1",
      question_id: 7,
      status: "KAPATILDI",
      notes: "yeni",
      updated_at: "2026-08-04T19:30:00Z",
      updated_by: "u9",
    });
    expect(result).toEqual({
      ...item,
      status: "KAPATILDI",
      notes: "yeni",
      updated_at: "2026-08-04T19:30:00Z",
      updated_by: "u9",
    });
  });

  test("preserves all non-response fields", () => {
    const result = applyPutResponseToItem(item, {
      status: "KAPATILDI",
      notes: "yeni",
      updated_at: "x",
      updated_by: "u9",
      audit_id: "a1",
      question_id: 7,
    });
    expect(result.restaurant_name).toBe("Merkez Şube");
    expect(result.risk_level).toBe("Dikkate Değer");
    expect(result.category).toBe("Eğitim");
  });

  test("returns the original item if response.dof is missing", () => {
    expect(applyPutResponseToItem(item, null)).toBe(item);
    expect(applyPutResponseToItem(item, undefined)).toBe(item);
  });

  test("returns the original item if response.dof is not an object", () => {
    expect(applyPutResponseToItem(item, "nope")).toBe(item);
  });

  test("returns the original item if item is invalid", () => {
    expect(applyPutResponseToItem(null, { status: "AÇIK" })).toBe(null);
  });

  test("does not crash when response.dof omits optional fields", () => {
    const result = applyPutResponseToItem(item, {
      status: "İŞLEMDE",
      notes: "q",
    });
    expect(result.status).toBe("İŞLEMDE");
    expect(result.notes).toBe("q");
    expect(result.updated_at).toBe(item.updated_at); // null fallback
    expect(result.updated_by).toBe(item.updated_by); // null fallback
  });
});

// ---------------------------------------------------------------------------
// computeKpis
// ---------------------------------------------------------------------------
describe("computeKpis", () => {
  test("returns zero counts for empty / null input", () => {
    expect(computeKpis([])).toEqual({ total: 0, acik: 0, islemde: 0, kapatildi: 0 });
    expect(computeKpis(null)).toEqual({ total: 0, acik: 0, islemde: 0, kapatildi: 0 });
  });

  test("counts each status", () => {
    const dofs = makeFixture();
    expect(computeKpis(dofs)).toEqual({
      total: 3,
      acik: 1,
      islemde: 1,
      kapatildi: 1,
    });
  });

  test("ignores entries with unknown status", () => {
    expect(
      computeKpis([
        { status: "AÇIK" },
        { status: "BİLİNMİYOR" },
        { status: "İŞLEMDE" },
      ])
    ).toEqual({ total: 3, acik: 1, islemde: 1, kapatildi: 0 });
  });

  test("skips non-object entries without crashing", () => {
    expect(
      computeKpis([null, undefined, { status: "KAPATILDI" }])
    ).toEqual({ total: 3, acik: 0, islemde: 0, kapatildi: 1 });
  });
});

// ---------------------------------------------------------------------------
// formatUpdatedAt
// ---------------------------------------------------------------------------
describe("formatUpdatedAt", () => {
  test("returns null for null / undefined / empty", () => {
    expect(formatUpdatedAt(null)).toBeNull();
    expect(formatUpdatedAt(undefined)).toBeNull();
    expect(formatUpdatedAt("")).toBeNull();
  });

  test("formats a valid ISO string with tr-TR locale", () => {
    const out = formatUpdatedAt("2026-08-01T10:00:00Z");
    expect(typeof out).toBe("string");
    // The exact format depends on Node ICU; just ensure both date and time
    // separators are present in the output.
    expect(out).toMatch(/2026/);
    expect(out.length).toBeGreaterThan(5);
  });

  test("falls back to raw value when input cannot be parsed", () => {
    expect(formatUpdatedAt("not-a-date")).toBe("not-a-date");
  });
});

// ---------------------------------------------------------------------------
// isDirty
// ---------------------------------------------------------------------------
describe("isDirty", () => {
  test("returns false when both status and notes match", () => {
    expect(isDirty({ status: "AÇIK", notes: "" }, { status: "AÇIK", notes: "" })).toBe(false);
  });

  test("returns true when status diverges", () => {
    expect(isDirty({ status: "AÇIK", notes: "" }, { status: "İŞLEMDE", notes: "" })).toBe(true);
  });

  test("returns true when notes diverge", () => {
    expect(isDirty({ status: "AÇIK", notes: "a" }, { status: "AÇIK", notes: "b" })).toBe(true);
  });

  test("returns false when either side is missing", () => {
    expect(isDirty(null, { status: "AÇIK", notes: "" })).toBe(false);
    expect(isDirty({ status: "AÇIK", notes: "" }, null)).toBe(false);
  });

  test("treats undefined status/notes as empty string", () => {
    expect(isDirty({}, { status: "", notes: "" })).toBe(false);
  });
});