import React from "react";
import { createRoot } from "react-dom/client";
import { act } from "react";
import RegulatoryInfoPanel, {
  DISCLAIMER_TEXT,
  UNVERIFIED_IPC_TEXT,
  UNVERIFIED_CRIMINAL_TEXT,
} from "./RegulatoryInfoPanel";
import regulatoryData from "@/data/question_regulatory_map.json";

const fs = require("fs");
const path = require("path");

// React 19 act() environment
globalThis.IS_REACT_ACT_ENVIRONMENT = true;

describe("RegulatoryInfoPanel — Behavioral, Theme & Integration Tests", () => {
  let container;
  let root;

  beforeEach(() => {
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
  });

  afterEach(() => {
    act(() => {
      root.unmount();
    });
    container.remove();
    container = null;
    document.body.innerHTML = "";
  });

  // --- Behavioral & Safety Tests ---

  test("renders full variant with all regulatory layers, disclaimer, and suppressed exact TL for unverified dataset (Q1)", async () => {
    await act(async () => {
      root.render(<RegulatoryInfoPanel questionId={1} variant="full" />);
    });

    const panel = container.querySelector('[data-testid="regulatory-panel-1"]');
    expect(panel).not.toBeNull();
    expect(panel.textContent).toContain("YÜKSEK RİSK");
    expect(panel.textContent).toContain("DOĞRULAMA BEKLENİYOR");
    expect(panel.textContent).toContain(DISCLAIMER_TEXT);
    expect(panel.textContent).toContain("Onaylı Defter + İSG tespitleri");
    expect(panel.textContent).toContain("MEVZUAT");
    expect(panel.textContent).toContain("6331 md. 4 (Genel yükümlülükler) + md. 24 (defter tutma)");
    expect(panel.textContent).toContain("İDARİ PARA CEZASI");
    expect(panel.textContent).toContain(UNVERIFIED_IPC_TEXT);
    expect(panel.textContent).toContain("CEZAİ SORUMLULUK");
    expect(panel.textContent).toContain(UNVERIFIED_CRIMINAL_TEXT);
    expect(panel.textContent).toContain("HUKUKİ SORUMLULUK");
    expect(panel.className).toContain("border-risk-critical-border");
    expect(panel.className).toContain("bg-risk-critical-bg");

    // Must NOT contain exact TL amounts or unverified sentence claims
    expect(panel.textContent).not.toContain("44.443");
    expect(panel.textContent).not.toContain("133.329");
    expect(panel.textContent).not.toContain("2-6 yıl hapis");
  });

  test("renders compact variant with visible disclaimer and neutral verification message (Q1)", async () => {
    await act(async () => {
      root.render(<RegulatoryInfoPanel questionId={1} variant="compact" />);
    });

    const compact = container.querySelector('[data-testid="regulatory-compact-1"]');
    expect(compact).not.toBeNull();
    expect(compact.textContent).toContain("YÜKSEK RİSK");
    expect(compact.textContent).toContain("DOĞRULAMA BEKLENİYOR");
    expect(compact.textContent).toContain("6331 md. 4");
    expect(compact.textContent).toContain(UNVERIFIED_IPC_TEXT);
    expect(compact.textContent).toContain(DISCLAIMER_TEXT);
    expect(compact.className).toContain("border-risk-critical-border");

    // Exact unverified values must not appear
    expect(compact.textContent).not.toContain("44.443");
    expect(compact.textContent).not.toContain("2-6 yıl hapis");
  });

  test("suppresses exact monetary amounts across questions (Q1, Q2, Q3, Q4, Q5, Q73)", async () => {
    const testIds = [1, 2, 3, 4, 5, 73];
    for (const qid of testIds) {
      await act(async () => {
        root.render(<RegulatoryInfoPanel questionId={qid} variant="full" />);
      });

      const panel = container.querySelector(`[data-testid="regulatory-panel-${qid}"]`);
      expect(panel).not.toBeNull();
      // Neutral message must be present
      expect(panel.textContent).toContain(UNVERIFIED_IPC_TEXT);
      // Specific unverified monetary strings must NOT be present
      expect(panel.textContent).not.toContain("44.443");
      expect(panel.textContent).not.toContain("22.194");
      expect(panel.textContent).not.toContain("8.980");
      expect(panel.textContent).not.toContain("66.725");
      expect(panel.textContent).not.toContain("114.000");
      expect(panel.textContent).not.toContain(" TL");
    }
  });

  test("all 84 questions render safely in both full and compact variants without monetary leaks", async () => {
    for (let qid = 1; qid <= 84; qid++) {
      // Test full variant
      await act(async () => {
        root.render(<RegulatoryInfoPanel questionId={qid} variant="full" />);
      });
      const panel = container.querySelector(`[data-testid="regulatory-panel-${qid}"]`);
      expect(panel).not.toBeNull();
      expect(panel.textContent).toContain(DISCLAIMER_TEXT);
      expect(panel.textContent).toContain(UNVERIFIED_IPC_TEXT);
      expect(panel.textContent).not.toContain(" TL");
      expect(panel.textContent).not.toContain("2-6 yıl hapis");

      // Test compact variant
      await act(async () => {
        root.render(<RegulatoryInfoPanel questionId={qid} variant="compact" />);
      });
      const compact = container.querySelector(`[data-testid="regulatory-compact-${qid}"]`);
      expect(compact).not.toBeNull();
      expect(compact.textContent).toContain(DISCLAIMER_TEXT);
      expect(compact.textContent).toContain(UNVERIFIED_IPC_TEXT);
      expect(compact.textContent).not.toContain(" TL");
      expect(compact.textContent).not.toContain("2-6 yıl hapis");
    }
  });

  test("renders medium severity question with moderate styling (Q2)", async () => {
    await act(async () => {
      root.render(<RegulatoryInfoPanel questionId={2} variant="full" />);
    });

    const panel = container.querySelector('[data-testid="regulatory-panel-2"]');
    expect(panel).not.toBeNull();
    expect(panel.textContent).toContain("ORTA RİSK");
    expect(panel.textContent).toContain(DISCLAIMER_TEXT);
    expect(panel.textContent).toContain(UNVERIFIED_IPC_TEXT);
    expect(panel.className).toContain("border-risk-moderate-border");
    expect(panel.className).toContain("bg-risk-moderate-bg");
  });

  test("renders low severity question with low styling (Q73)", async () => {
    await act(async () => {
      root.render(<RegulatoryInfoPanel questionId={73} variant="full" />);
    });

    const panel = container.querySelector('[data-testid="regulatory-panel-73"]');
    expect(panel).not.toBeNull();
    expect(panel.textContent).toContain("DÜŞÜK RİSK");
    expect(panel.textContent).toContain(DISCLAIMER_TEXT);
    expect(panel.className).toContain("border-border-default");
    expect(panel.className).toContain("bg-surface-card-2");
  });

  test("renders verified data when isVerified is true (future-proofing)", async () => {
    await act(async () => {
      root.render(<RegulatoryInfoPanel questionId={1} variant="full" isVerified={true} />);
    });

    const panel = container.querySelector('[data-testid="regulatory-panel-1"]');
    expect(panel).not.toBeNull();
    // When verified, exact data is shown and DOĞRULAMA BEKLENİYOR badge is absent
    expect(panel.textContent).not.toContain("DOĞRULAMA BEKLENİYOR");
    expect(panel.textContent).toContain("44.443 – 133.329 TL");
    expect(panel.textContent).toContain("2-6 yıl hapis");
  });

  test("returns null gracefully for invalid questionId", async () => {
    await act(async () => {
      root.render(<RegulatoryInfoPanel questionId={999} variant="full" />);
    });

    expect(container.innerHTML).toBe("");
  });

  test("returns null gracefully when questionId is missing or null", async () => {
    await act(async () => {
      root.render(<RegulatoryInfoPanel questionId={null} variant="full" />);
    });

    expect(container.innerHTML).toBe("");
  });

  // --- Source-level Integration Contracts ---

  test("AuditFormPage.jsx imports RegulatoryInfoPanel and uses full variant", () => {
    const filePath = path.join(__dirname, "..", "pages", "AuditFormPage.jsx");
    const content = fs.readFileSync(filePath, "utf8");
    expect(content).toContain('import RegulatoryInfoPanel from "@/components/RegulatoryInfoPanel"');
    expect(content).toContain('RegulatoryInfoPanel questionId={q.id} variant="full"');
  });

  test("DofPage.jsx imports RegulatoryInfoPanel and uses compact variant", () => {
    const filePath = path.join(__dirname, "..", "pages", "DofPage.jsx");
    const content = fs.readFileSync(filePath, "utf8");
    expect(content).toContain('import RegulatoryInfoPanel from "@/components/RegulatoryInfoPanel"');
    expect(content).toContain('RegulatoryInfoPanel questionId={item.question_id} variant="compact"');
  });

  // --- Data Integrity Contracts ---

  test("regulatory dataset contains status and all 84 questions with required keys", () => {
    expect(regulatoryData.status).toBe("UNVERIFIED — AUTHORITATIVE SOURCE CHECK REQUIRED");
    const qs = regulatoryData.questions;
    expect(Object.keys(qs).length).toBe(84);
    for (let i = 1; i <= 84; i++) {
      const q = qs[String(i)];
      expect(q).toBeDefined();
      expect(q.topic).toBeTruthy();
      expect(q.primary).toBeTruthy();
      expect(q.ipc_short).toBeTruthy();
      expect(q.criminal_short).toBeTruthy();
      expect(["high", "medium", "low"]).toContain(q.severity);
    }
  });
});
