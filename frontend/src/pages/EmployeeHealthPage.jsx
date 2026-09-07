import React from "react";
import ModulePageLayout from "@/components/ModulePageLayout";
import {
  HeartPulse,
  FileCheck,
  CalendarCheck,
  FileSpreadsheet,
} from "lucide-react";

const SUBPAGE_CONFIG = {
  "entry-reports": {
    pageTitle: "İşe Giriş Sağlık Raporları",
    noticeText: "⚠️ İşe giriş sağlık raporları ekranı güncelleme ile eklenecektir.",
    previewCards: [
      {
        icon: FileCheck,
        title: "Sağlık Raporları",
        description:
          "İşe giriş sağlık raporu belgelerinin görüntüleneceği belge görünümü.",
      },
      {
        icon: FileSpreadsheet,
        title: "Belge Görünümü",
        description:
          "İşe giriş raporlarına ait belgelerin listeleneceği takip alanı.",
      },
      {
        icon: HeartPulse,
        title: "Takip Alanı",
        description:
          "İşe giriş sağlık gözetim kayıtlarının izleneceği geliştirme alanı.",
      },
    ],
  },
  "periodic-reports": {
    pageTitle: "Periyodik Sağlık Raporları",
    noticeText: "⚠️ Periyodik sağlık raporları ekranı güncelleme ile eklenecektir.",
    previewCards: [
      {
        icon: CalendarCheck,
        title: "Sağlık Raporları",
        description:
          "Periyodik sağlık raporu belgelerinin görüntüleneceği belge görünümü.",
      },
      {
        icon: FileSpreadsheet,
        title: "Belge Görünümü",
        description:
          "Periyodik raporlara ait belgelerin listeleneceği takip alanı.",
      },
      {
        icon: HeartPulse,
        title: "Takip Alanı",
        description:
          "Periyodik sağlık gözetim kayıtlarının izleneceği geliştirme alanı.",
      },
    ],
  },
};

export default function EmployeeHealthPage({ subpage = "entry-reports" }) {
  const currentConfig = SUBPAGE_CONFIG[subpage] || SUBPAGE_CONFIG["entry-reports"];

  return (
    <ModulePageLayout
      moduleName="🩺 Çalışan Sağlık Gözetim"
      moduleBadge="İSG Modülü — Faz 2"
      moduleGradient="from-rose-600 via-red-600 to-orange-600"
      moduleIcon={HeartPulse}
      moduleDescription="ABCD Tech Solutions restoran personeli işe giriş ve periyodik sağlık raporu takip paneli."
      themeAccent="rose"
      pageTitle={currentConfig.pageTitle}
      noticeText={currentConfig.noticeText}
      previewCards={currentConfig.previewCards}
    />
  );
}
