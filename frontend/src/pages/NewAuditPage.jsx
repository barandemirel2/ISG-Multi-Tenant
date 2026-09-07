import CascadingRestaurantSelect from "@/components/CascadingRestaurantSelect";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import AppShell from "@/components/AppShell";
import api, { formatApiErrorDetail } from "@/lib/api";
import { ArrowLeft, ClipboardCheck, Building2, UserCheck, Shield, FileText, MapPin } from "lucide-react";
import { toast } from "sonner";
import { useAuth } from "@/context/AuthContext";
import { motion } from "framer-motion";

export default function NewAuditPage() {
  const { user } = useAuth();
  const [form, setForm] = useState({
    restaurant_name: "",
    brand: "",
    city: "",
    district: "",
    restaurant_manager: "",
    auditor_title: "İSG Uzmanı",
    branch_code: "",
    address: "",
    audit_date: new Date().toISOString().slice(0, 10),
    denetci: user?.name || "",
    audit_notes: "",
  });
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");
  const navigate = useNavigate();

  const update = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  const onSubmit = async (e) => {
    e.preventDefault();
    setErr("");
    setLoading(true);
    try {
      const { data } = await api.post("/audits", form);
      toast.success("Denetim başarıyla başlatıldı.");
      navigate(`/audits/${data.id}`);
    } catch (e) {
      setErr(formatApiErrorDetail(e.response?.data?.detail) || e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <AppShell>
      <div className="max-w-2xl mx-auto flex flex-col justify-center min-h-[80vh] py-6 font-sans">
        {/* BACK BUTTON */}
        <button
          type="button"
          onClick={() => navigate(-1)}
          className="flex items-center gap-2 text-xs font-sans font-medium text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white mb-4 transition-colors self-start cursor-pointer active:scale-95"
          data-testid="back-btn"
        >
          <ArrowLeft className="w-4 h-4 text-slate-500 dark:text-slate-400" /> Geri Dön
        </button>

        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3 }}
          className="space-y-6"
        >
          <div>
            <div className="text-[11px] font-bold text-red-600 dark:text-red-500 uppercase tracking-widest mb-1 flex items-center gap-1.5 font-sans">
              <Building2 className="w-3.5 h-3.5" /> YENİ DENETİM KAYDI
            </div>
            <h1 className="text-3xl font-extrabold text-slate-900 dark:text-white tracking-tight font-sans">Yeni Saha Denetimi Başlat</h1>
            <p className="text-xs text-slate-600 dark:text-slate-400 mt-1.5 leading-relaxed font-sans">
              Restoran ve denetçi bilgilerini girerek dijital İSG risk analizi denetimini oluşturun.
            </p>
          </div>

          {/* FORM CONTAINER */}
          <div className="p-6 sm:p-8 border border-slate-200/80 dark:border-white/10 rounded-card bg-white dark:bg-slate-950/90  shadow-lg dark:shadow-2xl space-y-6 font-sans transition-colors duration-300">
            <form onSubmit={onSubmit} className="space-y-5" data-testid="new-audit-form">
              
              {/* KATEGORİZASYON: ZİNCİR -> İL -> İLÇE */}
              <CascadingRestaurantSelect
                id="rn"
                dataTestId="input-restaurant"
                value={form.restaurant_name}
                onChange={(val) => setForm((f) => ({ ...f, restaurant_name: val }))}
                onSelectBranch={(b) => {
                  setForm((f) => ({
                    ...f,
                    restaurant_name: b.name || f.restaurant_name,
                    brand: b.brand || f.brand,
                    city: b.city || f.city,
                    district: b.district || f.district,
                    branch_code: b.code || f.branch_code,
                    address: b.address || f.address,
                  }));
                }}
              />

              {/* MANUEL RESTORAN ADI & ŞUBE KODU */}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <div className="sm:col-span-2 space-y-1.5">
                  <label htmlFor="rn_manual" className="text-xs font-bold text-slate-700 dark:text-slate-300 font-sans uppercase tracking-wider flex items-center gap-1.5">
                    <Building2 className="w-3.5 h-3.5 text-red-600 dark:text-red-400" /> RESTORAN TAM ADI *
                  </label>
                  <input
                    id="rn_manual"
                    required
                    value={form.restaurant_name}
                    onChange={update("restaurant_name")}
                    className="w-full bg-slate-100 dark:bg-slate-900/80 border border-slate-300 dark:border-slate-800 rounded-card px-4 py-3 text-xs text-slate-900 dark:text-slate-100 placeholder:text-slate-400 dark:placeholder:text-slate-500 focus:outline-none focus:border-red-500/60 focus:ring-2 focus:ring-red-500/20 transition-all duration-200 font-sans"
                    placeholder="Örn: Kadıköy Popeyes Şubesi"
                  />
                </div>

                <div className="space-y-1.5">
                  <label htmlFor="bc" className="text-xs font-bold text-slate-700 dark:text-slate-300 font-sans uppercase tracking-wider">ŞUBE KODU</label>
                  <input
                    id="bc"
                    value={form.branch_code}
                    onChange={update("branch_code")}
                    className="w-full bg-slate-100 dark:bg-slate-900/80 border border-slate-300 dark:border-slate-800 rounded-card px-4 py-3 text-xs text-slate-900 dark:text-slate-100 placeholder:text-slate-400 dark:placeholder:text-slate-500 focus:outline-none focus:border-red-500/60 focus:ring-2 focus:ring-red-500/20 transition-all duration-200 font-mono"
                    placeholder="Örn: POP-104"
                  />
                </div>
              </div>

              {/* RESTORAN MÜDÜRÜ & DENETÇİ UNVANI */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="space-y-1.5">
                  <label htmlFor="rm" className="text-xs font-bold text-slate-700 dark:text-slate-300 font-sans uppercase tracking-wider flex items-center gap-1.5">
                    <UserCheck className="w-3.5 h-3.5 text-amber-600 dark:text-amber-400" /> RESTORAN MÜDÜRÜ / SORUMLUSU
                  </label>
                  <input
                    id="rm"
                    value={form.restaurant_manager}
                    onChange={update("restaurant_manager")}
                    className="w-full bg-slate-100 dark:bg-slate-900/80 border border-slate-300 dark:border-slate-800 rounded-card px-4 py-2.5 text-xs text-slate-900 dark:text-slate-100 placeholder:text-slate-400 dark:placeholder:text-slate-500 focus:outline-none focus:border-red-500/60 focus:ring-2 focus:ring-red-500/20 transition-all duration-200 font-sans"
                    placeholder="Örn: Ahmet Yılmaz (Restoran Müdürü)"
                  />
                </div>

                <div className="space-y-1.5">
                  <label htmlFor="at" className="text-xs font-bold text-slate-700 dark:text-slate-300 font-sans uppercase tracking-wider flex items-center gap-1.5">
                    <Shield className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400" /> DENETÇİ UNVANI / İSG UZMANI
                  </label>
                  <input
                    id="at"
                    value={form.auditor_title}
                    onChange={update("auditor_title")}
                    className="w-full bg-slate-100 dark:bg-slate-900/80 border border-slate-300 dark:border-slate-800 rounded-card px-4 py-2.5 text-xs text-slate-900 dark:text-slate-100 placeholder:text-slate-400 dark:placeholder:text-slate-500 focus:outline-none focus:border-red-500/60 focus:ring-2 focus:ring-red-500/20 transition-all duration-200 font-sans"
                    placeholder="Örn: A Sınıfı İSG Uzmanı"
                  />
                </div>
              </div>

              {/* DENETİM TARİHİ & DENETÇİ ADI */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="space-y-1.5">
                  <label htmlFor="dt" className="text-xs font-bold text-slate-700 dark:text-slate-300 font-sans uppercase tracking-wider">DENETİM TARİHİ</label>
                  <input
                    id="dt"
                    type="date"
                    value={form.audit_date}
                    onChange={update("audit_date")}
                    data-testid="input-date"
                    className="w-full bg-slate-100 dark:bg-slate-900/80 border border-slate-300 dark:border-slate-800 rounded-card px-4 py-2.5 text-xs text-slate-900 dark:text-slate-100 focus:outline-none focus:border-red-500/60 focus:ring-2 focus:ring-red-500/20 transition-all duration-200 font-mono"
                  />
                </div>

                <div className="space-y-1.5">
                  <label htmlFor="dn" className="text-xs font-bold text-slate-700 dark:text-slate-300 font-sans uppercase tracking-wider">DENETÇİ ADI SOYADI</label>
                  <input
                    id="dn"
                    value={form.denetci}
                    onChange={update("denetci")}
                    data-testid="input-auditor"
                    className="w-full bg-slate-100 dark:bg-slate-900/80 border border-slate-300 dark:border-slate-800 rounded-card px-4 py-2.5 text-xs text-slate-900 dark:text-slate-100 focus:outline-none focus:border-red-500/60 focus:ring-2 focus:ring-red-500/20 transition-all duration-200 font-sans"
                  />
                </div>
              </div>

              {/* ADRES */}
              <div className="space-y-1.5">
                <label htmlFor="ad" className="text-xs font-bold text-slate-700 dark:text-slate-300 font-sans uppercase tracking-wider flex items-center gap-1.5">
                  <MapPin className="w-3.5 h-3.5 text-slate-400" /> ADRES
                </label>
                <textarea
                  id="ad"
                  value={form.address}
                  onChange={update("address")}
                  data-testid="input-address"
                  rows={2}
                  placeholder="Mahalle, cadde, ilçe / il bilgisi"
                  className="w-full bg-slate-100 dark:bg-slate-900/80 border border-slate-300 dark:border-slate-800 rounded-card p-3 text-xs text-slate-900 dark:text-slate-100 placeholder:text-slate-400 dark:placeholder:text-slate-500 focus:outline-none focus:border-red-500/60 focus:ring-2 focus:ring-red-500/20 transition-all duration-200 font-sans"
                />
              </div>

              {/* DENETİM NOTU */}
              <div className="space-y-1.5">
                <label htmlFor="an" className="text-xs font-bold text-slate-700 dark:text-slate-300 font-sans uppercase tracking-wider flex items-center gap-1.5">
                  <FileText className="w-3.5 h-3.5 text-slate-400" /> DENETİM GENEL NOTU / GÖZLEMLER
                </label>
                <textarea
                  id="an"
                  value={form.audit_notes}
                  onChange={update("audit_notes")}
                  rows={2}
                  placeholder="Opsiyonel ön denetim notları ve saha ortamı gözlemleri..."
                  className="w-full bg-slate-100 dark:bg-slate-900/80 border border-slate-300 dark:border-slate-800 rounded-card p-3 text-xs text-slate-900 dark:text-slate-100 placeholder:text-slate-400 dark:placeholder:text-slate-500 focus:outline-none focus:border-red-500/60 focus:ring-2 focus:ring-red-500/20 transition-all duration-200 font-sans"
                />
              </div>

              {err && (
                <div className="p-3 border border-red-500/30 bg-red-500/10  text-red-600 dark:text-red-400 text-xs rounded-card font-sans font-medium">{err}</div>
              )}

              <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 pt-4 border-t border-slate-200 dark:border-white/10">
                <div className="text-[11px] text-slate-600 dark:text-slate-400 font-sans">Sonraki adım: 84 soruluk dijital risk matrisi</div>
                <button
                  type="submit"
                  disabled={loading}
                  className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-6 py-3 rounded-card text-xs font-sans font-bold bg-risk-critical hover:bg-risk-critical-2 text-white  hover: transition-all duration-300 active:scale-95 cursor-pointer"
                  data-testid="submit-new-audit"
                >
                  <ClipboardCheck className="w-4 h-4" />
                  {loading ? "Oluşturuluyor…" : "Denetimi Başlat"}
                </button>
              </div>
            </form>
          </div>
        </motion.div>
      </div>
    </AppShell>
  );
}
