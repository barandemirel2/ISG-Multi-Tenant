// Regression test: NewAuditPage submit payload (extended metadata fields).
//
// Bug context (PR0 review): NewAuditPage collects ``restaurant_manager``,
// ``auditor_title``, ``branch_code`` ve ``audit_notes`` fields ve bunları
// ``api.post("/audits", form)`` ile gönderiyordu. Bu regression test, frontend
// payload contract'ının backend'in beklediği 4 alanı içerdiğini doğrular.
//
// Helper unit testi DEĞİLDİR; production wiring'i (NewAuditPage render +
// form submit + api.post payload) birebir simüle eder. Mevcut react-scripts
// jest (jsdom) altyapısı + react-dom/client kullanıldı; @testing-library ek
// bağımlılığı test kapsamı için gerekmedi.

import React from "react";
import { createRoot } from "react-dom/client";

// React 19 expects IS_REACT_ACT_ENVIRONMENT=true (RTL normally sets this).
// Etmezse ``act(...)`` sarmalı "not configured to support act" uyarısı
// basar; testler yine de geçer ama console.error noise yaratır.
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
const { act } = require("react");

// ---------------------------------------------------------------------------
// Stubs: NewAuditPage'in kullandığı tüm heavyweight bağımlılıklar jest.mock
// ile sıfırdan inşa edildi. RTL yok; render<->DOM kontratı minimum.
// ---------------------------------------------------------------------------

jest.mock("../components/AppShell", () => ({
  __esModule: true,
  default: ({ children }) => children,
}));

const mockUseAuth = jest.fn();
jest.mock("../context/AuthContext", () => ({
  useAuth: () => mockUseAuth(),
}));

const mockPost = jest.fn();
const mockFormat = jest.fn((detail) =>
  typeof detail === "string" ? detail : "Bilinmeyen hata"
);
jest.mock("../lib/api", () => ({
  __esModule: true,
  default: { post: (...args) => mockPost(...args) },
  formatApiErrorDetail: (...args) => mockFormat(...args),
}));

jest.mock("react-router-dom", () => ({
  useNavigate: () => jest.fn(),
}));

jest.mock("sonner", () => ({
  toast: { success: jest.fn(), error: jest.fn() },
}));

jest.mock("framer-motion", () => {
  const Stub = ({ children }) => children;
  const motion = { div: Stub, span: Stub, button: Stub };
  return { motion, AnimatePresence: Stub, MotionConfig: Stub };
});

jest.mock("lucide-react", () => {
  const Icon = () => null;
  return new Proxy(
    {
      ArrowLeft: Icon,
      ClipboardCheck: Icon,
      Building2: Icon,
      UserCheck: Icon,
      Shield: Icon,
      FileText: Icon,
      MapPin: Icon,
    },
    {
      get(target, prop) {
        if (prop in target) return target[prop];
        return Icon;
      },
    }
  );
});

// Subject (must come AFTER jest.mock calls; jest hoists jest.mock anyway).
import NewAuditPage from "./NewAuditPage";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function flush() {
  return new Promise((resolve) => setTimeout(resolve, 0));
}

function setNativeValue(el, value) {
  const proto =
    el.tagName === "TEXTAREA"
      ? window.HTMLTextAreaElement.prototype
      : window.HTMLInputElement.prototype;
  const setter = Object.getOwnPropertyDescriptor(proto, "value").set;
  setter.call(el, value);
  el.dispatchEvent(new Event("input", { bubbles: true }));
}

function setFieldById(container, id, value) {
  const el = container.querySelector(`#${id}`);
  if (!el) throw new Error(`Field not found: #${id}`);
  setNativeValue(el, value);
}

function submitForm(container) {
  const form = container.querySelector('[data-testid="new-audit-form"]');
  if (!form) throw new Error("Form not found");
  form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
}

async function renderPage() {
  const container = document.createElement("div");
  document.body.appendChild(container);
  const root = createRoot(container);
  await act(async () => {
    root.render(React.createElement(NewAuditPage));
    await flush();
  });
  return { container, root };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------
describe("NewAuditPage submit payload — extended metadata regression", () => {
  beforeEach(() => {
    mockUseAuth.mockReturnValue({ user: { id: "u1", name: "Test Denetçi" } });
    mockPost.mockReset();
    mockFormat.mockReset();
  });

  test("extended metadata fields are sent in the POST /audits payload", async () => {
    mockPost.mockResolvedValue({ data: { id: "new-audit-id" } });
    mockFormat.mockImplementation((d) => (typeof d === "string" ? d : "err"));

    const { container, root } = await renderPage();

    setFieldById(container, "rn", "Kadıköy Şubesi");
    setFieldById(container, "bc", "POP-104");
    setFieldById(container, "rm", "Ahmet Yılmaz (Restoran Müdürü)");
    setFieldById(container, "at", "A Sınıfı İSG Uzmanı");
    setFieldById(
      container,
      "an",
      "Ön denetim notu — havalandırma kontrol edildi."
    );

    await act(async () => {
      submitForm(container);
      await flush();
      await flush();
    });

    expect(mockPost).toHaveBeenCalledTimes(1);
    const [url, payload] = mockPost.mock.calls[0];
    expect(url).toBe("/audits");

    // Production regression: backend'in kalıcı hale getirdiği 4 alan payload'da
    // DOĞRU değerlerle bulunmalı. Bu kontrol başarısız olursa backend bu
    // alanları düşürür (Pydantic extra="ignore" default davranışı; Fix D).
    expect(payload).toEqual(
      expect.objectContaining({
        restaurant_name: "Kadıköy Şubesi",
        restaurant_manager: "Ahmet Yılmaz (Restoran Müdürü)",
        auditor_title: "A Sınıfı İSG Uzmanı",
        branch_code: "POP-104",
        audit_notes: "Ön denetim notu — havalandırma kontrol edildi.",
        denetci: "Test Denetçi",
      })
    );

    await act(async () => {
      root.unmount();
    });
    container.remove();
  });

  test("missing extended metadata fields default to empty strings (no undefined)", async () => {
    mockPost.mockResolvedValue({ data: { id: "x" } });
    mockFormat.mockImplementation((d) => (typeof d === "string" ? d : "err"));

    const { container, root } = await renderPage();

    // Yalnızca zorunlu alan dolduruluyor; extended alanlar boş bırakılıyor.
    setFieldById(container, "rn", "Tek Şube");

    await act(async () => {
      submitForm(container);
      await flush();
      await flush();
    });

    const [, payload] = mockPost.mock.calls[0];
    expect(payload.restaurant_name).toBe("Tek Şube");
    expect(payload.restaurant_manager).toBe("");
    expect(payload.auditor_title).toBe("İSG Uzmanı"); // initial state
    expect(payload.branch_code).toBe("");
    expect(payload.audit_notes).toBe("");

    await act(async () => {
      root.unmount();
    });
    container.remove();
  });
});