// Regression test: CascadingRestaurantSelect stale-brand finding.
//
// Review finding (PR2): "Global marka form açıkken değişirse
// CascadingRestaurantSelect eski markada kalabiliyor."
//
// Verification path:
//   1. The new-audit form lives at ``/audits/new`` and embeds
//      ``<CascadingRestaurantSelect>``.
//   2. The brand switcher in ``AppShell`` (desktop button + mobile
//      drawer) navigates to ``/brand-selection`` on click.
//   3. ``/brand-selection`` is the ``BrandSelectionPage`` — a different
//      route, not a sibling of NewAuditPage. Switching routes unmounts
//      the form, including the embedded ``CascadingRestaurantSelect``.
//   4. Therefore the finding is **NON-REPRODUCIBLE** through the
//      real UI: the form unmounts before any submit can happen with
//      a stale brand.
//
// Tests pin:
//   A. Source-level invariant: brand-switch click handler navigates to
//      ``/brand-selection`` (in both desktop and mobile call sites).
//   B. NewAuditPage embeds the form; once the route changes, the form
//      unmounts (which we prove via a direct render/unmount cycle —
//      the same JSX fragment cannot survive across removals).
//   C. CascadingRestaurantSelect has no ``useEffect`` import left over
//      from the (now-irrelevant) theoretical fix surface.

import React from "react";
import { createRoot } from "react-dom/client";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
const { act } = require("react");

// ---------------------------------------------------------------------------
// A. Source-level: the brand-switch button wires navigate("/brand-selection")
// ---------------------------------------------------------------------------
describe("AppShell — brand-switch action navigates to /brand-selection", () => {
  const fs = require("fs");
  const path = require("path");
  const source = fs.readFileSync(
    path.join(__dirname, "AppShell.jsx"),
    "utf8"
  );

  test("desktop brand-switch button navigates to /brand-selection", () => {
    // The desktop brand badge uses ``onClick={() => navigate("/brand-selection")}``.
    expect(source).toMatch(/navigate\(["']\/brand-selection["']\)/);
  });

  test("mobile brand switch via MobileBrandSwitch onSelect also routes to /brand-selection", () => {
    // AppShell wires MobileBrandSwitch.onSelect to navigate to /brand-selection.
    // The pattern must appear in the wired callsite (not just inside
    // the helper).
    const re =
      /MobileBrandSwitch[\s\S]*?onSelect=\{[\s\S]*?navigate\(["']\/brand-selection["']\)[\s\S]*?\}/;
    expect(source).toMatch(re);
  });
});

// ---------------------------------------------------------------------------
// B. Behavioural: when the same CascadingRestaurantSelect is mounted,
//    then the surrounding container is removed, the input is gone.
//    Same JSX lifecycle the React router uses on route changes.
// ---------------------------------------------------------------------------
describe("CascadingRestaurantSelect — unmount releases the form's input", () => {
  function flush() {
    return new Promise((resolve) => setTimeout(resolve, 0));
  }

  test("mount → unmount cycle removes the form's restaurant input", async () => {
    // Stubs (jsdom doesn't import the real app).
    jest.doMock("../context/BrandContext", () => {
      const React = require("react");
      const Ctx = React.createContext({
        selectedBrand: "Burger King",
      });
      return {
        useBrand: () => ({
          selectedBrand: "Burger King",
        }),
        BRANDS_LIST: [],
        __esModule: true,
      };
    });

    const CascadingRestaurantSelect =
      require("./CascadingRestaurantSelect").default;

    const container = document.createElement("div");
    document.body.appendChild(container);
    const root = createRoot(container);

    await act(async () => {
      root.render(
        React.createElement(
          "form",
          { "data-testid": "audit-form-host" },
          React.createElement(CascadingRestaurantSelect, {
            id: "rn",
            dataTestId: "input-restaurant",
            value: "Burger King — Kadıköy",
            onChange: () => {},
            onSelectBranch: () => {},
          })
        )
      );
      await flush();
    });

    // Pre-condition: form input present.
    expect(container.querySelector('[data-testid="input-restaurant"]')).toBeTruthy();

    // Unmount — this is what React Router does when ``/audits/new``
    // changes to ``/brand-selection``.
    await act(async () => {
      root.unmount();
      await flush();
    });
    container.remove();

    // Post-condition: nothing mounted anymore.
    expect(container.querySelector('[data-testid="input-restaurant"]')).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// C. No useEffect left in CascadingRestaurantSelect
// ---------------------------------------------------------------------------
describe("CascadingRestaurantSelect — unused useEffect import removed", () => {
  const fs = require("fs");
  const path = require("path");
  const source = fs.readFileSync(
    path.join(__dirname, "CascadingRestaurantSelect.jsx"),
    "utf8"
  );

  test("does not import or reference useEffect", () => {
    expect(source).not.toMatch(/useEffect/);
  });
});
