// Regression test: AppShell — mobile navigation parity with desktop.
//
// Bug context (PR2 review):
//   The new top-level Faz 2 modules (Acil Durum Eylem Planı / Çalışan
//   Eğitimi / Periyodik Kontroller) and the "Marka Seç" action were
//   rendered only in the desktop nav. The mobile SheetContent mirror'd
//   only the legacy ``navItems`` (Ana Panel / DÖF / UAT). Users on
//   phones could not reach any of the new modules or switch brand from
//   the drawer.
//
// Fix: AppShell now exports ``MobileNavList`` and ``MobileBrandSwitch``,
// both fed from the same ``moduleNavItems`` metadata array that drives
// the desktop top-level nav. The same module list is therefore present
// on every device tier.
//
// Tests pin observable contracts:
//   1. MobileNavList renders Dashboard / DÖF / UAT (legacy parity).
//   2. MobileNavList renders all three Faz 2 modules with stable
//      data-testids and matching hrefs.
//   3. MobileBrandSwitch renders a "Marka Seç" / "Marka: <name>" CTA
//      that surfaces the currently selected brand when one is set.
//
// Test runner: craco test (Jest + jsdom from react-scripts). No RTL.

import React from "react";
import { createRoot } from "react-dom/client";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
const { act } = require("react");

// ---------------------------------------------------------------------------
// Stubs
// ---------------------------------------------------------------------------
jest.mock("react-router-dom", () => {
  const MockReact = require("react");
  const Link = ({ to, children, onClick, ...rest }) =>
    MockReact.createElement("a", { href: to, onClick, ...rest }, children);
  return {
    __esModule: true,
    Link,
  };
});

// AppShell pulls getBrandLogo (lucide-using SVG/img composition).
// getBrandLogo is a thin resolver; the only behavior we exercise here
// is that the label is "Marka: X" when a brand is set. A null return
// from getBrandLogo (no matching logo) is acceptable for these tests
// — the brand-name text is what the parity assertion reads.

function flush() {
  return new Promise((resolve) => setTimeout(resolve, 0));
}

// Subject (must come AFTER jest.mock calls; jest hoists jest.mock anyway).
import { MobileNavList, MobileBrandSwitch } from "./AppShell";

// ---------------------------------------------------------------------------
// Test metadata — mirrors the AppShell "moduleNavItems" / "navItems"
// shapes. We construct icon/label stubs inline so we don't have to
// import the lucide-react component classes.
// ---------------------------------------------------------------------------
function makeNavItems(pathname = "/dashboard") {
  return [
    {
      href: "/dashboard",
      mobileTestId: "mobile-nav-dashboard",
      label: "Risk Analizi Denetim Paneli",
      icon: () => null,
      iconColor: "text-emerald-500",
      isActive: pathname === "/dashboard" || pathname === "/",
    },
    {
      href: "/dof",
      mobileTestId: "mobile-nav-dof",
      label: "DÖF Takip Paneli",
      icon: () => null,
      iconColor: "text-amber-500",
      isActive: pathname === "/dof",
    },
    {
      href: "/uat",
      mobileTestId: "mobile-nav-uat",
      label: "İş Yeri Beyan Formu Paneli",
      icon: () => null,
      iconColor: "text-sky-500",
      isActive: pathname === "/uat",
    },
  ];
}

function makeModuleNavItems() {
  return [
    {
      href: "/emergency-plan",
      mobileTestId: "mobile-nav-emergency-plan",
      label: "Acil Durum Paneli",
      icon: () => null,
      iconColor: "text-amber-500",
      activeClass: "bg-amber-class",
      idleClass: "bg-amber-idle",
      isActive: false,
    },
    {
      href: "/employee-training",
      mobileTestId: "mobile-nav-employee-training",
      label: "Çalışan Eğitimi Paneli",
      icon: () => null,
      iconColor: "text-blue-500",
      activeClass: "bg-blue-class",
      idleClass: "bg-blue-idle",
      isActive: false,
    },
    {
      href: "/periodic-controls",
      mobileTestId: "mobile-nav-periodic-controls",
      label: "Periyodik Kontroller Paneli",
      icon: () => null,
      iconColor: "text-emerald-500",
      activeClass: "bg-emerald-class",
      idleClass: "bg-emerald-idle",
      isActive: false,
    },
  ];
}

const RightStub = () => null;

async function renderMobileNav(pathname = "/dashboard", overrides = {}) {
  const container = document.createElement("div");
  document.body.appendChild(container);
  const root = createRoot(container);
  await act(async () => {
    root.render(
      React.createElement(
        "div",
        null,
        React.createElement(MobileNavList, {
          navItems: makeNavItems(pathname),
          moduleNavItems: overrides.moduleNavItems || makeModuleNavItems(),
          onNavigate: overrides.onNavigate || (() => {}),
          rightIcon: RightStub,
        }),
        React.createElement(MobileBrandSwitch, {
          selectedBrand: overrides.selectedBrand || "",
          onSelect: overrides.onSelectBrand || (() => {}),
        })
      )
    );
    await flush();
  });
  return { container, root };
}

function byTestId(container, testId) {
  return container.querySelector(`[data-testid="${testId}"]`);
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------
describe("AppShell — mobile nav parity with desktop", () => {
  test("mobile nav exposes the three Faz 2 modules as links", async () => {
    const { container, root } = await renderMobileNav();

    expect(byTestId(container, "mobile-nav-emergency-plan")).toBeTruthy();
    expect(byTestId(container, "mobile-nav-employee-training")).toBeTruthy();
    expect(byTestId(container, "mobile-nav-periodic-controls")).toBeTruthy();

    expect(byTestId(container, "mobile-nav-emergency-plan").textContent).toMatch(
      /Acil Durum Paneli/
    );
    expect(byTestId(container, "mobile-nav-employee-training").textContent).toMatch(
      /Çalışan Eğitimi Paneli/
    );
    expect(byTestId(container, "mobile-nav-periodic-controls").textContent).toMatch(
      /Periyodik Kontroller Paneli/
    );

    // Existing Dashboard / DÖF / UAT must not be dropped.
    expect(byTestId(container, "mobile-nav-dashboard")).toBeTruthy();
    expect(byTestId(container, "mobile-nav-dof")).toBeTruthy();
    expect(byTestId(container, "mobile-nav-uat")).toBeTruthy();

    await act(async () => {
      root.unmount();
    });
    container.remove();
  });

  test("each Faz 2 module link points to its canonical route (parity with desktop)", async () => {
    const { container, root } = await renderMobileNav();
    const expected = [
      ["mobile-nav-emergency-plan", "/emergency-plan"],
      ["mobile-nav-employee-training", "/employee-training"],
      ["mobile-nav-periodic-controls", "/periodic-controls"],
    ];
    for (const [tid, href] of expected) {
      const el = byTestId(container, tid);
      expect(el).toBeTruthy();
      expect(el.getAttribute("href")).toBe(href);
    }
    await act(async () => {
      root.unmount();
    });
    container.remove();
  });

  test("mobile brand switch renders as a button with 'Marka Seç' when no brand set", async () => {
    const { container, root } = await renderMobileNav("/dashboard", {
      selectedBrand: "",
    });
    const brandSwitch = byTestId(container, "mobile-nav-brand-selection");
    expect(brandSwitch).toBeTruthy();
    expect(brandSwitch.tagName.toLowerCase()).toBe("button");
    expect(brandSwitch.textContent).toMatch(/Marka Seç/);
    await act(async () => {
      root.unmount();
    });
    container.remove();
  });

  test("mobile brand switch surfaces the currently selected brand name", async () => {
    const { container, root } = await renderMobileNav("/dashboard", {
      selectedBrand: "Burger King",
    });
    const brandSwitch = byTestId(container, "mobile-nav-brand-selection");
    expect(brandSwitch.textContent).toMatch(/Burger King/);
    await act(async () => {
      root.unmount();
    });
    container.remove();
  });

  test("mobile brand switch hides the 'Tüm Markalar' pseudo-brand", async () => {
    const { container, root } = await renderMobileNav("/dashboard", {
      selectedBrand: "Tüm Markalar",
    });
    const brandSwitch = byTestId(container, "mobile-nav-brand-selection");
    // 'Tüm Markalar' should NOT bubble up as a chosen brand — the user
    // falls back to the generic 'Marka Seç' affordance.
    expect(brandSwitch.textContent).toMatch(/Marka Seç/);
    expect(brandSwitch.textContent).not.toMatch(/Tüm Markalar/);
    await act(async () => {
      root.unmount();
    });
    container.remove();
  });

  test("mobile brand switch fires onSelect handler when clicked", async () => {
    const onSelectBrand = jest.fn();
    const { container, root } = await renderMobileNav("/dashboard", {
      selectedBrand: "Subway",
      onSelectBrand,
    });
    const brandSwitch = byTestId(container, "mobile-nav-brand-selection");
    await act(async () => {
      brandSwitch.click();
      await flush();
    });
    expect(onSelectBrand).toHaveBeenCalledTimes(1);
    await act(async () => {
      root.unmount();
    });
    container.remove();
  });

  test("clicking a Faz 2 link fires onNavigate (closes the drawer)", async () => {
    const onNavigate = jest.fn();
    const { container, root } = await renderMobileNav("/dashboard", {
      onNavigate,
    });
    const emergencyLink = byTestId(container, "mobile-nav-emergency-plan");
    await act(async () => {
      emergencyLink.click();
      await flush();
    });
    expect(onNavigate).toHaveBeenCalledTimes(1);
    await act(async () => {
      root.unmount();
    });
    container.remove();
  });

  test("active flag propagates: active Faz 2 module gets the active class", async () => {
    const moduleItems = makeModuleNavItems();
    moduleItems[0].isActive = true; // emergency-plan active
    const { container, root } = await renderMobileNav("/emergency-plan", {
      moduleNavItems: moduleItems,
    });
    const active = byTestId(container, "mobile-nav-emergency-plan");
    expect(active.className).toContain("bg-amber-class");
    const inactive = byTestId(container, "mobile-nav-employee-training");
    expect(inactive.className).not.toContain("bg-blue-class");
    await act(async () => {
      root.unmount();
    });
    container.remove();
  });
});
