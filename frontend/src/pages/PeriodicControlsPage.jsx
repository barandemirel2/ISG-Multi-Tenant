import React from "react";
import ModulePageLayout from "@/components/ModulePageLayout";
import {
  Wrench,
  Zap,
  Cpu,
  Flame,
  CheckSquare,
  Clock,
  ShieldCheck,
  FileSpreadsheet,
  AlertTriangle,
} from "lucide-react";

const SUBPAGE_CONFIG = {
  inspection: {
    pageTitle: "Periyodik Muayene",
    noticeText:
      "⚠️ Periyodik muayene (akredite test ve ölçümler) ekranı güncelleme ile eklenecektir.",
    previewCards: [
      {
        icon: Zap,
        title: "Elektrik & Topraklama Ölçümleri",
        description:
          "Elektrik iç tesisat kontrolü, topraklama ölçüm raporları ve paratoner periyodik kontrol takibi.",
      },
      {
        icon: Cpu,
        title: "Basınçlı Kap & Kompresör Muayenesi",
        description:
          "Hava tankları, kompresörler ve hidrofor periyodik hidrostatik test ve akredite muayene belgeleri.",
      },
      {
        icon: Flame,
        title: "Yangın Tesisatı & Davlumbaz Muayenesi",
        description:
          "Mutfak otomatik söndürme sistemleri, hidrant ve yangın tüpü hidrostatik basınç muayene takibi.",
      },
    ],
  },
  maintenance: {
    pageTitle: "Periyodik Bakım",
    noticeText:
      "⚠️ Periyodik ekipman ve tesisat bakım takip ekranı güncelleme ile eklenecektir.",
    previewCards: [
      {
        icon: Wrench,
        title: "Restoran Ekipman Bakım Planı",
        description:
          "Fritöz, ızgara, buz makinesi ve soğuk hava deposu periyodik önleyici teknik bakım takvimi.",
      },
      {
        icon: CheckSquare,
        title: "Davlumbaz & Baca Temizlik Takibi",
        description:
          "Yetkili firma baca temizlik raporları, itfaiye onay formları ve periyodik filtre değişimleri.",
      },
      {
        icon: FileSpreadsheet,
        title: "Yetkili Servis Bakım Formları",
        description:
          "Tüm restorana ait teknik servis bakım fişleri, arıza kayıtları ve garanti takip arşivi.",
      },
    ],
  },
};

export default function PeriodicControlsPage({ subpage = "inspection" }) {
  const currentConfig = SUBPAGE_CONFIG[subpage] || SUBPAGE_CONFIG.inspection;

  return (
    <ModulePageLayout
      moduleName="🛠️ Periyodik Kontroller"
      moduleBadge="İSG Modülü — Faz 2"
      moduleGradient="from-emerald-600 via-teal-600 to-cyan-600"
      moduleIcon={Wrench}
      moduleDescription="ABCD Tech Solutions restoran tesisatı, basınçlı kaplar, elektrik panoları ve ekipman periyodik muayene takip paneli."
      themeAccent="emerald"
      pageTitle={currentConfig.pageTitle}
      noticeText={currentConfig.noticeText}
      previewCards={currentConfig.previewCards}
    />
  );
}
