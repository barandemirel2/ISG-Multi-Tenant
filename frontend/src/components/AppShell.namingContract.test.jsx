// Contract test: user-visible UI naming — fix/panel-naming & Phase 1 module navigation.
//
// Pins the literal naming contract applied by the navigation architecture so that any
// change that re-introduces legacy or incorrect strings fails the build.
//
// Scope:
//   * Global brand "AI Uzman" (was "Risk Analiz Sistemi").
//   * Dashboard heading "Risk Analizi Denetim Paneli" (was "Denetim Paneli").
//   * Module subpage navigation labels across all 4 ISG modules.
//
// Source-level invariant: each contract is asserted against the live
// source files in the repo (the same files the build bundles).

const fs = require("fs");
const path = require("path");

const SRC_DIR = path.join(__dirname, "..");

function read(relPath) {
  return fs.readFileSync(path.join(SRC_DIR, relPath), "utf8");
}

describe("UI naming contract — panel/brand labels", () => {
  const appShell = read("components/AppShell.jsx");
  const dashboardPage = read("pages/DashboardPage.jsx");
  const loginPage = read("pages/LoginPage.jsx");
  const registerPage = read("pages/RegisterPage.jsx");
  const errorBoundary = read("components/ErrorBoundary.jsx");

  // -- Global brand ----------------------------------------------------------
  test("AppShell header brand reads 'AI Uzman' (legacy 'Risk Analiz Sistemi' is gone)", () => {
    expect(appShell).not.toMatch(/Risk Analiz Sistemi/);
    expect(appShell).toMatch(/AI Uzman/);
  });

  test("LoginPage brand reads 'AI Uzman'", () => {
    expect(loginPage).not.toMatch(/Risk Analiz Sistemi/);
    expect(loginPage).toMatch(/AI Uzman/);
  });

  test("RegisterPage brand reads 'AI Uzman'", () => {
    expect(registerPage).not.toMatch(/Risk Analiz Sistemi/);
    expect(registerPage).toMatch(/AI Uzman/);
  });

  // -- Dashboard heading -----------------------------------------------------
  test("DashboardPage h1 reads 'Risk Analizi Denetim Paneli' (legacy 'Denetim Paneli' is gone)", () => {
    expect(dashboardPage).toMatch(/>Risk Analizi Denetim Paneli</);
    expect(dashboardPage).not.toMatch(/>Denetim Paneli</);
  });

  // -- Top-Level Module labels ----------------------------------------------
  describe("AppShell top-level module labels", () => {
    const expectedModuleLabels = [
      "Risk Analizi",
      "Çalışan Paneli",
      "Çalışan Eğitimi Paneli",
      "Çalışan Sağlık Gözetim Paneli",
      "Acil Durum Paneli",
      "Periyodik Kontroller Paneli",
    ];

    test.each(expectedModuleLabels)("AppShell defines top-level module label %p", (label) => {
      expect(appShell).toMatch(new RegExp(`label: "${label}"`));
    });
  });

  // -- Top-level navigation architecture (regression) -----------------------
  describe("AppShell desktop top-level navigation architecture", () => {
    test("AppShell does NOT define a global 'Modüller' dropdown trigger (regression: consolidated top-level dropdown is forbidden)", () => {
      // Regression: the previous implementation consolidated all six ISG
      // modules under a single "Modüller" trigger button using
      // `data-testid="nav-modules-trigger"`. The intended architecture
      // exposes six independent top-level module dropdowns — one per
      // MODULE_NAV_CONFIG entry. Any attempt to re-introduce a single
      // global dropdown must fail this contract.
      expect(appShell).not.toMatch(/data-testid="nav-modules-trigger"/);
      expect(appShell).not.toMatch(/nav-modules-trigger/);
    });

    test("AppShell defines a dedicated desktop module-nav row container (separate from primary header row)", () => {
      expect(appShell).toMatch(/module-nav-row/);
      expect(appShell).toMatch(/module-nav/);
    });

    test.each([
      ["nav-risk-analizi-trigger", "Risk Analizi"],
      ["nav-employees-trigger", "Çalışan Paneli"],
      ["nav-employee-training-trigger", "Çalışan Eğitimi Paneli"],
      ["nav-employee-health-trigger", "Çalışan Sağlık Gözetim Paneli"],
      ["nav-emergency-plan-trigger", "Acil Durum Paneli"],
      ["nav-periodic-controls-trigger", "Periyodik Kontroller Paneli"],
    ])("AppShell exposes independent desktop trigger %p for %p", (testId, _label) => {
      // The trigger testId is wired into MODULE_NAV_CONFIG.triggerTestId
      // and rendered via `data-testid={module.triggerTestId}`. We pin
      // BOTH the configuration literal AND the runtime usage so the
      // trigger cannot be silently dropped or renamed.
      expect(appShell).toMatch(new RegExp(`triggerTestId: "${testId}"`));
      expect(appShell).toMatch(/data-testid=\{module\.triggerTestId\}/);
    });
  });

  // -- Navigation labels — AppShell -----------------------------------------
  describe("AppShell navigation labels", () => {
    const expectedNavLabels = [
      // Risk Analizi
      "Risk Analizi Denetim Paneli",
      "DÖF Takip Paneli",
      "İş Yeri Beyan Formu Paneli",
      // Çalışan Paneli
      "Personel Listesi Paneli",
      "Görev Tanımları Paneli",
      // Acil Durum
      "Acil Durum Planı Paneli",
      "Ekipler Paneli",
      "Kroki Paneli",
      "Tatbikat Paneli",
      // Çalışan Eğitimi
      "İSG Temel Eğitimi Paneli",
      "İSG Oryantasyon Eğitimi Paneli",
      "Hijyen Eğitimi Paneli",
      "İlave Eğitim Paneli",
      "Toolbox Eğitimi Paneli",
      "Acil Durum Eğitimi Paneli",
      "Acil Durum Ekip Eğitimi Paneli",
      "Risk Analizi Ekip Eğitimi Paneli",
      "İlkyardım Eğitimi Paneli",
      "İşe Giriş Eğitim Paneli",
      // Çalışan Sağlık Gözetim
      "İşe Giriş Sağlık Raporları Paneli",
      "Periyodik Sağlık Raporları Paneli",
      // Periyodik Kontroller
      "Periyodik Muayene Paneli",
      "Periyodik Bakım Paneli",
    ];

    test.each(expectedNavLabels)("AppShell exposes nav label %p", (label) => {
      expect(appShell).toMatch(new RegExp(`label: "${label}"`));
    });

    const legacyRiskAnaliziLabels = [
      "Ana Panel",
      "DÖF Takip",
      "İş Yeri Beyan Formu",
    ];

    test.each(legacyRiskAnaliziLabels)(
      "AppShell does not contain legacy bare nav label %p",
      (label) => {
        expect(appShell).not.toMatch(
          new RegExp(`label: "${label.replace(/[.*+?^${}()|[\\]\\\\]/g, "\\$&")}"`)
        );
      }
    );
  });

  // -- ErrorBoundary home affordance ----------------------------------------
  test("ErrorBoundary home button reads 'Risk Analizi Denetim Paneli'", () => {
    expect(errorBoundary).not.toMatch(/Ana Panel/);
    expect(errorBoundary).toMatch(/Risk Analizi Denetim Paneli/);
  });
});
