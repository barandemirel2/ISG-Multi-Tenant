import React from "react";
import { createRoot } from "react-dom/client";
import { act } from "react";
import ConfirmDestructive from "./ConfirmDestructive";

const fs = require("fs");
const path = require("path");

// React 19 act() environment
globalThis.IS_REACT_ACT_ENVIRONMENT = true;

describe("ConfirmDestructive — Behavioral & Theme Contract Tests", () => {
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
    // Clean up any Radix portals attached to document.body
    document.body.innerHTML = "";
  });

  // --- Behavioral Tests ---

  test("renders dialog content when open=true", async () => {
    await act(async () => {
      root.render(
        <ConfirmDestructive
          open={true}
          onOpenChange={() => {}}
          title="Denetim Silme Onayı"
          description="Bu işlem geri alınamaz."
          itemName="Denetim #12345"
          action="Kalıcı Olarak Sil"
          onConfirm={() => {}}
        />
      );
    });

    expect(document.body.textContent).toContain("Denetim Silme Onayı");
    expect(document.body.textContent).toContain("Bu işlem geri alınamaz.");
    expect(document.body.textContent).toContain("Denetim #12345");
    expect(document.body.textContent).toContain("Kalıcı Olarak Sil");
    expect(document.body.textContent).toContain("İptal");
  });

  test("calls onConfirm when confirm button is clicked", async () => {
    const handleConfirm = jest.fn();
    const handleOpenChange = jest.fn();

    await act(async () => {
      root.render(
        <ConfirmDestructive
          open={true}
          onOpenChange={handleOpenChange}
          title="Kaydı Sil"
          action="Sil"
          onConfirm={handleConfirm}
        />
      );
    });

    const buttons = Array.from(document.querySelectorAll("button"));
    const confirmButton = buttons.find((b) => b.textContent.includes("Sil"));
    expect(confirmButton).toBeTruthy();

    await act(async () => {
      confirmButton.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });

    expect(handleConfirm).toHaveBeenCalledWith("");
  });

  test("enforces reasonRequired and minLength before calling onConfirm", async () => {
    const handleConfirm = jest.fn();

    await act(async () => {
      root.render(
        <ConfirmDestructive
          open={true}
          onOpenChange={() => {}}
          title="Gerekçeli İşlem"
          action="Onayla"
          reasonRequired={true}
          reasonMinLength={15}
          onConfirm={handleConfirm}
        />
      );
    });

    const buttons = Array.from(document.querySelectorAll("button"));
    const confirmButton = buttons.find((b) => b.textContent.includes("Onayla"));

    // Attempt to submit without entering reason
    await act(async () => {
      confirmButton.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });

    expect(handleConfirm).not.toHaveBeenCalled();
    expect(document.body.textContent).toContain("Sebep zorunlu (en az 15 karakter)");

    // Type short reason
    const textarea = document.querySelector("textarea");
    expect(textarea).toBeTruthy();

    await act(async () => {
      const nativeInputValueSetter = Object.getOwnPropertyDescriptor(
        window.HTMLTextAreaElement.prototype,
        "value"
      ).set;
      nativeInputValueSetter.call(textarea, "Kısa metin");
      textarea.dispatchEvent(new Event("input", { bubbles: true }));
      textarea.dispatchEvent(new Event("change", { bubbles: true }));
    });

    await act(async () => {
      confirmButton.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });

    expect(handleConfirm).not.toHaveBeenCalled();

    // Type valid long reason
    await act(async () => {
      const nativeInputValueSetter = Object.getOwnPropertyDescriptor(
        window.HTMLTextAreaElement.prototype,
        "value"
      ).set;
      nativeInputValueSetter.call(
        textarea,
        "Bu işlem mevzuat gereği iptal edilmiştir."
      );
      textarea.dispatchEvent(new Event("input", { bubbles: true }));
      textarea.dispatchEvent(new Event("change", { bubbles: true }));
    });

    await act(async () => {
      confirmButton.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });

    expect(handleConfirm).toHaveBeenCalledWith("Bu işlem mevzuat gereği iptal edilmiştir.");
  });

  test("calls onOpenChange when cancel button is clicked", async () => {
    const handleOpenChange = jest.fn();

    await act(async () => {
      root.render(
        <ConfirmDestructive
          open={true}
          onOpenChange={handleOpenChange}
          title="Vazgeçme Testi"
          onConfirm={() => {}}
        />
      );
    });

    const buttons = Array.from(document.querySelectorAll("button"));
    const cancelButton = buttons.find((b) => b.textContent.includes("İptal"));
    expect(cancelButton).toBeTruthy();

    await act(async () => {
      cancelButton.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });

    expect(handleOpenChange).toHaveBeenCalledWith(false);
  });

  test("renders moderate theme when destructive=false", async () => {
    await act(async () => {
      root.render(
        <ConfirmDestructive
          open={true}
          onOpenChange={() => {}}
          title="Uyarı Dialogu"
          action="Devam Et"
          destructive={false}
          onConfirm={() => {}}
        />
      );
    });

    const buttons = Array.from(document.querySelectorAll("button"));
    const actionBtn = buttons.find((b) => b.textContent.includes("Devam Et"));
    expect(actionBtn.className).toContain("bg-risk-moderate");
  });

  // --- Source Contract / Theme Token Tests ---

  describe("Source theme token contract", () => {
    const SRC_DIR = path.join(__dirname, "..");
    const componentSource = fs.readFileSync(
      path.join(SRC_DIR, "components/ConfirmDestructive.jsx"),
      "utf8"
    );

    test("AlertDialogContent uses bg-surface-card and border-border-default", () => {
      expect(componentSource).toMatch(/AlertDialogContent[^>]*bg-surface-card/);
      expect(componentSource).toMatch(/AlertDialogContent[^>]*border-border-default/);
    });

    test("Title and Description use semantic ink tokens", () => {
      expect(componentSource).toMatch(/AlertDialogTitle[^>]*text-ink-primary/);
      expect(componentSource).toMatch(/AlertDialogDescription[^>]*text-ink-secondary/);
    });

    test("Cancel button uses semantic surface and border tokens", () => {
      expect(componentSource).toMatch(/AlertDialogCancel[^>]*bg-surface-card-2/);
      expect(componentSource).toMatch(/AlertDialogCancel[^>]*border-border-default/);
    });

    test("Action button uses risk tokens", () => {
      expect(componentSource).toMatch(/bg-risk-critical/);
      expect(componentSource).toMatch(/bg-risk-moderate/);
    });

    test("No hardcoded slate or white without dark: variant in active code lines", () => {
      const lines = componentSource.split("\n");
      const codeLines = lines.filter(
        (l) => !l.trim().startsWith("//") && !l.trim().startsWith("*")
      );

      const hasPlainBgSlate = codeLines.some(
        (l) => /\bbg-slate-9\d{2}\b/.test(l) && !/dark:/.test(l)
      );
      expect(hasPlainBgSlate).toBe(false);

      const hasPlainTextSlate = codeLines.some(
        (l) => /\btext-slate-\d{2,3}\b/.test(l) && !/dark:/.test(l)
      );
      expect(hasPlainTextSlate).toBe(false);
    });
  });
});
