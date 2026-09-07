/**
 * PhotoUploader — "Fotoğraf Seç" presence contract (regression test).
 *
 * Root cause of the DÖF save-time visual jump (Experiment 3d):
 *   When `disabled=true`, the "Fotoğraf Seç" control was conditionally
 *   unmounted from the DOM, causing the card header geometry to change
 *   and Framer Motion `layout` to animate the jump.
 *
 * Permanent fix:
 *   `disabled` now changes INTERACTIVITY only. The upload button remains
 *   rendered in the DOM regardless of `disabled` state.
 *
 * Contract verified by this test:
 *   1. With available photo capacity and `!isModifyLocked`, the
 *      "Fotoğraf Seç" control is rendered when `disabled=false`.
 *   2. After rerender with `disabled=true`, the same control is STILL
 *      present in the DOM (no conditional unmount).
 *   3. While `disabled=true`, the control is natively disabled and does
 *      not trigger the file picker when activated.
 *   4. After rerender back to `disabled=false`, the control is
 *      interactive again.
 *
 *   In short: `disabled` changes interactivity, NOT presence/layout
 *   ownership.
 */
import React from "react";
import { createRoot } from "react-dom/client";
import { act } from "react";

// React 19 act() warning suppression.
globalThis.IS_REACT_ACT_ENVIRONMENT = true;

// ---------------------------------------------------------------------------
// Stubs / Mocks
// ---------------------------------------------------------------------------

jest.mock("lucide-react", () => {
  const Icon = () => null;
  return new Proxy(
    {
      Camera: Icon,
      Upload: Icon,
      Loader2: Icon,
      Image: Icon,
      ImageIcon: Icon,
      Trash2: Icon,
      Plus: Icon,
      Eye: Icon,
      Lock: Icon,
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

jest.mock("sonner", () => ({
  __esModule: true,
  toast: { success: jest.fn(), error: jest.fn() },
}));

// PhotoLightbox is only rendered when activePhoto is set; stub it to a
// no-op so the test does not pull in framer-motion dependencies.
jest.mock("./PhotoLightbox", () => ({
  __esModule: true,
  default: () => null,
}));

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const baseProps = {
  auditId: "audit-1",
  questionId: 42,
  photoType: "resolution",
  photos: [],
  onPhotosChange: jest.fn(),
  isAdmin: false,
  modifyCount: 0,
  maxModifyRights: 3,
  maxPhotos: 3,
};

function renderUploader(extraProps = {}) {
  const container = document.createElement("div");
  document.body.appendChild(container);
  // eslint-disable-next-line global-require
  const PhotoUploader = require("./PhotoUploader").default;
  const root = createRoot(container);
  act(() => {
    root.render(<PhotoUploader {...baseProps} {...extraProps} />);
  });
  container._reactRoot = root;
  return container;
}

function rerenderUploader(container, extraProps = {}) {
  // eslint-disable-next-line global-require
  const PhotoUploader = require("./PhotoUploader").default;
  act(() => {
    container._reactRoot.render(
      <PhotoUploader {...baseProps} {...extraProps} />
    );
  });
}

function getUploadButton(container) {
  const btns = Array.from(container.querySelectorAll("button"));
  return btns.find(
    (b) => b.textContent && b.textContent.includes("Fotoğraf Seç")
  );
}

afterEach(() => {
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
// Regression contract
// ---------------------------------------------------------------------------

describe("PhotoUploader — Fotoğraf Seç presence contract (regression)", () => {
  test("1) renders the upload button when disabled=false and capacity available", () => {
    const c = renderUploader({ disabled: false });
    const btn = getUploadButton(c);
    expect(btn).toBeTruthy();
    expect(btn.disabled).toBe(false);
  });

  test("2) upload button REMAINS in DOM after rerender with disabled=true (no unmount)", () => {
    const c = renderUploader({ disabled: false });
    expect(getUploadButton(c)).toBeTruthy();
    rerenderUploader(c, { disabled: true });
    const btn = getUploadButton(c);
    expect(btn).toBeTruthy();
    expect(btn.disabled).toBe(true);
  });

  test("3) while disabled=true, the control is natively disabled and does not open the file picker", () => {
    const c = renderUploader({ disabled: true });
    const btn = getUploadButton(c);
    expect(btn).toBeTruthy();
    expect(btn.disabled).toBe(true);

    // The hidden file input is rendered in the DOM. Spy on its native
    // .click() so we can verify the upload button's onClick does NOT
    // invoke it when the button is natively disabled.
    const fileInput = c.querySelector('input[type="file"]');
    expect(fileInput).toBeTruthy();
    const clickSpy = jest.spyOn(fileInput, "click");

    act(() => {
      btn.click();
    });

    // A natively disabled button does not dispatch its activation click
    // event, so the PhotoUploader onClick handler must not run, and
    // therefore fileInput.click() must not have been invoked.
    expect(clickSpy).not.toHaveBeenCalled();
    clickSpy.mockRestore();
  });

  test("4) rerender back to disabled=false restores interactivity", () => {
    const c = renderUploader({ disabled: true });
    expect(getUploadButton(c).disabled).toBe(true);
    rerenderUploader(c, { disabled: false });
    const btn = getUploadButton(c);
    expect(btn).toBeTruthy();
    expect(btn.disabled).toBe(false);
  });
});
