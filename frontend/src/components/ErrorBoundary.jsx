/**
 * Global Error Boundary — UI/UX P0
 *
 * Herhangi bir descendant component render sırasında exception fırlatırsa
 * uygulama tamamen çökmesin; kullanıcıya bilgilendirici bir hata ekranı
 * gösterilsin. Production'da bu olmadan "beyaz ekran" kullanıcıyı
 * tamamen kaybeder.
 *
 * Strateji:
 *   1. İlk seviye ErrorBoundary App.js'in en dışında — tüm sayfaları kapsar
 *   2. Route bazlı ErrorBoundary de sayfa düzeyinde çalışabilir (hangi sayfa
 *      çöktü bilgisi için)
 *   3. Hata loglanır (Sentry/console); kullanıcıya gösterilmez ama dev'de
 *      konsola yazılır
 *
 * Kullanım:
 *   <ErrorBoundary>
 *     <App />
 *   </ErrorBoundary>
 *
 *   <ErrorBoundary fallback={<CustomErrorPage />}>
 *     <DofPage />
 *   </ErrorBoundary>
 */
import React from "react";
import { AlertTriangle, RefreshCw, Home, Copy } from "lucide-react";
import { toast } from "sonner";

export class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = {
      hasError: false,
      error: null,
      errorInfo: null,
      copied: false,
    };
  }

  static getDerivedStateFromError(error) {
    // İlk render'da state güncelle — fallback UI'a düş
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    // Production'da Sentry/LogRocket'a gönderilebilir
    // Şimdilik: console.error ile development'ta görünür
    // eslint-disable-next-line no-console
    console.error("[ErrorBoundary] Component crash:", {
      error: error?.message,
      stack: error?.stack,
      componentStack: errorInfo?.componentStack,
    });

    this.setState({ errorInfo });

    // İsteğe bağlı: backend'e rapor
    if (this.props.onError) {
      try {
        this.props.onError(error, errorInfo);
      } catch (_) {
        // reporter'ın kendi hatası UI'ı bozmasın
      }
    }
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null, errorInfo: null });
  };

  handleReload = () => {
    window.location.reload();
  };

  handleHome = () => {
    window.location.href = "/";
  };

  handleCopyDetails = async () => {
    const details = JSON.stringify(
      {
        message: this.state.error?.message,
        stack: this.state.error?.stack,
        componentStack: this.state.errorInfo?.componentStack,
        url: window.location.href,
        timestamp: new Date().toISOString(),
        userAgent: navigator.userAgent,
      },
      null,
      2,
    );
    try {
      await navigator.clipboard.writeText(details);
      this.setState({ copied: true });
      toast.success("Hata detayları kopyalandı");
      setTimeout(() => this.setState({ copied: false }), 2000);
    } catch (e) {
      toast.error("Kopyalanamadı — manuel seçiniz");
    }
  };

  render() {
    if (!this.state.hasError) {
      return this.props.children;
    }

    // Custom fallback (örn. inline mini-message) verildiyse onu kullan
    if (this.props.fallback) {
      return typeof this.props.fallback === "function"
        ? this.props.fallback(this.state.error, this.handleReset)
        : this.props.fallback;
    }

    const isDev = process.env.NODE_ENV !== "production";
    const error = this.state.error;

    return (
      <div
        className="min-h-screen flex items-center justify-center p-4 bg-[#F5F5F0] dark:bg-[#0B0F17] font-sans"
        data-testid="error-boundary"
      >
        <div className="max-w-lg w-full bg-white dark:bg-slate-950/80 border border-red-200 dark:border-red-500/30 rounded-card p-6 sm:p-8 shadow-xl">
          <div className="flex items-start gap-4 mb-6">
            <div className="w-12 h-12 rounded-card bg-red-100 dark:bg-red-500/20 flex items-center justify-center shrink-0">
              <AlertTriangle className="w-6 h-6 text-red-600 dark:text-red-400" />
            </div>
            <div className="flex-1">
              <h1 className="text-xl font-extrabold text-slate-900 dark:text-white tracking-tight">
                Beklenmeyen Bir Hata Oluştu
              </h1>
              <p className="text-sm text-slate-600 dark:text-slate-400 mt-1">
                Uygulama beklenmedik bir sorunla karşılaştı. Verileriniz
                korunuyor; sayfayı yenileyebilir veya ana panele dönebilirsiniz.
              </p>
            </div>
          </div>

          {isDev && error && (
            <div className="mb-6 space-y-3">
              <div className="p-3 bg-red-50 dark:bg-red-500/10 border border-red-200 dark:border-red-500/30 rounded-card">
                <div className="text-[11px] uppercase tracking-wider font-bold text-red-700 dark:text-red-400 mb-1">
                  Hata Mesajı (sadece development)
                </div>
                <code className="text-xs text-red-900 dark:text-red-300 font-mono break-words">
                  {error.message || String(error)}
                </code>
              </div>
              {error.stack && (
                <details className="text-[11px] text-slate-600 dark:text-slate-400">
                  <summary className="cursor-pointer font-semibold hover:text-slate-900 dark:hover:text-white">
                    Stack trace
                  </summary>
                  <pre className="mt-2 p-3 bg-slate-100 dark:bg-slate-900/80 rounded-card overflow-x-auto text-[10px] font-mono whitespace-pre-wrap break-words max-h-48 overflow-y-auto">
                    {error.stack}
                  </pre>
                </details>
              )}
            </div>
          )}

          <div className="flex flex-col sm:flex-row gap-2">
            <button
              type="button"
              onClick={this.handleReload}
              className="flex-1 inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-card text-xs font-bold bg-risk-critical hover:bg-risk-critical-2 text-white active:scale-95 transition-colors duration-standard ease-swift"
              data-testid="error-reload"
            >
              <RefreshCw className="w-4 h-4" /> Sayfayı Yenile
            </button>
            <button
              type="button"
              onClick={this.handleHome}
              className="flex-1 inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-card text-xs font-bold bg-slate-100 dark:bg-slate-900/80 border border-slate-300 dark:border-white/10 text-slate-700 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-800 transition-all active:scale-95"
              data-testid="error-home"
            >
              <Home className="w-4 h-4" /> Risk Analizi Denetim Paneli
            </button>
            {isDev && (
              <button
                type="button"
                onClick={this.handleCopyDetails}
                className="inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-card text-xs font-bold bg-white dark:bg-slate-900/80 border border-slate-300 dark:border-white/10 text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 transition-all active:scale-95"
                title="Hata detaylarını panoya kopyala"
              >
                <Copy className="w-4 h-4" /> {this.state.copied ? "Kopyalandı" : "Detay"}
              </button>
            )}
          </div>

          <div className="mt-6 pt-6 border-t border-slate-200 dark:border-white/10 text-center text-[11px] text-slate-500 dark:text-slate-400">
            Sorun devam ederse lütfen destek ekibiyle iletişime geçin.
            <br />
            <span className="font-mono">v1.0 — ABCD Tech Solutions İSG</span>
          </div>
        </div>
      </div>
    );
  }
}

export default ErrorBoundary;
