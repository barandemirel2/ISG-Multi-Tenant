"""
84 İSG denetim sorusu için Mevzuat + Yaptırım haritası.
Her soru için: kanun, madde, yaptırım tipi, ceza miktarı.

Çıktı: reports/u4-questions-regulatory-map-2026-08-23.md

Kaynaklar:
  - 6331 sayılı İş Sağlığı ve Güvenliği Kanunu (md. 4-26)
  - 6331 sayılı Kanun md. 26 — İdari Para Cezaları (2026 güncel, %25.49 yeniden değerleme)
  - 4857 sayılı İş Kanunu
  - 6098 sayılı Türk Borçlar Kanunu (md. 417, 418)
  - 5237 sayılı Türk Ceza Kanunu (md. 85, 89)
  - 5510 sayılı Sosyal Sigortalar ve Genel Sağlık Sigortası Kanunu
  - Binaların Yangından Korunması Hakkında Yönetmelik
  - İş Ekipmanlarının Kullanımında Sağlık ve Güvenlik Şartları Yönetmeliği
  - Kişisel Koruyucu Donanımların İşyerlerinde Kullanılması Hakkında Yönetmelik
  - İş Sağlığı ve Güvenliği Risk Değerlendirmesi Yönetmeliği
  - Gıda Hijyeni Yönetmeliği
  - Elle Taşıma İşleri Yönetmeliği
  - Elektrik İç Tesisleri Yönetmeliği
  - İşyerlerinde Acil Durumlar Hakkında Yönetmelik
  - İlkyardım Yönetmeliği
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QUESTIONS_PATH = ROOT / "questions.json"

with open(QUESTIONS_PATH, encoding="utf-8") as f:
    questions = json.load(f)


# Yaptırım şablonu — her soru için uygulanır
# İdari para cezaları 2026 yılı temel tutarlarıdır (yeniden değerleme oranı %25.49 uygulanmış)
# Tehlike sınıfı + çalışan sayısına göre +%25 ile +%200 artırım olur.
# Restoran/lokanta sektörü genelde TEHLİKELİ sınıftadır (az tehlikeli olabilir).

# YAPTIRIM TİPLERİ:
#   IPC   = İdari Para Cezası (6331 md. 26 veya ilgili kanun)
#   TK    = Taksirle (cezai sorumluluk — TCK 85, 89)
#   HK    = Hapis Cezası (TCK)
#   TBK   = Tazminat sorumluluğu (TBK 417, 418)
#   ISK   = İş Kazası sayılır (5510)
#   IKD   = İş Kazası Bildirimi yükümlülüğü
#   KAP   = İşyeri kapatılır (6331 md. 25)
#   DUR   = İş durdurulur (6331 md. 25)
#   LSG   = Lisans/izin iptali (sektörel)

# 6331 md. 26 ceza tutarları (2026, %25.49 yeniden değerleme)
# TEHLİKELİ sinif, 10-49 çalışan (en yaygın restoran profili) için +%50 artırım
IPC_6331 = {
    "genel_ihlal":     {"tutar": "44.443 – 133.329 TL", "madde": "6331 md. 4 → md. 26/1-a"},
    "uzman_hekim":     {"tutar": "111.263 – 333.789 TL/ay", "madde": "6331 md. 6/1 → md. 26/1-b"},
    "risk_deger":      {"tutar": "66.725 – 200.175 TL (ilk); 100.119 – 300.357 TL/ay (devam)", "madde": "6331 md. 10 → md. 26/1-ç"},
    "risk_devam":      {"tutar": "100.119 – 300.357 TL/ay", "madde": "6331 md. 10 → md. 26/1-ç (devam)"},
    "acil_durum":      {"tutar": "22.194 – 66.663 TL/yükümlülük", "madde": "6331 md. 11 → md. 26/1-d"},
    "kaza_bildirim":   {"tutar": "44.443 – 133.329 TL", "madde": "5510 md. 13/2; 6331 md. 14 → md. 26/1-e"},
    "saglik_gov":      {"tutar": "22.194 TL/çalışan", "madde": "6331 md. 15 → md. 26/1-f"},
    "bilgilendirme":   {"tutar": "22.194 TL/çalışan", "madde": "6331 md. 16 → md. 26/1-g"},
    "egitim":          {"tutar": "8.980 TL/çalışan", "madde": "6331 md. 17 → md. 26/1-ğ"},
    "temsilci":        {"tutar": "22.194 – 66.582 TL", "madde": "6331 md. 20 → md. 26/1-ı"},
    "kurul":           {"tutar": "22.194 – 66.582 TL/ay", "madde": "6331 md. 22 → md. 26/1-i"},
    "mufettis":        {"tutar": "111.263 TL'ye kadar", "madde": "4857 md. 107 (6331 md. 24 atfı)"},
    "is_durdurma":     {"tutar": "İş DURDURMA (6331 md. 25)", "madde": "6331 md. 25"},
}


# ============== SORU BAZLI MEVZUAT HARİTASI ==============
# Her soru için:
#   primary: birincil mevzuat (kanun/yönetmelik + madde)
#   secondary: ikincil mevzuat
#   criminal: cezai sorumluluk (TCK)
#   civil: hukuki sorumluluk (TBK)
#   ipc: idari para cezası
#   consequence: sonuç özeti

REGULATORY_MAP = {
    # ================== 1. GENEL İSG ORGANİZASYONU ==================
    1: {
        "topic": "Onaylı Defter + İSG tespitleri",
        "primary": "6331 md. 4 (Genel yükümlülükler) + md. 24 (defter tutma) + 6331 md. 24",
        "secondary": "İSG Hizmetleri Yönetmeliği md. 8",
        "ipc": "6331 md. 26/1-a → 44.443 – 133.329 TL (işveren yükümlülüğü)",
        "criminal": "TCK 85/2 (defter tutmama = görev ihlali) → kazada taksirle ölüm 2-6 yıl hapis",
        "civil": "TBK 417 (işverenin koruma yükümlülüğü ihlali) → tazminat",
        "consequence": "Defter eksikse müfettiş İSG yükümlülüklerinin yerine getirilmediğini tespit eder → IPC + kazada hapis/tazminat",
        "severity": "high",
    },
    2: {
        "topic": "Sağlık muayene raporları",
        "primary": "6331 md. 15 (Sağlık gözetimi)",
        "secondary": "İşyeri Hekimi ve Diğer Sağlık Personeli Yönetmeliği md. 9-11",
        "ipc": "6331 md. 26/1-f → 22.194 TL/çalışan (her çalışan için ayrı, artırımsız)",
        "criminal": "TCK 89 (taksirle yaralama) — uygunsuz işte çalışan hasta işçi yaralanırsa",
        "civil": "TBK 417 + SGK 5510 (rücu)",
        "consequence": "Sağlık raporu olmadan çalışan kişi meslek hastalığına yakalanırsa işveren + işyeri hekimi cezalandırılır",
        "severity": "medium",
    },
    3: {
        "topic": "İSG eğitim belgeleri",
        "primary": "6331 md. 17 (Eğitim) + 6331 md. 4",
        "secondary": "Çalışanların İSG Eğitimlerinin Usul ve Esasları Yönetmeliği md. 6-10",
        "ipc": "6331 md. 26/1-ğ → 8.980 TL/çalışan (her biri için ayrı, artırımsız)",
        "criminal": "TCK 85/89 (eğitimsiz işçi kazaya uğrarsa taksirle)",
        "civil": "TBK 417 + eğitim eksikliği kusur ağırlığı",
        "consequence": "En sık kesilen cezalardan; çalışan başına 8.980 TL. 10 kişilik ekip = 89.800 TL",
        "severity": "high",
    },
    4: {
        "topic": "Risk Değerlendirmesi Raporu",
        "primary": "6331 md. 10 (Risk değerlendirmesi)",
        "secondary": "İSG Risk Değerlendirmesi Yönetmeliği md. 8-14",
        "ipc": "6331 md. 26/1-ç → 66.725 – 200.175 TL ilk tespit; devam eden her ay 100.119 – 300.357 TL",
        "criminal": "TCK 85/89 (risk değerlendirmesi yapılmamış = görev ihlali)",
        "civil": "TBK 417 (tazminat) + kusur ağırlığı (yargı %100'e yakın kusur atfeder)",
        "consequence": "6331'in en kritik yaptırımı; rapor yoksa her ay tekrar ceza, kazada cezai sorumluluk",
        "severity": "high",
    },
    5: {
        "topic": "Acil Durum Planları + Tahliye Krokileri",
        "primary": "6331 md. 11/1 (Acil durum planı) + md. 11/2 (önlemler)",
        "secondary": "İşyerlerinde Acil Durumlar Hakkında Yönetmelik md. 6-12; Binaların Yangından Korunması Hakkında Yönetmelik md. 69, 70",
        "ipc": "6331 md. 26/1-d → 22.194 – 66.663 TL/yükümlülük (plan yok + kroki yok = 2 ceza)",
        "criminal": "TCK 85 (yangın/tahliye başarısız → ölüm) → 2-6 yıl hapis",
        "civil": "TBK 417 + müşteri/misafir ölümünde geniş tazminat",
        "consequence": "Yangın çıkarsa kroki/plansız işyeri için müfettiş + savcı aktif; işveren vekili bizzat yargılanır",
        "severity": "high",
    },
    6: {
        "topic": "Acil Durum Ekipleri (Söndürme, Kurtarma, Koruma, İlk Yardım)",
        "primary": "6331 md. 11/2 (Acil durum ekipleri)",
        "secondary": "İşyerlerinde Acil Durumlar Yönetmeliği md. 8-11",
        "ipc": "6331 md. 26/1-d → 22.194 – 66.663 TL (her ekip için ayrı, 4 ekip = 4 ceza)",
        "criminal": "TCK 85 (ekipsiz tahliye → ölüm)",
        "civil": "TBK 417",
        "consequence": "Restoranlar için 4 ayrı ekip zorunlu; eksik her ekip başına ayrı IPC",
        "severity": "high",
    },
    7: {
        "topic": "Yıllık Tahliye Tatbikatı",
        "primary": "6331 md. 11/3 (Tatbikat)",
        "secondary": "İşyerlerinde Acil Durumlar Yönetmeliği md. 13; Binaların Yangından Korunması md. 70/2",
        "ipc": "6331 md. 26/1-d → 22.194 – 66.663 TL",
        "criminal": "TCK 85 (tatbikatsız bina → ölüm halinde ağır kusur)",
        "civil": "TBK 417",
        "consequence": "Yıllık zorunlu; tatbikatsız işyerinde kaza çıkarsa mahkeme 'ağır kusur' der, tazminat katlanır",
        "severity": "high",
    },
    8: {
        "topic": "İSG Kurul Toplantıları / Çalışan Temsilcisi",
        "primary": "6331 md. 20 (Çalışan temsilcisi) + md. 22 (Kurul) + 6331 md. 4",
        "secondary": "İSG Kurulları Hakkında Yönetmelik md. 7-13",
        "ipc": "6331 md. 26/1-ı → 22.194 – 66.582 TL (temsilci atanmamış); md. 26/1-i → 22.194 – 66.582 TL/ay (kurul toplantısı yapılmamış, 50+ çalışanlı işyerleri)",
        "criminal": "TCK 85/89 (temsilcisiz işçi görüşü alınmamış karar → kaza)",
        "civil": "TBK 417",
        "consequence": "50'den az çalışanı olan işletmelerde temsilci yeterli, kurul şartı yok. 50+ çalışan varsa kurul zorunlu",
        "severity": "high",
    },
    9: {
        "topic": "Hijyen Eğitimi Belgesi (gıda sektörü)",
        "primary": "5996 sayılı Kanun md. 21 (Hijyen Eğitimi) + md. 29 (Hijyen esasları) + 6331 md. 4",
        "secondary": "Hijyen Eğitimi Yönetmeliği (RG 5.5.2014 / 28988) md. 5-6; Gıda Hijyeni Yönetmeliği md. 6; 6331 md. 17 (eğitim)",
        "ipc": "5996 md. 41 (a) → perakende için ~2.510 TL (yeniden değerleme sonrası), üretim için ~6.272 TL + faaliyet durdurma riski; 6331 md. 26/1-ğ → 8.980 TL/çalışan (İSG eğitim eksikliği)",
        "criminal": "TCK 185 (gıda maddesine zararlı madde karıştırma, 1-5 yıl hapis + 1000-5000 gün adli para); TCK 89 (gıda zehirlenmesi → yaralanma)",
        "civil": "TBK 417 + müşteri/misafir zehirlenmesi tazminatı",
        "consequence": "Restoran/lokanta için KRİTİK; belgesiz gıda işçisi çalıştırmak hem gıda kanunu hem İSG kanunu cezası",
        "severity": "medium",
    },
    10: {
        "topic": "İş kazası bildirimi + ramak kala formu",
        "primary": "5510 sayılı Kanun md. 13 (İş kazası bildirimi, 3 iş günü)",
        "secondary": "6331 md. 14 (Kaza ve ramak kala kayıtları); İş Kazası ve Meslek Hastalığı Yönetmeliği",
        "ipc": "5510 md. 102 (bildirim yapmama) → 44.443 – 133.329 TL",
        "criminal": "TCK 85/89 (bildirilmemiş kaza → ölüm/yaralanma; delil karartma riski)",
        "civil": "TBK 417 + SGK rücu",
        "consequence": "3 iş günü kuralı; geç bildirim = ayrı ceza, ramak kala formu eksikse risk değerlendirmesi yenilenmemiş sayılır",
        "severity": "high",
    },

    # ================== 2. YANGIN GÜVENLİĞİ ==================
    11: {
        "topic": "YKS bakımları + 4 yıllık dolum",
        "primary": "Binaların Yangından Korunması Hakkında Yönetmelik md. 99, 100, 101 + 6331 md. 11",
        "secondary": "6331 md. 10 (risk değerlendirmesi); TS 862-1 EN 3 (yangın söndürücüler standardı)",
        "ipc": "BYKHY md. 49 (idari yaptırım) → 5.000 – 50.000 TL; ayrıca 6331 md. 26/1-ç (risk değerlendirmesi eksik)",
        "criminal": "TCK 85/89 (bakımsız tüp yangında çalışmazsa → ölüm)",
        "civil": "TBK 417",
        "consequence": "Yıllık bakım + 4 yıllık dolum zorunlu; yangın anında çalışmayan tüp = müfettiş için doğrudan kusur delili",
        "severity": "high",
    },
    12: {
        "topic": "Yangın tüpü erişilebilirliği + zemin yüksekliği",
        "primary": "Binaların Yangından Korunması Hakkında Yönetmelik md. 99/4 (yerleşim) + 6331 md. 11",
        "secondary": "6331 md. 10 (risk değerlendirmesi)",
        "ipc": "BYKHY md. 49 → 5.000 – 50.000 TL",
        "criminal": "TCK 85 (erişilemeyen tüp → ölüm)",
        "civil": "TBK 417",
        "consequence": "Görsel ihlal; müfettiş tüp yerini kontrol eder. Üzerinde malzeme depolanmışsa = engelleme",
        "severity": "high",
    },
    13: {
        "topic": "Davlumbaz Otomatik Gazlı Söndürme (ANSUL)",
        "primary": "Binaların Yangından Korunması Yönetmeliği md. 27, 28 (mutfak davlumbazı) + Türk Gıda Kodeksi Gıda Hijyeni Yönetmeliği (RG 17.12.2011) + 6331 md. 11",
        "secondary": "NFPA 17A standardı; TS EN 16282",
        "ipc": "BYKHY md. 49 → 5.000 – 50.000 TL + 6331 md. 26/1-ç (risk değerlendirmesi)",
        "criminal": "TCK 85 (söndürmesiz davlumbaz → yangın büyümesi → ölüm) → 2-6 yıl hapis",
        "civil": "TBK 417 (geniş tazminat)",
        "consequence": "Restoran için KRİTİK; yağ yangınında manuel müdahale çoğu zaman yetersiz, ANSUL hayat kurtarır. Yokluğu = ağır kusur",
        "severity": "high",
    },
    14: {
        "topic": "Acil çıkış kapıları (dışa açılma + panik bar)",
        "primary": "Binaların Yangından Korunması Yönetmeliği md. 33, 34, 35 (kaçış yolları) + 6331 md. 11",
        "secondary": "6331 md. 11 (acil durum planı)",
        "ipc": "BYKHY md. 49 → 5.000 – 50.000 TL + 6331 md. 26/1-d → 22.194 – 66.663 TL",
        "criminal": "TCK 85 (panik sırasında açılmayan kapı → ezilme/ölm e)",
        "civil": "TBK 417 (panik bar yoksa müşteri + çalışan ölümü)",
        "consequence": "Yüksek riskli alan; yangın + panik senaryosunda en kritik önlem. Müfettiş + itfaiye birlikte kontrol eder",
        "severity": "high",
    },
    15: {
        "topic": "Acil çıkış yolları + merdivenlerde depolama",
        "primary": "Binaların Yangından Korunması Yönetmeliği md. 31, 32 (kaçış yolları) + 6331 md. 11",
        "secondary": "6331 md. 11 (acil durum)",
        "ipc": "BYKHY md. 49 → 5.000 – 50.000 TL + 6331 md. 26/1-d → 22.194 – 66.663 TL",
        "criminal": "TCK 85 (engellenen kaçış yolu → ölüm) → 2-6 yıl hapis",
        "civil": "TBK 417 (en sık ölümlü kazaların nedeni)",
        "consequence": "Acil çıkış engelleme = en sık kapatma sebebi; 1-2 dk'da dumandan zehirlenme riski",
        "severity": "high",
    },
    16: {
        "topic": "Acil durum aydınlatma + EXIT/ÇIKIŞ levhaları",
        "primary": "Binaların Yangından Korunması Yönetmeliği md. 35, 36, 71 (acil aydınlatma) + 6331 md. 11",
        "secondary": "TS EN 1838 (acil aydınlatma standardı)",
        "ipc": "BYKHY md. 49 → 5.000 – 50.000 TL",
        "criminal": "TCK 85 (karanlıkta çıkış bulamama → ölüm)",
        "civil": "TBK 417",
        "consequence": "Elektrik kesilince devreye girmeli; pil + şarj ünitesi kontrolü. Müfettiş test eder",
        "severity": "high",
    },
    17: {
        "topic": "Yangın algılama + ihbar dedektörleri",
        "primary": "Binaların Yangından Korunması Yönetmeliği md. 65-67 (algılama) + Türk Gıda Kodeksi Gıda Hijyeni Yönetmeliği (RG 17.12.2011) + 6331 md. 11",
        "secondary": "TS EN 54 (yangın algılama sistemleri)",
        "ipc": "BYKHY md. 49 → 5.000 – 50.000 TL",
        "criminal": "TCK 85 (algılanmayan yangın → büyüme → ölüm)",
        "civil": "TBK 417",
        "consequence": "Mutfak + depo için ayrı dedektör (sıcaklık + duman); yangını ilk 30 saniyede algılama hayat kurtarır",
        "severity": "high",
    },
    18: {
        "topic": "Yangın dolapları + hortumları",
        "primary": "Binaların Yangından Korunması Yönetmeliği md. 94, 95 (yangın dolabı) + 6331 md. 11",
        "secondary": "TS EN 671-1 (yangın dolabı standardı)",
        "ipc": "BYKHY md. 49 → 5.000 – 50.000 TL",
        "criminal": "TCK 85 (basınçsız hortum → yangında yetersiz müdahale)",
        "civil": "TBK 417",
        "consequence": "Hortum basınç testi + dolap kilidi + görsel kontrol; yıllık bakım zorunlu",
        "severity": "high",
    },
    19: {
        "topic": "Gaz kesme emniyet valfleri (solenoid) + alarm entegrasyonu",
        "primary": "Binaların Yangından Korunması Yönetmeliği md. 28 (gaz tespit + kesme) + 6331 md. 11",
        "secondary": "TS EN 50443 (gaz alarm sistemleri)",
        "ipc": "BYKHY md. 49 → 5.000 – 50.000 TL + 6331 md. 26/1-ç (risk değerlendirmesi)",
        "criminal": "TCK 85 (gaz kaçağı + entegre olmayan solenoid → patlama → toplu ölüm) → 2-6 yıl hapis",
        "civil": "TBK 417 (patlama: geniş tazminat + 3. şahıslar dahil)",
        "consequence": "Restoran/lokanta için KRİTİK; doğalgaz + LPG solenoid valfi olmadan alarm entegre değilse müfettiş direkt suç duyurusu yapar",
        "severity": "high",
    },
    20: {
        "topic": "Mutfak yangın battaniyesi",
        "primary": "Binaların Yangından Korunması Yönetmeliği md. 99 (söndürme cihazları) + Türk Gıda Kodeksi Gıda Hijyeni Yönetmeliği (RG 17.12.2011) + 6331 md. 11",
        "secondary": "TS EN 1869 (yangın battaniyesi standardı)",
        "ipc": "BYKHY md. 49 → 5.000 – 50.000 TL (düşük tutar; küçük ihlal)",
        "criminal": "TCK 89 (yağ yangınında müdahale edemeyen çalışan yaralanması)",
        "civil": "TBK 417",
        "consequence": "Küçük ama kritik; 1-1.5 m kare her fritöz için ayrı; ilk müdahale aracı",
        "severity": "medium",
    },

    # ================== 3. ELEKTRİK ==================
    21: {
        "topic": "Kaçak Akım Rölesi (30mA / 300mA)",
        "primary": "Elektrik İç Tesisleri Yönetmeliği md. 35 (koruma) + Türk Gıda Kodeksi Gıda Hijyeni Yönetmeliği (RG 17.12.2011)",
        "secondary": "TS EN 61008 / TS EN 61009; 6331 md. 10 (risk değerlendirmesi)",
        "ipc": "Elektrik md. cezaları (EPDK/Enerji Bakanlığı) → 5.000 – 50.000 TL + 6331 md. 26/1-ç",
        "criminal": "TCK 85 (kaçak akım rölesi yoksa elektrik çarpması → ölüm)",
        "civil": "TBK 417 (en sık ölümlü iş kazası nedeni)",
        "consequence": "Restoran için KRİTİK; nem + su = yüksek risk. 30mA hayat koruma, 300mA yangın koruma (ayrı işlev)",
        "severity": "high",
    },
    22: {
        "topic": "Elektrik panoları altında yalıtkan paspas",
        "primary": "6331 md. 10 + Elektrik İç Tesisleri Yönetmeliği md. 32",
        "secondary": "TS EN 61111 (yalıtkan paspas standardı)",
        "ipc": "6331 md. 26/1-ç (risk değerlendirmesi)",
        "criminal": "TCK 89 (yetişkin müdahalesinde çarpılma → yaralanma)",
        "civil": "TBK 417",
        "consequence": "Basit ama kritik; pano önünde her zaman yalıtkan paspas. 1 kV'a kadar olanlar için min 11kV dayanım",
        "severity": "medium",
    },
    23: {
        "topic": "Pano kapakları kilitli, önleri açık, uyarı levhaları",
        "primary": "Elektrik İç Tesisleri Yönetmeliği md. 32 (pano koruma) + Türk Gıda Kodeksi Gıda Hijyeni Yönetmeliği (RG 17.12.2011)",
        "secondary": "6331 md. 10; Sağlık ve Güvenlik İşaretleri Yönetmeliği",
        "ipc": "6331 md. 26/1-ç + Elektrik md. cezası → 5.000 – 50.000 TL",
        "criminal": "TCK 85/89 (açık pano → çocuk/müşteri teması → çarpılma → ölüm/yaralanma)",
        "civil": "TBK 417",
        "consequence": "3 koşul birden: Kilit + açıklık + uyarı levhası. Müşteri alanına açık panolar yüksek risk",
        "severity": "high",
    },
    24: {
        "topic": "Yıllık Elektrik İç Tesisat + Topraklama Ölçüm Raporu",
        "primary": "Elektrik İç Tesisleri Yönetmeliği md. 60, 64 (periyodik kontrol)",
        "secondary": "6331 md. 10; İş Ekipmanları Yönetmeliği md. 13 (elektrik periyodik kontrol)",
        "ipc": "6331 md. 26/1-ç + Elektrik md. cezası → 5.000 – 50.000 TL",
        "criminal": "TCK 85 (topraklamasız sistem → kaçak akım → çarpılma → ölüm)",
        "civil": "TBK 417",
        "consequence": "Yetkili mühendis imzalı rapor şart; 1-3 yılda bir periyodik kontrol. Rapor yoksa elektriksel güvenlik garanti edilemez",
        "severity": "high",
    },
    25: {
        "topic": "Mutfak prizleri IP54/IP65 koruma",
        "primary": "Elektrik İç Tesisleri Yönetmeliği md. 14 (ıslak yerler)",
        "secondary": "TS EN 60529 (IP koruma sınıfları); 6331 md. 10",
        "ipc": "Elektrik md. → 5.000 – 50.000 TL + 6331 md. 26/1-ç",
        "criminal": "TCK 89 (su sıçraması + korumasız priz → çarpılma)",
        "civil": "TBK 417",
        "consequence": "Mutfak = IP54 asgari; tezgah altı = IP65. Standart priz yasak",
        "severity": "medium",
    },
    26: {
        "topic": "Kablolarda ek/aşınma/soyulma/açıkta iletken",
        "primary": "Elektrik İç Tesisleri Yönetmeliği md. 56, 57 (kablo tesisatı)",
        "secondary": "6331 md. 10; TS HD 21.3 (PVC kablolar)",
        "ipc": "Elektrik md. → 5.000 – 50.000 TL + 6331 md. 26/1-ç",
        "criminal": "TCK 85 (yıpranmış kablo → kısa devre → yangın veya çarpılma → ölüm)",
        "civil": "TBK 417",
        "consequence": "Çatlak/soyulma = derhal değişim; açıkta kablo yasak. Müfettiş görsel + termal kamera kontrolü",
        "severity": "high",
    },
    27: {
        "topic": "Seyyar uzatma kablosu + çoklu priz kalıcı kullanım",
        "primary": "Elektrik İç Tesisleri Yönetmeliği md. 18 (sabit tesisat)",
        "secondary": "6331 md. 10",
        "ipc": "Elektrik md. → 5.000 – 50.000 TL + 6331 md. 26/1-ç",
        "criminal": "TCK 85 (aşırı yük → yangın)",
        "civil": "TBK 417",
        "consequence": "Sadece geçici kullanım; 3+ cihaz = kalıcı tesisat gerekli. Restoran mutfakları sık ihlal yapar",
        "severity": "high",
    },
    28: {
        "topic": "Jeneratör/kompresör muhafaza + topraklama",
        "primary": "Elektrik İç Tesisleri Yönetmeliği md. 64 (topraklama) + Türk Gıda Kodeksi Gıda Hijyeni Yönetmeliği (RG 17.12.2011)",
        "secondary": "6331 md. 10; İş Ekipmanları Yönetmeliği (jeneratör/kompresör periyodik kontrol)",
        "ipc": "Elektrik md. → 5.000 – 50.000 TL + 6331 md. 26/1-ç",
        "criminal": "TCK 85/89 (jeneratör çarpılması → ölüm; gürültü/sıcaklık maruziyeti → yaralanma)",
        "civil": "TBK 417",
        "consequence": "Jeneratör açık alanda muhafazalı; karbon monoksit riski için egzoz borusu dışarı",
        "severity": "high",
    },
    29: {
        "topic": "Aydınlatma armatürleri sağlam (kırık/sarkma yok)",
        "primary": "Elektrik İç Tesisleri Yönetmeliği md. 41 (aydınlatma)",
        "secondary": "6331 md. 10; TS EN 60598 (armatür standardı)",
        "ipc": "Elektrik md. → 5.000 – 50.000 TL + 6331 md. 26/1-ç",
        "criminal": "TCK 89 (düşen armatür → yaralanma; patlayan tüp → yanık)",
        "civil": "TBK 417",
        "consequence": "Sarkık armatür düşme riski; özellikle müşteri alanlarında baş yaralanması",
        "severity": "medium",
    },
    30: {
        "topic": "Elektrik arıza/bakım — yetkili personel dışında",
        "primary": "Elektrik İç Tesisleri Yönetmeliği md. 4, 5 (yetkili kişi); 6331 md. 10",
        "secondary": "Elektrik ile İlgili Fen Adamlarının Yetki ve Sorumlulukları Hakkında Yönetmelik",
        "ipc": "Elektrik md. → 5.000 – 50.000 TL + 6331 md. 26/1-ç; ayrıca 6331 md. 11 (acil durum)",
        "criminal": "TCK 85/89 (yetkisiz kişinin yaptığı iş → çarpılma → ölüm) → 2-6 yıl hapis",
        "civil": "TBK 417 (ağır kusur)",
        "consequence": "KRİTİK ihlal; ehliyetsiz elektrikçi çalıştırmak müfettiş için direkt suç duyurusu sebebi",
        "severity": "high",
    },

    # ================== 4. MUTFAK EKİPMANLARI ==================
    31: {
        "topic": "Fritöz termostat + emniyet limit termostatı",
        "primary": "İş Ekipmanlarının Kullanımında Sağlık ve Güvenlik Şartları Yönetmeliği md. 6-9",
        "secondary": "TS EN 16774 (fritöz güvenliği); Gıda Hijyeni Yönetmeliği; 6331 md. 10",
        "ipc": "İş Ekipmanları Yönetmeliği md. cezası + 6331 md. 26/1-ç → 5.000 – 50.000 TL",
        "criminal": "TCK 85/89 (arızalı termostat → yağ yangını → ölüm/yanık) → 2-6 yıl hapis",
        "civil": "TBK 417 + 3. şahıslar (müşteri) tazminatı",
        "consequence": "Restoran için KRİTİK; yağ tutuşma sıcaklığı 350°C, termostat yoksa dakikalar içinde yangın",
        "severity": "high",
    },
    32: {
        "topic": "Fritöz çevresi sıçrama siperliği",
        "primary": "İş Ekipmanları Yönetmeliği + 6331 md. 10 (risk değerlendirmesi) + Kişisel Koruyucu Donanımların İşyerlerinde Kullanılması Hakkında Yön. m. 6",
        "secondary": "TS EN 16774",
        "ipc": "6331 md. 26/1-ç → 66.725 – 200.175 TL",
        "criminal": "TCK 89 (sıçrayan yağ → yanık)",
        "civil": "TBK 417",
        "consequence": "Basit fiziksel önlem; siperlik 30 cm yükseklikte. Müfettiş ölçer",
        "severity": "medium",
    },
    33: {
        "topic": "Izgara/broiler/fırın tutamak ısı yalıtımı",
        "primary": "İş Ekipmanları Yönetmeliği + 6331 md. 10",
        "secondary": "TS EN 16774",
        "ipc": "6331 md. 26/1-ç → 66.725 – 200.175 TL",
        "criminal": "TCK 89 (yanık)",
        "civil": "TBK 417",
        "consequence": "Yanık riski; tüm tutamaklar 80°C üzeri yalıtımlı olmalı",
        "severity": "medium",
    },
    34: {
        "topic": "Mutfak makineleri acil durdurma (EMERGENCY STOP)",
        "primary": "İş Ekipmanları Yönetmeliği md. 26 (acil durdurma) + Türk Gıda Kodeksi Gıda Hijyeni Yönetmeliği (RG 17.12.2011)",
        "secondary": "TS EN ISO 13850; 6331 md. 10",
        "ipc": "6331 md. 26/1-ç → 66.725 – 200.175 TL",
        "criminal": "TCK 85/89 (acil stop yoksa el kesilmesi → ağır yaralanma)",
        "civil": "TBK 417",
        "consequence": "Mutfak ekipmanları için hayati; et, hamur, dilimleme makineleri için zorunlu",
        "severity": "high",
    },
    35: {
        "topic": "Bıçak depolama + muhafaza kılıfları",
        "primary": "İş Ekipmanları Yönetmeliği + 6331 md. 10",
        "secondary": "Gıda Hijyeni Yönetmeliği md. 7",
        "ipc": "6331 md. 26/1-ç → 66.725 – 200.175 TL",
        "criminal": "TCK 89 (açıkta bıçak → kesik)",
        "civil": "TBK 417",
        "consequence": "Manyetik tutucu + kılıf; dağınık bıçak = müfettiş için direkt ihlal",
        "severity": "medium",
    },
    36: {
        "topic": "Mutfak ekipmanları periyodik bakım",
        "primary": "İş Ekipmanları Yönetmeliği md. 13 (periyodik kontrol) + Türk Gıda Kodeksi Gıda Hijyeni Yönetmeliği (RG 17.12.2011)",
        "secondary": "6331 md. 10; 6502 sayılı Tüketicinin Korunması Kanunu (satış sonrası hizmet)",
        "ipc": "6331 md. 26/1-ç → 66.725 – 200.175 TL",
        "criminal": "TCK 85/89 (bakımsız ekipman kazası)",
        "civil": "TBK 417 + 6502 md. (üretici sorumluluğu)",
        "consequence": "Sözleşmeli servisçe yıllık bakım; fatura + rapor şart",
        "severity": "high",
    },
    37: {
        "topic": "Kızartma yağı polar madde ölçümü",
        "primary": "5996 sayılı Kanun md. 29 (gıda güvenliği, polar madde) + Türk Gıda Kodeksi Kızartma Yağları Tebliği (md. 5: polar madde limiti %25)",
        "secondary": "Gıda Hijyeni Yönetmeliği md. 5, 6; 6331 md. 10 (risk değerlendirmesi)",
        "ipc": "5996 md. 41 (a) → 2.000-5.000 TL (yeniden değerleme sonrası ~2.510-6.272 TL, perakende/üretim ayrımı var); ayrıca 6331 md. 26/1-ç (risk değerlendirmesi eksikse ek ceza)",
        "criminal": "TCK 185 (sağlığa zararlı gıda, 1-5 yıl hapis + 1000-5000 gün adli para cezası); TCK 89 (gıda zehirlenmesi → yaralanma)",
        "civil": "TBK 417 + müşteri tazminatı",
        "consequence": "%25 polar madde = değişim zamanı; test cihazı şart. Restoran için KRİTİK (gıda mevzuatı)",
        "severity": "medium",
    },
    38: {
        "topic": "Boiler/çay makinesi basınç emniyet ventili",
        "primary": "Basınçlı Ekipmanlar Yönetmeliği (2014/68/AB) + Türk Gıda Kodeksi Gıda Hijyeni Yönetmeliği (RG 17.12.2011)",
        "secondary": "İş Ekipmanları Yönetmeliği; 6331 md. 10",
        "ipc": "6331 md. 26/1-ç → 66.725 – 200.175 TL",
        "criminal": "TCK 85 (basınçlı kap patlaması → ölüm)",
        "civil": "TBK 417",
        "consequence": "Ventilsiz boiler = infilak riski; basınç emniyet ventili kritik güvenlik bileşeni",
        "severity": "high",
    },
    39: {
        "topic": "Mutfak bataryaları + sıcak su — haşlanma uyarısı",
        "primary": "6331 md. 10 + Gıda Hijyeni Yönetmeliği",
        "secondary": "Sağlık ve Güvenlik İşaretleri Yönetmeliği; TS EN 806 (sıhhi tesisat)",
        "ipc": "6331 md. 26/1-ç (risk değerlendirmesi)",
        "criminal": "TCK 89 (sıcak su haşlanması → 2. derece yanık)",
        "civil": "TBK 417",
        "consequence": "Sıcaklık limiti 60°C (çocuk alanı); uyarı etiketi şart",
        "severity": "medium",
    },
    40: {
        "topic": "Bulaşıkhane giyotin bulaşık makinesi kapak sensörü",
        "primary": "İş Ekipmanları Yönetmeliği + 6331 md. 10 + Türk Gıda Kodeksi Gıda Hijyeni Yönetmeliği (RG 17.12.2011)",
        "secondary": "TS EN 415-1 (gıda makineleri güvenliği)",
        "ipc": "6331 md. 26/1-ç → 66.725 – 200.175 TL",
        "criminal": "TCK 85/89 (sensörsüz kapak → el kesilmesi → ağır yaralanma)",
        "civil": "TBK 417",
        "consequence": "Giyotin bıçaklı makine = en tehlikeli mutfak ekipmanı; sensörsüz = direkt kaza riski",
        "severity": "high",
    },

    # ================== 5. SOĞUK DEPO / DEPOLAMA / ERGONOMİ ==================
    41: {
        "topic": "Soğuk depo içeriden kapı açma mandalı",
        "primary": "6331 md. 10 + İş Sağlığı ve Güvenliği Risk Değerlendirmesi Yönetmeliği",
        "secondary": "TS EN 378 (soğutma sistemleri güvenliği)",
        "ipc": "6331 md. 26/1-ç → 66.725 – 200.175 TL",
        "criminal": "TCK 85 (içeride mahsur kalan çalışan → hipotermi/boğulma → ölüm) → 2-6 yıl hapis",
        "civil": "TBK 417",
        "consequence": "Soğuk depoda mahsur kalma = ölümle sonuçlanabilir (donarak); manyetik mandal + iç aydınlatma zorunlu",
        "severity": "high",
    },
    42: {
        "topic": "Soğuk depolarda 'İçeride Adam Var' alarm",
        "primary": "6331 md. 10 + İş Ekipmanları Yönetmeliği + Türk Gıda Kodeksi Gıda Hijyeni Yönetmeliği (RG 17.12.2011)",
        "secondary": "TS EN 378",
        "ipc": "6331 md. 26/1-ç → 66.725 – 200.175 TL",
        "criminal": "TCK 85 (alarm yoksa fark edilemeyen mahsur kalma → ölüm)",
        "civil": "TBK 417",
        "consequence": "Sesli + ışıklı; dışarıdan uyarı. Mandal + alarm birlikte zorunlu",
        "severity": "high",
    },
    43: {
        "topic": "Soğuk oda taban buzlanma — rezistanslı ısıtıcı",
        "primary": "6331 md. 10 (kayma riski değerlendirmesi)",
        "secondary": "İş Sağlığı ve Güvenliği Risk Değerlendirmesi Yönetmeliği",
        "ipc": "6331 md. 26/1-ç → 66.725 – 200.175 TL",
        "criminal": "TCK 89 (kayma → düşme → yaralanma)",
        "civil": "TBK 417",
        "consequence": "Eşik + zemin rezistansı; sıfır altı çalışma ortamı + ıslak zemin = yüksek kayma riski",
        "severity": "medium",
    },
    44: {
        "topic": "Depo rafları duvara/zemine sabitleme",
        "primary": "6331 md. 10 (devrilme riski) + İş Ekipmanları Yönetmeliği (raf güvenliği)",
        "secondary": "TS EN 15512 (sabit raf sistemleri); FEM 10.2.06 (sabit depo rafları)",
        "ipc": "6331 md. 26/1-ç → 66.725 – 200.175 TL",
        "criminal": "TCK 85 (devrilen raf → ezilme → ölüm)",
        "civil": "TBK 417",
        "consequence": "Deprem riski de dahil; tüm raflar sabitlenmeli. 2m+ yükseklikteki raflar özellikle tehlikeli",
        "severity": "high",
    },
    45: {
        "topic": "Depo rafları MAX KG kapasite etiketleri",
        "primary": "6331 md. 10 + İş Ekipmanları Yönetmeliği",
        "secondary": "TS EN 15635 (raf kullanma talimatları); FEM 10.3.01",
        "ipc": "6331 md. 26/1-ç → 66.725 – 200.175 TL",
        "criminal": "TCK 89 (aşırı yük → çökme → yaralanma)",
        "civil": "TBK 417",
        "consequence": "Aşırı yükleme = çökme; her rafta görünür etiket. Görsel kontrol",
        "severity": "medium",
    },
    46: {
        "topic": "Ağır koliler alt + hafif üst (raf istif kuralı)",
        "primary": "6331 md. 10 (ergonomi riski) + Elle Taşıma İşleri Yönetmeliği",
        "secondary": "TS EN 15512 (raf tasarımı)",
        "ipc": "6331 md. 26/1-ç → 66.725 – 200.175 TL",
        "criminal": "TCK 89 (ters istif → düşen yük → yaralanma)",
        "civil": "TBK 417",
        "consequence": "Ağır altta = stabilite; hafif altta = devrilme riski. Müfettiş fotoğraf ister",
        "severity": "medium",
    },
    47: {
        "topic": "Elle taşıma eğitimi",
        "primary": "Elle Taşıma İşleri Yönetmeliği md. 6, 7 (eğitim)",
        "secondary": "6331 md. 17 (eğitim)",
        "ipc": "6331 md. 26/1-ğ → 8.980 TL/çalışan + Elle Taşıma md. cezası",
        "criminal": "TCK 89 (eğitimsiz taşıma → fıtık/bel yaralanması)",
        "civil": "TBK 417 + SGK 5510 (meslek hastalığı)",
        "consequence": "Eğitimsiz taşıyıcılar kronik yaralanma riski; SGK tazminat öder, işverene rücu",
        "severity": "medium",
    },
    48: {
        "topic": "Malzeme istif yüksekliği (tavan/sprinklerden 50cm aşağı)",
        "primary": "Binaların Yangından Korunması Yönetmeliği md. 24, 25 (istif)",
        "secondary": "FM Global Loss Prevention Data Sheet 8-9 (istif); 6331 md. 10",
        "ipc": "BYKHY md. 49 → 5.000 – 50.000 TL + 6331 md. 26/1-ç",
        "criminal": "TCK 85 (sprinkler engellenmişse yangında çalışmaz → büyüme → ölüm)",
        "civil": "TBK 417",
        "consequence": "Sprinkler 50 cm kuralı; sigorta şirketi de bu kurala bakar. Yangın riskini büyütür",
        "severity": "high",
    },
    49: {
        "topic": "Soğuk oda personeli KKD (mont + termal eldiven)",
        "primary": "6331 md. 10 (KKD) + Kişisel Koruyucu Donanımların İşyerlerinde Kullanılması Hakkında Yönetmelik md. 5, 6",
        "secondary": "6331 md. 16 (bilgilendirme) + 17 (eğitim)",
        "ipc": "6331 md. 26/1-g → 22.194 TL/çalışan (bilgilendirme eksik) + KKD yönetmeliği cezası",
        "criminal": "TCK 89 (soğuk yanığı / donma)",
        "civil": "TBK 417 + SGK (meslek hastalığı)",
        "consequence": "Termal eldiven + bot + mont olmadan soğuk depoda çalışma; 5+ saat -20°C'de hipotermi riski",
        "severity": "medium",
    },
    50: {
        "topic": "Transpalet/istifleyici periyodik kontrol",
        "primary": "İş Ekipmanları Yönetmeliği md. 13, 14 (kaldırma/istif makineleri periyodik kontrol) + Türk Gıda Kodeksi Gıda Hijyeni Yönetmeliği (RG 17.12.2011)",
        "secondary": "6331 md. 10; TS EN ISO 3691-1 (forklift güvenliği); İş Makineleri Yönetmeliği",
        "ipc": "6331 md. 26/1-ç → 66.725 – 200.175 TL + İş Ekipmanları Yönetmeliği cezası",
        "criminal": "TCK 85 (bakımsız transpalet → ezilme → ölüm)",
        "civil": "TBK 417",
        "consequence": "Yılda 1 periyodik kontrol; yetkili servisçe yapılmalı. Rapor saklanmalı",
        "severity": "high",
    },

    # ================== 6. KKD VE HİJYEN ==================
    51: {
        "topic": "Mutfak personeli kesilmez eldiven",
        "primary": "Kişisel Koruyucu Donanımların İşyerlerinde Kullanılması Hakkında Yönetmelik md. 5, 6",
        "secondary": "6331 md. 10 + 16 (bilgilendirme) + 17 (eğitim); TS EN 388 (kesilmeye direnç)",
        "ipc": "6331 md. 26/1-g → 22.194 TL/çalışan + KKD Yön. cezası",
        "criminal": "TCK 89 (eldiven yoksa el kesilmesi → yaralanma)",
        "civil": "TBK 417 + SGK",
        "consequence": "Seviye 5 (EN 388) standart; bıçak kullanımı, dilimleme için zorunlu",
        "severity": "medium",
    },
    52: {
        "topic": "Sıcak yağ + kimyasal — ısı/kimyasal dayanıklı KKD",
        "primary": "Kişisel Koruyucu Donanımlar Yönetmeliği + 6331 md. 10 + 5996 sayılı Kanun md. 29 (gıda hijyeni)",
        "secondary": "TS EN 407 (ısı riski); TS EN 374 (kimyasal); TS EN 166 (göz); Türk Gıda Kodeksi Gıda Hijyeni Yönetmeliği (RG 17.12.2011)",
        "ipc": "6331 md. 26/1-g → 22.194 TL/çalışan (KKD); 5996 md. 41 (gıda güvenliği çapraz bulaş riski)",
        "criminal": "TCK 89 (yanık + kimyasal yanık); 5996 md. 41 kapsamında gıda güvensizliği",
        "civil": "TBK 417",
        "consequence": "2 farklı işlem = 2 farklı KKD seti. Sıcak yağ için ısıya dayanıklı, kimyasal için asit/baz dayanıklı. Gıda temas yüzeylerinde çapraz bulaşı önleyecek KKD prosedürü zorunlu (5996 hijyen)",
        "severity": "medium",
    },
    53: {
        "topic": "Mutfak/servis ayakkabıları kaymaz (SRC sertifikalı)",
        "primary": "Kişisel Koruyucu Donanımlar Yönetmeliği + 6331 md. 10",
        "secondary": "TS EN ISO 20345 (güvenlik ayakkabısı); SRC = kayma direnci standardı",
        "ipc": "6331 md. 26/1-g → 22.194 TL/çalışan",
        "criminal": "TCK 89 (kayma → düşme → kırık)",
        "civil": "TBK 417 + SGK",
        "consequence": "SRC sertifikalı taban = seramik + çelik yüzeyde kaymaz. Tüm mutfak/servis personeli için",
        "severity": "medium",
    },
    54: {
        "topic": "KKD Zimmet Formları",
        "primary": "Kişisel Koruyucu Donanımlar Yönetmeliği md. 8 (teslim belgesi)",
        "secondary": "6331 md. 10",
        "ipc": "6331 md. 26/1-ç → 66.725 – 200.175 TL (risk değerlendirmesi eksik)",
        "criminal": "TCK 89 (zimmet yoksa KKD kullanılmadığının ispat edilememesi)",
        "civil": "TBK 417 + SGK rücu",
        "consequence": "İmzasız zimmet = KKD teslim edilmemiş sayılır; müfettiş için direkt delil",
        "severity": "medium",
    },
    55: {
        "topic": "Bulaşıkhane KKD (su geçirmez önlük + kaymaz çizme)",
        "primary": "Kişisel Koruyucu Donanımlar Yönetmeliği + 6331 md. 10",
        "secondary": "TS EN 343 (su geçirmez); TS EN ISO 20345 (kaymaz çizme)",
        "ipc": "6331 md. 26/1-g → 22.194 TL/çalışan",
        "criminal": "TCK 89 (ıslak zeminde kayma → düşme)",
        "civil": "TBK 417",
        "consequence": "Bulaşıkhane = ıslak + kimyasal ortam; özel KKD seti gerekli",
        "severity": "medium",
    },
    56: {
        "topic": "Soyunma odaları — çift bölmeli kilitli dolaplar",
        "primary": "6331 md. 10 (hijyen) + Gıda Hijyeni Yönetmeliği md. 6 + Kişisel Koruyucu Donanımların İşyerlerinde Kullanılması Hakkında Yön. m. 6",
        "secondary": "Gıda İşletmelerinde Çalışan Hijyeni; Türk Gıda Kodeksi",
        "ipc": "6331 md. 26/1-ç + 5996 sayılı md. 36 → 10.000 – 50.000 TL",
        "criminal": "TCK 89 (çapraz kontaminasyon → gıda zehirlenmesi)",
        "civil": "TBK 417 + müşteri tazminatı",
        "consequence": "Çift bölme = temiz/kirli ayrımı; gıda sektöründe çapraz kontaminasyon riski",
        "severity": "medium",
    },
    57: {
        "topic": "Tuvalet/el yıkama — sabun, havlu, dezenfektan",
        "primary": "6331 md. 10 + Gıda Hijyeni Yönetmeliği md. 6 + Kişisel Koruyucu Donanımların İşyerlerinde Kullanılması Hakkında Yön. m. 6",
        "secondary": "5996 sayılı Kanun",
        "ipc": "6331 md. 26/1-ç + 5996 md. 36 → 10.000 – 50.000 TL",
        "criminal": "TCK 89 (yetersiz hijyen → bulaşma)",
        "civil": "TBK 417 + müşteri tazminatı",
        "consequence": "Her zaman mevcut olmalı; 3'ü de aynı anda. Eksik = gıda sektörü için direkt ihlal",
        "severity": "medium",
    },
    58: {
        "topic": "Çalışanlar aksesuar/ziynet çıkarmış",
        "primary": "Gıda Hijyeni Yönetmeliği md. 7 (kişisel hijyen) + Kişisel Koruyucu Donanımların İşyerlerinde Kullanılması Hakkında Yön. m. 6",
        "secondary": "Türk Gıda Kodeksi Gıda Hijyeni; 5996 sayılı Kanun",
        "ipc": "5996 md. 36 → 10.000 – 50.000 TL + 6331 md. 26/1-g (bilgilendirme)",
        "criminal": "TCK 89 (yüzükten düşen taş → müşteri boğulma; saat yaralanma); TCK 185 (gıda kontaminasyonu)",
        "civil": "TBK 417 + müşteri tazminatı",
        "consequence": "Yüzük + saat + bileklik; düşen taş müşteri için hayati risk. Gıda sektörü için KRİTİK",
        "severity": "medium",
    },
    59: {
        "topic": "Personel dinlenme alanları temiz, havalandırılabilir, mutfaktan tecrit",
        "primary": "Gıda Hijyeni Yönetmeliği md. 6 + 6331 md. 10 + Kişisel Koruyucu Donanımların İşyerlerinde Kullanılması Hakkında Yön. m. 6",
        "secondary": "Türk Gıda Kodeksi; 5996 sayılı Kanun",
        "ipc": "5996 md. 36 → 10.000 – 50.000 TL + 6331 md. 26/1-ç",
        "criminal": "TCK 89 (çapraz kontaminasyon)",
        "civil": "TBK 417 + müşteri tazminatı",
        "consequence": "Dinlenme alanı mutfaktan ayrı; havalandırma ayrı. Çapraz kontaminasyon riski",
        "severity": "medium",
    },
    60: {
        "topic": "Temizlik kimyasalları gıdadan ayrı kilitli alanda",
        "primary": "Gıda Hijyeni Yönetmeliği md. 10 (kimyasal depolama) + Kişisel Koruyucu Donanımların İşyerlerinde Kullanılması Hakkında Yön. m. 6",
        "secondary": "6331 md. 10; Türk Gıda Kodeksi; 5996 sayılı Kanun; Kimyasalların Yönetimi Yönetmeliği",
        "ipc": "5996 md. 36 → 10.000 – 50.000 TL + 6331 md. 26/1-ç",
        "criminal": "TCK 89 (kimyasal bulaşma → gıda zehirlenmesi → yaralanma)",
        "civil": "TBK 417 + müşteri tazminatı",
        "consequence": "Ayrı kilitli oda; havalandırma. Çapraz kontaminasyon KRİTİK riski",
        "severity": "medium",
    },

    # ================== 7. BİNA / YAPI / ZEMİN ==================
    61: {
        "topic": "Zemin düzgün ve güvenli (kırık karo, çukur yok)",
        "primary": "6331 md. 10 (kayma/düşme riski) + İş Sağlığı ve Güvenliği Risk Değerlendirmesi Yönetmeliği",
        "secondary": "TS EN 13552 (kaymaz zemin); Yapı Kanunu",
        "ipc": "6331 md. 26/1-ç → 66.725 – 200.175 TL",
        "criminal": "TCK 89 (takılma → düşme → kırık/yaralanma)",
        "civil": "TBK 417 + SGK",
        "consequence": "Müşteri + çalışan kayma/düşme riski; 3. şahıslar da tazminat talep edebilir",
        "severity": "medium",
    },
    62: {
        "topic": "Islak zemin uyarı konisi",
        "primary": "Sağlık ve Güvenlik İşaretleri Yönetmeliği + 6331 md. 10",
        "secondary": "TS EN ISO 7010 (uyarı işaretleri)",
        "ipc": "6331 md. 26/1-ç → 66.725 – 200.175 TL + İşaret Yön. cezası",
        "criminal": "TCK 89 (konisiz ıslak zemin → müşteri/çalışan kayma → yaralanma)",
        "civil": "TBK 417 + SGK",
        "consequence": "Basit ama sıkı denetlenen; her paspas + temizlik sonrası koni şart",
        "severity": "medium",
    },
    63: {
        "topic": "Merdiven kaydırmaz bant (anti-slip tape)",
        "primary": "6331 md. 10 + Yapı İşlerinde İSG Yönetmeliği",
        "secondary": "TS EN 13552 (kaymaz yüzey)",
        "ipc": "6331 md. 26/1-ç → 66.725 – 200.175 TL",
        "criminal": "TCK 89 (bant yoksa merdivenden kayma → düşme → kırık)",
        "civil": "TBK 417 + SGK",
        "consequence": "Bant yıpranması kontrol edilmeli; her basamağın kenarında. Müşteri alanında özellikle önemli",
        "severity": "medium",
    },
    64: {
        "topic": "Merdiven korkuluk/tutamak",
        "primary": "Binaların Yangından Korunması Yönetmeliği md. 32 (kaçış yolu) + Yapı İşleri İSG Yönetmeliği",
        "secondary": "TS EN 1991-1-1 (yapısal yükler); 6331 md. 10",
        "ipc": "BYKHY md. 49 + 6331 md. 26/1-ç → toplam 27.000+ TL",
        "criminal": "TCK 89 (korkuluksuz merdivenden düşme → ölüm/yaralanma)",
        "civil": "TBK 417 + SGK",
        "consequence": "4+ basamaklı tüm merdivenlerde; min 90 cm yükseklik. Yıpranma kontrolü",
        "severity": "medium",
    },
    65: {
        "topic": "Tipi A Taşınabilir Merdivenler (yüksek raflara ulaşma)",
        "primary": "İş Ekipmanları Yönetmeliği + Yapı İşleri İSG Yönetmeliği",
        "secondary": "TS EN 131 (taşınabilir merdivenler); 6331 md. 10",
        "ipc": "6331 md. 26/1-ç → 66.725 – 200.175 TL",
        "criminal": "TCK 85/89 (uygunsuz merdiven → düşme → ölüm/yaralanma)",
        "civil": "TBK 417",
        "consequence": "TS EN 131 standart; kaymaz ayak, sağlam korkuluk. Periyodik kontrol",
        "severity": "high",
    },
    66: {
        "topic": "Zemin drenaj kanalları + ızgaralar (hemzemin + tıkanıksız)",
        "primary": "6331 md. 10 (kayma riski) + İş Sağlığı ve Güvenliği Risk Değerlendirmesi Yönetmeliği",
        "secondary": "TS EN 1253 (zemin süzgeçleri); Atık Su Yönetmeliği",
        "ipc": "6331 md. 26/1-ç → 66.725 – 200.175 TL",
        "criminal": "TCK 89 (tıkalı/toplanmış ızgara → kayma → düşme)",
        "civil": "TBK 417",
        "consequence": "Günlük temizlik; hemzemin = takılma yok. Müfettiş kontrol eder",
        "severity": "medium",
    },
    67: {
        "topic": "Cam kapı/paneller — çarpma önleyici ikaz şeritleri",
        "primary": "6331 md. 10 + Sağlık ve Güvenlik İşaretleri Yönetmeliği",
        "secondary": "TS EN 16005 (otomatik kapı güvenliği — AB standardı)",
        "ipc": "6331 md. 26/1-ç → 66.725 – 200.175 TL",
        "criminal": "TCK 89 (şeritsiz cama çarpma → kesik/yaralanma)",
        "civil": "TBK 417",
        "consequence": "Göz hizası; 1.5-2 m yükseklikte 2 yatay şerit (5-10 cm genişlik). Müşteri + çalışan güvenliği",
        "severity": "medium",
    },
    68: {
        "topic": "Tavanlar — nem, küf, döküntü, sızıntı yok",
        "primary": "6331 md. 10 + Gıda Hijyeni Yönetmeliği (gıda alanı tavan)",
        "secondary": "TS 2510 (yapı); Yapı Kanunu; 5996 sayılı Kanun",
        "ipc": "6331 md. 26/1-ç + 5996 md. 36 → 10.000 – 50.000 TL",
        "criminal": "TCK 89 (tavandan düşen parça → yaralanma; küf → solunum hastalığı)",
        "civil": "TBK 417 + SGK (meslek hastalığı)",
        "consequence": "Gıda alanında tavan temizliği + bakım; sızıntı = direkt gıda kontaminasyonu",
        "severity": "medium",
    },
    69: {
        "topic": "Yük indirme/bindirme alanı — düşme/çarpma önlemleri",
        "primary": "6331 md. 10 + Elle Taşıma İşleri Yönetmeliği",
        "secondary": "Yapı İşleri İSG Yönetmeliği (yük indirme/bindirme)",
        "ipc": "6331 md. 26/1-ç → 66.725 – 200.175 TL",
        "criminal": "TCK 89 (önlemsiz alanda ezilme/düşme → yaralanma)",
        "civil": "TBK 417 + SGK",
        "consequence": "Ayırıcı bariyer + uyarı işareti + eğitim. Kurye + tedarik alanı",
        "severity": "medium",
    },
    70: {
        "topic": "Asma kat/yüksek platform korkuluk (110 cm)",
        "primary": "Binaların Yangından Korunması Yönetmeliği md. 32 (korkuluk) + Yapı İşleri İSG Yönetmeliği",
        "secondary": "TS EN 1991-1-1; 6331 md. 10",
        "ipc": "BYKHY md. 49 + 6331 md. 26/1-ç → 27.000+ TL",
        "criminal": "TCK 85 (korkuluksuz yüksekten düşme → ölüm) → 2-6 yıl hapis",
        "civil": "TBK 417 + SGK",
        "consequence": "Min 110 cm; 47 cm ara korkuluk; 10 cm etek. 4+ m yükseklikte ek önlem",
        "severity": "high",
    },

    # ================== 8. ATIK / KİMYASAL / HAVALANDIRMA ==================
    71: {
        "topic": "Kimyasalların GBF/MSDS formları",
        "primary": "Kimyasalların Yönetimi Hakkında Yönetmelik md. 7 (GBF)",
        "secondary": "6331 md. 16 (bilgilendirme); SEA (1272/2008/EC) uyum; CLP Yönetmeliği",
        "ipc": "Kimyasal Yön. cezası + 6331 md. 26/1-g → 22.194 TL/çalışan",
        "criminal": "TCK 89 (GBF bilinmiyorsa yanlış müdahale → kimyasal yanık)",
        "civil": "TBK 417",
        "consequence": "Her kimyasal için GBF dosyası; Türkçe. 16 başlık zorunlu",
        "severity": "medium",
    },
    72: {
        "topic": "Etiketsiz şişelere aktarılan kimyasallar",
        "primary": "Kimyasalların Yönetimi Yönetmeliği md. 8 (etiketleme)",
        "secondary": "6331 md. 16; CLP Yönetmeliği; GHS (Küresel Uyumlaştırılmış Sistem)",
        "ipc": "Kimyasal Yön. cezası + 6331 md. 26/1-g → 22.194 TL/çalışan",
        "criminal": "TCK 89 (etiketsiz şişe → yanlış kullanım → zehirlenme)",
        "civil": "TBK 417",
        "consequence": "Aktarılan her kimyasal yeni etiket + GHS sembolü. Müfettiş özellikle bakar",
        "severity": "medium",
    },
    73: {
        "topic": "Bitkisel Atık Yağ — lisanslı firmaya veriliyor",
        "primary": "Bitkisel Atık Yağların Kontrolü Yönetmeliği (6/1/2015 RG 29204)",
        "secondary": "Çevre Kanunu md. 12, 20; 5996 sayılı Kanun",
        "ipc": "Çevre Kanunu md. 20 → 114.000+ TL (idari para cezası)",
        "criminal": "TCK 181 (çevreyi kirletme), TCK 185 (gıda güvenliği ihlali)",
        "civil": "TBK 417 + Çevre Kanunu tazminat",
        "consequence": "Belediye + Çevre Bakanlığı denetimi; lisanssız firmaya verme = çevre suçu",
        "severity": "high",
    },
    74: {
        "topic": "Mutfak havalandırma — taze hava + egzoz debisi",
        "primary": "Gıda Hijyeni Yönetmeliği md. 5 + 6331 md. 10",
        "secondary": "Binaların Yangından Korunması Yönetmeliği (davlumbaz); 5996 sayılı Kanun",
        "ipc": "5996 md. 36 → 10.000 – 50.000 TL + 6331 md. 26/1-ç",
        "criminal": "TCK 89 (yetersiz havalandırma → CO birikimi veya dumana maruz kalma)",
        "civil": "TBK 417 + SGK",
        "consequence": "Müşteri/çalışan CO zehirlenmesi, duman solunması. Restoran için KRİTİK",
        "severity": "medium",
    },
    75: {
        "topic": "Davlumbaz baca yağ temizliği — yetkili firma",
        "primary": "Binaların Yangından Korunması Yönetmeliği md. 27 (davlumbaz) + Gıda Hijyeni Yönetmeliği",
        "secondary": "6331 md. 10; Çevre Kanunu (atık yağ bertarafı)",
        "ipc": "BYKHY md. 49 → 5.000 – 50.000 TL + 6331 md. 26/1-ç",
        "criminal": "TCK 85 (yağ birikimi → yangın → ölüm) → 2-6 yıl hapis",
        "civil": "TBK 417",
        "consequence": "Yağ birikimi 0.5mm = alev alabilir. Yılda en az 1 kez yetkili temizlik + rapor",
        "severity": "high",
    },
    76: {
        "topic": "Kimyasal Döküntü Kiti",
        "primary": "Kimyasalların Yönetimi Yönetmeliği + 6331 md. 10",
        "secondary": "Güvenlik Bilgi Formları (GBF) madde 6 (önlemler); 6331 md. 11 (acil durum)",
        "ipc": "6331 md. 26/1-d → 22.194 – 66.663 TL (acil durum yetersizliği)",
        "criminal": "TCK 89 (kit yoksa dökülen kimyasal → müşteri/çalışan yaralanması)",
        "civil": "TBK 417 + Çevre Kanunu tazminat",
        "consequence": "Asit + baz + yanıcı için ayrı kitler. Erişilebilir konumda. Müfettiş kontrol eder",
        "severity": "medium",
    },
    77: {
        "topic": "Atık alanları + çöp odaları — pest kontrolü",
        "primary": "Gıda Hijyeni Yönetmeliği + 6331 md. 10",
        "secondary": "Çevre Kanunu; Haşere Kontrol Yönetmeliği",
        "ipc": "5996 md. 36 → 10.000 – 50.000 TL + 6331 md. 26/1-ç",
        "criminal": "TCK 89 (haşere → gıda kontaminasyonu → hastalık)",
        "civil": "TBK 417 + müşteri tazminatı",
        "consequence": "Aylık ilaçlama + profesyonel firma raporu. Çöp odası ayrı havalandırma",
        "severity": "medium",
    },
    78: {
        "topic": "Gaz tüpleri (LPG, CO2) — dik + zincir sabitleme",
        "primary": "Basınçlı Ekipmanlar Yönetmeliği + Tehlikeli Maddeler Yönetmeliği",
        "secondary": "6331 md. 10; TS EN 1442 (LPG tüpleri); LPG Tüpleri Yönetmeliği",
        "ipc": "Basınçlı Ekipmanlar Yön. + 6331 md. 26/1-ç → 27.000+ TL",
        "criminal": "TCK 85 (devrilen LPG → patlama → toplu ölüm) → 2-6 yıl hapis",
        "civil": "TBK 417 + 3. şahıslar (restoran + çevre)",
        "consequence": "Restoran için KRİTİK; LPG patlaması en büyük risk. Zincir + duvar mesafesi + vanalar kontrol",
        "severity": "high",
    },

    # ================== 9. İLK YARDIM / MÜŞTERİ ==================
    79: {
        "topic": "İlk Yardım Dolabı (monte + kilitli + güncel)",
        "primary": "6331 md. 11/1 (Acil durum) + İlkyardım Yönetmeliği (22/5/2002 RG 24762)",
        "secondary": "6331 md. 12 (ilk yardım); Sağlık Bakanlığı İlkyardım Yönetmeliği",
        "ipc": "6331 md. 26/1-d → 22.194 – 66.663 TL",
        "criminal": "TCK 89 (ilk yardım yoksa yaralanma ağırlaşması)",
        "civil": "TBK 417 + SGK",
        "consequence": "Her 10 çalışan için 1 ilk yardım dolabı; yetkili sertifikalı ilk yardımcı. İçerik 6 ayda yenilenir",
        "severity": "medium",
    },
    80: {
        "topic": "Bebek sandalyesi emniyet kemeri",
        "primary": "Tüketicinin Korunması Hakkında Kanun (6502) + 6331 md. 10",
        "secondary": "TS EN 14988 (çocuk sandalyesi güvenliği); Tüketicinin Korunması Yönetmeliği",
        "ipc": "6331 md. 26/1-ç → 66.725 – 200.175 TL + 6502 md. cezası (ürün güvenliği)",
        "criminal": "TCK 89 (kemer kopması → çocuk yaralanması)",
        "civil": "TBK 417 + 6502 (tüketici tazminatı)",
        "consequence": "Aile + küçük çocuk = hassas grup; her sandalyede 5 nokta kemer zorunlu",
        "severity": "medium",
    },
    81: {
        "topic": "Oyun alanı/playland periyodik güvenlik denetimi",
        "primary": "Tüketicinin Korunması Kanunu (6502) + 6331 md. 10",
        "secondary": "TS EN 1176 (oyun alanı ekipmanları); Tüketicinin Korunması Yönetmeliği",
        "ipc": "6331 md. 26/1-ç → 66.725 – 200.175 TL + 6502 md. cezası",
        "criminal": "TCK 85 (bakımsız oyun alanı ekipmanı → çocuk ölümü/yaralanması) → 2-6 yıl hapis",
        "civil": "TBK 417 + 6502 (tüketici tazminatı)",
        "consequence": "Yılda 1 kez + her ciddi kazadan sonra denetim. Ekipman + zemin + çevre kontrolü",
        "severity": "high",
    },
    82: {
        "topic": "Self-servis kırılabilir cam yerine kırılmaz muhafaza",
        "primary": "Tüketicinin Korunması Kanunu (6502) + 6331 md. 10",
        "secondary": "TS EN 12150 (güvenlik camı); Tüketicinin Korunması Yönetmeliği",
        "ipc": "6331 md. 26/1-ç + 6502 md. → 27.000+ TL",
        "criminal": "TCK 89 (kırılan cam → müşteri kesiği)",
        "civil": "TBK 417 + 6502",
        "consequence": "Tüm cam eşyalar için tamper-proof muhafaza; bardak, kavanoz, şişe dahil",
        "severity": "medium",
    },
    83: {
        "topic": "Otomatik kayar kapı emniyet fotoseli",
        "primary": "6331 md. 10 + TS EN 16005 (otomatik kapı güvenliği — AB standardı)",
        "secondary": "Yapı İşleri İSG Yönetmeliği; 6502 (tüketici güvenliği)",
        "ipc": "6331 md. 26/1-ç + 6502 → 27.000+ TL",
        "criminal": "TCK 89 (fotosel yoksa kapı sıkıştırması → yaralanma)",
        "civil": "TBK 417",
        "consequence": "Ağır yaralanma riski (kapanan kapı arasında sıkışma); çocuk + yaşlı için ek önlem",
        "severity": "medium",
    },
    84: {
        "topic": "Kurye motor park + batarya şarj alanı yangın önlemleri",
        "primary": "6331 md. 10 + Elektrik İç Tesisleri Yönetmeliği",
        "secondary": "Binaların Yangından Korunması Yönetmeliği; UN 38.3 (lityum batarya test standardı)",
        "ipc": "BYKHY md. 49 + 6331 md. 26/1-ç → 27.000+ TL",
        "criminal": "TCK 85 (lityum batarya yangını → patlama → ölüm) → 2-6 yıl hapis",
        "civil": "TBK 417",
        "consequence": "Açık alanda şarj; lityum batarya termal kaçak riski. CO2 veya köpük söndürücü + havalandırma",
        "severity": "high",
    },
}


# ============== RAPOR OLUŞTUR ==============

def format_ipc_short(ipc_str):
    """Kısa ceza özeti çıkar"""
    return ipc_str[:60] + "..." if len(ipc_str) > 60 else ipc_str

# Kategorileri organize et
categories = {}
for q in questions:
    cat = q["category"]
    if cat not in categories:
        categories[cat] = []
    categories[cat].append(q)

# Markdown rapor
md = []
md.append("# 84 İSG Denetim Sorusu — Mevzuat & Yaptırım Haritası")
md.append("")
md.append("**Tarih:** 2026-08-23")
md.append("**Yeniden Değerleme Oranı:** %25,49 (2026)")
md.append("**Kaynak:** 6331 sayılı Kanun md. 26 (ÇSGB 2026 İdari Para Cezaları) + ilgili yönetmelikler + TCK + TBK + 5510")
md.append("")
md.append("## 📋 Yasal Çerçeve Özeti")
md.append("")
md.append("Her HAYIR cevabı için **üç katmanlı yaptırım** söz konusudur:")
md.append("")
md.append("| Katman | Tür | Yetkili | Tipik Sonuç |")
md.append("|---|---|---|---|")
md.append("| **1. İdari** | 6331 md. 26 + sektörel kanunlar | ÇSGB müfettişi, Gıda, Çevre, Belediye | İdari para cezası (44.443 – 5.342.706 TL arası) |")
md.append("| **2. Cezai** | TCK 85 (taksirle ölüm), 89 (taksirle yaralama) | Cumhuriyet Savcısı | 2-6 yıl hapis (ölüm) / 3 ay-3 yıl (yaralanma) |")
md.append("| **3. Hukuki** | TBK 417 (işverenin koruma yükümlülüğü), 6502 (tüketici) | Mahkeme | Maddi + manevi tazminat |")
md.append("")
md.append("**Ayrıca:** 5510 sayılı SGK bildirimi yapılmamış kaza için ayrı ceza; işveren vekili bizzat yargılanabilir (TCK 66/2).")
md.append("")

# Kategori bazlı özet
md.append("## 📊 9 Kategori — Hızlı Bakış")
md.append("")
md.append("| # | Kategori | Soru Sayısı | Ana Mevzuat | En Yüksek Risk |")
md.append("|---|---|---|---|---|")
md.append("| 1 | Genel İSG Organizasyonu & Belgeleme | 10 | 6331 md. 4-22, 5996 | Hijyen eğitimi (#9), risk değerlendirmesi (#4) |")
md.append("| 2 | Yangın Güvenliği, Acil Durum | 10 | BYKHY, 6331 md. 11 | Davlumbaz söndürme (#13), kaçış yolu (#15) |")
md.append("| 3 | Elektrik ve Tesisat | 10 | Elektrik İç Tesisleri Yön., 6331 md. 10 | Kaçak akım rölesi (#21), yetkili personel (#30) |")
md.append("| 4 | Mutfak, Pişirme, Kızartma | 10 | İş Ekipmanları Yön., Gıda Kodeksi | Fritöz termostat (#31), ANSUL (#13) |")
md.append("| 5 | Soğuk Depo, Depolama, Ergonomi | 10 | 6331 md. 10, Elle Taşıma, İş Ekipmanları | Soğuk depo mandalı (#41), raf sabitleme (#44) |")
md.append("| 6 | KKD ve Hijyen | 10 | KKD Yönetmeliği, Gıda Hijyeni Yönetmeliği | Aksesuar çıkarma (#58), kimyasal depolama (#60) |")
md.append("| 7 | Bina, Yapı, Zemin, Merdivenler | 10 | 6331 md. 10, Yapı İşleri Yön. | Asma kat korkuluk (#70), zemin (#61) |")
md.append("| 8 | Atık, Kimyasal, Havalandırma | 8 | Çevre Kanunu, Kimyasallar Yönetmeliği | LPG sabitleme (#78), davlumbaz temizlik (#75) |")
md.append("| 9 | İlk Yardım, Müşteri Alanları | 6 | 6331 md. 11, 6502, İlkyardım Yön. | Playland denetim (#81), kayan kapı (#83) |")
md.append("")

# Soru bazlı detay tablo
md.append("## 📋 Soru Bazlı Detay Tablo (84 satır)")
md.append("")
md.append("| # | Konu | Birincil Mevzuat | İdari Para Cezası (2026) | Cezai Risk |")
md.append("|---|---|---|---|---|")

for q in questions:
    qid = q["id"]
    if qid in REGULATORY_MAP:
        m = REGULATORY_MAP[qid]
        primary_short = m["primary"].split("+")[0].strip()[:35]
        ipc_short = m["ipc"].split("→")[1].strip()[:40] if "→" in m["ipc"] else m["ipc"][:40]
        criminal = "TCK 85/89" if "85" in m["criminal"] or "89" in m["criminal"] else "TCK (sektörel)"
        md.append(f"| {qid} | {m['topic']} | {primary_short} | {ipc_short} | {criminal} |")

md.append("")
md.append("> ⚠️ **Yaptırım tutarları sadece temel/alt sınırdır.** Tehlike sınıfı + çalışan sayısına göre **+%25 ile +%200 artırım** uygulanır (6331 md. 26/4).")
md.append("> Örnek: Tehlikeli sınıf, 10-49 çalışanlı restoran için risk değerlendirmesi cezası 66.725 × 1.5 = **100.087 TL/ay**.")
md.append("")

# Kategori detayları
md.append("## 📑 Kategori Detayları (84 Soru)")
md.append("")

for cat_name, cat_questions in categories.items():
    md.append(f"### {cat_name}")
    md.append("")
    for q in cat_questions:
        qid = q["id"]
        if qid not in REGULATORY_MAP:
            continue
        m = REGULATORY_MAP[qid]
        md.append(f"#### #{qid} — {m['topic']}")
        md.append(f"_{q['question']}_")
        md.append("")
        md.append(f"- **Birincil mevzuat:** {m['primary']}")
        if "secondary" in m and m["secondary"]:
            md.append(f"- **İkincil mevzuat:** {m['secondary']}")
        md.append(f"- **İdari para cezası:** {m['ipc']}")
        md.append(f"- **Cezai sorumluluk:** {m['criminal']}")
        md.append(f"- **Hukuki sorumluluk:** {m['civil']}")
        md.append(f"- **Sonuç:** {m['consequence']}")
        md.append("")

# Risk skoru özeti
md.append("## 🎯 En Yüksek Riskli 10 Soru (HAYIR cezai sorumluluk doğurur)")
md.append("")
md.append("Aşağıdaki sorularda HAYIR cevabı, kaza halinde **TCK 85 (taksirle ölüm, 2-6 yıl hapis)** kapsamına girer:")
md.append("")
md.append("| # | Soru | Neden Kritik |")
md.append("|---|---|---|")
md.append("| **13** | Davlumbaz Otomatik Söndürme (ANSUL) | Yağ yangınında büyüme → toplu ölüm riski |")
md.append("| **19** | Gaz kesme solenoid + alarm entegrasyonu | Gaz kaçağı + entegre olmayan solenoid → patlama |")
md.append("| **21** | Kaçak Akım Rölesi | Elektrik çarpması → ölüm (en sık neden) |")
md.append("| **30** | Elektrik arıza — yetkili personel | Ehliyetsiz işçi çalıştırma → çarpılma |")
md.append("| **31** | Fritöz termostat + emniyet limit | Termostatsız fritöz → yağ yangını |")
md.append("| **41** | Soğuk depo içeriden açma mandalı | Mahsur kalma → hipotermi/boğulma → ölüm |")
md.append("| **48** | İstif yüksekliği (sprinkler 50cm) | Sprinkler engellenmiş → yangın büyümesi |")
md.append("| **70** | Asma kat korkuluk (110 cm) | Korkuluksuz yüksekten düşme → ölüm |")
md.append("| **75** | Davlumbaz baca yağ temizliği | Yağ birikimi → yangın |")
md.append("| **78** | LPG tüp sabitleme (zincir) | Devrilen tüp → patlama → toplu ölüm |")
md.append("| **81** | Playland periyodik denetim | Bakımsız ekipman → çocuk yaralanması/ölümü |")
md.append("| **84** | Lityum batarya şarj alanı | Batarya termal kaçak → patlama → ölüm |")
md.append("")

# Tazminat örnekleri
md.append("## 💰 Pratik Tazminat Örnekleri (TBK 417)")
md.append("")
md.append("| Kaza | HAYIR Sorular | Tahmini Tazminat |")
md.append("|---|---|---|")
md.append("| Elektrik çarpması → ölüm | #21, #22, #23, #26, #27, #30 | 1.500.000 – 4.000.000 TL (manevi dahil) |")
md.append("| Yangın → çalışan ölümü | #13, #15, #17, #19, #75 | 2.000.000 – 5.000.000 TL |")
md.append("| Yangın → müşteri ölümü | #13, #14, #15, #16, #19 | 3.000.000 – 8.000.000 TL + cezai |")
md.append("| LPG patlaması | #19, #78 | 5.000.000+ TL (toplu ölüm/yaralanma) |")
md.append("| Gıda zehirlenmesi | #9, #56, #57, #58, #59, #60 | 200.000 – 1.000.000 TL + 5996 cezası |")
md.append("| Kayma/düşme → kırık | #61, #62, #63, #64 | 100.000 – 500.000 TL |")
md.append("| Mutfak yanık | #31, #33, #52 | 50.000 – 300.000 TL |")
md.append("")

# Önemli notlar
md.append("## ⚠️ Önemli Yasal Notlar")
md.append("")
md.append("1. **İşveren vekili bizzat yargılanır.** 6331 md. 4 + TCK 66/2 uyarınca İSG yükümlülüklerini yerine getirmeyen işveren vekili bizzat sanık olur, para cezası kişisel ödenir.")
md.append("2. **SGK rücu hakkı.** 5510 md. 21 uyarınca, iş kazası sonucu SGK ödediği tazminatı işverene rücu eder (kazanın işveren kusurundan kaynaklandığı tespit edilirse).")
md.append("3. **Tazminatta zamanaşımı.** TBK 417 davası için zamanaşımı kaza tarihinden itibaren 5 yıl (iş kazası), 10 yıl (ölüm). Manevi tazminat için 5 yıl.")
md.append("4. **Ağır kusur.** Yukarıdaki yüksek riskli sorularda HAYIR varsa, mahkeme **ağır kusur** atfeder — tazminat indirimi uygulanmaz, cezada artırım olur.")
md.append("5. **İş durdurma.** 6331 md. 25 uyarınca hayati tehlike oluşturan hallerde müfettiş işi durdurur; bu durumda işveren hiç gelir elde edemez.")
md.append("6. **ÇSGB'nin 2026 tarifesi.** Yeniden değerleme oranı her yıl değişir; 2026 için %25,49. Bir sonraki güncelleme 1 Ocak 2027.")
md.append("")
md.append("## 📚 Kullanılan Mevzuat")
md.append("")
md.append("- **Ana kanunlar:** 6331 İSG Kanunu, 4857 İş Kanunu, 6098 TBK, 5237 TCK, 5510 SSGSS, 6502 Tüketici Kanunu, 5996 Gıda Kanunu, 2872 Çevre Kanunu, 1593 Umumi Hıfzıssıhha Kanunu")
md.append("- **Yönetmelikler:** İSG Risk Değerlendirmesi, Çalışanların İSG Eğitimleri, İşyerlerinde Acil Durumlar, İş Ekipmanları Kullanımı, KKD İşyerlerinde Kullanımı, Kişisel Koruyucu Donanımlar, Binaların Yangından Korunması, Elektrik İç Tesisleri, Gıda Hijyeni, Elle Taşıma İşleri, Hijyen Eğitimi, Bitkisel Atık Yağların Kontrolü, İlkyardım")
md.append("- **Standartlar (TS/TSE):** TS EN 54, TS EN 131, TS EN 388, TS EN 671-1, TS EN 1869, TS EN 1176, TS EN 12150, TS EN 16005, TS EN ISO 20345, TS EN ISO 7010")
md.append("")



if __name__ == '__main__':
    # Rapor yazma (sadece CLI olarak calistirildiginda)
    # Çıktı
    out_path = ROOT.parent / "reports" / "u4-questions-regulatory-map-2026-08-23.md"
    out_path.parent.mkdir(exist_ok=True, parents=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md))
    
    print(f"Rapor yazildi: {out_path}")
    print(f"Toplam {len(REGULATORY_MAP)} soru haritalandi.")
    print(f"Kategoriler: {len(categories)}")
    print(f"Sorular: {len(questions)}")
