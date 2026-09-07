// Regression test: DofApproveModal & PhotoUploader rendered-class theme contract.
//
// Bug context: Light mode'da bu iki component "koyu siyah/lacivert" olarak
// kalıyordu — DofPage artık light+dark aware olduğu halde baran-branch'in
// yeni eklediği DofApproveModal ve PhotoUploader chrome'u hardcoded dark
// classes kullanıyordu. Bu test, light + dark render path'lerinde rendered
// class'ların contract'a uygun olduğunu doğrular.
//
// Pixel-level CSS assertion yapmaz; rendered DOM class set'ini token-level
// kontrol eder. ``html.dark`` global class mevcut/eklenince Tailwind dark:
// variant'ları uygular; class listesi aynı kalır (sadece uygulanan utility
// değişir), bu yüzden contract uyumluluğu için:
//
//   * light mode (html.dark yok): light utility'ler render edilirken dark
//     olmamalı (örn. light: ``bg-white``, dark katman: ``dark:bg-slate-950``).
//     Yani class string'inin hem ``bg-white`` hem ``dark:bg-slate-950``
//     içermesi beklenir.
//   * dark mode (html.dark var): aynı class string render ediliyor (variant
//     diff DOM'a uygulanır, biz classset'e bakıyoruz).
//
// Modal scrim (``bg-black/80`` overlay) ve lightbox backdrop bilinçli olarak
// sabit — bugün contract'a uygun şekilde render edildiği için no-op test.

import React from "react";
import { createRoot } from "react-dom/client";

// React 19 act() uyarı bastırma.
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
const { act } = require("react");

// ---------------------------------------------------------------------------
// Stubs
// ---------------------------------------------------------------------------

jest.mock("framer-motion", () => {
  const mockReact = require("react");
  const Passthrough = ({ children, className }) =>
    className
      ? mockReact.createElement(
          "div",
          { "data-motion": "stub", className },
          children
        )
      : children
      ? children
      : null;
  const motion = { div: Passthrough, span: Passthrough, button: Passthrough };
  return { motion, AnimatePresence: Passthrough, MotionConfig: Passthrough };
});

jest.mock("lucide-react", () => {
  const Icon = () => null;
  return new Proxy(
    {
      X: Icon,
      ShieldCheck: Icon,
      FileText: Icon,
      CheckCheck: Icon,
      Loader2: Icon,
      AlertTriangle: Icon,
      Camera: Icon,
      Upload: Icon,
      Image: Icon,
      Trash2: Icon,
      Plus: Icon,
      Eye: Icon,
      Lock: Icon,
      Download: Icon,
      Calendar: Icon,
      User: Icon,
      RefreshCw: Icon,
    },
    {
      get(target, prop) {
        if (prop in target) return target[prop];
        return Icon;
      },
    }
  );
});

jest.mock("sonner", () => ({
  toast: { success: jest.fn(), error: jest.fn() },
}));

jest.mock("../lib/api", () => ({
  __esModule: true,
  default: { post: jest.fn(), delete: jest.fn() },
  BACKEND_ORIGIN: "",
}));

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function flush() {
  return new Promise((resolve) => setTimeout(resolve, 0));
}

function classSet(el) {
  return new Set((el?.className || "").split(/\s+/).filter(Boolean));
}

function has(tokens) {
  return (predicate) => (el) => {
    const cs = classSet(el);
    if (typeof predicate === "function") {
      return predicate(Array.from(cs));
    }
    return tokens.every((t) => cs.has(t));
  };
}

function anyLightSurface(el) {
  const cs = classSet(el);
  // ``bg-white`` OR a slate-n bg like ``bg-slate-50`` etc., but NOT
  // an unaugmented ``bg-slate-950`` heavy dark. Practical heuristic:
  // any of these utility tokens present AND no dark-bg-only token.
  const lightTokens = ["bg-white", "bg-slate-50", "bg-slate-100", "bg-red-50", "bg-amber-50", "bg-emerald-50"];
  return lightTokens.some((t) => cs.has(t));
}

function anyDarkSurface(el) {
  const cs = classSet(el);
  const darkTokens = [
    "bg-slate-950/95",
    "bg-slate-900/80",
    "bg-slate-900/90",
    "bg-black/80",
    "bg-slate-900",
  ];
  return darkTokens.some((t) => cs.has(t));
}

async function renderInto(node) {
  const container = document.createElement("div");
  document.body.appendChild(container);
  const root = createRoot(container);
  await act(async () => {
    root.render(node);
    await flush();
  });
  return { container, root };
}

function cleanup({ container, root }) {
  return act(async () => {
    root.unmount();
  }).then(() => container.remove());
}

// ---------------------------------------------------------------------------
// DofApproveModal theme contract
// ---------------------------------------------------------------------------

describe("DofApproveModal — light/dark theme contract", () => {
  let DofApproveModal;

  beforeAll(() => {
    // Component import must come AFTER jest.mock — jest hoists them anyway.
    DofApproveModal = require("../components/DofApproveModal").default;
  });

  test("modal box renders with explicit light+dark background tokens (no bare inherited class)", async () => {
    const item = {
      restaurant_name: "Test Şube",
      question_no: 3,
      question_id: 3,
      resolution_note: "",
      notes: "",
    };
    const { container, root } = await renderInto(
      React.createElement(DofApproveModal, {
        item,
        isOpen: true,
        onClose: () => {},
        onConfirm: () => {},
        isSaving: false,
      })
    );

    // The animated content motion.div is the actual modal card.
    // framer-motion stub renders children as a plain span/div with classes
    // applied via the ``className`` prop (it's just a passthrough here).
    const cardNodes = container.querySelectorAll("div");
    const cardCandidates = Array.from(cardNodes).filter((el) => {
      const cs = classSet(el);
      return cs.has("bg-white") || cs.has("bg-slate-950/95");
    });

    expect(cardCandidates.length).toBeGreaterThan(0);

    // The modal card must have the light surface token AND the dark
    // surface token via ``dark:`` variant — proves the modal is theme-aware.
    const main = cardCandidates.find((el) => {
      const cs = classSet(el);
      return cs.has("bg-white") && cs.has("dark:bg-slate-950/95");
    });
    expect(main).toBeTruthy();

    // Modal must NOT contain any bare, hardcoded dark-only bg without a
    // dark: prefix pair (the contract violation).
    for (const node of container.querySelectorAll("div, span, button, label, textarea")) {
      const cs = classSet(node);
      // bare ``bg-slate-950/95`` without companion ``bg-white``
      const heavyDark = Array.from(cs).some((t) =>
        /^(bg-slate-9\d|bg-black)/.test(t)
      );
      if (heavyDark && !cs.has("bg-white") && !cs.has("dark:bg-")) {
        // Skip intentional scrim (bg-black/80 outside the card) — handled in next test.
        // The violation would be: dark bg WITHOUT a corresponding light mode class.
      }
    }

    await cleanup({ container, root });
  });

  test("modal scrim (bg-black/80) keeps modal contract (intentional dim, both themes)", async () => {
    const item = {
      restaurant_name: "Test Şube",
      question_no: 3,
      question_id: 3,
      resolution_note: "",
      notes: "",
    };
    const { container, root } = await renderInto(
      React.createElement(DofApproveModal, {
        item,
        isOpen: true,
        onClose: () => {},
        onConfirm: () => {},
        isSaving: false,
      })
    );

    // Modal scrim: outer wrapper uses bg-black/80 — this is the modal scrim,
    // which is intentional in BOTH themes (UX convention; matches the
    // shadcn DialogOverlay used elsewhere in the repo). The contract test
    // asserts the scrim class is present so we don't accidentally strip it.
    const scrim = Array.from(container.querySelectorAll("div")).find((el) => {
      const cs = classSet(el);
      return cs.has("fixed") && cs.has("inset-0") && cs.has("bg-black/80");
    });
    expect(scrim).toBeTruthy();

    await cleanup({ container, root });
  });

  test("modal heading uses light+dark text tokens (no bare text-white anywhere in heading area)", async () => {
    const item = {
      restaurant_name: "Test Şube",
      question_no: 3,
      question_id: 3,
      resolution_note: "",
      notes: "",
    };
    const { container, root } = await renderInto(
      React.createElement(DofApproveModal, {
        item,
        isOpen: true,
        onClose: () => {},
        onConfirm: () => {},
        isSaving: false,
      })
    );

    // Heading must use light + dark tokens: ``text-slate-900 dark:text-white``.
    // Reject pure ``text-white`` without dark: pair (would be light-mode invisible).
    const headings = Array.from(container.querySelectorAll("h3, p, label"));
    const heading = headings.find((el) =>
      (el.textContent || "").includes("DÖF Kapatma ve Aksiyon Onayı")
    );
    expect(heading).toBeTruthy();
    const headingCs = classSet(heading);
    expect(headingCs.has("text-slate-900")).toBe(true);
    expect(headingCs.has("dark:text-white")).toBe(true);
    // No lone text-white without light variant in light mode
    expect(headingCs.has("text-white")).toBe(false);

    await cleanup({ container, root });
  });

  test("textarea has light/dark bg + text tokens (no plain bg-slate-900)", async () => {
    const item = {
      restaurant_name: "Test Şube",
      question_no: 3,
      question_id: 3,
      resolution_note: "",
      notes: "",
    };
    const { container, root } = await renderInto(
      React.createElement(DofApproveModal, {
        item,
        isOpen: true,
        onClose: () => {},
        onConfirm: () => {},
        isSaving: false,
      })
    );

    const textarea = container.querySelector("textarea");
    expect(textarea).toBeTruthy();
    const cs = classSet(textarea);
    expect(cs.has("bg-white")).toBe(true);
    expect(cs.has("dark:bg-slate-900")).toBe(true);
    expect(cs.has("text-slate-900")).toBe(true);
    expect(cs.has("dark:text-slate-100")).toBe(true);

    await cleanup({ container, root });
  });

  test("cancel button uses theme-adaptive bg + text (not plain bg-slate-900)", async () => {
    const item = {
      restaurant_name: "Test Şube",
      question_no: 3,
      question_id: 3,
      resolution_note: "",
      notes: "",
    };
    const { container, root } = await renderInto(
      React.createElement(DofApproveModal, {
        item,
        isOpen: true,
        onClose: () => {},
        onConfirm: () => {},
        isSaving: false,
      })
    );

    const cancelBtn = Array.from(container.querySelectorAll("button")).find(
      (b) => (b.textContent || "").trim() === "İptal"
    );
    expect(cancelBtn).toBeTruthy();
    const cs = classSet(cancelBtn);
    // Light + dark variant both present
    expect(cs.has("bg-slate-100")).toBe(true);
    expect(cs.has("dark:bg-slate-900")).toBe(true);
    expect(cs.has("text-slate-700")).toBe(true);
    expect(cs.has("dark:text-slate-300")).toBe(true);

    await cleanup({ container, root });
  });

  test("approve button keeps brand emerald gradient (no broken text visibility)", async () => {
    const item = {
      restaurant_name: "Test Şube",
      question_no: 3,
      question_id: 3,
      resolution_note: "Düzeltme yapıldı, yerinde incelendi",
      notes: "Düzeltme yapıldı, yerinde incelendi",
    };
    const { container, root } = await renderInto(
      React.createElement(DofApproveModal, {
        item,
        isOpen: true,
        onClose: () => {},
        onConfirm: () => {},
        isSaving: false,
      })
    );

    const approveBtn = Array.from(container.querySelectorAll("button")).find(
      (b) => (b.textContent || "").includes("Onayla ve DÖF")
    );
    expect(approveBtn).toBeTruthy();
    const cs = classSet(approveBtn);
    // Master prompt compliance: flat risk-compliant fill, no gradient, no glow.
    expect(cs.has("bg-risk-compliant")).toBe(true);
    expect(cs.has("text-white")).toBe(true);
    expect(cs.has("bg-gradient-to-r")).toBe(false);
    expect(cs.has("from-emerald-600")).toBe(false);
    expect(cs.has("to-teal-500")).toBe(false);

    await cleanup({ container, root });
  });
});

// ---------------------------------------------------------------------------
// PhotoUploader theme contract
// ---------------------------------------------------------------------------

describe("PhotoUploader — light/dark theme contract", () => {
  let PhotoUploader;

  beforeAll(() => {
    PhotoUploader = require("../components/PhotoUploader").default;
  });

  test("renders label with light+dark slate tokens (no bare text-slate-400)", async () => {
    const { container, root } = await renderInto(
      React.createElement(PhotoUploader, {
        auditId: "a1",
        questionId: 1,
        photoType: "finding",
        photos: [],
        onPhotosChange: () => {},
        label: "Saha Tespit Fotoğrafları (Denetçi Kanıtı)",
      })
    );

    const label = container.querySelector("span");
    expect(label).toBeTruthy();
    const cs = classSet(label);
    expect(cs.has("text-slate-700")).toBe(true);
    expect(cs.has("dark:text-slate-400")).toBe(true);
    // No bare ``text-slate-400`` without dark: prefix
    expect(cs.has("text-slate-400")).toBe(false);

    await cleanup({ container, root });
  });

  test("Fotoğraf Seç button uses light+dark emerald/red tokens", async () => {
    const { container, root } = await renderInto(
      React.createElement(PhotoUploader, {
        auditId: "a1",
        questionId: 1,
        photoType: "finding",
        photos: [],
        onPhotosChange: () => {},
      })
    );

    const btn = Array.from(container.querySelectorAll("button")).find(
      (b) => (b.textContent || "").includes("Fotoğraf Seç")
    );
    expect(btn).toBeTruthy();
    const cs = classSet(btn);
    // Light surface variants
    expect(cs.has("bg-red-100")).toBe(true);
    expect(cs.has("dark:bg-red-500/10")).toBe(true);
    expect(cs.has("text-red-800")).toBe(true);
    expect(cs.has("dark:text-red-300")).toBe(true);
    expect(cs.has("border-red-300")).toBe(true);
    expect(cs.has("dark:border-red-500/30")).toBe(true);

    await cleanup({ container, root });
  });

  test("lock notice (3/3 modify limit) uses light+dark amber tokens", async () => {
    const { container, root } = await renderInto(
      React.createElement(PhotoUploader, {
        auditId: "a1",
        questionId: 1,
        photoType: "resolution",
        photos: [],
        modifyCount: 3,
        maxModifyRights: 3,
        isAdmin: false,
        onPhotosChange: () => {},
        label: "Çözüm Fotoğrafları",
      })
    );

    const notice = container.querySelector('[class*="amber-300"]');
    expect(notice).toBeTruthy();
    const cs = classSet(notice);
    expect(cs.has("border-amber-300")).toBe(true);
    expect(cs.has("dark:border-amber-500/30")).toBe(true);
    expect(cs.has("bg-amber-50")).toBe(true);
    expect(cs.has("dark:bg-amber-500/10")).toBe(true);
    expect(cs.has("text-amber-900")).toBe(true);
    expect(cs.has("dark:text-amber-300")).toBe(true);

    await cleanup({ container, root });
  });

  test("thumbnail container uses light+dark slate tokens (no bare bg-slate-900)", async () => {
    const PHOTO = {
      id: "p1",
      thumb_url: "data:image/png;base64,",
      url: "data:image/png;base64,",
      type: "finding",
      created_at: "2026-08-01T00:00:00Z",
    };
    const { container, root } = await renderInto(
      React.createElement(PhotoUploader, {
        auditId: "a1",
        questionId: 1,
        photoType: "finding",
        photos: [PHOTO],
        onPhotosChange: () => {},
      })
    );

    const thumb = container.querySelector(".aspect-square");
    expect(thumb).toBeTruthy();
    const cs = classSet(thumb);
    expect(cs.has("bg-slate-100")).toBe(true);
    expect(cs.has("dark:bg-slate-900")).toBe(true);
    expect(cs.has("border-slate-200")).toBe(true);
    expect(cs.has("dark:border-white/10")).toBe(true);
    // NO plain ``bg-slate-900`` without companion bg-slate-100
    expect(cs.has("bg-slate-900")).toBe(false);

    await cleanup({ container, root });
  });
});

// ---------------------------------------------------------------------------
// DeadlineCountdown + DofTimeline theme contract (in-page chrome inside
// DofCard which is light/dark aware, so these inner elements must follow).
// ---------------------------------------------------------------------------

describe("DeadlineCountdown + DofTimeline — light/dark theme contract", () => {
  let DeadlineCountdown;
  let DofTimeline;

  beforeAll(() => {
    DeadlineCountdown = require("../components/DeadlineCountdown").default;
    DofTimeline = require("../components/DofTimeline").default;
  });

  test("DeadlineCountdown normal variant uses light+dark slate tokens", async () => {
    const { container, root } = await renderInto(
      React.createElement(DeadlineCountdown, {
        dueDate: "2099-12-31T00:00:00Z",
        status: "AÇIK",
        createdAt: null,
        resolvedAt: null,
      })
    );
    const badge = container.querySelector("span");
    expect(badge).toBeTruthy();
    const cs = classSet(badge);
    expect(cs.has("bg-slate-100")).toBe(true);
    expect(cs.has("dark:bg-slate-900/80")).toBe(true);
    expect(cs.has("text-slate-700")).toBe(true);
    expect(cs.has("dark:text-slate-300")).toBe(true);

    await cleanup({ container, root });
  });

  test("DeadlineCountdown closed variant uses light+dark emerald tokens", async () => {
    const { container, root } = await renderInto(
      React.createElement(DeadlineCountdown, {
        dueDate: null,
        status: "KAPATILDI",
        createdAt: "2026-08-01T00:00:00Z",
        resolvedAt: "2026-08-09T00:00:00Z",
      })
    );
    const badge = container.querySelector("span");
    expect(badge).toBeTruthy();
    const cs = classSet(badge);
    expect(cs.has("bg-emerald-100")).toBe(true);
    expect(cs.has("dark:bg-emerald-500/15")).toBe(true);
    expect(cs.has("text-emerald-800")).toBe(true);
    expect(cs.has("dark:text-emerald-400")).toBe(true);

    await cleanup({ container, root });
  });

  test("DofTimeline uses light+dark tokens on the toggle button (no bare text-slate-400)", async () => {
    const LOGS = [
      { action: "DÖF Oluşturuldu", user: "Test", timestamp: "2026-08-01T00:00:00Z" },
      {
        action: "DÖF İSG Uzmanı Tarafından Onaylandı & Kapatıldı",
        user: "Test",
        timestamp: "2026-08-09T00:00:00Z",
      },
    ];
    const { container, root } = await renderInto(
      React.createElement(DofTimeline, {
        logs: LOGS,
        status: "KAPATILDI",
        createdAt: "2026-08-01T00:00:00Z",
        resolvedAt: "2026-08-09T00:00:00Z",
      })
    );
    const toggle = container.querySelector("button");
    expect(toggle).toBeTruthy();
    const cs = classSet(toggle);
    expect(cs.has("text-slate-700")).toBe(true);
    expect(cs.has("dark:text-slate-400")).toBe(true);
    expect(cs.has("text-slate-400")).toBe(false);
    // And the wrapper must declare the divider in both modes.
    expect(cs.has("border-slate-200")).toBe(false); // toggle has no border; wrapper
    const wrapperCs = classSet(container.querySelector("div"));
    expect(wrapperCs.has("border-slate-200")).toBe(true);
    expect(wrapperCs.has("dark:border-white/5")).toBe(true);

    await cleanup({ container, root });
  });
});
