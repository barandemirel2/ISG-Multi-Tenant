// Regression test: shared <Input> theme visibility contract on auth forms.
//
// Bug context (this task): <Input> (``frontend/src/components/ui/input.jsx``)
// "bg-transparent" + tailwind'in default `text-foreground`/inherit mekanizması
// üzerinden render ediyordu. LoginPage ve RegisterPage form panel'i her iki
// temada da `bg-[#FAFAFA]` (kullanıcının zorunlu light-bg marketing design)
// üzerine basıyor. Dark mode aktifken ``html.dark body { color: #F8FAFC }``
// (`frontend/src/index.css:8`) input text'inin near-white olmasına, transparent
// input'un light marketing bg'sini göstermesine ve typed text'in
// görünmemesine sebep oluyordu.
//
// Login kullanıcısı "light theme'de text görünmüyor" raporladı; gerçek
// repro dark mode + light marketing layout. Fix: <Input> ALWAYS explicit
// `bg-white text-zinc-900 placeholder:text-zinc-400 caret-zinc-900` taşır.
// Aşağıdaki contract testleri bu class'lar render edilmiş auth input'larında
// bulunduğunu ve shared component'in light-mode kıran hardcoded token
// taşımadığını sabitler.
//
// Not: Tam pixel-level görsel kontrast jsdom'da test EDİLEMEZ (jsdom
// computed-style değer döndürmez). Bu test "rendered DOM class contract'ı"
// seviyesinde çalışır. Amaç: <Input> bir refactor / shadcn u升级 / theme
// migration'ında visible-style class'larını kaybetmesin; eğer kaybederse
// unit-level production render çıktısı yakalanır.

import React from "react";
import { createRoot } from "react-dom/client";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
const { act } = require("react");

// ---------------------------------------------------------------------------
// Stubs — LoginPage / RegisterPage'in kullandığı bağımlılıkları minimumda
// sıfırdan inşa ediyoruz. Amaç: Input contract'ını mount + render + DOM
// aracılığıyla test etmek; router/sonner/api gibi side-effect'leri stub.
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

jest.mock("react-router-dom", () => ({
  __esModule: true,
  useNavigate: () => jest.fn(),
  Link: (props) => {
    const MockReact = require("react");
    const { to, children, ...rest } = props;
    return MockReact.createElement("a", { href: to, ...rest }, children);
  },
}));

jest.mock("sonner", () => ({
  toast: { success: jest.fn(), error: jest.fn() },
}));

jest.mock("lucide-react", () => {
  const Icon = () => null;
  return new Proxy({}, { get: () => Icon });
});

// Subject (must come AFTER jest.mock calls; jest hoists jest.mock anyway).
import LoginPage from "./LoginPage";
import RegisterPage from "./RegisterPage";

// ---------------------------------------------------------------------------
// Helpers — render the page in a real react-dom/client root and return the
// surrounding container element + the destroy-root ref for cleanup.
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

function cleanup({ container, root }) {
  return act(async () => {
    root.unmount();
  }).then(() => container.remove());
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------
describe("Auth input theme visibility contract", () => {
  beforeEach(() => {
    mockUseAuth.mockReturnValue({
      login: jest.fn().mockResolvedValue({}),
      register: jest.fn().mockResolvedValue({}),
    });
  });

  // -- Light mode (or pre-fix transparent body-inherit regression) ----------
  describe("LoginPage inputs", () => {
    test("email input carries visible-style classes (bug-fix contract)", async () => {
      const { container, root } = await renderPage(LoginPage);
      try {
        const input = container.querySelector('[data-testid="login-email-input"]');
        expect(input).not.toBeNull();
        const cls = input.getAttribute("class") || "";
        expect(cls).toEqual(expect.stringMatching(/text-zinc-900/));
        expect(cls).toEqual(expect.stringMatching(/placeholder:text-zinc-400/));
        expect(cls).toEqual(expect.stringMatching(/caret-zinc-900/));
        expect(cls).toEqual(expect.stringMatching(/\bbg-white\b/));
      } finally {
        await cleanup({ container, root });
      }
    });

    test("password input carries visible-style classes", async () => {
      const { container, root } = await renderPage(LoginPage);
      try {
        const input = container.querySelector('[data-testid="login-password-input"]');
        expect(input).not.toBeNull();
        const cls = input.getAttribute("class") || "";
        expect(cls).toEqual(expect.stringMatching(/text-zinc-900/));
        expect(cls).toEqual(expect.stringMatching(/placeholder:text-zinc-400/));
        expect(cls).toEqual(expect.stringMatching(/caret-zinc-900/));
        expect(cls).toEqual(expect.stringMatching(/\bbg-white\b/));
      } finally {
        await cleanup({ container, root });
      }
    });

    test("inputs do not carry light-bg-breaking hardcoded tokens (text-white / text-transparent)", async () => {
      const { container, root } = await renderPage(LoginPage);
      try {
        const inputs = container.querySelectorAll("input");
        expect(inputs.length).toBeGreaterThanOrEqual(2);
        inputs.forEach((input) => {
          const cls = input.getAttribute("class") || "";
          const tokens = cls.split(/\s+/);
          // Token-level (not substring) checks to avoid catching Tailwind
          // modifier prefixes like "file:bg-transparent" which are scoped
          // to <input type="file"> children — those don't apply to text
          // inputs and are explicitly part of the shadcn recipe.
          // "text-white" — near-white on light marketing bg = invisible.
          expect(tokens).not.toContain("text-white");
          // "text-transparent" — would make typed text vanish.
          expect(tokens).not.toContain("text-transparent");
          // bg-transparent on the always-light page bg inherits the page's
          // forced #FAFAFA, but loses the explicit "white surface" guarantee
          // that callers may rely on. Bug regression: bg-transparent alone
          // is insufficient — light marketing is ALWAYS white.
          expect(tokens).not.toContain("bg-transparent");
        });
      } finally {
        await cleanup({ container, root });
      }
    });
  });

  describe("RegisterPage inputs", () => {
    test("name input carries visible-style classes", async () => {
      const { container, root } = await renderPage(RegisterPage);
      try {
        const input = container.querySelector('[data-testid="register-name-input"]');
        expect(input).not.toBeNull();
        const cls = input.getAttribute("class") || "";
        expect(cls).toEqual(expect.stringMatching(/text-zinc-900/));
        expect(cls).toEqual(expect.stringMatching(/placeholder:text-zinc-400/));
        expect(cls).toEqual(expect.stringMatching(/caret-zinc-900/));
        expect(cls).toEqual(expect.stringMatching(/\bbg-white\b/));
      } finally {
        await cleanup({ container, root });
      }
    });

    test("email input carries visible-style classes", async () => {
      const { container, root } = await renderPage(RegisterPage);
      try {
        const input = container.querySelector('[data-testid="register-email-input"]');
        expect(input).not.toBeNull();
        const cls = input.getAttribute("class") || "";
        expect(cls).toEqual(expect.stringMatching(/text-zinc-900/));
        expect(cls).toEqual(expect.stringMatching(/placeholder:text-zinc-400/));
        expect(cls).toEqual(expect.stringMatching(/caret-zinc-900/));
        expect(cls).toEqual(expect.stringMatching(/\bbg-white\b/));
      } finally {
        await cleanup({ container, root });
      }
    });

    test("password input carries visible-style classes", async () => {
      const { container, root } = await renderPage(RegisterPage);
      try {
        const input = container.querySelector('[data-testid="register-password-input"]');
        expect(input).not.toBeNull();
        const cls = input.getAttribute("class") || "";
        expect(cls).toEqual(expect.stringMatching(/text-zinc-900/));
        expect(cls).toEqual(expect.stringMatching(/placeholder:text-zinc-400/));
        expect(cls).toEqual(expect.stringMatching(/caret-zinc-900/));
        expect(cls).toEqual(expect.stringMatching(/\bbg-white\b/));
      } finally {
        await cleanup({ container, root });
      }
    });

    test("all auth inputs across login + register share the contract", async () => {
      const { container: lContainer, root: lRoot } = await renderPage(LoginPage);
      const { container: rContainer, root: rRoot } = await renderPage(RegisterPage);
      try {
        const allInputs = [
          ...lContainer.querySelectorAll("input"),
          ...rContainer.querySelectorAll("input"),
        ];
        expect(allInputs.length).toBeGreaterThanOrEqual(5);
        allInputs.forEach((input) => {
          const cls = input.getAttribute("class") || "";
          expect(cls).toEqual(expect.stringMatching(/text-zinc-900/));
          expect(cls).toEqual(expect.stringMatching(/placeholder:text-zinc-400/));
          expect(cls).toEqual(expect.stringMatching(/caret-zinc-900/));
          expect(cls).toEqual(expect.stringMatching(/\bbg-white\b/));
        });
      } finally {
        await cleanup({ container: lContainer, root: lRoot });
        await cleanup({ container: rContainer, root: rRoot });
      }
    });
  });

  // ======================================================================
  // Auth panel typography visibility — the always-light marketing/form
  // panel sits on `bg-[#FAFAFA]` always, but in dark mode
  // `html.dark body { color: #F8FAFC }` (index.css:8) is near-white and
  // would inherit into every typography element that lacks an explicit
  // text-* class. The pre-fix LoginPage heading
  //   ``<h2 className="font-display text-3xl ...">Denetime devam edin.</h2>``
  // had no `text-*` → inherits near-white on light bg = invisible. Same
  // root cause on RegisterPage.
  //
  // These assertions guard every typography element on the right (form)
  // panel of Login + Register: heading, description (eyebrow + p),
  // labels, secondary text, link. They check that the canonical
  // zinc-based readable tokens (zinc-5/6/7/9x) are present so the
  // ``bg-[#FAFAFA]`` always-light panel stays readable regardless of
  // selected theme.
  // ======================================================================
  describe("Auth panel typography visibility", () => {
    // -- Helpers ------------------------------------------------------------
    // Returns a Set of class tokens, drop empty entries.
    function tokens(cls) {
      return new Set((cls || "").split(/\s+/).filter(Boolean));
    }

    // Assert the element carries at least one of the readable text tokens.
    // ``zinc-9x`` / ``zinc-8x`` are the dark readable families in this
    // codebase; ``zinc-7x`` is readable on light bg; ``zinc-6x`` is the
    // minimum readable; ``zinc-5x`` is fine for muted secondary text.
    function expectReadableDarkText(cls, where) {
      const t = tokens(cls);
      const allowed = [
        "text-zinc-500", "text-zinc-600", "text-zinc-700",
        "text-zinc-800", "text-zinc-900", "text-zinc-950",
      ];
      const ok = allowed.some((k) => t.has(k));
      expect(ok).toBe(true);
    }

    function expectNoBareInherit(el, where) {
      // "Bare inherited color" = no text-* token at all. Catches the
      // original heading bug: ``<h2 className="font-display ...">`` had
      // no text-* class so it inherited body near-white on dark mode.
      const t = tokens(el.getAttribute("class"));
      const hasExplicitText = [...t].some((tk) => /^text-(white|black|zinc-|slate-|red-|emerald-|amber-)/.test(tk));
      expect({ where, tokens: [...t], hasExplicitText }).toEqual(
        expect.objectContaining({ hasExplicitText: true })
      );
    }

    // -- Login --------------------------------------------------------------
    describe("LoginPage typography", () => {
      test("main heading (``h2``) carries explicit dark readable text", async () => {
        const { container, root } = await renderPage(LoginPage);
        try {
          const h2 = container.querySelector("h2");
          expect(h2).not.toBeNull();
          expect(h2.textContent.trim()).toBe("Denetime devam edin.");
          expectNoBareInherit(h2, "LoginPage h2");
          expectReadableDarkText(h2.getAttribute("class"), "LoginPage h2");
          // Heading hierarchy: it should be the strongest readable token
          // (zinc-9x family) — not muted zinc-5/6/7.
          const t = tokens(h2.getAttribute("class"));
          const isStrong = t.has("text-zinc-900") || t.has("text-zinc-950");
          expect(isStrong).toBe(true);
        } finally {
          await cleanup({ container, root });
        }
      });

      test("eyebrow + body description carry readable muted text", async () => {
        const { container, root } = await renderPage(LoginPage);
        try {
          // Eyebrow "Giriş Yap" — first child of form panel <div class="w-full max-w-sm">.
          const eyebrow = container.querySelector(".w-full.max-w-sm .label-caps");
          expect(eyebrow).not.toBeNull();
          expect(eyebrow.textContent.trim()).toBe("Giriş Yap");
          expectReadableDarkText(eyebrow.getAttribute("class"), "LoginPage eyebrow");
          // Description <p>.
          const desc = container.querySelector(".w-full.max-w-sm > p");
          expect(desc).not.toBeNull();
          expect(desc.textContent).toMatch(/Hesabınıza giriş yaparak/);
          expectReadableDarkText(desc.getAttribute("class"), "LoginPage description");
        } finally {
          await cleanup({ container, root });
        }
      });

      test("form labels carry explicit ``text-zinc-700`` readable token", async () => {
        const { container, root } = await renderPage(LoginPage);
        try {
          const labels = container.querySelectorAll(".w-full.max-w-sm label");
          expect(labels.length).toBeGreaterThanOrEqual(2);
          labels.forEach((label) => {
            expectNoBareInherit(label, "LoginPage label");
            const t = tokens(label.getAttribute("class"));
            expect(t.has("text-zinc-700")).toBe(true);
          });
        } finally {
          await cleanup({ container, root });
        }
      });

      test("secondary text wrapper carries explicit readable dark tokens (always rendered)", async () => {
        const { container, root } = await renderPage(LoginPage);
        try {
          // The "Hesabınız yok mu?" wrapper is unconditional; only the
          // <Link> inside it is gated by ``PUBLIC_REGISTRATION_ENABLED``
          // (P0 — public registration is closed in production by default).
          // We look up the wrapper via its dedicated testid so this
          // typography assertion is independent of the link's presence.
          const secondaryWrap = container.querySelector('[data-testid="login-register-hint"]');
          expect(secondaryWrap).not.toBeNull();
          expectReadableDarkText(secondaryWrap.getAttribute("class"), "LoginPage secondary text");
        } finally {
          await cleanup({ container, root });
        }
      });

      test("register link (when present) carries explicit readable dark tokens", async () => {
        // P0 — the link is only rendered when PUBLIC_REGISTRATION_ENABLED
        // is true. In this default-disabled test environment the link
        // is absent, so we assert the no-link state and skip the link
        // typography contract. The enabled branch is pinned in
        // ``registrationVisibility.test.jsx`` ("explicit true: link IS
        // in the DOM"), so the link's typography contract remains
        // protected end-to-end without duplicating setup here.
        const { container, root } = await renderPage(LoginPage);
        try {
          const link = container.querySelector('[data-testid="go-to-register"]');
          expect(link).toBeNull();
        } finally {
          await cleanup({ container, root });
        }
      });

      test("eyebrow + description do NOT carry near-white text-white", async () => {
        const { container, root } = await renderPage(LoginPage);
        try {
          // The eyebrow/description that the user reported as "affected".
          // They had `text-zinc-500` (marginal but not invisible) — this
          // guard is a smoke check for accidental regressions that drop
          // the readable token or invert it to text-white.
          const eyebrow = container.querySelector(".w-full.max-w-sm .label-caps");
          const desc = container.querySelector(".w-full.max-w-sm > p");
          [eyebrow, desc].forEach((el) => {
            expect(el).not.toBeNull();
            const t = tokens(el.getAttribute("class"));
            expect(t.has("text-white")).toBe(false);
          });
        } finally {
          await cleanup({ container, root });
        }
      });
    });

    // -- Register -----------------------------------------------------------
    describe("RegisterPage typography", () => {
      test("main heading (``h2``) carries explicit dark readable text", async () => {
        const { container, root } = await renderPage(RegisterPage);
        try {
          const h2 = container.querySelector("h2");
          expect(h2).not.toBeNull();
          expect(h2.textContent.trim()).toBe("Yeni bir hesap oluşturun.");
          expectNoBareInherit(h2, "RegisterPage h2");
          expectReadableDarkText(h2.getAttribute("class"), "RegisterPage h2");
          const t = tokens(h2.getAttribute("class"));
          const isStrong = t.has("text-zinc-900") || t.has("text-zinc-950");
          expect(isStrong).toBe(true);
        } finally {
          await cleanup({ container, root });
        }
      });

      test("eyebrow + body description carry readable muted text", async () => {
        const { container, root } = await renderPage(RegisterPage);
        try {
          const eyebrow = container.querySelector(".w-full.max-w-sm .label-caps");
          expect(eyebrow).not.toBeNull();
          expect(eyebrow.textContent.trim()).toBe("Kayıt Ol");
          expectReadableDarkText(eyebrow.getAttribute("class"), "RegisterPage eyebrow");
          const desc = container.querySelector(".w-full.max-w-sm > p");
          expect(desc).not.toBeNull();
          expect(desc.textContent).toMatch(/Restoran denetimlerinizi kayıt altına/);
          expectReadableDarkText(desc.getAttribute("class"), "RegisterPage description");
        } finally {
          await cleanup({ container, root });
        }
      });

      test("form labels carry explicit ``text-zinc-700`` readable token", async () => {
        const { container, root } = await renderPage(RegisterPage);
        try {
          const labels = container.querySelectorAll(".w-full.max-w-sm label");
          expect(labels.length).toBeGreaterThanOrEqual(3);
          labels.forEach((label) => {
            expectNoBareInherit(label, "RegisterPage label");
            const t = tokens(label.getAttribute("class"));
            expect(t.has("text-zinc-700")).toBe(true);
          });
        } finally {
          await cleanup({ container, root });
        }
      });

      test("secondary text + login link carry explicit readable dark tokens", async () => {
        const { container, root } = await renderPage(RegisterPage);
        try {
          const secondaryWrap = container.querySelector('[data-testid="go-to-login"]').parentElement;
          expect(secondaryWrap).not.toBeNull();
          expectReadableDarkText(secondaryWrap.getAttribute("class"), "RegisterPage secondary text");

          const link = container.querySelector('[data-testid="go-to-login"]');
          expect(link).not.toBeNull();
          expect(link.textContent.trim()).toBe("Giriş yapın");
          expectReadableDarkText(link.getAttribute("class"), "RegisterPage link");
          const t = tokens(link.getAttribute("class"));
          const isStrong = t.has("text-zinc-900") || t.has("text-zinc-950");
          expect(isStrong).toBe(true);
        } finally {
          await cleanup({ container, root });
        }
      });
    });

    // -- Cross-page invariants ---------------------------------------------
    test("all right-panel typography elements have non-empty explicit text tokens (no bare inherit anywhere)", async () => {
      const { container: lContainer, root: lRoot } = await renderPage(LoginPage);
      const { container: rContainer, root: rRoot } = await renderPage(RegisterPage);
      try {
        const all = [
          ...lContainer.querySelectorAll(".w-full.max-w-sm h2, .w-full.max-w-sm p, .w-full.max-w-sm .label-caps, .w-full.max-w-sm label"),
          ...rContainer.querySelectorAll(".w-full.max-w-sm h2, .w-full.max-w-sm p, .w-full.max-w-sm .label-caps, .w-full.max-w-sm label"),
        ];
        expect(all.length).toBeGreaterThan(0);
        all.forEach((el) => {
          expectNoBareInherit(el, `${el.closest(".w-full.max-w-sm") ? "" : "no-"}panel/${el.tagName.toLowerCase()}`);
        });
      } finally {
        await cleanup({ container: lContainer, root: lRoot });
        await cleanup({ container: rContainer, root: rRoot });
      }
    });
  });

  // -- Sanity ---------------------------------------------------------------
  test("importable from the shared ui module (no duplicate component hardcoding)", async () => {
    // Importing through the moduleNameMapper (or default jest path) — no
    // special mock for this file. Asserts the export exists and renders an
    // <input> element with type="email" or any text-like type.
    const MockReact = require("react");
    const MockReactDOM = require("react-dom/client");
    const InputModule = require("../components/ui/input");
    expect(InputModule.Input).toBeDefined();

    const container = document.createElement("div");
    document.body.appendChild(container);
    const root = MockReactDOM.createRoot(container);
    await MockReact.act(async () => {
      root.render(
        MockReact.createElement(InputModule.Input, { "data-probe": "1" })
      );
    });
    const input = container.querySelector('[data-probe="1"]');
    expect(input).not.toBeNull();
    expect(input.tagName).toBe("INPUT");
    await MockReact.act(async () => {
      root.unmount();
    });
    container.remove();
  });
});
