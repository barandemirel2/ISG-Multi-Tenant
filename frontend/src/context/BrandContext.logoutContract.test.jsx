// Regression test: brand state must NOT survive logout across users.
//
// Bug context (PR2 review):
//   ``tab_selected_brand`` was persisted to localStorage by BrandContext
//   but never cleared on logout. The same browser's next user inherited
//   the previous user's selected brand on first render, landing in the
//   wrong workspace before /brand-selection could re-derive it.
//
// Fix: BrandAuthSync observes the auth state transition (truthy user →
// false) and calls ``clearSelectedBrand()``. This suite pins four
// observable contracts:
//
//   1. BrandContext rehydrates ``tab_selected_brand`` from localStorage
//      on mount.
//   2. ``clearSelectedBrand()`` empties both state and localStorage.
//   3. The BrandAuthSync side-effect clears brand when auth becomes
//      unauthenticated.
//   4. After a logout, a fresh BrandContext mount (next-user scenario)
//      starts with no persisted brand.
//
// Test runner: craco test (Jest + jsdom from react-scripts). No RTL.

import React from "react";
import { createRoot } from "react-dom/client";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
const { act } = require("react");

// ---------------------------------------------------------------------------
// AuthContext mock — BrandAuthSync reads only useAuth().user. We control
// the user object via ``mockUseAuth`` in each test.
// ---------------------------------------------------------------------------
const mockUseAuth = jest.fn();
jest.mock("../context/AuthContext", () => ({
  useAuth: () => mockUseAuth(),
}));

// Subject (must come AFTER jest.mock calls; jest hoists jest.mock anyway).
import BrandAuthSync from "../components/BrandAuthSync";
import { BrandProvider, useBrand } from "./BrandContext";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function flush() {
  return new Promise((resolve) => setTimeout(resolve, 0));
}

function resetStorage() {
  localStorage.clear();
}

function mountBrandSync() {
  let captured = null;
  const Consumer = () => {
    captured = useBrand();
    return null;
  };
  const container = document.createElement("div");
  document.body.appendChild(container);
  const root = createRoot(container);
  return {
    capturedRef: () => captured,
    container,
    root,
    trigger: async () => {
      await act(async () => {
        root.render(
          React.createElement(
            BrandProvider,
            null,
            React.createElement(BrandAuthSync, null),
            React.createElement(Consumer, null)
          )
        );
        await flush();
      });
    },
    unmount: async () => {
      await act(async () => {
        root.unmount();
      });
      container.remove();
    },
  };
}

// ---------------------------------------------------------------------------
// 1 + 2. BrandContext pure contracts
// ---------------------------------------------------------------------------
describe("BrandContext — persistence + clear", () => {
  beforeEach(() => {
    resetStorage();
    mockUseAuth.mockReturnValue({ user: null });
  });

  test("provider rehydrates tab_selected_brand from localStorage on mount", async () => {
    localStorage.setItem("tab_selected_brand", "Burger King");
    let captured = null;
    const Consumer = () => {
      captured = useBrand();
      return null;
    };
    const container = document.createElement("div");
    document.body.appendChild(container);
    const root = createRoot(container);
    await act(async () => {
      root.render(
        React.createElement(
          BrandProvider,
          null,
          React.createElement(Consumer, null)
        )
      );
      await flush();
    });

    expect(captured.selectedBrand).toBe("Burger King");
    expect(localStorage.getItem("tab_selected_brand")).toBe("Burger King");

    await act(async () => {
      root.unmount();
    });
    container.remove();
  });

  test("setSelectedBrand persists non-empty and removes on empty", async () => {
    let captured = null;
    const Consumer = () => {
      captured = useBrand();
      return null;
    };
    const container = document.createElement("div");
    document.body.appendChild(container);
    const root = createRoot(container);
    await act(async () => {
      root.render(
        React.createElement(
          BrandProvider,
          null,
          React.createElement(Consumer, null)
        )
      );
      await flush();
    });

    await act(async () => {
      captured.setSelectedBrand("Popeyes");
    });
    expect(captured.selectedBrand).toBe("Popeyes");
    expect(localStorage.getItem("tab_selected_brand")).toBe("Popeyes");

    await act(async () => {
      captured.setSelectedBrand("");
    });
    expect(captured.selectedBrand).toBe("");
    expect(localStorage.getItem("tab_selected_brand")).toBeNull();

    await act(async () => {
      root.unmount();
    });
    container.remove();
  });

  test("clearSelectedBrand empties state and removes the localStorage entry", async () => {
    localStorage.setItem("tab_selected_brand", "Subway");
    let captured = null;
    const Consumer = () => {
      captured = useBrand();
      return null;
    };
    const container = document.createElement("div");
    document.body.appendChild(container);
    const root = createRoot(container);
    await act(async () => {
      root.render(
        React.createElement(
          BrandProvider,
          null,
          React.createElement(Consumer, null)
        )
      );
      await flush();
    });
    expect(captured.selectedBrand).toBe("Subway");

    await act(async () => {
      captured.clearSelectedBrand();
    });
    expect(captured.selectedBrand).toBe("");
    expect(localStorage.getItem("tab_selected_brand")).toBeNull();

    await act(async () => {
      root.unmount();
    });
    container.remove();
  });
});

// ---------------------------------------------------------------------------
// 3 + 4. BrandAuthSync clears brand on truthy → false logout edge.
//     Next-user scenario: a fresh BrandProvider mount after logout has
//     no brand in storage and no brand in state.
// ---------------------------------------------------------------------------
describe("BrandAuthSync — clear on logout + next-user scenario", () => {
  beforeEach(() => {
    resetStorage();
    mockUseAuth.mockReturnValue({ user: null });
  });

  test("truthy → false auth transition clears the persisted brand", async () => {
    mockUseAuth.mockReturnValue({ user: { id: "u1", name: "User 1", role: "user" } });
    localStorage.setItem("tab_selected_brand", "Sbarro");

    const harness = mountBrandSync();
    await harness.trigger();

    expect(harness.capturedRef().selectedBrand).toBe("Sbarro");
    expect(localStorage.getItem("tab_selected_brand")).toBe("Sbarro");

    // Simulate logout — auth.user flips truthy → false.
    mockUseAuth.mockReturnValue({ user: false });
    await harness.trigger();

    expect(harness.capturedRef().selectedBrand).toBe("");
    expect(localStorage.getItem("tab_selected_brand")).toBeNull();

    await harness.unmount();
  });

  test("first-load guest render (null → null) does NOT mutate an empty brand storage", async () => {
    mockUseAuth.mockReturnValue({ user: null });

    const harness = mountBrandSync();
    await harness.trigger();

    // No transition on first mount of BrandAuthSync; stay as guest.
    expect(localStorage.getItem("tab_selected_brand")).toBeNull();
    expect(harness.capturedRef().selectedBrand).toBe("");

    await harness.unmount();
  });

  test("next-user scenario: after logout, a fresh BrandProvider mount sees no persisted brand", async () => {
    mockUseAuth.mockReturnValue({ user: { id: "u-old", name: "Old User", role: "user" } });
    localStorage.setItem("tab_selected_brand", "Arby's");

    // User-1 mounts, picks a brand.
    const harnessOld = mountBrandSync();
    await harnessOld.trigger();
    expect(harnessOld.capturedRef().selectedBrand).toBe("Arby's");

    // Logout: auth flips to false → BrandAuthSync clears storage.
    mockUseAuth.mockReturnValue({ user: false });
    await harnessOld.trigger();
    expect(localStorage.getItem("tab_selected_brand")).toBeNull();
    expect(harnessOld.capturedRef().selectedBrand).toBe("");
    await harnessOld.unmount();

    // Next user mounts a fresh BrandContext. Auth is the next user's
    // truthy identity. The brand they see MUST be empty.
    mockUseAuth.mockReturnValue({ user: { id: "u-new", name: "New User", role: "user" } });
    const harnessNew = mountBrandSync();
    await harnessNew.trigger();

    // The whole point: a new user does NOT inherit the previous user's
    // brand. They must see empty brand and proceed through
    // /brand-selection.
    expect(harnessNew.capturedRef().selectedBrand).toBe("");
    expect(localStorage.getItem("tab_selected_brand")).toBeNull();

    await harnessNew.unmount();
  });

  test("logout from a guest state (false → false) does not crash and leaves storage untouched", async () => {
    // Brand persisted while logged-out is unusual but the invariant is
    // about clear on truthy → false. False → false (already unauth)
    // does NOT trigger the side-effect; storage is preserved.
    mockUseAuth.mockReturnValue({ user: false });
    localStorage.setItem("tab_selected_brand", "Popeyes");

    const harness = mountBrandSync();
    await harness.trigger();
    expect(harness.capturedRef().selectedBrand).toBe("Popeyes");

    // Re-render with the same user=false — no transition.
    await harness.trigger();
    expect(localStorage.getItem("tab_selected_brand")).toBe("Popeyes");

    await harness.unmount();
  });
});
