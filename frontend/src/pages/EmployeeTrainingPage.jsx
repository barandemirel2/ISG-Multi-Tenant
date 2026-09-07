import React from "react";
import ModulePageLayout from "@/components/ModulePageLayout";
import {
  GraduationCap,
  BookOpen,
  Sparkles,
  FilePlus,
  Wrench,
  Siren,
  Users,
  ShieldAlert,
  HeartPulse,
  Award,
  UserPlus,
  FileSpreadsheet,
  CheckCircle2,
  Clock,
  Briefcase,
  AlertOctagon,
} from "lucide-react";

const SUBPAGE_CONFIG = {
  basic: {
    pageTitle: "İSG Temel Eğitimi",
    noticeText: "⚠️ İSG Temel Eğitimi takip ekranı güncelleme ile eklenecektir.",
    previewCards: [
      {
        icon: Award,
        title: "Yasal Zorunlu İSG Sertifikasyon",
        description:
          "Çok tehlikeli ve tehlikeli sınıf restoran personeli yasal geçerlilik periyotları ve sertifika takibi.",
      },
      {
        icon: Clock,
        title: "Eğitim Yenileme Hatırlatıcıları",
        description:
          "Süresi dolmak üzere olan temel eğitimler için otomatik bildirim ve planlama desteği.",
      },
      {
        icon: FileSpreadsheet,
        title: "Denetim İbraz Kayıtları",
        description:
          "Bakanlık ve iç denetim ibrazı için hazır çalışan eğitim katılım ve imza çizelgeleri.",
      },
    ],
  },
  orientation: {
    pageTitle: "İSG Oryantasyon Eğitimi",
    noticeText: "⚠️ İSG Oryantasyon Eğitimi ekranı güncelleme ile eklenecektir.",
    previewCards: [
      {
        icon: BookOpen,
        title: "İşe Başlama İSG Eğitimi",
        description:
          "Yeni istihdam edilen restoran personeline ilk gün verilmesi gereken iş güvenliği kuralları.",
      },
      {
        icon: CheckCircle2,
        title: "Oryantasyon Onay Formları",
        description:
          "Restoran müdürü ve İSG uzmanı onaylı dijital oryantasyon tamamlama kayıtları.",
      },
      {
        icon: Briefcase,
        title: "İstasyon Bazlı Güvenlik",
        description:
          "Fritöz, ızgara, bulaşıkhane ve kasa istasyonu özel risk ve güvenlik talimatları.",
      },
    ],
  },
  hygiene: {
    pageTitle: "Hijyen Eğitimi",
    noticeText: "⚠️ Hijyen Eğitimi takip ekranı güncelleme ile eklenecektir.",
    previewCards: [
      {
        icon: Sparkles,
        title: "Gıda Hijyeni & Sanitasyon",
        description:
          "Gıda üretim ve servis alanlarında çapraz bulaşma önleme, el hijyeni ve kişisel koruma.",
      },
      {
        icon: Award,
        title: "Milli Eğitim Onaylı Sertifikalar",
        description:
          "Portör muayene ve hijyen eğitim sertifikalarının güncellik durumu ve geçerlilik süreleri.",
      },
      {
        icon: FileSpreadsheet,
        title: "Restoran Hijyen Matrisi",
        description:
          "Restoran personelinin hijyen eğitimi tamamlama oranları ve eksik sertifika uyarıları.",
      },
    ],
  },
  additional: {
    pageTitle: "İlave Eğitim",
    noticeText:
      "⚠️ İlave eğitim ve DÖF kaynaklı eğitimler ekranı güncelleme ile eklenecektir.",
    previewCards: [
      {
        icon: FilePlus,
        title: "DÖF Kaynaklı İSG Eğitimleri",
        description:
          "Denetimlerde veya ramak kala olaylarında açılan DÖF maddelerine istinaden planlanan telafi eğitimleri.",
      },
      {
        icon: ShieldAlert,
        title: "Özel Risk Bilgilendirmeleri",
        description:
          "Mevsimsel riskler, yeni ekipman kurulumu veya prosedür değişiklikleri sonrası ek eğitimler.",
      },
      {
        icon: CheckCircle2,
        title: "Etkinlik Değerlendirme",
        description:
          "Verilen ilave eğitimin sahada uygulanma başarısı ve tekrar denetim geri bildirimleri.",
      },
    ],
  },
  toolbox: {
    pageTitle: "Toolbox Eğitimi",
    noticeText: "⚠️ Toolbox (Kısa İş Başı) Eğitimi ekranı güncelleme ile eklenecektir.",
    previewCards: [
      {
        icon: Wrench,
        title: "5-10 Dakikalık Vardiya Öncesi İSG",
        description:
          "Vardiya başlangıcında mutfak ve servis ekibiyle yapılan operasyonel güvenlik konuşmaları.",
      },
      {
        icon: Clock,
        title: "Haftalık Konu Başlıkları",
        description:
          "Kayma-düşme, kesici alet kullanımı, sıcak yüzeyler ve kimyasal temas konuları takvimi.",
      },
      {
        icon: FileSpreadsheet,
        title: "Vardiya Katılım Çizelgesi",
        description:
          "Restoran vardiya amiri tarafından kayıt altına alınan günlük toolbox katılım listesi.",
      },
    ],
  },
  emergency: {
    pageTitle: "Acil Durum Eğitimi",
    noticeText: "⚠️ Acil Durum Eğitimi ekranı güncelleme ile eklenecektir.",
    previewCards: [
      {
        icon: Siren,
        title: "Genel Acil Durum Bilinci",
        description:
          "Tüm restoran personeline yönelik yangın tüpü kullanımı, alarm sistemleri ve tahliye protokolleri.",
      },
      {
        icon: AlertOctagon,
        title: "Deprem & Yangın Anı Davranış",
        description:
          "Çök-kapan-tutun, acil kaçış kapılarının kullanımı ve panik yönetimi bilgilendirmeleri.",
      },
      {
        icon: Award,
        title: "Katılım & Sınav Değerlendirme",
        description:
          "Acil durum teorik eğitim test sonuçları ve eğitim katılım sertifikasyonu.",
      },
    ],
  },
  "emergency-team": {
    pageTitle: "Acil Durum Ekip Eğitimi",
    noticeText: "⚠️ Acil Durum Ekip Eğitimi ekranı güncelleme ile eklenecektir.",
    previewCards: [
      {
        icon: Users,
        title: "Özel Görevli Ekip Eğitimleri",
        description:
          "Söndürme, kurtarma ve koruma ekiplerine verilen ileri düzey müdahale ve ekipman eğitimleri.",
      },
      {
        icon: Siren,
        title: "Yangın Söndürme Pratikleri",
        description:
          "Davlumbaz söndürme sistemleri, CO2 ve kuru kimyevi tozlu söndürücü tatbiki uygulamaları.",
      },
      {
        icon: FileSpreadsheet,
        title: "Ekip Yetkinlik Matrisi",
        description:
          "Ekip üyelerinin eğitim tamamlama ve tatbikat performans skorları takip paneli.",
      },
    ],
  },
  "risk-team": {
    pageTitle: "Risk Analizi Ekip Eğitimi",
    noticeText: "⚠️ Risk Analizi Ekip Eğitimi ekranı güncelleme ile eklenecektir.",
    previewCards: [
      {
        icon: ShieldAlert,
        title: "Risk Değerlendirme Metodolojisi",
        description:
          "Fine-Kinney ve L Tipi matris risk derecelendirme eğitimleri ve tehlike tanımlama pratikleri.",
      },
      {
        icon: Briefcase,
        title: "Saha Denetim Pratikleri",
        description:
          "Restoran İSG kurulu üyelerine yönelik periyodik saha kontrol ve uygunsuzluk tespit kriterleri.",
      },
      {
        icon: Award,
        title: "Ekip Yetki Belgelendirmesi",
        description:
          "ABCD Tech Solutions Risk Analizi Ekibi resmi görevlendirme ve eğitim onay kayıtları.",
      },
    ],
  },
  "first-aid": {
    pageTitle: "İlkyardım Eğitimi",
    noticeText: "⚠️ İlkyardım Eğitimi takip ekranı güncelleme ile eklenecektir.",
    previewCards: [
      {
        icon: HeartPulse,
        title: "Sertifikalı İlkyardımcı Takibi",
        description:
          "Sağlık Bakanlığı onaylı ilkyardımcı personel sayısı, restoran kotası ve sertifika geçerlilikleri.",
      },
      {
        icon: Clock,
        title: "Yenileme & Güncelleme Eğitimleri",
        description:
          "3 yıllık ilkyardımcı sertifika süresi bitiş uyarıları ve güncelleme sınav takvimi.",
      },
      {
        icon: FileSpreadsheet,
        title: "İlkyardım Dolabı & Müdahale Kayıtları",
        description:
          "Dolap malzeme kontrolleri ve restoranda gerçekleşen ilk yardım müdahale tutanakları.",
      },
    ],
  },
  entry: {
    pageTitle: "İşe Giriş Eğitim",
    noticeText: "⚠️ İşe Giriş Eğitim takip ekranı güncelleme ile eklenecektir.",
    previewCards: [
      {
        icon: UserPlus,
        title: "İşe Giriş Eğitim Takibi",
        description:
          "İşe yeni başlayan personelin giriş eğitimlerinin kayıt altına alınacağı takip alanı.",
      },
      {
        icon: BookOpen,
        title: "Eğitim Kapsamı",
        description:
          "İşe giriş eğitimlerinde yer alacak konu başlıklarının görüntüleneceği görünüm.",
      },
      {
        icon: FileSpreadsheet,
        title: "Katılım Kayıtları",
        description:
          "İşe giriş eğitim katılımlarının listeleneceği geliştirme alanı.",
      },
    ],
  },
};

export default function EmployeeTrainingPage({ subpage = "basic" }) {
  const currentConfig = SUBPAGE_CONFIG[subpage] || SUBPAGE_CONFIG.basic;

  return (
    <ModulePageLayout
      moduleName="🎓 Çalışan Eğitimi"
      moduleBadge="İSG Modülü — Faz 2"
      moduleGradient="from-blue-600 via-indigo-600 to-purple-600"
      moduleIcon={GraduationCap}
      moduleDescription="ABCD Tech Solutions restoran personeli Temel İSG eğitimleri, hijyen oryantasyon sertifikaları ve eğitim matrisi yönetim paneli."
      themeAccent="blue"
      pageTitle={currentConfig.pageTitle}
      noticeText={currentConfig.noticeText}
      previewCards={currentConfig.previewCards}
    />
  );
}
