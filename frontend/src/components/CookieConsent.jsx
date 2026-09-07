/**
 * KVKK / GDPR Cookie Consent Banner — UI/UX P0
 *
 * Türkiye KVKK ve AB GDPR uyumu için zorunlu. Ziyaretçi ilk kez
 * geldiğinde oturum/çerez kullanımı hakkında bilgilendirilir ve
 * onayı alınır. Onay ``localStorage``'da saklanır; bir daha sorulmaz.
 *
 * Banner konumu: ekranın alt-orta, sticky.
 *
 * Neden gerekli:
 *   - HttpOnly auth cookie kullanılıyor (oturum için)
 *   - ``localStorage`` autosave recovery için kullanılıyor
 *   - Yani "teknik zorunlu çerezler" kategorisinde — kullanıcı
 *     bilgilendirilmeli ve reddetme hakkı saklı kalmalı
 *
 * Not: Reddetme durumunda uygulama yine çalışır (teknik çerezler
 * zorunlu); sadece kullanıcı bilgilendirilmiş olur.
 */
import React, { useState, useEffect } from "react";
import { Cookie, X, ShieldCheck, ChevronDown, ChevronUp } from "lucide-react";

const STORAGE_KEY = "kvkk_consent_v1";

const CONSENT_VERSION = "1.0";

export default function CookieConsent() {
  const [visible, setVisible] = useState(false);
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    // İlk mount'ta kontrol — daha önce onaylanmış mı?
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (!stored) {
        setVisible(true);
        return;
      }
      const parsed = JSON.parse(stored);
      // Versiyon değiştiyse yeniden sor
      if (parsed?.version !== CONSENT_VERSION) {
        setVisible(true);
      }
    } catch (_) {
      // parse hatası → yeniden sor
      setVisible(true);
    }
  }, []);

  const handleAccept = () => {
    try {
      localStorage.setItem(
        STORAGE_KEY,
        JSON.stringify({
          version: CONSENT_VERSION,
          accepted: true,
          acceptedAt: new Date().toISOString(),
        }),
      );
    } catch (_) {
      // localStorage yazılamadı (private mode) — banner'ı yine de kapat
    }
    setVisible(false);
  };

  const handleDecline = () => {
    // Reddetme durumunda da onayı kaydet (sadece bilgilendirme yaptık)
    try {
      localStorage.setItem(
        STORAGE_KEY,
        JSON.stringify({
          version: CONSENT_VERSION,
          accepted: false,
          acceptedAt: new Date().toISOString(),
        }),
      );
    } catch (_) {}
    setVisible(false);
  };

  const handleClose = () => {
    setVisible(false);
  };

  if (!visible) return null;

  return (
    <div
      className="fixed bottom-4 left-4 right-4 sm:left-1/2 sm:right-auto sm:bottom-6 sm:translate-x-[-50%] z-[100] max-w-2xl font-sans"
      role="dialog"
      aria-label="Çerez kullanımı bildirimi"
      data-testid="cookie-consent-banner"
    >
      <div className="surface-card border border-slate-200 dark:border-border rounded-card shadow-2xl overflow-hidden">
        {/* HEADER */}
        <div className="flex items-start gap-3 p-4 sm:p-5">
          <div className="w-10 h-10 rounded-card bg-amber-100 dark:bg-amber-500/20 flex items-center justify-center shrink-0">
            <Cookie className="w-5 h-5 text-amber-600 dark:text-amber-400" />
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <h3 className="text-sm font-extrabold text-slate-900 dark:text-white">
                Çerez Kullanımı
              </h3>
              <span className="text-[10px] uppercase tracking-wider font-bold text-amber-600 dark:text-amber-400 bg-amber-50 dark:bg-amber-500/10 border border-amber-200 dark:border-amber-500/30 px-1.5 py-0.5 rounded">
                KVKK / GDPR
              </span>
            </div>
            <p className="text-xs text-slate-600 dark:text-slate-400 mt-1 leading-relaxed">
              Bu uygulama oturum yönetimi için zorunlu çerezler ve taslak
              kurtarma için yerel depolama kullanır. Kişisel verileriniz
              <strong className="text-slate-900 dark:text-white"> üçüncü taraflarla paylaşılmaz</strong>;
              yalnızca ABCD Tech Solutions İSG ekibi tarafından denetim amacıyla işlenir.
            </p>
          </div>
          <button
            type="button"
            onClick={handleClose}
            data-testid="cookie-consent-close"
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-700 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors shrink-0"
            aria-label="Kapat"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* EXPANDED DETAILS */}
        {expanded && (
          <div className="px-5 pb-2 text-[11px] text-slate-600 dark:text-slate-400 space-y-2 border-t border-slate-200 dark:border-white/10 pt-3">
            <div className="space-y-1">
              <div className="flex items-center gap-1.5 text-slate-800 dark:text-slate-200 font-semibold">
                <ShieldCheck className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400" />
                Teknik / Zorunlu Çerezler
              </div>
              <p className="ml-5">
                <strong>Oturum (access_token, refresh_token):</strong> JWT tabanlı
                kimlik doğrulama için HttpOnly cookie. Reddedilemez (uygulamayı
                kullanmanız için gerekli).
              </p>
              <p className="ml-5">
                <strong>Yerel depolama (localStorage):</strong> Denetim taslağı
                kurtarma için kullanılır. Yalnızca tarayıcınızda saklanır,
                sunucuya gönderilmez.
              </p>
            </div>
            <div className="space-y-1">
              <div className="flex items-center gap-1.5 text-slate-800 dark:text-slate-200 font-semibold">
                <Cookie className="w-3.5 h-3.5 text-amber-600 dark:text-amber-400" />
                İstatistik / Analitik
              </div>
              <p className="ml-5">
                Şu an <strong className="text-emerald-600 dark:text-emerald-400">hiçbir analitik çerezi kullanılmıyor</strong>.
                Gelecekte eklendiğinde bu banner güncellenecek ve yeniden onay
                istenecektir.
              </p>
            </div>
            <p className="text-[10px] text-slate-500 dark:text-slate-500 italic">
              Veri sorumlusunun haklarınız ve KVKK Aydınlatma Metni için
              ABCD Tech Solutions İSG birimiyle iletişime geçiniz.
            </p>
          </div>
        )}

        {/* ACTIONS */}
        <div className="flex items-center gap-2 p-3 sm:p-4 bg-slate-50 dark:bg-slate-900/40 border-t border-slate-200 dark:border-white/10">
          <button
            type="button"
            onClick={() => setExpanded((v) => !v)}
            data-testid="cookie-consent-details"
            className="inline-flex items-center gap-1 px-2 py-1.5 text-[11px] font-semibold text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white transition-colors"
          >
            {expanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
            {expanded ? "Detayları gizle" : "Detayları göster"}
          </button>
          <div className="flex-1" />
          <button
            type="button"
            onClick={handleDecline}
            data-testid="cookie-consent-decline"
            className="px-3 py-1.5 rounded-lg text-xs font-semibold text-slate-700 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-800 border border-slate-200 dark:border-white/10 transition-colors"
          >
            Yalnızca Zorunlu
          </button>
          <button
            type="button"
            onClick={handleAccept}
            data-testid="cookie-consent-accept"
            className="px-4 py-1.5 rounded-lg text-xs font-bold bg-risk-critical hover:bg-risk-critical-2 text-white active:scale-95 transition-colors duration-standard ease-swift"
          >
            Kabul Et
          </button>
        </div>
      </div>
    </div>
  );
}
