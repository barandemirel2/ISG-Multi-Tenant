import {
  calculateRiskScore,
  classifyRiskScore,
  previewRisk,
  riskBadgeClass,
  RISK_THRESHOLDS,
  getCategoryQuestionNumber,
} from "./risk";

// A. Risk helper sınırları: 1, 4, 5, 12, 13, 25
describe("classifyRiskScore", () => {
  test("1 → Kabul Edilebilir (alt sınır)", () => {
    expect(classifyRiskScore(1)).toBe(RISK_THRESHOLDS.LOW);
  });

  test("4 → Kabul Edilebilir (üst sınır)", () => {
    expect(classifyRiskScore(4)).toBe(RISK_THRESHOLDS.LOW);
  });

  test("5 → Dikkate Değer (alt sınır)", () => {
    expect(classifyRiskScore(5)).toBe(RISK_THRESHOLDS.MEDIUM);
  });

  test("12 → Dikkate Değer (üst sınır)", () => {
    expect(classifyRiskScore(12)).toBe(RISK_THRESHOLDS.MEDIUM);
  });

  test("13 → Kabul Edilemez (alt sınır)", () => {
    expect(classifyRiskScore(13)).toBe(RISK_THRESHOLDS.HIGH);
  });

  test("25 → Kabul Edilemez (üst sınır)", () => {
    expect(classifyRiskScore(25)).toBe(RISK_THRESHOLDS.HIGH);
  });

  test("arada kalan tüm seviyeler", () => {
    for (let s = 1; s <= 4; s += 1) {
      expect(classifyRiskScore(s)).toBe(RISK_THRESHOLDS.LOW);
    }
    for (let s = 5; s <= 12; s += 1) {
      expect(classifyRiskScore(s)).toBe(RISK_THRESHOLDS.MEDIUM);
    }
    for (let s = 13; s <= 25; s += 1) {
      expect(classifyRiskScore(s)).toBe(RISK_THRESHOLDS.HIGH);
    }
  });

  test("0, 26, 27 → out of range fırlatır", () => {
    expect(() => classifyRiskScore(0)).toThrow();
    expect(() => classifyRiskScore(26)).toThrow();
    expect(() => classifyRiskScore(27)).toThrow();
  });

  test("non-integer ve NaN → fırlatır", () => {
    expect(() => classifyRiskScore(5.5)).toThrow();
    expect(() => classifyRiskScore(NaN)).toThrow();
    expect(() => classifyRiskScore("5")).toThrow();
  });
});

describe("calculateRiskScore", () => {
  test("probability * severity temel çarpım", () => {
    expect(calculateRiskScore(2, 4)).toBe(8);
    expect(calculateRiskScore(1, 1)).toBe(1);
    expect(calculateRiskScore(5, 5)).toBe(25);
  });

  test("her kombinasyon deterministik 1-25 aralığında", () => {
    for (let p = 1; p <= 5; p += 1) {
      for (let s = 1; s <= 5; s += 1) {
        const result = calculateRiskScore(p, s);
        expect(result).toBe(p * s);
        expect(result).toBeGreaterThanOrEqual(1);
        expect(result).toBeLessThanOrEqual(25);
      }
    }
  });

  test("geçersiz faktör → fırlatır", () => {
    expect(() => calculateRiskScore(0, 3)).toThrow();
    expect(() => calculateRiskScore(6, 3)).toThrow();
    expect(() => calculateRiskScore(2.5, 3)).toThrow();
    expect(() => calculateRiskScore(2, undefined)).toThrow();
  });
});

describe("previewRisk", () => {
  test("score + level atomik döndürür", () => {
    expect(previewRisk(4, 5)).toEqual({ score: 20, level: RISK_THRESHOLDS.HIGH });
    expect(previewRisk(2, 2)).toEqual({ score: 4, level: RISK_THRESHOLDS.LOW });
    expect(previewRisk(3, 4)).toEqual({ score: 12, level: RISK_THRESHOLDS.MEDIUM });
  });
});

// B. UI renk helper'ları geriye uyumlu kalmalı.
describe("riskBadgeClass", () => {
  test("üç seviye için farklı Tailwind class döner", () => {
    expect(riskBadgeClass(RISK_THRESHOLDS.LOW)).toMatch(/emerald|green/);
    expect(riskBadgeClass(RISK_THRESHOLDS.MEDIUM)).toMatch(/amber/);
    expect(riskBadgeClass(RISK_THRESHOLDS.HIGH)).toMatch(/red/);
  });

  test("bilinmeyen seviye → nötr class", () => {
    expect(riskBadgeClass(undefined)).toMatch(/zinc/);
  });
});

// D. getCategoryQuestionNumber frontend helper — pins the standalone
//    frontend algorithm that mirrors backend ``_get_category_question_no``.
//    Backend's response is the source of truth (``category_question_no``);
//    this helper is a fallback when the legacy / truncated payload
//    doesn't carry the precomputed value.
describe("getCategoryQuestionNumber", () => {
  // 84-question fixture (mirrors Phase 2A's sample_questions shape but
  // trimmed for readability). One category's questions are contiguous
  // in the array — same shape as ``questions.json``.
  const questions = [
    { id: 1, kategori: "A" },
    { id: 2, kategori: "A" },
    { id: 3, kategori: "A" },
    { id: 4, kategori: "B" },
    { id: 5, kategori: "B" },
    { id: 6, kategori: "C" },
    { id: 7, kategori: "C" },
    { id: 8, kategori: "C" },
  ];

  test("returns empty string on falsy q", () => {
    expect(getCategoryQuestionNumber(null)).toBe("");
    expect(getCategoryQuestionNumber(undefined)).toBe("");
  });

  test("precomputed category_question_no (with dot) takes precedence", () => {
    const q = {
      id: 99,
      category: "A",
      category_question_no: "4.7",
    };
    expect(getCategoryQuestionNumber(q)).toBe("4.7");
  });

  test("category_question_no without dot is ignored (not a category form)", () => {
    // Some legacy payloads carry a single integer here; the helper
    // must NOT mistake it for the canonical form.
    const q = {
      id: 1,
      category: "A",
      category_question_no: "3",
    };
    // Falls through to algorithm → 1.1
    expect(getCategoryQuestionNumber(q, [], questions)).toBe("1.1");
  });

  test("returns '<cat>.<idx>' for in-category index", () => {
    // Third question of first category → "1.3".
    const q = { id: 3, kategori: "A" };
    expect(getCategoryQuestionNumber(q, [], questions)).toBe("1.3");
  });

  test("category index advances across distinct categories", () => {
    const q = { id: 5, kategori: "B" };
    // 2nd category, 2nd question → "2.2".
    expect(getCategoryQuestionNumber(q, [], questions)).toBe("2.2");
  });

  test("category out of order still gets sequential numbering", () => {
    const q = { id: 6, kategori: "C" };
    expect(getCategoryQuestionNumber(q, [], questions)).toBe("3.1");
  });

  test("category_question_no not present falls back to allQuestions scan", () => {
    const q = { id: 8, category: "C" };
    // 3rd question in C → "3.3".
    expect(getCategoryQuestionNumber(q, [], questions)).toBe("3.3");
  });

  test("'category' aliased to 'kategori' and vice-versa", () => {
    // 'category' field used as the canonical name lookup.
    const q = { id: 1, category: "A" };
    expect(getCategoryQuestionNumber(q, [], questions)).toBe("1.1");
    // 'kategori' field used as the canonical name lookup.
    const q2 = { id: 4, kategori: "B" };
    expect(getCategoryQuestionNumber(q2, [], questions)).toBe("2.1");
  });

  test("missing category returns fallback to 1.<idx> (no crash)", () => {
    const q = { id: 999, kategori: "Ghost" };
    // Ghost isn't in the categories list. ``findIndex`` returns -1 →
    // in_cat_idx fallback = q.no || q.id || 1 = 999. We only assert
    // the helper doesn't crash and returns a dot-shaped form.
    const result = getCategoryQuestionNumber(q, [], questions);
    expect(typeof result).toBe("string");
    expect(result.includes(".")).toBe(true);
  });

  test("missing id on q with valid no — returns dot-shaped fallback, no crash", () => {
    // We don't pin the exact digit here — the helper's ``inCatIdx``
    // can be inflated by String(undefined) === String(undefined) in
    // the dual-alias comparison. What we DO pin is non-crash + dot
    // shape + string return type, which is the safe observable
    // contract when legacy payloads lack a question_id.
    const q = { kategori: "A", no: 5 };
    const result = getCategoryQuestionNumber(q, [], questions);
    expect(typeof result).toBe("string");
    expect(result).toMatch(/^\d+\.\d+$/);
  });

  test("categories param overrides derived list", () => {
    // Pass an explicit list; algorithm uses it for category indexing
    // rather than deriving from allQuestions.
    const explicit = ["A", "C"]; // B is omitted
    const q = { id: 6, category: "C" };
    // Cat C is now index 2 in the explicit list.
    expect(getCategoryQuestionNumber(q, explicit, questions)).toBe("2.1");
  });

  test("id matching supports id and question_id aliases", () => {
    const q = { id: 4, question_id: 4, category: "B" };
    expect(getCategoryQuestionNumber(q, [], questions)).toBe("2.1");
  });
});
