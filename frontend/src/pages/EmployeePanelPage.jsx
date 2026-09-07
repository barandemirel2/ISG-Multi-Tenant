import React from "react";
import ModulePageLayout from "@/components/ModulePageLayout";
import { Users, ClipboardList, Briefcase, FileSpreadsheet } from "lucide-react";

const SUBPAGE_CONFIG = {
  list: {
    pageTitle: "Personel Listesi",
    noticeText: "⚠️ Personel listesi ekranı güncelleme ile eklenecektir.",
    previewCards: [
      {
        icon: ClipboardList,
        title: "Personel Bilgileri",
        description:
          "Restoran personeline ait temel bilgilerin görüntüleneceği kayıt görünümü.",
      },
      {
        icon: Users,
        title: "Personel Listesi",
        description:
          "Şube ve rol bazlı personel listesinin izleneceği takip alanı.",
      },
      {
        icon: FileSpreadsheet,
        title: "Kayıt Görünümü",
        description:
          "Personel kayıtlarının listelenip inceleneceği geliştirme alanı.",
      },
    ],
  },
  "job-descriptions": {
    pageTitle: "Görev Tanımları",
    noticeText: "⚠️ Görev tanımları ekranı güncelleme ile eklenecektir.",
    previewCards: [
      {
        icon: Briefcase,
        title: "Görev Tanımları",
        description:
          "Restoran görev ve rollerine ait tanımların yer alacağı görünüm.",
      },
      {
        icon: ClipboardList,
        title: "Rol / Görev Bilgileri",
        description:
          "Rollere bağlı görev bilgilerinin izleneceği takip alanı.",
      },
      {
        icon: FileSpreadsheet,
        title: "Tanım Görünümü",
        description:
          "Görev tanımlarının listeleneceği geliştirme alanı.",
      },
    ],
  },
};

export default function EmployeePanelPage({ subpage = "list" }) {
  const currentConfig = SUBPAGE_CONFIG[subpage] || SUBPAGE_CONFIG.list;

  return (
    <ModulePageLayout
      moduleName="👥 Çalışan Paneli"
      moduleBadge="İSG Modülü — Faz 2"
      moduleGradient="from-violet-600 via-purple-600 to-indigo-600"
      moduleIcon={Users}
      moduleDescription="ABCD Tech Solutions restoran personel kayıtları ve görev tanımı yönetim paneli."
      themeAccent="violet"
      pageTitle={currentConfig.pageTitle}
      noticeText={currentConfig.noticeText}
      previewCards={currentConfig.previewCards}
    />
  );
}
