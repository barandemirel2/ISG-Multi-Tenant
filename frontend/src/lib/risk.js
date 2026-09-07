// ---------------------------------------------------------------------------
// Risk level ↔ Tailwind class helpers (UI-only)
// ---------------------------------------------------------------------------

export function riskBadgeClass(level) {
  switch (level) {
    case "Kabul Edilemez":
      return "bg-red-600 text-white";
    case "Dikkate Değer":
      return "bg-amber-500 text-white";
    case "Kabul Edilebilir":
      return "bg-emerald-600 text-white";
    default:
      return "bg-zinc-200 text-zinc-700";
  }
}

export function riskSurfaceClass(level) {
  switch (level) {
    case "Kabul Edilemez":
      return "bg-red-50 border-red-200";
    case "Dikkate Değer":
      return "bg-amber-50 border-amber-200";
    case "Kabul Edilebilir":
      return "bg-emerald-50 border-emerald-200";
    default:
      return "bg-zinc-50 border-zinc-200";
  }
}

// ---------------------------------------------------------------------------
// Risk score primitives (frontend preview only — backend is canonical).
//
// The whole UI (OverrideEditor, future risk panels) MUST go through these
// helpers so the 1–4 / 5–12 / 13–25 thresholds live in exactly one place.
// ---------------------------------------------------------------------------

const RISK_LIMITS = Object.freeze({
  LOW_MAX: 4,
  MEDIUM_MAX: 12,
  HIGH_MAX: 25,
  MIN: 1,
});

const RISK_LEVEL_LOW = "Kabul Edilebilir";
const RISK_LEVEL_MEDIUM = "Dikkate Değer";
const RISK_LEVEL_HIGH = "Kabul Edilemez";

const RISK_LEVEL_RANGE = Object.freeze({
  [RISK_LEVEL_LOW]: [1, RISK_LIMITS.LOW_MAX],
  [RISK_LEVEL_MEDIUM]: [RISK_LIMITS.LOW_MAX + 1, RISK_LIMITS.MEDIUM_MAX],
  [RISK_LEVEL_HIGH]: [RISK_LIMITS.MEDIUM_MAX + 1, RISK_LIMITS.HIGH_MAX],
});

const isFactor = (value) =>
  Number.isInteger(value) && value >= RISK_LIMITS.MIN && value <= 5;

/**
 * Pure: probability (1-5) * severity (1-5) → integer score (1-25).
 * Throws for any out-of-range or non-integer factor so the UI surfaces the
 * bug immediately instead of silently masking it with a NaN.
 */
export function calculateRiskScore(probability, severity) {
  if (!isFactor(probability) || !isFactor(severity)) {
    throw new Error(
      `calculateRiskScore requires integer factors 1-5; got ` +
        `probability=${probability}, severity=${severity}`,
    );
  }
  return probability * severity;
}

/**
 * Pure: integer score (1-25) → "Kabul Edilebilir" | "Dikkate Değer" |
 * "Kabul Edilemez". Boundary scores (1, 4, 5, 12, 13, 25) stay deterministic.
 */
export function classifyRiskScore(score) {
  if (!Number.isInteger(score) || score < RISK_LIMITS.MIN || score > RISK_LIMITS.HIGH_MAX) {
    throw new Error(`classifyRiskScore requires integer 1-25; got ${score}`);
  }
  if (score >= RISK_LEVEL_RANGE[RISK_LEVEL_HIGH][0]) return RISK_LEVEL_HIGH;
  if (score >= RISK_LEVEL_RANGE[RISK_LEVEL_MEDIUM][0]) return RISK_LEVEL_MEDIUM;
  return RISK_LEVEL_LOW;
}

/**
 * Convenience: combine the two primitives so a UI never hand-rolls the
 * score*score logic. Returns {score, level} where level is the canonical
 * Turkish label above.
 */
export function previewRisk(probability, severity) {
  const score = calculateRiskScore(probability, severity);
  return { score, level: classifyRiskScore(score) };
}

// Constants are re-exported for tests and downstream assertions that need
// to compare boundaries explicitly without duplicating the magic numbers.
export const RISK_THRESHOLDS = Object.freeze({
  LOW_MAX: RISK_LIMITS.LOW_MAX,
  MEDIUM_MAX: RISK_LIMITS.MEDIUM_MAX,
  HIGH_MAX: RISK_LIMITS.HIGH_MAX,
  MIN: RISK_LIMITS.MIN,
  LOW: RISK_LEVEL_LOW,
  MEDIUM: RISK_LEVEL_MEDIUM,
  HIGH: RISK_LEVEL_HIGH,
});

/**
 * Calculates hierarchical category-based question number (e.g. 1.3, 4.1).
 *
 * Example: 3rd question in 1st category → "1.3"
 *          1st question in 4th category → "4.1"
 */
export function getCategoryQuestionNumber(q, categories = [], allQuestions = []) {
  if (!q) return "";
  if (q.category_question_no && typeof q.category_question_no === "string" && q.category_question_no.includes(".")) {
    return q.category_question_no;
  }

  const catName = q.kategori || q.category || "";

  let catList = Array.isArray(categories) && categories.length > 0 ? categories : [];
  if (catList.length === 0 && Array.isArray(allQuestions) && allQuestions.length > 0) {
    catList = Array.from(new Set(allQuestions.map((item) => item?.kategori || item?.category).filter(Boolean)));
  }

  const catIdx = catList.findIndex((c) => c === catName);
  const categoryNumber = catIdx >= 0 ? catIdx + 1 : 1;

  const catQuestions = (allQuestions || []).filter((item) => (item?.kategori || item?.category) === catName);
  const inCatIdx = catQuestions.findIndex(
    (item) => String(item?.id) === String(q.id || q.question_id) || String(item?.question_id) === String(q.question_id || q.id)
  );

  const questionNumber = inCatIdx >= 0 ? inCatIdx + 1 : (q.no || q.id || 1);

  return `${categoryNumber}.${questionNumber}`;
}
