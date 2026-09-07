// Smoke test: EmergencyPlanPage / EmployeeTrainingPage / PeriodicControlsPage
// — render without crashing and surface the expected module identity across all subpages.
//
// These pages are placeholder / under-construction views (Faz 2).
// Per the PR2 review plan and Phase 1 navigation architecture we pin:
//   * Component renders without crashing for all child subpages.
//   * The module's heading / hero text is present.
//   * The subpage title and notice banner render accurately.

import React from "react";
import { createRoot } from "react-dom/client";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
const { act } = require("react");

// Heavy deps stubbed to keep the smoke test cheap.
jest.mock("../components/AppShell", () => {
  const Stub = ({ children }) => children;
  return { __esModule: true, default: Stub };
});
const mockUseBrand = jest.fn();
jest.mock("../context/BrandContext", () => ({
  __esModule: true,
  useBrand: () => mockUseBrand(),
  BRANDS_LIST: [],
}));
jest.mock("../components/BrandLogos", () => ({
  __esModule: true,
  getBrandLogo: () => null,
}));
jest.mock("framer-motion", () => {
  const Stub = ({ children }) => children;
  const motion = { div: Stub, span: Stub, button: Stub };
  return { motion, AnimatePresence: Stub, MotionConfig: Stub };
});
jest.mock("lucide-react", () => {
  const Icon = () => null;
  return new Proxy({}, { get: () => Icon });
});

function flush() {
  return new Promise((resolve) => setTimeout(resolve, 0));
}

async function renderPage(PageComponent, props = {}) {
  mockUseBrand.mockReturnValue({ selectedBrand: "Burger King" });
  const container = document.createElement("div");
  document.body.appendChild(container);
  const root = createRoot(container);
  let error = null;
  await act(async () => {
    try {
      root.render(React.createElement(PageComponent, props));
      await flush();
    } catch (e) {
      error = e;
    }
  });
  return {
    container,
    root,
    error,
    unmount: async () => {
      await act(async () => {
        root.unmount();
      });
      container.remove();
    },
  };
}

function text(container) {
  return (container.textContent || "").trim();
}

describe("Faz 2 module pages — smoke & subpage coverage", () => {
  test("EmergencyPlanPage renders all 4 child subpages without crashing", async () => {
    const Page = require("./EmergencyPlanPage").default;
    const subpages = [
      ["plan", "Acil Durum Planı"],
      ["teams", "Ekipler"],
      ["layout", "Kroki"],
      ["drills", "Tatbikat"],
    ];

    for (const [subpage, expectedTitle] of subpages) {
      const h = await renderPage(Page, { subpage });
      expect(h.error).toBeNull();
      expect(text(h.container)).toMatch(/Acil Durum Eylem Planı/);
      expect(text(h.container)).toMatch(new RegExp(expectedTitle));
      expect(text(h.container)).toMatch(/Geliştirme Aşamasında/);
      await h.unmount();
    }
  });

  test("EmployeeTrainingPage renders all 10 child subpages without crashing", async () => {
    const Page = require("./EmployeeTrainingPage").default;
    const subpages = [
      ["basic", "İSG Temel Eğitimi"],
      ["orientation", "İSG Oryantasyon Eğitimi"],
      ["hygiene", "Hijyen Eğitimi"],
      ["additional", "İlave Eğitim"],
      ["toolbox", "Toolbox Eğitimi"],
      ["emergency", "Acil Durum Eğitimi"],
      ["emergency-team", "Acil Durum Ekip Eğitimi"],
      ["risk-team", "Risk Analizi Ekip Eğitimi"],
      ["first-aid", "İlkyardım Eğitimi"],
      ["entry", "İşe Giriş Eğitim"],
    ];

    for (const [subpage, expectedTitle] of subpages) {
      const h = await renderPage(Page, { subpage });
      expect(h.error).toBeNull();
      expect(text(h.container)).toMatch(/Çalışan Eğitimi/);
      expect(text(h.container)).toMatch(new RegExp(expectedTitle));
      expect(text(h.container)).toMatch(/Geliştirme Aşamasında/);
      await h.unmount();
    }
  });

  test("EmployeePanelPage renders both child subpages without crashing", async () => {
    const Page = require("./EmployeePanelPage").default;
    const subpages = [
      ["list", "Personel Listesi"],
      ["job-descriptions", "Görev Tanımları"],
    ];

    for (const [subpage, expectedTitle] of subpages) {
      const h = await renderPage(Page, { subpage });
      expect(h.error).toBeNull();
      expect(text(h.container)).toMatch(/Çalışan Paneli/);
      expect(text(h.container)).toMatch(new RegExp(expectedTitle));
      expect(text(h.container)).toMatch(/Geliştirme Aşamasında/);
      await h.unmount();
    }
  });

  test("EmployeeHealthPage renders both child subpages without crashing", async () => {
    const Page = require("./EmployeeHealthPage").default;
    const subpages = [
      ["entry-reports", "İşe Giriş Sağlık Raporları"],
      ["periodic-reports", "Periyodik Sağlık Raporları"],
    ];

    for (const [subpage, expectedTitle] of subpages) {
      const h = await renderPage(Page, { subpage });
      expect(h.error).toBeNull();
      expect(text(h.container)).toMatch(/Çalışan Sağlık Gözetim/);
      expect(text(h.container)).toMatch(new RegExp(expectedTitle));
      expect(text(h.container)).toMatch(/Geliştirme Aşamasında/);
      await h.unmount();
    }
  });

  test("PeriodicControlsPage renders both child subpages without crashing", async () => {
    const Page = require("./PeriodicControlsPage").default;
    const subpages = [
      ["inspection", "Periyodik Muayene"],
      ["maintenance", "Periyodik Bakım"],
    ];

    for (const [subpage, expectedTitle] of subpages) {
      const h = await renderPage(Page, { subpage });
      expect(h.error).toBeNull();
      expect(text(h.container)).toMatch(/Periyodik Kontroller/);
      expect(text(h.container)).toMatch(new RegExp(expectedTitle));
      expect(text(h.container)).toMatch(/Geliştirme Aşamasında/);
      await h.unmount();
    }
  });
});
