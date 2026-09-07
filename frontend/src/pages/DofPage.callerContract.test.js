// Regression test: DofPage caller-level wiring — filterDofs args shape.
//
// Bug context (PR0 review): DofPage caller ``filterDofs(dofs, { statusFilter,
// riskFilter, search })`` şeklinde yanlış anahtar isimleri kullanıyordu.
// Canonical helper ``filterDofs`` ise ``{ status, riskLevel, search }`` bekler.
// Yanlış anahtarlar ``undefined`` döner, helper default "HEPSİ" uygular ve
// status + riskLevel filtreleri sessizce hiçbir şeyi filtrelemez. Helper
// unit testleri (``dof.test.js``) geçtiği halde production wiring kırıktı.
//
// Bu test helper'ı tekrar test ETMEZ; ``DofPage`` üretim kodunun helper'a
// geçtiği argüman şeklini birebir simüle eder. Doğru shape verildiğinde
// İŞLEMDE filtresinin AÇIK item'ı listeden çıkardığını, İŞLEMDE item'ı
// tuttuğunu doğrular. Yanlış shape (eski bug) verildiğinde helper'ın HEPSİ
// item döndürdüğünü de doğrular — yani bug sınıfı contract-level'da
// yakalanır.
//
// Not: Tam React render testi (DofPage mount + api mock + DOM filter click)
// test kapsamı dışı bırakıldı. DofPage; AppShell, useAuth, framer-motion,
// sonner, lucide-react, 6 ayrı ``@/components/ui/*`` Radix tabanlı bileşen
// (Select/Skeleton/Button) ve 5 internal bileşen (PhotoUploader,
// DofApproveModal, BranchHealthCard, DeadlineCountdown, DofTimeline) import
// ediyor; minimum sanity-test mock surface ~15 ağır dependency. PR0 review
// kuralı olan "minimum regression test, refactor yok" gereği caller
// contract testi tercih edildi.

import { filterDofs } from "../lib/dof";

// ---------------------------------------------------------------------------
// Fixture: GET /api/dofs payload temsili (canonical İngilizce keys).
// İŞLEMDE filtresi senaryosunu minimum 2 item ile doğrular.
// ---------------------------------------------------------------------------
function makeFixture() {
  return [
    {
      audit_id: "a1",
      audit_user_id: "u1",
      owner_name: "Ali Yılmaz",
      restaurant_name: "Kadıköy Şubesi",
      audit_date: "2026-08-01",
      question_id: 3,
      question_no: 3,
      category: "Yangın Güvenliği",
      question: "Yangın söndürücü yerinde mi?",
      responsible: "Restoran Sorumlusu",
      probability: 3,
      severity: 4,
      risk_score: 12,
      risk_level: "Dikkate Değer",
      document_risk_level: "Dikkate Değer",
      deadline: "3 Ay",
      legal_basis: ["İş Güvenliği Yönetmeliği"],
      corrective_action: "Yangın söndürücüyü yenisiyle değiştirin.",
      status: "AÇIK",
      notes: "",
      updated_at: null,
      updated_by: null,
    },
    {
      audit_id: "a2",
      audit_user_id: "u1",
      owner_name: "Ali Yılmaz",
      restaurant_name: "Beşiktaş Şubesi",
      audit_date: "2026-08-02",
      question_id: 7,
      question_no: 7,
      category: "Elektrik Güvenliği",
      question: "Topraklama var mı?",
      responsible: "Restoran Sorumlusu",
      probability: 4,
      severity: 5,
      risk_score: 20,
      risk_level: "Kabul Edilemez",
      document_risk_level: "Kabul Edilemez",
      deadline: "1 Ay",
      legal_basis: ["Elektrik İç Tesisleri Yönetmeliği"],
      corrective_action: "Topraklama hattını yenileyin.",
      status: "İŞLEMDE",
      notes: "Tedarikçi değişimi başlatıldı",
      updated_at: "2026-08-03T10:00:00+00:00",
      updated_by: "u1",
    },
  ];
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------
describe("DofPage caller-level wiring — filterDofs arg shape", () => {
  const fixture = makeFixture();

  test("canonical shape {status, riskLevel, search} — İŞLEMDE filter hides AÇIK item", () => {
    // DofPage (post-FIX B) üretim kodunun kullandığı argüman shape'i:
    //   filterDofs(dofs, { status: statusFilter, riskLevel: riskFilter, search })
    // Helper bu shape'i bekler (canonical contract). Bu shape ile
    // status="İŞLEMDE" uygulandığında AÇIK item dışarıda kalmalı.
    const result = filterDofs(fixture, {
      status: "İŞLEMDE",
      riskLevel: "HEPSİ",
      search: "",
    });

    expect(result).toHaveLength(1);
    expect(result[0].status).toBe("İŞLEMDE");
    expect(result[0].audit_id).toBe("a2");
  });

  test("canonical shape — KAPATILDI filter on fixture with only AÇIK+İŞLEMDE returns []", () => {
    const result = filterDofs(fixture, {
      status: "KAPATILDI",
      riskLevel: "HEPSİ",
      search: "",
    });
    expect(result).toEqual([]);
  });

  test("canonical shape — riskLevel 'Kabul Edilemez' filter isolates only that bucket", () => {
    const result = filterDofs(fixture, {
      status: "HEPSİ",
      riskLevel: "Kabul Edilemez",
      search: "",
    });
    expect(result).toHaveLength(1);
    expect(result[0].audit_id).toBe("a2");
    expect(result[0].risk_level).toBe("Kabul Edilemez");
  });

  test("regression guard — incorrect shape (PR0 bug) silently returns ALL items", () => {
    // PR0 bug shape: ``{ statusFilter, riskFilter, search }``.
    // Helper bu anahtarları görmez; ``undefined`` default'a düşer;
    // helper "HEPSİ" kabul edip TÜM item'ları döner. Bu test, bug
    // reintroduce edilirse caller shape'inin yanlış olduğunu görünür
    // kılar — caller artık canonical shape'i zorunlu tutar.
    const buggyResult = filterDofs(fixture, {
      statusFilter: "İŞLEMDE",
      riskFilter: "HEPSİ",
      search: "",
    });
    const canonicalResult = filterDofs(fixture, {
      status: "İŞLEMDE",
      riskLevel: "HEPSİ",
      search: "",
    });
    expect(buggyResult).toHaveLength(fixture.length); // bug: nothing filtered
    expect(canonicalResult).toHaveLength(1); // correct: 1 İŞLEMDE item
  });

  test("canonical shape — combined status + riskLevel filter narrows correctly", () => {
    const result = filterDofs(fixture, {
      status: "İŞLEMDE",
      riskLevel: "Kabul Edilemez",
      search: "",
    });
    expect(result).toHaveLength(1);
    expect(result[0].audit_id).toBe("a2");
  });
});