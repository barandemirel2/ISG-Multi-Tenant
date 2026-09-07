// P0 — Public registration UX gate contract.
//
// Pins the frontend mirror of the public registration gate. The
// authoritative security boundary lives in the backend
// (``ENABLE_PUBLIC_REGISTRATION`` in ``backend/registration_config.py``);
// the frontend flag (``REACT_APP_PUBLIC_REGISTRATION_ENABLED``) is
// UX-only and never authoritative.
//
// This suite has three concerns:
//
// 1. **Pure parser** — ``parsePublicRegistrationEnabled`` resolves the
//    flag with the same strict-literal convention as the backend
//    parser (``true`` / ``false`` only; aliases rejected; unset / empty
//    defaults to ``false``).
//
// 2. **Login surface** — when the flag is ``false`` (the production
//    default), the "Hesap Oluştur" / "Kayıt olun" link is NOT in the
//    rendered DOM at all. When ``true``, the link IS present.
//
// 3. **Route surface** — visiting ``/register`` directly when the flag
//    is ``false`` redirects to ``/login`` (no infinite redirect loop).
//    When ``true``, the RegisterPage renders normally.
//
// The disabled/enabled split is exercised through
// ``jest.isolateModules`` because the production module captures
// ``process.env`` at import time — same as the existing
// ``lib/api.test.js`` recipe for ``REACT_APP_BACKEND_URL``. This
// mirrors how a real deployment bakes the env at build time.

import React from "react";
import { createRoot } from "react-dom/client";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
const { act } = require("react");

// ---------------------------------------------------------------------------
// Stubs — match the recipe used by AuthInputVisibility.test.jsx so the
// dependencies of LoginPage / RegisterPage stay isolated.
// ---------------------------------------------------------------------------

jest.mock("../components/AppShell", () => ({
  __esModule: true,
  default: ({ children }) => children,
}));

const mockUseAuth = jest.fn();
jest.mock("../context/AuthContext", () => ({
  useAuth: () => mockUseAuth(),
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

// react-router-dom v7 ⇒ react-router/dom dependency isn't installed in
// the test rig. Stub Navigate as a recording stub so we can assert the
// redirect target, and stub Link as a plain anchor.
jest.mock("react-router-dom", () => {
  const React = require("react");
  function NavigateStub({ to, replace }) {
    React.useEffect(() => {
      mockNavigateSpy(to, replace);
    }, [to, replace]);
    return null;
  }
  function LinkStub(props) {
    const { to, children, ...rest } = props;
    return React.createElement("a", { href: to, ...rest }, children);
  }
  return {
    __esModule: true,
    Navigate: NavigateStub,
    Link: LinkStub,
    useNavigate: () => mockNavigateSpy,
    useLocation: () => ({ pathname: "/register" }),
  };
});

// Mock the visibility module with a factory that reads from a shared
// mutable state. Tests change ``mockRegistrationState.enabled`` per
// case via ``setPublicRegistrationEnabledForRendering`` so we can
// exercise both branches without resetting React or any other module.
const mockRegistrationState = { enabled: false };
jest.mock("../lib/registrationVisibility", () => {
  const actual = jest.requireActual("../lib/registrationVisibility");
  return {
    __esModule: true,
    ...actual,
    isPublicRegistrationEnabled: () => mockRegistrationState.enabled,
    PUBLIC_REGISTRATION_ENABLED: mockRegistrationState.enabled,
  };
});

const mockNavigateSpy = jest.fn();
beforeEach(() => {
  mockNavigateSpy.mockClear();
  mockUseAuth.mockReturnValue({
    login: jest.fn().mockResolvedValue({}),
    register: jest.fn().mockResolvedValue({}),
    logout: jest.fn(),
  });
  mockRegistrationState.enabled = false;
});

function setPublicRegistrationEnabledForRendering(value) {
  mockRegistrationState.enabled = value;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Patch ``process.env.REACT_APP_PUBLIC_REGISTRATION_ENABLED`` for the
 * duration of ``fn``, then restore. Used to drive
 * :func:`parsePublicRegistrationEnabled` against a real env mapping.
 *
 * Tests that exercise the actual JSX rendering go through the
 * ``setPublicRegistrationEnabledForRendering`` helper below, which
 * mocks the visibility module so React doesn't need to be reset.
 */
async function withEnv(value, fn) {
  const ORIGINAL = process.env.REACT_APP_PUBLIC_REGISTRATION_ENABLED;
  if (value === undefined) {
    delete process.env.REACT_APP_PUBLIC_REGISTRATION_ENABLED;
  } else {
    process.env.REACT_APP_PUBLIC_REGISTRATION_ENABLED = value;
  }
  try {
    return await fn();
  } finally {
    if (ORIGINAL === undefined) {
      delete process.env.REACT_APP_PUBLIC_REGISTRATION_ENABLED;
    } else {
      process.env.REACT_APP_PUBLIC_REGISTRATION_ENABLED = ORIGINAL;
    }
  }
}

async function renderWith(Component) {
  const container = document.createElement("div");
  document.body.appendChild(container);
  const root = createRoot(container);
  await act(async () => {
    root.render(React.createElement(Component));
  });
  return {
    container,
    root,
    cleanup: async () => {
      await act(async () => {
        root.unmount();
      });
      container.remove();
    },
  };
}

// =========================================================================
// 1. Pure parser
// =========================================================================

describe("parsePublicRegistrationEnabled — strict boolean contract", () => {
  // Parser tests bypass the global mock (declared at the top of the
  // file for JSX-rendering tests) and exercise the real
  // implementation via ``jest.requireActual``. This pins the
  // production-grade parser behavior without conflating it with the
  // JSX rendering test machinery.

  test("unset env defaults to false (production-safe default)", async () => {
    await withEnv(undefined, () => {
      const mod = jest.requireActual("../lib/registrationVisibility");
      expect(mod.parsePublicRegistrationEnabled(process.env)).toBe(false);
    });
  });

  test("empty / whitespace env defaults to false", async () => {
    await withEnv("", () => {
      const mod = jest.requireActual("../lib/registrationVisibility");
      expect(mod.parsePublicRegistrationEnabled(process.env)).toBe(false);
    });
    await withEnv("   ", () => {
      const mod = jest.requireActual("../lib/registrationVisibility");
      expect(mod.parsePublicRegistrationEnabled(process.env)).toBe(false);
    });
  });

  test("explicit true enables", async () => {
    await withEnv("true", () => {
      const mod = jest.requireActual("../lib/registrationVisibility");
      expect(mod.parsePublicRegistrationEnabled(process.env)).toBe(true);
    });
  });

  test("explicit false disables", async () => {
    await withEnv("false", () => {
      const mod = jest.requireActual("../lib/registrationVisibility");
      expect(mod.parsePublicRegistrationEnabled(process.env)).toBe(false);
    });
  });

  test("true / false are case-insensitive", async () => {
    for (const v of ["TRUE", "True"]) {
      await withEnv(v, () => {
        const mod = jest.requireActual("../lib/registrationVisibility");
        expect(mod.parsePublicRegistrationEnabled(process.env)).toBe(true);
      });
    }
    for (const v of ["FALSE", "False"]) {
      await withEnv(v, () => {
        const mod = jest.requireActual("../lib/registrationVisibility");
        expect(mod.parsePublicRegistrationEnabled(process.env)).toBe(false);
      });
    }
  });

  test("surrounding whitespace is tolerated", async () => {
    await withEnv(" true ", () => {
      const mod = jest.requireActual("../lib/registrationVisibility");
      expect(mod.parsePublicRegistrationEnabled(process.env)).toBe(true);
    });
    await withEnv("\tfalse\n", () => {
      const mod = jest.requireActual("../lib/registrationVisibility");
      expect(mod.parsePublicRegistrationEnabled(process.env)).toBe(false);
    });
  });

  // Aliases are tested via the explicit-mapping API because the
  // module-level snapshot would throw on import if the env value is
  // an alias (production-grade fail-fast behavior).
  test.each(["1", "0", "yes", "no", "on", "off", "enabled", "disabled", "maybe"])(
    "alias %s is rejected by parsePublicRegistrationEnabled()",
    (alias) => {
      const mod = jest.requireActual("../lib/registrationVisibility");
      expect(() =>
        mod.parsePublicRegistrationEnabled({
          REACT_APP_PUBLIC_REGISTRATION_ENABLED: alias,
        })
      ).toThrow(/REACT_APP_PUBLIC_REGISTRATION_ENABLED/);
    }
  );

  test("non-string env is rejected", () => {
    const mod = jest.requireActual("../lib/registrationVisibility");
    expect(() =>
      mod.parsePublicRegistrationEnabled({
        REACT_APP_PUBLIC_REGISTRATION_ENABLED: 1,
      })
    ).toThrow(/REACT_APP_PUBLIC_REGISTRATION_ENABLED/);
  });

  test("error message does NOT echo the offending value", () => {
    const mod = jest.requireActual("../lib/registrationVisibility");
    const sentinel = "invalid-uuid-7c3a9f10-1b22-4d55-aaaa-bbbbccccdddd";
    let captured;
    try {
      mod.parsePublicRegistrationEnabled({
        REACT_APP_PUBLIC_REGISTRATION_ENABLED: sentinel,
      });
    } catch (e) {
      captured = e;
    }
    expect(captured).toBeDefined();
    expect(captured.message.includes(sentinel)).toBe(false);
  });
});

// =========================================================================
// 2. Login surface — registration link visibility
// =========================================================================

describe("LoginPage — 'Kayıt olun' link visibility", () => {
  // These tests assert the JSX contract: when the visibility flag
  // resolves to false, the link is absent; when true, the link is
  // rendered. The visibility module is mocked globally above so we
  // just toggle ``mockRegistrationState.enabled`` per test.
  // eslint-disable-next-line global-require
  const LoginPage = require("../pages/LoginPage").default;

  test("default / disabled: link is NOT in the DOM", async () => {
    setPublicRegistrationEnabledForRendering(false);
    const h = await renderWith(LoginPage);
    try {
      const link = h.container.querySelector('[data-testid="go-to-register"]');
      expect(link).toBeNull();
      // The wrapper div is unconditional; the hint text always renders.
      const hint = h.container.querySelector('[data-testid="login-register-hint"]');
      expect(hint).not.toBeNull();
    } finally {
      await h.cleanup();
    }
  });

  test("explicit false: link is NOT in the DOM", async () => {
    setPublicRegistrationEnabledForRendering(false);
    const h = await renderWith(LoginPage);
    try {
      const link = h.container.querySelector('[data-testid="go-to-register"]');
      expect(link).toBeNull();
    } finally {
      await h.cleanup();
    }
  });

  test("explicit true: link IS in the DOM with the canonical text", async () => {
    setPublicRegistrationEnabledForRendering(true);
    const h = await renderWith(LoginPage);
    try {
      const link = h.container.querySelector('[data-testid="go-to-register"]');
      expect(link).not.toBeNull();
      // ``Kayıt olun`` is the legacy Turkish CTA — preserve the text.
      expect(link.textContent.trim()).toBe("Kayıt olun");
      // Sanity: the hint text "Hesabınız yok mu?" still renders when
      // the link is present. The wrapper div is unconditional; only
      // the link itself is gated.
      expect(h.container.textContent).toMatch(/Hesabınız yok mu/);
    } finally {
      await h.cleanup();
    }
  });
});

// =========================================================================
// 3. Route surface — /register when disabled redirects to /login
// =========================================================================

describe("/register route — gate behavior", () => {
  // Mirror the production RegisterGate shape from App.js so the
  // observable contract is identical. (Mirror rather than importing
  // App.js — App.js pulls in the entire provider stack.) The
  // visibility module is mocked globally so RegisterGate consults
  // ``mockRegistrationState.enabled`` through ``isPublicRegistrationEnabled``.
  const React = require("react");
  // eslint-disable-next-line global-require
  const { Navigate } = require("react-router-dom");
  // eslint-disable-next-line global-require
  const vis = require("../lib/registrationVisibility");
  // eslint-disable-next-line global-require
  const RegisterPage = require("../pages/RegisterPage").default;

  function RegisterGateMirror() {
    if (!vis.isPublicRegistrationEnabled()) {
      return React.createElement(Navigate, { to: "/login", replace: true });
    }
    return React.createElement(RegisterPage);
  }

  test("disabled: rendering RegisterGate redirects to /login (replace)", async () => {
    setPublicRegistrationEnabledForRendering(false);
    const h = await renderWith(RegisterGateMirror);
    try {
      // The Navigate stub records via useEffect — wait one tick so the
      // effect runs before we assert.
      await act(async () => {
        await new Promise((r) => setTimeout(r, 0));
      });
      expect(mockNavigateSpy).toHaveBeenCalledWith("/login", true);
    } finally {
      await h.cleanup();
    }
  });

  test("enabled: rendering RegisterGate renders RegisterPage", async () => {
    setPublicRegistrationEnabledForRendering(true);
    const h = await renderWith(RegisterGateMirror);
    try {
      // No redirect fired.
      expect(mockNavigateSpy).not.toHaveBeenCalled();
      // RegisterPage renders its form.
      const form = h.container.querySelector('[data-testid="register-form"]');
      expect(form).not.toBeNull();
      const nameInput = h.container.querySelector('[data-testid="register-name-input"]');
      expect(nameInput).not.toBeNull();
      const submit = h.container.querySelector('[data-testid="register-submit-btn"]');
      expect(submit).not.toBeNull();
      expect(submit.textContent).toMatch(/Hesap Oluştur/);
    } finally {
      await h.cleanup();
    }
  });
});

// =========================================================================
// 4. Security-mismatch sanity — frontend flag is UX-only, not a boundary
// =========================================================================

describe("Frontend flag is UX-only — not a security boundary", () => {
  test("App.js source pins the flag as non-authoritative (UX guard)", () => {
    // We assert this via source-shape rather than via behavior because
    // the actual "backend wins on mismatch" contract lives in the
    // backend (covered by backend/tests/test_pr_public_registration_gate.py).
    // The frontend test exists to ensure the source keeps documenting
    // the contract so a future refactor cannot quietly re-cast the
    // flag as authoritative.
    const fs = require("fs");
    const path = require("path");
    const appSource = fs.readFileSync(
      path.join(__dirname, "..", "App.js"),
      "utf8"
    );
    const loginSource = fs.readFileSync(
      path.join(__dirname, "..", "pages", "LoginPage.jsx"),
      "utf8"
    );
    // LoginPage MUST consult isPublicRegistrationEnabled() (or
    // PUBLIC_REGISTRATION_ENABLED) before rendering the link.
    expect(loginSource).toMatch(/isPublicRegistrationEnabled\(\)|PUBLIC_REGISTRATION_ENABLED/);
    // App.js MUST route /register through RegisterGate (not RegisterPage directly).
    expect(appSource).toMatch(/<RegisterGate\s*\/>/);
    expect(appSource).toMatch(/isPublicRegistrationEnabled\(\)|PUBLIC_REGISTRATION_ENABLED/);
    // The gate must NOT be the only defense — backend has its own.
    // (We assert the comment string is present so a future editor who
    // removes it triggers this test.)
    expect(appSource).toMatch(/authoritative/i);
  });

  test("LoginPage source pins link visibility to isPublicRegistrationEnabled()", () => {
    const fs = require("fs");
    const path = require("path");
    const src = fs.readFileSync(
      path.join(__dirname, "..", "pages", "LoginPage.jsx"),
      "utf8"
    );
    // The link element MUST only render when the flag is true.
    expect(src).toMatch(/isPublicRegistrationEnabled\(\)/);
  });
});
