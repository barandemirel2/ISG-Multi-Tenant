import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ShieldCheck, AlertCircle } from "lucide-react";
import { formatApiErrorDetail } from "@/lib/api";
import { isPublicRegistrationEnabled } from "@/lib/registrationVisibility";
import { toast } from "sonner";

export default function LoginPage() {
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const onSubmit = async (e) => {
    e.preventDefault();
    setErr("");
    setLoading(true);
    try {
      await login(email, password);
      toast.success("Giriş başarılı — Lütfen restoran zincirini seçin");
      navigate("/brand-selection");
    } catch (e) {
      setErr(formatApiErrorDetail(e.response?.data?.detail) || e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen grid md:grid-cols-2 bg-[#FAFAFA]">
      {/* Left visual — custom SVG hero (no external Unsplash dependency) */}
      <div className="hidden md:block relative overflow-hidden">
        <img
          src="/assets/login-hero.svg"
          alt=""
          className="absolute inset-0 w-full h-full object-cover"
        />
        <div className="absolute inset-0 bg-zinc-950/75" />
        <div className="relative z-10 h-full flex flex-col justify-between p-12 text-white">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-white text-zinc-950 flex items-center justify-center rounded-control">
              <ShieldCheck className="w-6 h-6" />
            </div>
            <div>
              <div className="text-[11px] label-caps text-white/70">ABCD Tech Solutions</div>
              <div className="text-sm font-display font-bold">AI Uzman</div>
            </div>
          </div>
          <div className="max-w-md">
            <div className="text-[11px] label-caps text-white/60 mb-4">İSG — İŞ SAĞLIĞI ve GÜVENLİĞİ</div>
            <h1 className="font-display text-4xl md:text-5xl font-black leading-tight tracking-tight">
              Restoran denetimlerinizi <span className="text-amber-400">sistematik</span> ve <span className="text-emerald-400">güvenli</span> yönetin.
            </h1>
            <p className="mt-6 text-white/80 leading-relaxed text-sm">
              84 soruluk kapsamlı İSG risk değerlendirme formu ile ofis, mutfak, depo ve tüm alanlarınızı denetleyin.
              Kabul edilemez risk noktalarını anında tespit edip aksiyon planlayın.
            </p>
          </div>
          <div className="grid grid-cols-3 gap-4 text-xs">
            {[
              ["84", "Soru"],
              ["9", "Alan"],
              ["100%", "Uyumluluk"],
            ].map(([n, l]) => (
              <div key={l} className="border-t border-white/20 pt-3">
                <div className="text-2xl font-display font-black tabular-nums">{n}</div>
                <div className="label-caps text-white/60">{l}</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Right form */}
      <div className="flex items-center justify-center p-8">
        <div className="w-full max-w-sm">
          <div className="text-[11px] label-caps text-zinc-500 mb-2">Giriş Yap</div>
          <h2 className="font-display text-3xl font-black tracking-tight text-zinc-950">Denetime devam edin.</h2>
          <p className="text-sm text-zinc-500 mt-2">Hesabınıza giriş yaparak restoranınızın risk analizini yönetin.</p>

          <form onSubmit={onSubmit} className="mt-8 space-y-4" data-testid="login-form">
            <div>
              <Label htmlFor="email" className="label-caps text-zinc-700">E-posta</Label>
              <Input
                id="email"
                type="email"
                required
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                data-testid="login-email-input"
                className="mt-1 h-11"
                placeholder="ornek@firma.com"
              />
            </div>
            <div>
              <Label htmlFor="password" className="label-caps text-zinc-700">Şifre</Label>
              <Input
                id="password"
                type="password"
                required
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                data-testid="login-password-input"
                className="mt-1 h-11"
              />
            </div>
            {err && (
              <div className="flex items-start gap-2 p-3 border border-risk-critical-border bg-risk-critical-bg text-risk-critical text-sm rounded-control" data-testid="login-error">
                <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
                <div>{err}</div>
              </div>
            )}
            <Button type="submit" disabled={loading} className="w-full density-form bg-action-primary hover:bg-action-primary-hover text-action-primary-foreground transition-colors duration-standard ease-swift" data-testid="login-submit-btn">
              {loading ? "Giriş yapılıyor…" : "Giriş Yap"}
            </Button>
          </form>

          <div className="mt-6 text-sm text-zinc-600" data-testid="login-register-hint">
            Hesabınız yok mu?{" "}
            {isPublicRegistrationEnabled() ? (
              <Link to="/register" className="font-semibold text-zinc-950 underline underline-offset-4" data-testid="go-to-register">
                Kayıt olun
              </Link>
            ) : null}
          </div>
        </div>
      </div>
    </div>
  );
}
