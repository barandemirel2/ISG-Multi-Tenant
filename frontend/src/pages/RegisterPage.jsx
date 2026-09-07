import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ShieldCheck, AlertCircle } from "lucide-react";
import { formatApiErrorDetail } from "@/lib/api";
import { toast } from "sonner";

export default function RegisterPage() {
  const { register } = useAuth();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const onSubmit = async (e) => {
    e.preventDefault();
    setErr("");
    if (password.length < 6) {
      setErr("Şifre en az 6 karakter olmalıdır.");
      return;
    }
    setLoading(true);
    try {
      await register(name, email, password);
      toast.success("Kayıt başarılı — Lütfen restoran zincirini seçin");
      navigate("/brand-selection");
    } catch (e) {
      setErr(formatApiErrorDetail(e.response?.data?.detail) || e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen grid md:grid-cols-2 bg-[#FAFAFA]">
      <div className="hidden md:block relative overflow-hidden grain-overlay">
        <img
          src="https://images.unsplash.com/photo-1600565193348-f74bd3c7ccdf?auto=format&fit=crop&w=1600&q=80"
          alt=""
          className="absolute inset-0 w-full h-full object-cover"
        />
        <div className="absolute inset-0 bg-zinc-950/75" />
        <div className="relative z-10 h-full flex flex-col justify-between p-12 text-white">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-white text-zinc-950 flex items-center justify-center rounded-sm">
              <ShieldCheck className="w-6 h-6" />
            </div>
            <div>
              <div className="text-[11px] label-caps text-white/70">ABCD Tech Solutions</div>
              <div className="text-sm font-display font-bold">AI Uzman</div>
            </div>
          </div>
          <div className="max-w-md">
            <div className="text-[11px] label-caps text-white/60 mb-4">Yeni Hesap</div>
            <h1 className="font-display text-4xl md:text-5xl font-black leading-tight tracking-tight">
              Denetim ekibinize <span className="text-amber-400">katılın.</span>
            </h1>
            <p className="mt-6 text-white/80 leading-relaxed text-sm">
              Her restoranınız için ayrı denetim kaydı oluşturun. Kabul edilemez riskleri anında görüntüleyin,
              Excel / PDF raporlar alın.
            </p>
          </div>
          <div className="text-[11px] label-caps text-white/60">İSG Uyumlu — Mevzuata Uygun</div>
        </div>
      </div>

      <div className="flex items-center justify-center p-8">
        <div className="w-full max-w-sm">
          <div className="text-[11px] label-caps text-zinc-500 mb-2">Kayıt Ol</div>
          <h2 className="font-display text-3xl font-black tracking-tight text-zinc-950">Yeni bir hesap oluşturun.</h2>
          <p className="text-sm text-zinc-500 mt-2">Restoran denetimlerinizi kayıt altına almaya başlayın.</p>

          <form onSubmit={onSubmit} className="mt-8 space-y-4" data-testid="register-form">
            <div>
              <Label htmlFor="name" className="label-caps text-zinc-700">Ad Soyad</Label>
              <Input id="name" required value={name} onChange={(e) => setName(e.target.value)}
                data-testid="register-name-input" className="mt-1 h-11" />
            </div>
            <div>
              <Label htmlFor="email" className="label-caps text-zinc-700">E-posta</Label>
              <Input id="email" type="email" required value={email} onChange={(e) => setEmail(e.target.value)}
                data-testid="register-email-input" className="mt-1 h-11" />
            </div>
            <div>
              <Label htmlFor="password" className="label-caps text-zinc-700">Şifre (min 6)</Label>
              <Input id="password" type="password" required value={password} onChange={(e) => setPassword(e.target.value)}
                data-testid="register-password-input" className="mt-1 h-11" />
            </div>
            {err && (
              <div className="flex items-start gap-2 p-3 border border-red-200 bg-red-50 text-red-700 text-sm rounded-sm" data-testid="register-error">
                <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
                <div>{err}</div>
              </div>
            )}
            <Button type="submit" disabled={loading} className="w-full h-11 bg-ink-primary text-ink-inverse hover:bg-ink-secondary font-bold" data-testid="register-submit-btn">
              {loading ? "Kayıt yapılıyor…" : "Hesap Oluştur"}
            </Button>
          </form>

          <div className="mt-6 text-sm text-zinc-600">
            Zaten hesabınız var mı?{" "}
            <Link to="/login" className="font-semibold text-zinc-950 underline underline-offset-4" data-testid="go-to-login">
              Giriş yapın
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
