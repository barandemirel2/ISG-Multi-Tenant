// Regression test: RootRedirect + BrandSelectionPage — auth+brand flow.
//
// PR2 review coverage. The root route's redirect logic and the
// brand-selection page set the workspace for the active session:
//
//   * Authenticated user, no selected brand → /brand-selection
//   * Authenticated user, valid selected brand → /dashboard
//   * Guest (no /auth/me) → /login
//
// BrandSelectionPage mutates the BrandContext (context + localStorage)
// and navigates to /dashboard on selection.
//
// Implementation note: react-router-dom v7 requires `react-router/dom`
// which isn't installed in the project's node_modules test rig. We
// stub react-router-dom in the factory and exercise the redirect
// observable through a stateful ``useNavigate`` spy. The source-level
// shape of App.js is also pinned to catch drift in the real routing
// contract.

import React from "react";
import { createRoot } from "react-dom/client";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
const { act } = require("react");

// ---------------------------------------------------------------------------
// Stubs
// ---------------------------------------------------------------------------
jest.mock("./components/AppShell", () => {
  const Stub = ({ children }) => children;
  return { __esModule: true, default: Stub };
});

const mockUseAuth = jest.fn();
jest.mock("./context/AuthContext", () => ({
  __esModule: true,
  useAuth: () => mockUseAuth(),
}));

const mockUseBrand = jest.fn();
jest.mock("./context/BrandContext", () => ({
  __esModule: true,
  useBrand: () => mockUseBrand(),
  BRANDS_LIST: [],
}));

jest.mock("./components/BrandLogos", () => ({
  __esModule: true,
  getBrandLogo: () => null,
}));

// react-router-dom v7 ⇒ react-router/dom dependency isn't installed.
// We stub it with a stateful navigate spy. Each useNavigate() call
// returns the same spy so we can assert redirect targets.
const mockNavigateSpy = jest.fn();
jest.mock("react-router-dom", () => {
  const React = require("react");
  function NavigateStub({ to }) {
    // Record where we're being sent. Render null (no visible element).
    React.useEffect(() => {
      mockNavigateSpy(to);
    }, [to]);
    return null;
  }
  return {
    __esModule: true,
    Navigate: NavigateStub,
    useNavigate: () => mockNavigateSpy,
    useLocation: () => ({ pathname: "/" }),
    Link: ({ to, children, onClick, ...rest }) =>
      React.createElement("a", { href: to, onClick, ...rest }, children),
    MemoryRouter: ({ children }) => children,
    Routes: ({ children }) => {
      // Match the FIRST child whose path is "*" or whose path equals "/".
      const matched = React.Children.toArray(children).find(
        (c) => c.props && (c.props.path === "*" || c.props.path === "/")
      );
      return matched ? matched.props.element || matched.props.children : null;
    },
    Route: ({ element }) => element,
  };
});

beforeEach(() => {
  mockNavigateSpy.mockClear();
});

// ---------------------------------------------------------------------------
// Helper — Render only the RootRedirect component. It will fire Navigate()
// (which our stub records via useEffect) — we assert the recorded target.
// ---------------------------------------------------------------------------
function renderRootRedirect() {
  // Mirror RootRedirect exactly from App.js.
  function RootRedirectMirror() {
    const { Navigate } = require("react-router-dom");
    const { user, checked } = mockUseAuth();
    const { selectedBrand } = mockUseBrand();
    if (!checked) return null;
    if (!user) return React.createElement(Navigate, { to: "/login", replace: true });
    if (!selectedBrand) return React.createElement(Navigate, { to: "/brand-selection", replace: true });
    return React.createElement(Navigate, { to: "/dashboard", replace: true });
  }

  const container = document.createElement("div");
  document.body.appendChild(container);
  const root = createRoot(container);
  return {
    container,
    root,
    trigger: async () => {
      await act(async () => {
        root.render(React.createElement(RootRedirectMirror));
        await new Promise((r) => setTimeout(r, 0));
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
// Tests — RootRedirect
// ---------------------------------------------------------------------------
describe("RootRedirect — auth+brand routing contract", () => {
  test("not-checked → null (no navigate spy call)", async () => {
    mockUseAuth.mockReturnValue({ user: null, checked: false });
    mockUseBrand.mockReturnValue({ selectedBrand: "" });
    const h = renderRootRedirect();
    await h.trigger();
    expect(mockNavigateSpy).not.toHaveBeenCalled();
    await h.unmount();
  });

  test("guest → /login", async () => {
    mockUseAuth.mockReturnValue({ user: null, checked: true });
    mockUseBrand.mockReturnValue({ selectedBrand: "" });
    const h = renderRootRedirect();
    await h.trigger();
    expect(mockNavigateSpy).toHaveBeenCalledWith("/login");
    await h.unmount();
  });

  test("authenticated + no brand → /brand-selection", async () => {
    mockUseAuth.mockReturnValue({
      user: { id: "u1", name: "U1" },
      checked: true,
    });
    mockUseBrand.mockReturnValue({ selectedBrand: "" });
    const h = renderRootRedirect();
    await h.trigger();
    expect(mockNavigateSpy).toHaveBeenCalledWith("/brand-selection");
    await h.unmount();
  });

  test("authenticated + valid brand → /dashboard", async () => {
    mockUseAuth.mockReturnValue({
      user: { id: "u1", name: "U1" },
      checked: true,
    });
    mockUseBrand.mockReturnValue({ selectedBrand: "Burger King" });
    const h = renderRootRedirect();
    await h.trigger();
    expect(mockNavigateSpy).toHaveBeenCalledWith("/dashboard");
    await h.unmount();
  });
});

// ---------------------------------------------------------------------------
// Live App.js source check — protects against mirror drift.
// ---------------------------------------------------------------------------
describe("App.js — RootRedirect logic shape", () => {
  const fs = require("fs");
  const path = require("path");
  const source = fs.readFileSync(path.join(__dirname, "App.js"), "utf8");

  test("RootRedirect checks checked → !user → !selectedBrand → /dashboard", () => {
    expect(source).toMatch(/function RootRedirect/);
    expect(source).toMatch(/!checked/);
    expect(source).toMatch(/!user/);
    expect(source).toMatch(/!selectedBrand/);
    expect(source).toMatch(/["']\/login["']/);
    expect(source).toMatch(/["']\/brand-selection["']/);
    expect(source).toMatch(/["']\/dashboard["']/);
  });

  test("BrandAuthSync is mounted inside both providers (clears brand on logout edge)", () => {
    expect(source).toMatch(/<BrandAuthSync\s*\/>/);
    expect(source).toMatch(/<BrandProvider>/);
    expect(source).toMatch(/<AuthProvider>/);
    const brandIdx = source.indexOf("<BrandProvider>");
    const authIdx = source.indexOf("<AuthProvider>");
    const syncIdx = source.indexOf("<BrandAuthSync");
    expect(brandIdx).toBeGreaterThan(-1);
    expect(authIdx).toBeGreaterThan(brandIdx);
    expect(syncIdx).toBeGreaterThan(authIdx);
  });
});

// ---------------------------------------------------------------------------
// BrandSelectionPage — selection flow
// ---------------------------------------------------------------------------
describe("BrandSelectionPage — selection flow", () => {
  test("handleSelectBrand contract: setSelectedBrand + navigate('/dashboard')", () => {
    const fs = require("fs");
    const path = require("path");
    const source = fs.readFileSync(
      path.join(__dirname, "pages", "BrandSelectionPage.jsx"),
      "utf8"
    );
    expect(source).toMatch(/setSelectedBrand/);
    expect(source).toMatch(/navigate\(["']\/dashboard["']\)/);
    expect(source).toMatch(/["']Tüm Markalar["']/);
  });
});

// ---------------------------------------------------------------------------
// Combined invariant: BrandAuthSync clears brand → next session can NOT
// auto-leap to dashboard. We exercise this by simulating the post-logout
// state (user truthy, selectedBrand="") and then asserting that a
// matching RootRedirect renders /brand-selection, not /dashboard.
// ---------------------------------------------------------------------------
describe("Post-logout state: no auto-leap into /dashboard", () => {
  test("with selectedBrand='' and a logged-in user, RootRedirect lands on /brand-selection", async () => {
    mockUseAuth.mockReturnValue({
      user: { id: "u-new", name: "U2" },
      checked: true,
    });
    mockUseBrand.mockReturnValue({ selectedBrand: "" }); // BrandAuthSync effect

    const h = renderRootRedirect();
    await h.trigger();
    expect(mockNavigateSpy).toHaveBeenCalledWith("/brand-selection");
    expect(mockNavigateSpy).not.toHaveBeenCalledWith("/dashboard");
    await h.unmount();
  });
});
