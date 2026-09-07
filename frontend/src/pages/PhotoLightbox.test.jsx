/**
 * PhotoLightbox layout / theme / close-UX contract tests.
 *
 * Spec recap (from task):
 *   - Lightbox overlay viewport-bounded (fixed inset-0).
 *   - Viewer card flex-column with toolbar flex-none, image area flex-1 min-h-0.
 *   - Image ``object-contain`` with max-width/max-height constraints so
 *     landscape/portrait/tall/wide photos never push toolbar off-screen.
 *   - Close UX: X, Escape, backdrop click, image click → onClose.
 *   - Action clicks (download/delete) → do NOT close.
 *   - Light mode chrome (toolbar bg-slate-50 + slate-900 readable).
 *   - Dark mode chrome preserved.
 *   - Thumbnail wrapper stable aspect (aspect-square), overflow-hidden,
 *     image ``object-cover``/``object-contain``.
 */
import React, { createRef } from "react";
import { createRoot } from "react-dom/client";
import { act } from "react";

// React 19 act() uyarı bastırma.
globalThis.IS_REACT_ACT_ENVIRONMENT = true;

// ---------------------------------------------------------------------------
// Stubs / Mocks
// ---------------------------------------------------------------------------

jest.mock("framer-motion", () => {
  const mockReact = require("react");
  const Passthrough = ({ children, className, onMouseDown, ...rest }) =>
    mockReact.createElement(
      "div",
      {
        ...rest,
        "data-motion": "stub",
        className,
        onMouseDown,
      },
      children
    );
  const motion = { div: Passthrough, span: Passthrough, button: Passthrough };
  return { motion, AnimatePresence: Passthrough, MotionConfig: Passthrough };
});

jest.mock("lucide-react", () => {
  const Icon = () => null;
  return new Proxy(
    {
      X: Icon,
      Download: Icon,
      Trash2: Icon,
      Calendar: Icon,
      User: Icon,
    },
    {
      get(target, prop) {
        if (prop in target) return target[prop];
        return Icon;
      },
    }
  );
});

jest.mock("../lib/api", () => ({
  __esModule: true,
  default: { post: jest.fn(), delete: jest.fn() },
  BACKEND_ORIGIN: "http://localhost:8000",
}));

jest.mock("../constants/testIds", () => ({
  __esModule: true,
  PHOTO: {
    lightboxOverlay: "photo-lightbox-overlay",
    lightboxViewer: "photo-lightbox-viewer",
    lightboxToolbar: "photo-lightbox-toolbar",
    lightboxImageWrap: "photo-lightbox-image-wrap",
    lightboxImage: "photo-lightbox-image",
    lightboxClose: "photo-lightbox-close",
    lightboxDownload: "photo-lightbox-download",
    lightboxDelete: "photo-lightbox-delete",
    lightboxFooter: "photo-lightbox-footer",
    lightboxBadge: "photo-lightbox-badge",
  },
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

function renderLightbox(props, opts = {}) {
  const container = document.createElement("div");
  document.body.appendChild(container);
  // eslint-disable-next-line global-require
  const PhotoLightbox = require("../components/PhotoLightbox").default;
  const root = createRoot(container);
  act(() => {
    root.render(
      <PhotoLightbox
        photo={
          props.photo || {
            id: "test-photo-1",
            type: "finding",
            url: "/uploads/photos/2026/08/test.webp",
            thumb_url: "/uploads/photos/2026/08/test_thumb.webp",
            created_at: "2026-08-10T22:00:00.000000+00:00",
            created_by: "user-test",
          }
        }
        {...props}
      />
    );
  });
  container._reactRoot = root;
  if (opts.captureRoot) opts.captureRoot(root, container);
  return container;
}

afterEach(() => {
  // Properly unmount each React root we created.
  document.querySelectorAll("[data-reactroot], [data-testid]").forEach((el) => {
    const root = el.parentElement?._reactRoot;
    if (root) {
      try {
        act(() => {
          root.unmount();
        });
      } catch (_e) {
        /* ignore */
      }
    }
  });
  document.body.innerHTML = "";
});

// ---------------------------------------------------------------------------
// Layout contract
// ---------------------------------------------------------------------------
describe("PhotoLightbox viewport-bounded layout contract", () => {
  test("overlay covers viewport (fixed inset-0)", () => {
    const c = renderLightbox({ onClose: () => {} });
    const overlay = c.querySelector('[data-testid="photo-lightbox-overlay"]');
    expect(overlay).toBeTruthy();
    const cs = classSet(overlay);
    expect(cs.has("fixed")).toBe(true);
    expect(cs.has("inset-0")).toBe(true);
    expect(cs.has("flex")).toBe(true);
  });

  test("viewer card is flex-column with viewport-bounded max-height", () => {
    const c = renderLightbox({ onClose: () => {} });
    const viewer = c.querySelector('[data-testid="photo-lightbox-viewer"]');
    expect(viewer).toBeTruthy();
    const cs = classSet(viewer);
    expect(cs.has("flex")).toBe(true);
    expect(cs.has("flex-col")).toBe(true);
    expect(cs.has("overflow-hidden")).toBe(true);
    const arbitrary = Array.from(cs).filter((x) => x.startsWith("max-h-"));
    expect(arbitrary.length).toBeGreaterThan(0);
    expect(arbitrary.some((x) => x.includes("vh") || x.includes("dvh"))).toBe(true);
  });

  test("toolbar is flex-none so it never shrinks/grows", () => {
    const c = renderLightbox({ onClose: () => {} });
    const toolbar = c.querySelector('[data-testid="photo-lightbox-toolbar"]');
    expect(toolbar).toBeTruthy();
    expect(classSet(toolbar).has("flex-none")).toBe(true);
  });

  test("image area is flex-1 min-h-0 (overflow-bounded independently of image)", () => {
    const c = renderLightbox({ onClose: () => {} });
    const wrap = c.querySelector('[data-testid="photo-lightbox-image-wrap"]');
    expect(wrap).toBeTruthy();
    const cs = classSet(wrap);
    expect(cs.has("flex-1")).toBe(true);
    expect(cs.has("min-h-0")).toBe(true);
    expect(cs.has("overflow-auto")).toBe(true);
  });

  test("image element has object-contain and max-bounded sizing tokens", () => {
    const c = renderLightbox({ onClose: () => {} });
    const img = c.querySelector('[data-testid="photo-lightbox-image"]');
    expect(img).toBeTruthy();
    const cs = classSet(img);
    expect(cs.has("object-contain")).toBe(true);
    expect(cs.has("max-w-full")).toBe(true);
    expect(cs.has("max-h-full")).toBe(true);
    expect(cs.has("w-auto")).toBe(true);
    expect(cs.has("h-auto")).toBe(true);
  });

  test("footer is also flex-none (no layout shift when content varies)", () => {
    const c = renderLightbox({ onClose: () => {} });
    const footer = c.querySelector('[data-testid="photo-lightbox-footer"]');
    expect(footer).toBeTruthy();
    expect(classSet(footer).has("flex-none")).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// Close UX contract
// ---------------------------------------------------------------------------
describe("PhotoLightbox close UX", () => {
  test("X button closes", () => {
    const onClose = jest.fn();
    const c = renderLightbox({ onClose });
    const xBtn = c.querySelector('[data-testid="photo-lightbox-close"]');
    act(() => {
      xBtn.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });
    expect(onClose).toHaveBeenCalled();
  });

  test("Escape key closes (registered window listener)", () => {
    const onClose = jest.fn();
    renderLightbox({ onClose });
    act(() => {
      window.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" }));
    });
    expect(onClose).toHaveBeenCalled();
  });

  test("Escape key listener is cleaned up on unmount", () => {
    const onClose = jest.fn();
    let capturedRoot = null;
    let capturedContainer = null;
    const c = renderLightbox({ onClose }, {
      captureRoot: (root, container) => {
        capturedRoot = root;
        capturedContainer = container;
      },
    });
    expect(capturedRoot).toBeTruthy();
    act(() => {
      capturedRoot.unmount();
    });
    capturedContainer.remove();
    void c;
    act(() => {
      window.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" }));
    });
    expect(onClose).not.toHaveBeenCalled();
  });

  test("backdrop click (on overlay itself) closes", () => {
    const onClose = jest.fn();
    const c = renderLightbox({ onClose });
    const overlay = c.querySelector('[data-testid="photo-lightbox-overlay"]');
    act(() => {
      overlay.dispatchEvent(new MouseEvent("mousedown", { bubbles: true, target: overlay }));
    });
    expect(onClose).toHaveBeenCalled();
  });

  test("image click closes", () => {
    const onClose = jest.fn();
    const c = renderLightbox({ onClose });
    const img = c.querySelector('[data-testid="photo-lightbox-image"]');
    act(() => {
      img.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });
    expect(onClose).toHaveBeenCalled();
  });

  test("download link click does NOT close (propagation barrier)", () => {
    const onClose = jest.fn();
    const c = renderLightbox({ onClose, onDelete: jest.fn() });
    const dl = c.querySelector('[data-testid="photo-lightbox-download"]');
    act(() => {
      dl.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });
    expect(onClose).not.toHaveBeenCalled();
  });

  test("delete button click does NOT close, but DOES invoke onDelete", () => {
    const onClose = jest.fn();
    const onDelete = jest.fn();
    const c = renderLightbox({ onClose, onDelete });
    const del = c.querySelector('[data-testid="photo-lightbox-delete"]');
    act(() => {
      del.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });
    expect(onClose).not.toHaveBeenCalled();
    expect(onDelete).toHaveBeenCalled();
  });

  test("clicking on viewer chrome does NOT close (mouseDown stops propagation)", () => {
    const onClose = jest.fn();
    const c = renderLightbox({ onClose });
    const viewer = c.querySelector('[data-testid="photo-lightbox-viewer"]');
    act(() => {
      // Dispatch on viewer with `target = viewer` — this means the overlay's
      // onMouseDown sees e.target === e.currentTarget? No: e.currentTarget on
      // the overlay handler would still be the overlay. So when mousedown
      // fires on viewer, e.target=viewer but e.currentTarget (overlay
      // handler) = overlay; our guard `e.target === e.currentTarget` is false,
      // so onClose is NOT called.
      viewer.dispatchEvent(new MouseEvent("mousedown", { bubbles: true }));
    });
    expect(onClose).not.toHaveBeenCalled();
  });
});

// ---------------------------------------------------------------------------
// Theme contract
// ---------------------------------------------------------------------------
describe("PhotoLightbox theme contract", () => {
  test("viewer surface uses bg-white + dark:bg-slate-950/95 (theme-aware)", () => {
    const c = renderLightbox({ onClose: () => {} });
    const viewer = c.querySelector('[data-testid="photo-lightbox-viewer"]');
    const cs = classSet(viewer);
    expect(cs.has("bg-white")).toBe(true);
    expect(cs.has("dark:bg-slate-950/95")).toBe(true);
  });

  test("toolbar uses bg-slate-50 + dark:bg-slate-900/70 (light surface)", () => {
    const c = renderLightbox({ onClose: () => {} });
    const tb = c.querySelector('[data-testid="photo-lightbox-toolbar"]');
    const cs = classSet(tb);
    expect(cs.has("bg-slate-50")).toBe(true);
    expect(cs.has("dark:bg-slate-900/70")).toBe(true);
  });

  test("footer uses bg-slate-50 + dark:bg-slate-900/70 (light surface)", () => {
    const c = renderLightbox({ onClose: () => {} });
    const f = c.querySelector('[data-testid="photo-lightbox-footer"]');
    const cs = classSet(f);
    expect(cs.has("bg-slate-50")).toBe(true);
    expect(cs.has("dark:bg-slate-900/70")).toBe(true);
  });

  test("close (X) button has light-readable slate text + dark mode preserved", () => {
    const c = renderLightbox({ onClose: () => {} });
    const btn = c.querySelector('[data-testid="photo-lightbox-close"]');
    const cs = classSet(btn);
    expect(cs.has("text-slate-700")).toBe(true);
    expect(cs.has("hover:text-slate-900")).toBe(true);
    expect(cs.has("dark:text-slate-300")).toBe(true);
    expect(cs.has("dark:hover:text-white")).toBe(true);
  });

  test("resolution badge uses emerald light variants + dark variants", () => {
    const c = renderLightbox({ photo: { id: "x", type: "resolution",
      url: "/uploads/photos/2026/08/x.webp", thumb_url: "/uploads/photos/2026/08/x_thumb.webp" },
      onClose: () => {} });
    const badge = c.querySelector('[data-testid="photo-lightbox-badge"]');
    const cs = classSet(badge);
    expect(cs.has("bg-emerald-100")).toBe(true);
    expect(cs.has("text-emerald-800")).toBe(true);
    expect(cs.has("border-emerald-300")).toBe(true);
    expect(cs.has("dark:bg-emerald-500/15")).toBe(true);
    expect(cs.has("dark:text-emerald-300")).toBe(true);
  });

  test("finding badge uses red light variants + dark variants", () => {
    const c = renderLightbox({ photo: { id: "x", type: "finding",
      url: "/uploads/photos/2026/08/x.webp", thumb_url: "/uploads/photos/2026/08/x_thumb.webp" },
      onClose: () => {} });
    const badge = c.querySelector('[data-testid="photo-lightbox-badge"]');
    const cs = classSet(badge);
    expect(cs.has("bg-red-100")).toBe(true);
    expect(cs.has("text-red-800")).toBe(true);
    expect(cs.has("border-red-300")).toBe(true);
    expect(cs.has("dark:bg-red-500/15")).toBe(true);
    expect(cs.has("dark:text-red-300")).toBe(true);
  });

  test("delete button (light mode) is red-light, not bare dark red", () => {
    const c = renderLightbox({ onClose: () => {}, onDelete: () => {} });
    const btn = c.querySelector('[data-testid="photo-lightbox-delete"]');
    const cs = classSet(btn);
    expect(cs.has("bg-red-50")).toBe(true);
    expect(cs.has("text-red-700")).toBe(true);
    expect(cs.has("border-red-200")).toBe(true);
    expect(cs.has("dark:bg-red-500/10")).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// Thumbnail dimension contract (source-level, no rendering needed)
// ---------------------------------------------------------------------------
describe("PhotoUploader thumbnail dimension contract", () => {
  test("PhotoUploader JSX uses aspect-square + overflow-hidden + object-cover", () => {
    // eslint-disable-next-line global-require
    const fs = require("fs");
    // eslint-disable-next-line global-require
    const path = require("path");
    const src = fs.readFileSync(
      path.join(__dirname, "..", "components", "PhotoUploader.jsx"),
      "utf8"
    );
    expect(src).toMatch(/aspect-square/);
    expect(src).toMatch(/overflow-hidden/);
    expect(src).toMatch(/object-cover/);
    expect(src).toMatch(/w-full h-full object-cover/);
  });
});
