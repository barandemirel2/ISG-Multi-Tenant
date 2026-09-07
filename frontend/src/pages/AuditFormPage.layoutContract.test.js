/**
 * Regression test: AuditFormPage Question List Layout Contract (PR #28 / Phase 2B).
 *
 * Problem description:
 * When EVET <-> HAYIR toggling was performed, Framer Motion's `layout` prop on the parent
 * question-list container (`<motion.div layout ...>`) calculated layout bounding box
 * projections and applied inline transforms (`translate3d(0, -385px, 0)`), causing the
 * question card and siblings to visibly slide/jump vertically during expansion.
 *
 * Remediation:
 * The parent container in AuditFormPage must NOT have the `layout` prop.
 *
 * Test limitation note:
 * True browser layout geometry and Framer Motion layout projection transforms cannot be
 * calculated in Jest/jsdom because jsdom lacks a layout engine (all getBoundingClientRect
 * return 0). Full geometric verification is performed via CDP automated browser tests.
 * This unit test provides structural contract protection against accidental regression
 * of the `layout` prop on the question list container.
 */

import fs from "fs";
import path from "path";

describe("AuditFormPage Question List Layout Contract", () => {
  const auditFormPagePath = path.resolve(__dirname, "AuditFormPage.jsx");
  const source = fs.readFileSync(auditFormPagePath, "utf-8");

  test("question list parent container does NOT declare Framer Motion `layout` prop", () => {
    const listContainerMatch = source.match(/<motion\.div([^>]*?)divide-y/);
    expect(listContainerMatch).not.toBeNull();

    const attributes = listContainerMatch[1];
    expect(attributes).not.toMatch(/\blayout\b/);
  });

  test("each QuestionRow retains internal AnimatePresence for HAYIR expansion", () => {
    expect(source).toContain("<AnimatePresence initial={false}>");
    expect(source).toContain("isHayir &&");
  });
});
