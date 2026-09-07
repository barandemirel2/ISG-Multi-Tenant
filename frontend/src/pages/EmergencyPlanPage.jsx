import React from "react";
import ModulePageLayout from "@/components/ModulePageLayout";
import {
  Siren,
  ShieldAlert,
  AlertTriangle,
  Users,
  HeartPulse,
  ClipboardCheck,
  MapPin,
  Flame,
  Construction,
  Clock,
  Activity,
  ShieldCheck,
} from "lucide-react";

const SUBPAGE_CONFIG = {
  plan: {
    pageTitle: "Acil Durum Planı",
    noticeText: "⚠️ Acil durum planı ekranı güncelleme ile eklenecektir.",
    previewCards: [
      {
        icon: Siren,
        title: "Acil Durum Senaryoları",
        description:
          "Yangın, deprem, su baskını, sabotaj ve gıda zehirlenmesi acil durum müdahale senaryoları.",
      },
      {
        icon: ShieldAlert,
        title: "Yetkili & İletişim Protokolü",
        description:
          "İtfaiye, AFAD, ambulans ve ABCD Tech Solutions kriz masası irtibat ve bildirim akışları.",
      },
      {
        icon: AlertTriangle,
        title: "Risk Derecelendirme",
        description:
          "Restoran lokasyon tipi, bina yapısı ve risk seviyesi bazlı acil eylem matrisi.",
      },
    ],
  },
  teams: {
    pageTitle: "Ekipler",
    noticeText: "⚠️ Acil durum ekipleri ekranı güncelleme ile eklenecektir.",
    previewCards: [
      {
        icon: Users,
        title: "Söndürme & Kurtarma Ekibi",
        description:
          "Yangın ve tahliye anında görev alacak sertifikalı personel görev dağılımı.",
      },
      {
        icon: HeartPulse,
        title: "Koruma & İlk Yardım Ekibi",
        description:
          "Güvenlik, ilk müdahale ve toplanma alanı sayım koordinatörleri.",
      },
      {
        icon: ClipboardCheck,
        title: "Yedek Personel & Görev Matrisi",
        description:
          "Vardiya bazlı ekip lideri ataması ve acil durum ekip yedekleme takibi.",
      },
    ],
  },
  layout: {
    pageTitle: "Kroki",
    noticeText: "⚠️ Tahliye ve yerleşim krokisi ekranı güncelleme ile eklenecektir.",
    previewCards: [
      {
        icon: MapPin,
        title: "Tahliye Yolları & Çıkışlar",
        description:
          "Restoran mutfak, servis alanı ve depo acil çıkış yönlendirme planı.",
      },
      {
        icon: Flame,
        title: "Ekipman Konumlandırma",
        description:
          "Yangın tüpleri, yangın dolapları, alarm butonları ve ilk yardım dolabı yerleşimi.",
      },
      {
        icon: Construction,
        title: "Toplanma Alanı Koordinatları",
        description:
          "AVM ve cadde restoranı onaylı dış toplanma bölgesi tanımları.",
      },
    ],
  },
  drills: {
    pageTitle: "Tatbikat",
    noticeText: "⚠️ Tatbikat planlama ve kayıt ekranı güncelleme ile eklenecektir.",
    previewCards: [
      {
        icon: Clock,
        title: "Yıllık Tatbikat Takvimi",
        description:
          "Yasal zorunlu yangın ve tahliye tatbikatı planlama ve periyot takibi.",
      },
      {
        icon: Activity,
        title: "Tatbikat Raporlama & Süreler",
        description:
          "Tahliye süresi, katılımcı sayısı ve tatbikat başarı değerlendirme formu.",
      },
      {
        icon: ShieldCheck,
        title: "Aksiyon & İyileştirme (DÖF)",
        description:
          "Tatbikat sırasında tespit edilen aksaklıkların giderilme ve takip kaydı.",
      },
    ],
  },
};

export default function EmergencyPlanPage({ subpage = "plan" }) {
  const currentConfig = SUBPAGE_CONFIG[subpage] || SUBPAGE_CONFIG.plan;

  return (
    <ModulePageLayout
      moduleName="🚨 Acil Durum Eylem Planı"
      moduleBadge="İSG Modülü — Faz 2"
      moduleGradient="from-amber-600 via-orange-600 to-red-600"
      moduleIcon={Siren}
      moduleDescription="ABCD Tech Solutions restoran zincirleri acil durum yönetimi, kaçış yolları planlaması ve müdahale eylem planı paneli."
      themeAccent="amber"
      pageTitle={currentConfig.pageTitle}
      noticeText={currentConfig.noticeText}
      previewCards={currentConfig.previewCards}
    />
  );
}
