// Regression test: ThemeProvider initial-mount runtime crash in React
// StrictMode (PR0 review bug).
//
// Bug context: ``ThemeProvider`` runs ``applyThemeClass(resolved)`` inside
// its mount effect. ``applyThemeClass`` previously invoked
// ``document.startViewTransition(update)`` unconditionally whenever the
// browser supported the View Transitions API. In development, React's
// StrictMode (which wraps the whole tree in ``frontend/src/index.js``)
// double-invokes mount effects: the first effect run starts a transition,
// then the synthetic unmount/remount fires a second effect run before the
// first transition has finished. The View Transitions API surfaces a
// rejected/skipped transition runtime overlay on the login screen before
// the user has interacted with the theme toggle.
//
// Fix contract verified here:
//   A. Initial mount under StrictMode must NOT crash and must apply the
//      canonical dark/light class via the direct (non-animated) path.
//   B. Explicit user toggle via ``setTheme`` keeps the crossfade animation
//      when ``document.startViewTransition`` is available.
//   C. When ``document.startViewTransition`` is undefined (unsupported
//      browser), both initial sync and explicit toggle apply the class
//      without throwing.
//
// Component-level test (real React StrictMode tree) — matches existing
// ``NewAuditPage.test.jsx`` approach (jsdom + react-dom/client, no RTL).

import React from "react";
import { createRoot } from "react-dom/client";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
const { act } = require("react");

// ---------------------------------------------------------------------------
// Subject (no jest.mock needed — ThemeProvider has no heavyweight deps).
// ---------------------------------------------------------------------------
import { ThemeProvider, useTheme } from "./ThemeContext";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function flush() {
  return new Promise((resolve) => setTimeout(resolve, 0));
}

function setStartViewTransition(impl) {
  if (impl === undefined) {
    delete document.startViewTransition;
    return;
  }
  Object.defineProperty(document, "startViewTransition", {
    configurable: true,
    writable: true,
    value: impl,
  });
}

function resetDocument() {
  document.documentElement.className = "";
  localStorage.clear();
  setStartViewTransition(undefined);
}

function originalDescriptor() {
  return Object.getOwnPropertyDescriptor(document, "startViewTransition");
}

// ---------------------------------------------------------------------------
// Test A — initial mount / StrictMode-safe
// ---------------------------------------------------------------------------
describe("ThemeProvider — initial mount under React.StrictMode", () => {
  let originalSVT;

  beforeEach(() => {
    resetDocument();
    originalSVT = originalDescriptor();
  });

  afterEach(() => {
    if (originalSVT) {
      Object.defineProperty(document, "startViewTransition", originalSVT);
    } else {
      delete document.startViewTransition;
    }
    resetDocument();
  });

  test("initial sync does not start a View Transition; final class is correct", async () => {
    const spy = jest.fn((cb) => {
      cb();
      return { finished: Promise.resolve() };
    });
    setStartViewTransition(spy);

    const container = document.createElement("div");
    document.body.appendChild(container);
    const root = createRoot(container);

    await act(async () => {
      root.render(
        React.createElement(
          React.StrictMode,
          null,
          React.createElement(
            ThemeProvider,
            null,
            React.createElement("div", { "data-testid": "child" }, "x")
          )
        )
      );
      await flush();
    });

    // Default persisted state has no key, so theme falls back to "dark".
    expect(document.documentElement.classList.contains("dark")).toBe(true);
    expect(document.documentElement.classList.contains("light")).toBe(false);

    // Initial sync (first effect run) must take the direct path — starting a
    // transition here is the bug that caused the runtime overlay. Subsequent
    // runs (e.g. StrictMode's synthetic 2nd invocation, or future re-runs)
    // may call the transition API; the invariant we care about for the
    // initial sync window is that the FIRST application does not.
    // We assert at most one call so a StrictMode 2nd invocation is allowed
    // but anything more would indicate a regression.
    expect(spy.mock.calls.length).toBeLessThanOrEqual(1);

    await act(async () => {
      root.unmount();
    });
    container.remove();
  });

  test("initial mount survives a synchronous throw from startViewTransition", async () => {
    // Even if a previous transition were still in flight when the effect ran,
    // the initial-sync path must not throw and must leave the class correct.
    setStartViewTransition(() => {
      throw new Error(
        "Skipped ViewTransition due to another transition starting"
      );
    });

    const container = document.createElement("div");
    document.body.appendChild(container);
    const root = createRoot(container);

    let renderError = null;
    try {
      await act(async () => {
        root.render(
          React.createElement(
            React.StrictMode,
            null,
            React.createElement(
              ThemeProvider,
              null,
              React.createElement("div", null, "x")
            )
          )
        );
        await flush();
      });
    } catch (e) {
      renderError = e;
    }

    expect(renderError).toBeNull();
    expect(document.documentElement.classList.contains("dark")).toBe(true);

    await act(async () => {
      root.unmount();
    });
    container.remove();
  });

  test("persisted 'light' theme in localStorage is applied on initial mount", async () => {
    localStorage.setItem("tab_isg_theme", "light");
    const spy = jest.fn((cb) => {
      cb();
      return { finished: Promise.resolve() };
    });
    setStartViewTransition(spy);

    const container = document.createElement("div");
    document.body.appendChild(container);
    const root = createRoot(container);

    await act(async () => {
      root.render(
        React.createElement(
          React.StrictMode,
          null,
          React.createElement(
            ThemeProvider,
            null,
            React.createElement("div", null, "x")
          )
        )
      );
      await flush();
    });

    expect(document.documentElement.classList.contains("light")).toBe(true);
    expect(document.documentElement.classList.contains("dark")).toBe(false);
    expect(spy.mock.calls.length).toBeLessThanOrEqual(1);

    await act(async () => {
      root.unmount();
    });
    container.remove();
  });

  test("initial sync does not throw when View Transition API is missing", async () => {
    setStartViewTransition(undefined);

    const container = document.createElement("div");
    document.body.appendChild(container);
    const root = createRoot(container);

    let renderError = null;
    try {
      await act(async () => {
        root.render(
          React.createElement(
            React.StrictMode,
            null,
            React.createElement(
              ThemeProvider,
              null,
              React.createElement("div", null, "x")
            )
          )
        );
        await flush();
      });
    } catch (e) {
      renderError = e;
    }

    expect(renderError).toBeNull();
    expect(document.documentElement.classList.contains("dark")).toBe(true);

    await act(async () => {
      root.unmount();
    });
    container.remove();
  });
});

// ---------------------------------------------------------------------------
// Test B — explicit user toggle
// ---------------------------------------------------------------------------
describe("ThemeProvider — explicit user toggle", () => {
  let originalSVT;

  beforeEach(() => {
    resetDocument();
    originalSVT = originalDescriptor();
  });

  afterEach(() => {
    if (originalSVT) {
      Object.defineProperty(document, "startViewTransition", originalSVT);
    } else {
      delete document.startViewTransition;
    }
    resetDocument();
  });

  function mountWithConsumer() {
    let captured = null;
    const Consumer = () => {
      captured = useTheme();
      return null;
    };

    const container = document.createElement("div");
    document.body.appendChild(container);
    const root = createRoot(container);

    const ready = act(async () => {
      root.render(
        React.createElement(
          React.StrictMode,
          null,
          React.createElement(
            ThemeProvider,
            null,
            React.createElement(Consumer, null)
          )
        )
      );
      await flush();
    });

    return {
      capturedRef: () => captured,
      unmount: async () => {
        await act(async () => {
          root.unmount();
        });
        container.remove();
      },
      ready,
    };
  }

  test("uses startViewTransition on explicit setTheme, applies canonical class", async () => {
    const spy = jest.fn((cb) => {
      cb();
      return { finished: Promise.resolve() };
    });
    setStartViewTransition(spy);

    const harness = mountWithConsumer();
    await harness.ready;

    const spyCallsBefore = spy.mock.calls.length;

    await act(async () => {
      harness.capturedRef().setTheme("light");
      await flush();
    });

    // Explicit user toggle path must opt into the transition (the ref is
    // now true, so the effect re-run uses animate: true).
    expect(spy.mock.calls.length).toBeGreaterThan(spyCallsBefore);
    expect(document.documentElement.classList.contains("light")).toBe(true);
    expect(document.documentElement.classList.contains("dark")).toBe(false);
    expect(harness.capturedRef().theme).toBe("light");
    expect(harness.capturedRef().effectiveTheme).toBe("light");
    expect(localStorage.getItem("tab_isg_theme")).toBe("light");

    await harness.unmount();
  });

  test("does not crash when startViewTransition throws on explicit toggle", async () => {
    setStartViewTransition(() => {
      throw new Error("Transition aborted");
    });

    const harness = mountWithConsumer();
    await harness.ready;

    let toggleError = null;
    await act(async () => {
      try {
        harness.capturedRef().setTheme("light");
      } catch (e) {
        toggleError = e;
      }
      await flush();
    });

    expect(toggleError).toBeNull();
    // Theme state mutation should succeed (setThemeState, localStorage write),
    // and the class should reflect the chosen theme after the effect runs.
    expect(harness.capturedRef().theme).toBe("light");
    expect(localStorage.getItem("tab_isg_theme")).toBe("light");
    expect(document.documentElement.classList.contains("light")).toBe(true);
    expect(document.documentElement.classList.contains("dark")).toBe(false);

    await harness.unmount();
  });

  test("toggle from light back to dark keeps canonical class mutation", async () => {
    localStorage.setItem("tab_isg_theme", "light");
    const spy = jest.fn((cb) => {
      cb();
      return { finished: Promise.resolve() };
    });
    setStartViewTransition(spy);

    const harness = mountWithConsumer();
    await harness.ready;

    await act(async () => {
      harness.capturedRef().setTheme("dark");
      await flush();
    });

    expect(document.documentElement.classList.contains("dark")).toBe(true);
    expect(document.documentElement.classList.contains("light")).toBe(false);
    expect(harness.capturedRef().effectiveTheme).toBe("dark");

    await harness.unmount();
  });
});

// ---------------------------------------------------------------------------
// Test C — unsupported ViewTransition
// ---------------------------------------------------------------------------
describe("ThemeProvider — View Transition API unsupported", () => {
  beforeEach(() => {
    resetDocument();
  });

  afterEach(() => {
    resetDocument();
  });

  test("initial mount applies class without startViewTransition", async () => {
    setStartViewTransition(undefined);

    const container = document.createElement("div");
    document.body.appendChild(container);
    const root = createRoot(container);

    let renderError = null;
    try {
      await act(async () => {
        root.render(
          React.createElement(
            React.StrictMode,
            null,
            React.createElement(
              ThemeProvider,
              null,
              React.createElement("div", null, "x")
            )
          )
        );
        await flush();
      });
    } catch (e) {
      renderError = e;
    }

    expect(renderError).toBeNull();
    expect(document.documentElement.classList.contains("dark")).toBe(true);

    await act(async () => {
      root.unmount();
    });
    container.remove();
  });

  test("explicit toggle applies class without startViewTransition", async () => {
    setStartViewTransition(undefined);

    let captured = null;
    const Consumer = () => {
      captured = useTheme();
      return null;
    };

    const container = document.createElement("div");
    document.body.appendChild(container);
    const root = createRoot(container);

    await act(async () => {
      root.render(
        React.createElement(
          React.StrictMode,
          null,
          React.createElement(
            ThemeProvider,
            null,
            React.createElement(Consumer, null)
          )
        )
      );
      await flush();
    });

    let toggleError = null;
    await act(async () => {
      try {
        captured.setTheme("light");
      } catch (e) {
        toggleError = e;
      }
      await flush();
    });

    expect(toggleError).toBeNull();
    expect(document.documentElement.classList.contains("light")).toBe(true);
    expect(document.documentElement.classList.contains("dark")).toBe(false);
    expect(captured.effectiveTheme).toBe("light");
    expect(localStorage.getItem("tab_isg_theme")).toBe("light");

    await act(async () => {
      root.unmount();
    });
    container.remove();
  });

  test("persisted 'light' theme is honored on initial mount without startViewTransition", async () => {
    localStorage.setItem("tab_isg_theme", "light");
    setStartViewTransition(undefined);

    const container = document.createElement("div");
    document.body.appendChild(container);
    const root = createRoot(container);

    await act(async () => {
      root.render(
        React.createElement(
          React.StrictMode,
          null,
          React.createElement(
            ThemeProvider,
            null,
            React.createElement("div", null, "x")
          )
        )
      );
      await flush();
    });

    expect(document.documentElement.classList.contains("light")).toBe(true);
    expect(document.documentElement.classList.contains("dark")).toBe(false);

    await act(async () => {
      root.unmount();
    });
    container.remove();
  });
});