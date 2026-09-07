// Integration & Contract test: ISG Module Navigation Architecture (Phase 1)
//
// Verifies:
//   1. All 6 top-level modules (Risk Analizi, Çalışan Paneli, Çalışan Eğitimi,
//      Çalışan Sağlık Gözetim, Acil Durum, Periyodik Kontroller)
//      expose their correct subpages and route paths.
//   2. Mobile drawer renders the modules and all child routes hierarchically.
//   3. Active module and child item detection works accurately for nested child routes.
//   4. Desktop and mobile testIds are uniquely preserved.
//   5. Desktop navigation renders SIX independent top-level module dropdowns —
//      NOT a single consolidated "Modüller" dropdown containing every module.

import React from "react";
import { createRoot } from "react-dom/client";
import { MODULE_NAV_CONFIG, MobileNavList, ModuleDropdownTrigger } from "./AppShell";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
const { act } = require("react");

jest.mock("react-router-dom", () => {
  const MockReact = require("react");
  const Link = ({ to, children, onClick, ...rest }) =>
    MockReact.createElement("a", { href: to, onClick, ...rest }, children);
  return {
    __esModule: true,
    Link,
  };
});

// ModuleMenuGroups wraps each child in a Radix DropdownMenuItem which expects
// the dropdown roving-focus context; stub it for isolated rendering.
// The local ui/dropdown-menu wrapper references SubTrigger / Content / Item
// etc. on the radix namespace — provide a Proxy stub so any property access
// resolves to a harmless renderable component.
jest.mock("@radix-ui/react-dropdown-menu", () => {
  const MockReact = require("react");
  const Stub = ({ children }) =>
    MockReact.createElement(MockReact.Fragment, null, children);
  Stub.displayName = "RadixStub";
  return {
    __esModule: true,
    Root: Stub,
    Trigger: Stub,
    Group: Stub,
    Portal: Stub,
    Sub: Stub,
    SubTrigger: Stub,
    SubContent: Stub,
    Content: Stub,
    Item: Stub,
    CheckboxItem: Stub,
    RadioItem: Stub,
    RadioGroup: Stub,
    Label: Stub,
    Separator: Stub,
    ItemIndicator: Stub,
  };
});

function flush() {
  return new Promise((resolve) => setTimeout(resolve, 0));
}

function byTestId(container, testId) {
  return container.querySelector(`[data-testid="${testId}"]`);
}

describe("ISG Module Navigation Architecture — Phase 1", () => {
  test("MODULE_NAV_CONFIG defines all 6 top-level modules", () => {
    const moduleIds = MODULE_NAV_CONFIG.map((m) => m.id);
    expect(moduleIds).toEqual([
      "risk-analizi",
      "employees",
      "employee-training",
      "employee-health",
      "emergency-plan",
      "periodic-controls",
    ]);
  });

  test("Çalışan Paneli module has all 2 expected child pages with correct routes", () => {
    const employees = MODULE_NAV_CONFIG.find((m) => m.id === "employees");
    expect(employees).toBeDefined();
    expect(employees.label).toBe("Çalışan Paneli");
    expect(employees.items).toHaveLength(2);

    expect(employees.items[0].label).toBe("Personel Listesi Paneli");
    expect(employees.items[0].href).toBe("/employees/list");
    expect(employees.items[0].isItemActive("/employees")).toBe(true);
    expect(employees.items[0].isItemActive("/employees/list")).toBe(true);

    expect(employees.items[1].label).toBe("Görev Tanımları Paneli");
    expect(employees.items[1].href).toBe("/employees/job-descriptions");

    expect(employees.isModuleActive("/employees/list")).toBe(true);
    expect(employees.isModuleActive("/employees/job-descriptions")).toBe(true);
    expect(employees.isModuleActive("/dashboard")).toBe(false);
  });

  test("Acil Durum module has all 4 expected child pages with correct routes", () => {
    const emergency = MODULE_NAV_CONFIG.find((m) => m.id === "emergency-plan");
    expect(emergency).toBeDefined();
    expect(emergency.label).toBe("Acil Durum Paneli");
    expect(emergency.items).toHaveLength(4);

    const expected = [
      { label: "Acil Durum Planı Paneli", href: "/emergency-plan/plan", testId: "nav-emergency-plan-plan" },
      { label: "Ekipler Paneli", href: "/emergency-plan/teams", testId: "nav-emergency-plan-teams" },
      { label: "Kroki Paneli", href: "/emergency-plan/layout", testId: "nav-emergency-plan-layout" },
      { label: "Tatbikat Paneli", href: "/emergency-plan/drills", testId: "nav-emergency-plan-drills" },
    ];

    expected.forEach((exp, idx) => {
      expect(emergency.items[idx].label).toBe(exp.label);
      expect(emergency.items[idx].href).toBe(exp.href);
      expect(emergency.items[idx].testId).toBe(exp.testId);
    });
  });

  test("Çalışan Eğitimi module has all 10 expected child pages with correct routes", () => {
    const training = MODULE_NAV_CONFIG.find((m) => m.id === "employee-training");
    expect(training).toBeDefined();
    expect(training.label).toBe("Çalışan Eğitimi Paneli");
    expect(training.items).toHaveLength(10);

    const expectedLabels = [
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
    ];

    const expectedHrefs = [
      "/employee-training/basic",
      "/employee-training/orientation",
      "/employee-training/hygiene",
      "/employee-training/additional",
      "/employee-training/toolbox",
      "/employee-training/emergency",
      "/employee-training/emergency-team",
      "/employee-training/risk-team",
      "/employee-training/first-aid",
      "/employee-training/entry",
    ];

    expectedLabels.forEach((label, idx) => {
      expect(training.items[idx].label).toBe(label);
      expect(training.items[idx].href).toBe(expectedHrefs[idx]);
    });
  });

  test("Çalışan Sağlık Gözetim module has all 2 expected child pages with correct routes", () => {
    const health = MODULE_NAV_CONFIG.find((m) => m.id === "employee-health");
    expect(health).toBeDefined();
    expect(health.label).toBe("Çalışan Sağlık Gözetim Paneli");
    expect(health.items).toHaveLength(2);

    expect(health.items[0].label).toBe("İşe Giriş Sağlık Raporları Paneli");
    expect(health.items[0].href).toBe("/employee-health/entry-reports");
    expect(health.items[0].isItemActive("/employee-health")).toBe(true);
    expect(health.items[0].isItemActive("/employee-health/entry-reports")).toBe(true);

    expect(health.items[1].label).toBe("Periyodik Sağlık Raporları Paneli");
    expect(health.items[1].href).toBe("/employee-health/periodic-reports");

    expect(health.isModuleActive("/employee-health/entry-reports")).toBe(true);
    expect(health.isModuleActive("/employee-health/periodic-reports")).toBe(true);
    expect(health.isModuleActive("/employees/list")).toBe(false);
  });

  test("Periyodik Kontroller module has all 2 expected child pages with correct routes", () => {
    const periodic = MODULE_NAV_CONFIG.find((m) => m.id === "periodic-controls");
    expect(periodic).toBeDefined();
    expect(periodic.label).toBe("Periyodik Kontroller Paneli");
    expect(periodic.items).toHaveLength(2);

    expect(periodic.items[0].label).toBe("Periyodik Muayene Paneli");
    expect(periodic.items[0].href).toBe("/periodic-controls/inspection");

    expect(periodic.items[1].label).toBe("Periyodik Bakım Paneli");
    expect(periodic.items[1].href).toBe("/periodic-controls/maintenance");
  });

  test("Active module detection correctly identifies nested subpaths", () => {
    const emergency = MODULE_NAV_CONFIG.find((m) => m.id === "emergency-plan");
    const training = MODULE_NAV_CONFIG.find((m) => m.id === "employee-training");
    const periodic = MODULE_NAV_CONFIG.find((m) => m.id === "periodic-controls");
    const risk = MODULE_NAV_CONFIG.find((m) => m.id === "risk-analizi");
    const employees = MODULE_NAV_CONFIG.find((m) => m.id === "employees");
    const health = MODULE_NAV_CONFIG.find((m) => m.id === "employee-health");

    // Emergency paths
    expect(emergency.isModuleActive("/emergency-plan")).toBe(true);
    expect(emergency.isModuleActive("/emergency-plan/teams")).toBe(true);
    expect(emergency.isModuleActive("/dashboard")).toBe(false);

    // Training paths
    expect(training.isModuleActive("/employee-training")).toBe(true);
    expect(training.isModuleActive("/employee-training/first-aid")).toBe(true);
    expect(training.isModuleActive("/employee-training/entry")).toBe(true);
    expect(training.isModuleActive("/emergency-plan/drills")).toBe(false);

    // Periodic paths
    expect(periodic.isModuleActive("/periodic-controls")).toBe(true);
    expect(periodic.isModuleActive("/periodic-controls/maintenance")).toBe(true);
    expect(periodic.isModuleActive("/employee-training/basic")).toBe(false);

    // Risk Analizi paths
    expect(risk.isModuleActive("/dashboard")).toBe(true);
    expect(risk.isModuleActive("/dof")).toBe(true);
    expect(risk.isModuleActive("/uat")).toBe(true);
    expect(risk.isModuleActive("/audits/123")).toBe(true);
    expect(risk.isModuleActive("/periodic-controls/inspection")).toBe(false);

    // Employees paths
    expect(employees.isModuleActive("/employees")).toBe(true);
    expect(employees.isModuleActive("/employees/list")).toBe(true);
    expect(employees.isModuleActive("/employees/job-descriptions")).toBe(true);
    expect(employees.isModuleActive("/employee-health/entry-reports")).toBe(false);

    // Health paths
    expect(health.isModuleActive("/employee-health")).toBe(true);
    expect(health.isModuleActive("/employee-health/entry-reports")).toBe(true);
    expect(health.isModuleActive("/employee-health/periodic-reports")).toBe(true);
    expect(health.isModuleActive("/employee-training/basic")).toBe(false);
  });

  test("MobileNavList renders all 6 modules and all 23 child links", async () => {
    const container = document.createElement("div");
    document.body.appendChild(container);
    const root = createRoot(container);

    await act(async () => {
      root.render(
        React.createElement(MobileNavList, {
          modules: MODULE_NAV_CONFIG,
          currentPath: "/emergency-plan/teams",
          onNavigate: () => {},
        })
      );
      await flush();
    });

    // Check all subpage links are present
    const totalChildItems = MODULE_NAV_CONFIG.reduce(
      (acc, mod) => acc + mod.items.length,
      0
    );
    expect(totalChildItems).toBe(23);

    MODULE_NAV_CONFIG.forEach((mod) => {
      mod.items.forEach((item) => {
        const el = byTestId(container, item.mobileTestId);
        expect(el).toBeTruthy();
        expect(el.getAttribute("href")).toBe(item.href);
      });
    });

    // Check active item in MobileNavList
    const activeItemEl = byTestId(container, "mobile-nav-emergency-plan-teams");
    expect(activeItemEl.className).toMatch(/bg-risk-moderate-bg/);

    await act(async () => {
      root.unmount();
    });
    container.remove();
  });

  test("ModuleDropdownTrigger renders a single module's independent dropdown with only its own children", async () => {
    const employees = MODULE_NAV_CONFIG.find((m) => m.id === "employees");
    const container = document.createElement("div");
    document.body.appendChild(container);
    const root = createRoot(container);

    await act(async () => {
      root.render(
        React.createElement(ModuleDropdownTrigger, {
          module: employees,
          currentPath: "/employees/list",
        })
      );
      await flush();
    });

    // The trigger exists with the module's stable testId.
    const trigger = byTestId(container, "nav-employees-trigger");
    expect(trigger).toBeTruthy();
    expect(trigger.textContent).toMatch(/Çalışan Paneli/);

    // Children of THIS module appear with their desktop testIds.
    expect(byTestId(container, "nav-employees-list")).toBeTruthy();
    expect(byTestId(container, "nav-employees-job-descriptions")).toBeTruthy();

    // The active child renders with the module's accent + bold styling.
    const activeChild = byTestId(container, "nav-employees-list");
    expect(activeChild.className).toMatch(/font-bold/);
    expect(activeChild.className).toMatch(/bg-violet-500\/10/);

    await act(async () => {
      root.unmount();
    });
    container.remove();
  });

  test("Each of the 6 modules exposes an INDEPENDENT desktop dropdown — no global 'Modüller' consolidation", async () => {
    // Regression: the prior regression consolidated every module under a
    // single "Modüller" trigger. This test renders the six modules as
    // separate triggers and asserts:
    //   * No global `nav-modules-trigger` testId exists.
    //   * Each module gets its own trigger testId.
    //   * Each module exposes ONLY its own children (no foreign testIds).
    const container = document.createElement("div");
    document.body.appendChild(container);
    const root = createRoot(container);

    await act(async () => {
      root.render(
        React.createElement(
          React.Fragment,
          null,
          MODULE_NAV_CONFIG.map((mod) =>
            React.createElement(ModuleDropdownTrigger, {
              key: mod.id,
              module: mod,
              currentPath: "/employees/list",
            })
          )
        )
      );
      await flush();
    });

    // No consolidated global trigger anywhere in the document.
    expect(document.querySelector('[data-testid="nav-modules-trigger"]')).toBeNull();

    // Each module has its own dedicated trigger.
    const expectedTriggers = [
      "nav-risk-analizi-trigger",
      "nav-employees-trigger",
      "nav-employee-training-trigger",
      "nav-employee-health-trigger",
      "nav-emergency-plan-trigger",
      "nav-periodic-controls-trigger",
    ];
    expectedTriggers.forEach((testId) => {
      expect(document.querySelector(`[data-testid="${testId}"]`)).toBeTruthy();
    });

    // Each module exposes its own children with stable desktop testIds.
    // Use the *module* parameter as the single source of truth to verify
    // every child appears at least once in the rendered DOM.
    MODULE_NAV_CONFIG.forEach((mod) => {
      mod.items.forEach((item) => {
        const el = document.querySelector(`[data-testid="${item.testId}"]`);
        expect(el).toBeTruthy();
        expect(el.getAttribute("href")).toBe(item.href);
      });
    });

    await act(async () => {
      root.unmount();
    });
    container.remove();
  });

  test("ModuleDropdownTrigger renders ONLY its own module's children (no foreign leakage)", async () => {
    // Render ONLY the Çalışan Paneli module and assert that its DOM
    // contains exactly the two employee children and NO foreign child
    // (e.g. health or training). Radix renders dropdown content via
    // Portal into document.body, so the test inspects the whole DOM.
    const employees = MODULE_NAV_CONFIG.find((m) => m.id === "employees");
    const container = document.createElement("div");
    document.body.appendChild(container);
    const root = createRoot(container);

    await act(async () => {
      root.render(
        React.createElement(ModuleDropdownTrigger, {
          module: employees,
          currentPath: "/employees/list",
        })
      );
      await flush();
    });

    // Çalışan Paneli children present.
    expect(document.querySelector('[data-testid="nav-employees-list"]')).toBeTruthy();
    expect(document.querySelector('[data-testid="nav-employees-job-descriptions"]')).toBeTruthy();

    // No foreign child should leak in: any other module's child testId
    // must be absent from the rendered DOM.
    const foreignTestIds = [
      "nav-risk-analizi-trigger",
      "nav-dashboard",
      "nav-dof",
      "nav-uat",
      "nav-employee-training-trigger",
      "nav-employee-training-basic",
      "nav-employee-health-trigger",
      "nav-employee-health-entry-reports",
      "nav-employee-health-periodic-reports",
      "nav-emergency-plan-trigger",
      "nav-emergency-plan-plan",
      "nav-periodic-controls-trigger",
      "nav-periodic-controls-inspection",
    ];
    foreignTestIds.forEach((foreignId) => {
      expect(document.querySelector(`[data-testid="${foreignId}"]`)).toBeNull();
    });

    await act(async () => {
      root.unmount();
    });
    container.remove();
  });

  test("ModuleDropdownTrigger for Çalışan Sağlık Gözetim renders ONLY its own 2 children", async () => {
    const health = MODULE_NAV_CONFIG.find((m) => m.id === "employee-health");
    const container = document.createElement("div");
    document.body.appendChild(container);
    const root = createRoot(container);

    await act(async () => {
      root.render(
        React.createElement(ModuleDropdownTrigger, {
          module: health,
          currentPath: "/employee-health/periodic-reports",
        })
      );
      await flush();
    });

    // Health children present.
    expect(document.querySelector('[data-testid="nav-employee-health-entry-reports"]')).toBeTruthy();
    expect(document.querySelector('[data-testid="nav-employee-health-periodic-reports"]')).toBeTruthy();

    // No employee/training/etc children.
    const foreignTestIds = [
      "nav-employees-list",
      "nav-employees-job-descriptions",
      "nav-employee-training-basic",
      "nav-employee-training-entry",
      "nav-dashboard",
      "nav-emergency-plan-plan",
      "nav-periodic-controls-inspection",
    ];
    foreignTestIds.forEach((foreignId) => {
      expect(document.querySelector(`[data-testid="${foreignId}"]`)).toBeNull();
    });

    await act(async () => {
      root.unmount();
    });
    container.remove();
  });

  test("Çalışan Eğitimi ModuleDropdownTrigger retains all 10 children", async () => {
    const training = MODULE_NAV_CONFIG.find((m) => m.id === "employee-training");
    const container = document.createElement("div");
    document.body.appendChild(container);
    const root = createRoot(container);

    await act(async () => {
      root.render(
        React.createElement(ModuleDropdownTrigger, {
          module: training,
          currentPath: "/employee-training/first-aid",
        })
      );
      await flush();
    });

    const trainingChildren = training.items;
    expect(trainingChildren).toHaveLength(10);
    trainingChildren.forEach((item) => {
      expect(document.querySelector(`[data-testid="${item.testId}"]`)).toBeTruthy();
    });

    await act(async () => {
      root.unmount();
    });
    container.remove();
  });
});
