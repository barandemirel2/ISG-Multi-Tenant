// Regression test: post-authentication landing-route contract.
//
// Contract (this bugfix):
//   successful /api/auth/login     → /brand-selection
//   successful /api/auth/register  → /brand-selection
//   BrandSelectionPage selection   → /dashboard (preserved)
//
// History: a previous auth review found the asymmetry
//   LoginPage    → /brand-selection
//   RegisterPage → /dashboard
// on main. That asymmetry caused first-registration / local-demo auto-login
// to drop users straight onto /dashboard with no brand selected, instead of
// routing them through /brand-selection first. This test pins the corrected
// contract at three layers:
//
//   1. Source-level shape of LoginPage.jsx / RegisterPage.jsx.
//   2. Behavioral: invoke onSubmit with a successful auth context and assert
//      the navigate destination. Persisted `tab_selected_brand` in
//      localStorage must NOT cause explicit login to bypass /brand-selection.
//   3. End-to-end wiring: LoginPage + RegisterPage agree with
//      BrandSelectionPage on the post-auth flow.

import React from "react";
import { createRoot } from "react-dom/client";
import fs from "fs";
import path from "path";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
const { act } = require("react");

// ---------------------------------------------------------------------------
// Stubs
// ---------------------------------------------------------------------------
jest.mock("../components/AppShell", () => ({
  __esModule: true,
  default: ({ children }) => children,
}));

const mockUseAuth = jest.fn();
jest.mock("../context/AuthContext", () => ({
  __esModule: true,
  useAuth: () => mockUseAuth(),
}));

jest.mock("../components/BrandLogos", () => ({
  __esModule: true,
  getBrandLogo: () => null,
}));

jest.mock("../lib/api", () => ({
  __esModule: true,
  formatApiErrorDetail: () => null,
}));

jest.mock("sonner", () => ({
  toast: { success: jest.fn(), error: jest.fn() },
}));

jest.mock("lucide-react", () => {
  const Icon = () => null;
  return new Proxy({}, { get: () => Icon });
});

// react-router-dom v7 → react-router/dom isn't installed in this rig.
// We stub it with a stateful navigate spy so we can assert redirect targets
// for the live LoginPage / RegisterPage source (not a mirror).
const mockNavigateSpy = jest.fn();
jest.mock("react-router-dom", () => {
  const React = require("react");
  return {
    __esModule: true,
    Navigate: ({ to }) => null,
    useNavigate: () => mockNavigateSpy,
    Link: ({ to, children, ...rest }) =>
      React.createElement("a", { href: to, ...rest }, children),
    MemoryRouter: ({ children }) => children,
    Routes: ({ children }) => children,
    Route: ({ element }) => element,
  };
});

// Subject — must come AFTER jest.mock hoisting.
import LoginPage from "./LoginPage";
import RegisterPage from "./RegisterPage";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
async function renderPage(PageComponent) {
  const container = document.createElement("div");
  document.body.appendChild(container);
  const root = createRoot(container);
  await act(async () => {
    root.render(React.createElement(PageComponent));
  });
  return { container, root };
}

async function cleanup({ container, root }) {
  await act(async () => {
    root.unmount();
  });
  container.remove();
}

function flush() {
  return new Promise((resolve) => setTimeout(resolve, 0));
}

// Find the auth form on a rendered container.
async function submitAuthForm(container, { values } = {}) {
  const form = container.querySelector(
    'form[data-testid="login-form"], form[data-testid="register-form"]'
  );
  if (!form) throw new Error("auth form not found in rendered page");
  await act(async () => {
    if (values) {
      // Programmatic input population: React-controlled inputs react to
      // the input event, not direct .value writes. We dispatch a real
      // input event so React schedules the onChange → setState. Auth
      // inputs are keyed by ``id`` (no ``name`` attribute).
      Object.entries(values).forEach(([id, value]) => {
        const input = form.querySelector(`#${id}`);
        if (!input) return;
        const setter = Object.getOwnPropertyDescriptor(
          window.HTMLInputElement.prototype,
          "value"
        ).set;
        setter.call(input, value);
        input.dispatchEvent(new Event("input", { bubbles: true }));
      });
    }
    // Native submit triggers the React onSubmit handler.
    form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    // The onSubmit handler is async (await login/register); let microtasks
    // resolve before the caller asserts on navigate destinations.
    await flush();
  });
}

// ---------------------------------------------------------------------------
// 1. Source-level shape
// ---------------------------------------------------------------------------
describe("AuthPage source — post-auth redirect contract", () => {
  const loginSrc = fs.readFileSync(
    path.join(__dirname, "LoginPage.jsx"),
    "utf8"
  );
  const registerSrc = fs.readFileSync(
    path.join(__dirname, "RegisterPage.jsx"),
    "utf8"
  );

  test("LoginPage calls navigate('/brand-selection') after a successful login", () => {
    // Slice: the onSubmit body of LoginPage. The post-login flow must end
    // in /brand-selection, never /dashboard.
    expect(loginSrc).toMatch(/await login\(/);
    expect(loginSrc).toMatch(/navigate\(["']\/brand-selection["']\)/);
    expect(loginSrc).not.toMatch(/navigate\(["']\/dashboard["']/);
  });

  test("RegisterPage calls navigate('/brand-selection') after a successful registration", () => {
    expect(registerSrc).toMatch(/await register\(/);
    expect(registerSrc).toMatch(/navigate\(["']\/brand-selection["']\)/);
    expect(registerSrc).not.toMatch(/navigate\(["']\/dashboard["']/);
  });

  test("LoginPage and RegisterPage agree on the post-auth landing route", () => {
    // Symmetry guard: if either side drifts back to /dashboard (the bug
    // we're guarding against) this fails loudly.
    const loginLanding = loginSrc.match(
      /navigate\(["'](\/[a-z\-]+)["']\)/
    );
    const registerLanding = registerSrc.match(
      /navigate\(["'](\/[a-z\-]+)["']\)/
    );
    expect(loginLanding).not.toBeNull();
    expect(registerLanding).not.toBeNull();
    expect(loginLanding[1]).toBe(registerLanding[1]);
    expect(loginLanding[1]).toBe("/brand-selection");
  });
});

// ---------------------------------------------------------------------------
// 2. Behavioral: explicit-login-with-persisted-brand still routes to
//    /brand-selection. localStorage may carry a previous user's
//    ``tab_selected_brand`` (e.g. session expired without logout) but
//    explicit login must NOT auto-leap into /dashboard on that basis.
// ---------------------------------------------------------------------------
describe("AuthPage behavior — explicit login ignores persisted brand", () => {
  beforeEach(() => {
    localStorage.clear();
    mockNavigateSpy.mockClear();
    mockUseAuth.mockReturnValue({
      login: jest.fn().mockResolvedValue({ id: "u1", name: "U1" }),
      register: jest.fn().mockResolvedValue({ id: "u2", name: "U2" }),
    });
  });

  test("login with a stale persisted brand in localStorage still navigates to /brand-selection", async () => {
    // Simulate a previous user selecting a brand; the next user logs in
    // and must still see /brand-selection, never auto-leap to /dashboard.
    localStorage.setItem("tab_selected_brand", "Burger King");

    const { container, root } = await renderPage(LoginPage);
    try {
      submitAuthForm(container, {
        values: { email: "u@example.com", password: "secret123" },
      });
      await flush();

      expect(mockUseAuth().login).toHaveBeenCalled();
      expect(mockNavigateSpy).toHaveBeenCalledWith("/brand-selection");
      expect(mockNavigateSpy).not.toHaveBeenCalledWith("/dashboard");
    } finally {
      await cleanup({ container, root });
    }
  });

  test("successful registration + auto-login navigates to /brand-selection (no persisted brand)", async () => {
    const { container, root } = await renderPage(RegisterPage);
    try {
      submitAuthForm(container, {
        values: {
          name: "New User",
          email: "new@example.com",
          password: "secret123",
        },
      });
      await flush();

      expect(mockUseAuth().register).toHaveBeenCalled();
      expect(mockNavigateSpy).toHaveBeenCalledWith("/brand-selection");
      expect(mockNavigateSpy).not.toHaveBeenCalledWith("/dashboard");
    } finally {
      await cleanup({ container, root });
    }
  });

  test("auth error path: failure leaves navigate() uninvoked (no premature redirect)", async () => {
    mockUseAuth.mockReturnValue({
      login: jest.fn().mockRejectedValue(new Error("bad creds")),
      register: jest.fn().mockResolvedValue({ id: "u2", name: "U2" }),
    });

    const { container, root } = await renderPage(LoginPage);
    try {
      submitAuthForm(container, {
        values: { email: "u@example.com", password: "secret123" },
      });
      await flush();

      // Failure → no navigation. LoginPage's catch sets ``err`` and
      // returns; the user stays on /login to correct the input.
      expect(mockNavigateSpy).not.toHaveBeenCalledWith("/brand-selection");
      expect(mockNavigateSpy).not.toHaveBeenCalledWith("/dashboard");
    } finally {
      await cleanup({ container, root });
    }
  });
});

// ---------------------------------------------------------------------------
// 3. End-to-end wiring: BrandSelectionPage still navigates to /dashboard
//    after brand pick (preserved contract from RootRedirect.brandFlowContract).
//    Re-pinned here to make the full auth chain self-contained.
// ---------------------------------------------------------------------------
describe("AuthPage chain — brand-selection → /dashboard is preserved", () => {
  test("BrandSelectionPage source still routes to /dashboard on brand pick", () => {
    const src = fs.readFileSync(
      path.join(__dirname, "BrandSelectionPage.jsx"),
      "utf8"
    );
    expect(src).toMatch(/setSelectedBrand/);
    expect(src).toMatch(/navigate\(["']\/dashboard["']\)/);
  });

  test("App.js RootRedirect still maps authenticated+brand → /dashboard", () => {
    const src = fs.readFileSync(
      path.join(__dirname, "..", "App.js"),
      "utf8"
    );
    expect(src).toMatch(/function RootRedirect/);
    expect(src).toMatch(/!user/);
    expect(src).toMatch(/!selectedBrand/);
    expect(src).toMatch(/["']\/login["']/);
    expect(src).toMatch(/["']\/brand-selection["']/);
    expect(src).toMatch(/["']\/dashboard["']/);
  });
});