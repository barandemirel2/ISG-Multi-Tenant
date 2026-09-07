import catalogData from "@/constants/restaurantCatalog.json";
import { getBrandLogo } from "@/components/BrandLogos";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import AppShell from "@/components/AppShell";
import api from "@/lib/api";
import { CountUp } from "@/components/CountUp";
import { SpotlightCard } from "@/components/SpotlightCard";
import BranchHealthCard from "@/components/BranchHealthCard";
import { useAuth } from "@/context/AuthContext";
import { useBrand } from "@/context/BrandContext";
import { Plus, FileText, Trash2, AlertTriangle, CheckCircle2, Building2, Calendar, ArrowRight, ShieldCheck, UserCircle, Search, Filter, MapPin, Stamp } from "lucide-react";
import AuditStateBadge from "@/components/AuditStateBadge";
import RiskDistributionChart from "@/components/RiskDistributionChart";
import ConfirmDestructive from "@/components/ConfirmDestructive";
import { toast } from "sonner";
import { motion, AnimatePresence } from "framer-motion";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

export default function DashboardPage() {
  const { user } = useAuth();
  const { selectedBrand: activeBrand } = useBrand();
  const isAdmin = user?.role === "admin";
  const [audits, setAudits] = useState([]);
  const [loading, setLoading] = useState(true);
  const [deleteId, setDeleteId] = useState(null);
  const [searchParams, setSearchParams] = useSearchParams();
  // URL query string'den filter state'lerini oku (sayfa yenileyince korunur)
  const defaultBrandFilter = searchParams.get("brand") || (activeBrand && activeBrand !== "Tüm Markalar" ? activeBrand : "HEPSİ");
  const [selectedBranch, setSelectedBranch] = useState(searchParams.get("branch") || "HEPSİ");
  const [selectedBrand, setSelectedBrand] = useState(defaultBrandFilter);
  const [selectedCity, setSelectedCity] = useState(searchParams.get("city") || "HEPSİ");
  const [selectedDistrict, setSelectedDistrict] = useState(searchParams.get("district") || "HEPSİ");
  const [search, setSearch] = useState(searchParams.get("q") || "");
  const navigate = useNavigate();

  // Active brand context değiştiğinde varsayılan brand filtresini senkronize et
  useEffect(() => {
    if (activeBrand && activeBrand !== "Tüm Markalar" && !searchParams.get("brand")) {
      setSelectedBrand(activeBrand);
    }
  }, [activeBrand, searchParams]);

  // Filter değişince URL'i güncelle (UI/UX P1: shareable URL)
  useEffect(() => {
    const next = new URLSearchParams();
    if (selectedBranch !== "HEPSİ") next.set("branch", selectedBranch);
    if (selectedBrand !== "HEPSİ") next.set("brand", selectedBrand);
    if (selectedCity !== "HEPSİ") next.set("city", selectedCity);
    if (selectedDistrict !== "HEPSİ") next.set("district", selectedDistrict);
    if (search) next.set("q", search);
    setSearchParams(next, { replace: true });
  }, [selectedBranch, selectedBrand, selectedCity, selectedDistrict, search, setSearchParams]);

  // Şehir değişince ilçeyi sıfırla (eski davranış korunuyor)
  // (selectedDistrict'e bağımlı olursa sonsuz döngü olur; kasıtlı)
  useEffect(() => {
    if (selectedCity === "HEPSİ" && selectedDistrict !== "HEPSİ") {
      setSelectedDistrict("HEPSİ");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedCity]);

  const load = useCallback(async () => {
    try {
      const { data } = await api.get("/audits");
      setAudits(Array.isArray(data) ? data : []);
    } catch (e) {
      toast.error("Denetimler yüklenemedi");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const confirmDelete = async (reason = "") => {
    if (!deleteId) return;
    try {
      // Sebep notu query string ile gönderilir (DELETE body semantiği yok).
      // Backend opsiyonel olarak log'a yazacak.
      const params = reason ? `?reason=${encodeURIComponent(reason)}` : "";
      await api.delete(`/audits/${deleteId}${params}`);
      toast.success("Denetim silindi");
      setDeleteId(null);
      load();
    } catch (e) {
      toast.error("Silme başarısız");
    }
  };

  // Extract unique filter options
  const branchOptions = useMemo(() => {
    const set = new Set();
    audits.forEach((a) => {
      if (a.restaurant_name) set.add(a.restaurant_name);
    });
    return ["HEPSİ", ...Array.from(set)];
  }, [audits]);

  const brandOptions = useMemo(() => {
    return ["HEPSİ", ...catalogData.brands.map((b) => b.name)];
  }, []);

  const cityOptions = useMemo(() => {
    return ["HEPSİ", ...catalogData.brands[0].cities.map((c) => c.name)];
  }, []);

  const districtOptions = useMemo(() => {
    if (selectedCity === "HEPSİ") return ["HEPSİ"];
    const found = catalogData.brands[0].cities.find((c) => c.name === selectedCity);
    return ["HEPSİ", ...(found?.districts || [])];
  }, [selectedCity]);

  const filteredAudits = useMemo(() => {
    return audits.filter((a) => {
      const matchBranch =
        selectedBranch === "HEPSİ" ||
        (a.restaurant_name || "").toLowerCase() === selectedBranch.toLowerCase();
      const matchBrand =
        selectedBrand === "HEPSİ" ||
        (a.brand || a.restaurant_name || "").toLowerCase().includes(selectedBrand.toLowerCase());
      const matchCity =
        selectedCity === "HEPSİ" ||
        (a.city || a.restaurant_name || a.address || "").toLowerCase().includes(selectedCity.toLowerCase());
      const matchDistrict =
        selectedDistrict === "HEPSİ" ||
        (a.district || a.restaurant_name || a.address || "").toLowerCase().includes(selectedDistrict.toLowerCase());
      const matchSearch =
        !search ||
        (a.restaurant_name || "").toLowerCase().includes(search.toLowerCase()) ||
        (a.denetci || "").toLowerCase().includes(search.toLowerCase()) ||
        (a.branch_code || "").toLowerCase().includes(search.toLowerCase()) ||
        (a.city || "").toLowerCase().includes(search.toLowerCase()) ||
        (a.district || "").toLowerCase().includes(search.toLowerCase());

      return matchBranch && matchBrand && matchCity && matchDistrict && matchSearch;
    });
  }, [audits, selectedBranch, selectedBrand, selectedCity, selectedDistrict, search]);

  const totalAudits = filteredAudits.length;
  const totalUnacceptable = filteredAudits.reduce((s, a) => s + (a.summary?.risk_counts?.["KABUL EDİLEMEZ"] || a.summary?.risk_counts?.["Kabul Edilemez"] || 0), 0);
  const totalDikkate = filteredAudits.reduce((s, a) => s + (a.summary?.risk_counts?.["DİKKATE DEĞER"] || a.summary?.risk_counts?.["Dikkate Değer"] || 0), 0);
  const avgCompletion = totalAudits
    ? Math.round(filteredAudits.reduce((s, a) => s + (a.summary?.completion || 0), 0) / totalAudits)
    : 0;

  return (
    <AppShell>
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
        className="font-sans space-y-6"
      >
        {/* HEADER BAR */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-6 border-b border-slate-200/80 dark:border-white/10 pb-5">
          <div className="space-y-1.5 font-sans">
            <div className="flex items-center gap-2 mb-1">
              <span className="text-[11px] font-sans font-bold text-red-600 dark:text-red-500 uppercase tracking-widest">GENEL BAKIŞ</span>
              {isAdmin && (
                <span className="inline-flex items-center gap-1 bg-red-500/10 text-red-600 dark:text-red-400 border border-red-500/30  px-2.5 py-0.5 rounded-full text-[10px] font-sans font-bold uppercase tracking-wider" data-testid="admin-badge">
                  <ShieldCheck className="w-3.5 h-3.5 text-red-500 dark:text-red-400" /> Admin Yetkisi
                </span>
              )}
            </div>
            <h1 className="text-3xl sm:text-4xl font-extrabold text-slate-900 dark:text-white tracking-tight font-sans">Risk Analizi Denetim Paneli</h1>
            <p className="text-xs text-slate-600 dark:text-slate-400 font-sans max-w-2xl leading-relaxed">
              {isAdmin
                ? "Sistemdeki tüm restoran İSG denetimlerini görüntüleyin, detaylarını inceleyin veya yeni saha denetimi başlatın."
                : "Restoranlarınız için yürüttüğünüz İSG risk analizi denetimlerini yönetin, yeni saha denetimi başlatın."}
            </p>
          </div>

          <Link to="/audits/new">
            <button
              type="button"
              className="inline-flex items-center justify-center gap-2 px-5 py-3 rounded-card text-xs font-sans font-bold bg-risk-critical hover:bg-risk-critical-2 text-white  hover: transition-all duration-300 active:scale-95 cursor-pointer self-start sm:self-auto"
              data-testid="hero-new-audit-btn"
            >
              <Plus className="w-4 h-4" />
              <span>Yeni Denetim Başlat</span>
            </button>
          </Link>
        </div>

        {/* MULTI-FILTER & SEARCH BAR */}
        <div className="search-bar rounded-card border border-slate-200/80 dark:border-white/10 bg-white dark:bg-slate-950/80  p-4 sm:p-5 shadow-lg dark:shadow-xl space-y-4 font-sans">
          <div className="flex flex-col lg:flex-row gap-3 items-stretch lg:items-center justify-between">
            {/* MANUEL ARAMA GİRDİSİ */}
            <div className="relative flex-1">
              <Search className="w-4 h-4 text-slate-400 dark:text-slate-500 absolute left-3.5 top-1/2 -translate-y-1/2" />
              <input
                type="search"
                placeholder="Manuel restoran adı, şube kodu, denetçi veya il/ilçe ara…"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="w-full bg-slate-100 dark:bg-slate-900/80 border border-slate-300 dark:border-slate-800 rounded-card pl-10 pr-4 py-2 text-xs text-slate-900 dark:text-slate-100 placeholder:text-slate-400 dark:placeholder:text-slate-500 focus:outline-none focus:border-red-500/60 focus:ring-2 focus:ring-red-500/20 transition-all duration-200 font-sans"
              />
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 shrink-0">
              {/* RESTORAN ZİNCİRİ FİLTRESİ */}
              <Select value={selectedBrand} onValueChange={setSelectedBrand}>
                <SelectTrigger className="bg-slate-100 dark:bg-slate-900/80 border-slate-300 dark:border-slate-800 text-xs text-slate-900 dark:text-slate-100 font-sans h-9 rounded-card focus:border-red-500/60 focus:ring-2 focus:ring-red-500/20">
                  <div className="flex items-center gap-1.5 truncate">
                    <Building2 className="w-3.5 h-3.5 text-red-600 dark:text-red-400 shrink-0" />
                    <SelectValue placeholder="Zincir" />
                  </div>
                </SelectTrigger>
                <SelectContent className="bg-white dark:bg-slate-950 border-slate-300 dark:border-slate-800 text-slate-900 dark:text-white font-sans text-xs">
                  {brandOptions.map((b) => (
                    <SelectItem key={b} value={b}>
                      {b === "HEPSİ" ? "Tüm Zincirler" : b}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>

              {/* İL FİLTRESİ (81 İL) */}
              <Select value={selectedCity} onValueChange={(c) => { setSelectedCity(c); setSelectedDistrict("HEPSİ"); }}>
                <SelectTrigger className="bg-slate-100 dark:bg-slate-900/80 border-slate-300 dark:border-slate-800 text-xs text-slate-900 dark:text-slate-100 font-sans h-9 rounded-card focus:border-red-500/60 focus:ring-2 focus:ring-red-500/20">
                  <div className="flex items-center gap-1.5 truncate">
                    <MapPin className="w-3.5 h-3.5 text-amber-600 dark:text-amber-400 shrink-0" />
                    <SelectValue placeholder="İl" />
                  </div>
                </SelectTrigger>
                <SelectContent className="bg-white dark:bg-slate-950 border-slate-300 dark:border-slate-800 text-slate-900 dark:text-white font-sans text-xs max-h-56">
                  {cityOptions.map((c) => (
                    <SelectItem key={c} value={c}>
                      {c === "HEPSİ" ? "Tüm İller (81)" : c}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>

              {/* İLÇE FİLTRESİ */}
              <Select value={selectedDistrict} onValueChange={setSelectedDistrict}>
                <SelectTrigger className="bg-slate-100 dark:bg-slate-900/80 border-slate-300 dark:border-slate-800 text-xs text-slate-900 dark:text-slate-100 font-sans h-9 rounded-card focus:border-red-500/60 focus:ring-2 focus:ring-red-500/20">
                  <div className="flex items-center gap-1.5 truncate">
                    <MapPin className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400 shrink-0" />
                    <SelectValue placeholder="İlçe" />
                  </div>
                </SelectTrigger>
                <SelectContent className="bg-white dark:bg-slate-950 border-slate-300 dark:border-slate-800 text-slate-900 dark:text-white font-sans text-xs max-h-56">
                  {districtOptions.map((d) => (
                    <SelectItem key={d} value={d}>
                      {d === "HEPSİ" ? "Tüm İlçeler" : d}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
        </div>

        {/* BRANCH HEALTH SUMMARY BANNER (IF A SPECIFIC BRANCH IS SELECTED) */}
        {selectedBranch !== "HEPSİ" && (
          <BranchHealthCard branchName={selectedBranch} audits={audits} items={[]} />
        )}

        {/* VERCEL/LINEAR DASHBOARD KPIS */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4" data-testid="kpis-container">
          <SpotlightCard className="p-5 font-sans bg-white dark:bg-slate-950/80 border-slate-200/80 dark:border-white/10" data-testid="kpi-total-audits">
            <div className="text-[11px] font-sans font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">TOPLAM DENETİM</div>
            <div className="text-3xl md:text-4xl font-extrabold text-slate-900 dark:text-white mt-2 font-sans tabular-nums">
              <CountUp to={totalAudits} />
            </div>
          </SpotlightCard>

          <SpotlightCard className="p-5 font-sans bg-white dark:bg-slate-950/80 border-slate-200/80 dark:border-white/10" data-testid="kpi-avg-completion">
            <div className="text-[11px] font-sans font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">ORTALAMA TAMAMLANMA</div>
            <div className="text-3xl md:text-4xl font-extrabold text-emerald-600 dark:text-emerald-400 mt-2 font-sans tabular-nums">
              %<CountUp to={avgCompletion} />
            </div>
          </SpotlightCard>

          <SpotlightCard className="p-5 font-sans bg-white dark:bg-slate-950/80 border-slate-200/80 dark:border-white/10" data-testid="kpi-unacceptable">
            <div className="text-[11px] font-sans font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">KRİTİK RİSK (KABUL EDİLEMEZ)</div>
            <div className="text-3xl md:text-4xl font-extrabold text-red-600 dark:text-red-500 mt-2 font-sans tabular-nums">
              <CountUp to={totalUnacceptable} />
            </div>
          </SpotlightCard>

          <SpotlightCard className="p-5 font-sans bg-white dark:bg-slate-950/80 border-slate-200/80 dark:border-white/10" data-testid="kpi-notable">
            <div className="text-[11px] font-sans font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">DİKKATE DEĞER RİSK</div>
            <div className="text-3xl md:text-4xl font-extrabold text-amber-600 dark:text-amber-400 mt-2 font-sans tabular-nums">
              <CountUp to={totalDikkate} />
            </div>
          </SpotlightCard>
        </div>

        {/* RISK DAĞILIMI DONUT CHART (UI/UX P1) */}
        <RiskDistributionChart audits={filteredAudits} />

        {/* RECENT AUDITS SECTION */}
        <div className="space-y-4">
          <div className="flex items-center justify-between font-sans">
            <h2 className="text-lg font-bold text-slate-900 dark:text-white tracking-tight flex items-center gap-2">
              <FileText className="w-5 h-5 text-red-600 dark:text-red-400" />
              Saha Denetim Kayıtları {selectedBranch !== "HEPSİ" ? `(${selectedBranch})` : ""}
            </h2>
            <span className="text-xs text-slate-500 dark:text-slate-400 font-mono">Toplam {filteredAudits.length} Kayıt</span>
          </div>

          {loading ? (
            <div className="py-12 text-center text-slate-500 dark:text-slate-400 text-xs font-sans">Yükleniyor…</div>
          ) : filteredAudits.length === 0 ? (
            <div className="py-16 text-center rounded-card border border-dashed border-slate-300 dark:border-white/10 bg-white dark:bg-slate-950/60 font-sans space-y-3">
              <Building2 className="w-8 h-8 text-slate-400 dark:text-slate-500 mx-auto opacity-70" />
              <p className="text-slate-800 dark:text-slate-300 font-bold text-sm">Denetim Kaydı Bulunamadı</p>
              <p className="text-xs text-slate-500 dark:text-slate-400">Henüz oluşturulmuş bir denetim kaydı bulunmuyor.</p>
              <Link to="/audits/new">
                <button type="button" className="mt-2 px-4 py-2 rounded-card text-xs font-sans font-bold bg-red-600 text-white shadow-md cursor-pointer">
                  + Yeni Denetim Başlat
                </button>
              </Link>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4" data-testid="audits-grid">
              <AnimatePresence>
                {filteredAudits.map((a) => (
                  <motion.div
                    key={a.id}
                    layout
                    initial={{ opacity: 0, scale: 0.96 }}
                    animate={{ opacity: 1, scale: 1 }}
                    exit={{ opacity: 0, scale: 0.96 }}
                    transition={{ duration: 0.2 }}
                    className="p-5 border border-slate-200/80 dark:border-white/10 rounded-card bg-white dark:bg-slate-950/80  shadow-lg dark:shadow-xl hover:border-slate-300 dark:hover:border-white/20 transition-all duration-300 flex flex-col justify-between space-y-4 font-sans group"
                  >
                    <div className="space-y-2">
                      <div className="flex items-start justify-between gap-2">
                        <span className="text-red-600 dark:text-red-400 font-bold text-sm flex items-center gap-1.5 group-hover:text-red-700 dark:group-hover:text-red-300 transition-colors">
                          <div className="w-5 h-5 flex items-center justify-center shrink-0">
                            {getBrandLogo(a.brand || a.restaurant_name, "w-4 h-4 object-contain")}
                          </div>
                          <span>{a.restaurant_name}</span>
                        </span>
                        <AuditStateBadge state={a.state} isCompleted={a.is_completed} size="xs" />
                      </div>

                      {/* BRAND & LOCATION BADGES */}
                      <div className="flex items-center gap-1.5 flex-wrap">
                        {a.brand && (
                          <span className="px-2 py-0.5 rounded-md bg-slate-100 dark:bg-slate-900 text-slate-700 dark:text-slate-300 border border-slate-200 dark:border-slate-800 text-[10px] font-bold font-sans">
                            {a.brand}
                          </span>
                        )}
                        {(a.city || a.district) && (
                          <span className="px-2 py-0.5 rounded-md bg-amber-500/10 text-amber-700 dark:text-amber-300 border border-amber-500/20 text-[10px] font-medium font-sans flex items-center gap-1">
                            <MapPin className="w-3 h-3 text-amber-600 dark:text-amber-400" />
                            {a.city} {a.district ? `/ ${a.district}` : ""}
                          </span>
                        )}
                      </div>

                      <div className="text-[11px] text-slate-500 dark:text-slate-400 flex items-center gap-3 font-mono">
                        <span className="flex items-center gap-1"><Calendar className="w-3 h-3 text-slate-400 dark:text-slate-500" /> {a.audit_date || "—"}</span>
                        <span>•</span>
                        <span>{a.denetci || "Denetçi yok"}</span>
                      </div>

                      {a.address && (
                        <div className="text-xs text-slate-600 dark:text-slate-400 line-clamp-1">{a.address}</div>
                      )}
                    </div>

                    {/* RISK SUMMARY PILLS */}
                    <div className="pt-3 border-t border-slate-200/60 dark:border-white/5 flex items-center justify-between text-xs font-sans">
                      <div className="flex items-center gap-2">
                        <span className="px-2 py-0.5 rounded bg-red-500/20 text-red-700 dark:text-red-400 font-bold text-[10px]">
                          {a.summary?.risk_counts?.["KABUL EDİLEMEZ"] || a.summary?.risk_counts?.["Kabul Edilemez"] || 0} Kritik
                        </span>
                        <span className="px-2 py-0.5 rounded bg-amber-500/20 text-amber-700 dark:text-amber-400 font-bold text-[10px]">
                          {a.summary?.risk_counts?.["DİKKATE DEĞER"] || a.summary?.risk_counts?.["Dikkate Değer"] || 0} Dikkate
                        </span>
                      </div>

                      <div className="flex items-center gap-2">
                        {/* S20: İbraz Belgesi indir — yalnız DOF_CLOSED / FINAL audit'ler için */}
                        {(a.state === "DOF_CLOSED" || a.state === "FINAL") && (
                          <button
                            type="button"
                            onClick={async (e) => {
                              e.preventDefault();
                              e.stopPropagation();
                              try {
                                const resp = await api.get(`/audits/${a.id}/ibraz`, { responseType: "blob" });
                                const url = window.URL.createObjectURL(new Blob([resp.data], { type: "application/pdf" }));
                                const link = document.createElement("a");
                                link.href = url;
                                const hash = resp.headers?.["x-ibraz-hash"] || "";
                                link.setAttribute("download", `Ibraz_${a.restaurant_name?.replace(/\s+/g, "_") || "denetim"}_${hash}.pdf`);
                                document.body.appendChild(link);
                                link.click();
                                link.remove();
                                window.URL.revokeObjectURL(url);
                                toast.success("İbraz belgesi indirildi.");
                              } catch (err) {
                                const detail = err?.response?.data?.detail || "İbraz belgesi oluşturulamadı.";
                                toast.error(detail);
                              }
                            }}
                            className="p-1.5 text-emerald-600 dark:text-emerald-400 hover:bg-emerald-500/10 rounded-lg transition-colors cursor-pointer"
                            title="İbraz Belgesi İndir (mahkeme format)"
                          >
                            <Stamp className="w-4 h-4" />
                          </button>
                        )}
                        {isAdmin && (
                          <button
                            type="button"
                            onClick={() => setDeleteId(a.id)}
                            className="p-1.5 text-slate-400 hover:text-red-600 dark:hover:text-red-400 hover:bg-red-500/10 rounded-lg transition-colors cursor-pointer"
                            title="Sil"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        )}
                        <Link to={`/audits/${a.id}`}>
                          <button
                            type="button"
                            className="p-2 rounded-card bg-slate-100 dark:bg-slate-900 hover:bg-slate-200 dark:hover:bg-slate-800 text-slate-700 dark:text-slate-300 hover:text-slate-900 dark:hover:text-white border border-slate-300 dark:border-white/10 transition-colors flex items-center gap-1 text-xs font-semibold cursor-pointer active:scale-95"
                          >
                            <span>İncele</span>
                            <ArrowRight className="w-3.5 h-3.5" />
                          </button>
                        </Link>
                      </div>
                    </div>
                  </motion.div>
                ))}
              </AnimatePresence>
            </div>
          )}
        </div>
        {/* DELETE CONFIRMATION (S19: tutarlı onay mekanizması) */}
        <ConfirmDestructive
          open={Boolean(deleteId)}
          onOpenChange={(o) => !o && setDeleteId(null)}
          title="Denetim Silinecek"
          description={
            audits.find((a) => a.id === deleteId)?.state === "DRAFT"
              ? "DRAFT audit'ler kalıcı olarak silinir. DİKKAT: bu geri alınamaz."
              : "SUBMITTED+ audit'ler soft-delete yapılır (is_archived + deleted_at). Audit kaydı korunur."
          }
          itemName={audits.find((a) => a.id === deleteId)?.restaurant_name || ""}
          action="Sil"
          actionVerb="silmek"
          reasonRequired={false}
          reasonPlaceholder="(opsiyonel) Silme sebebi — audit_log'a yazılır"
          onConfirm={confirmDelete}
        />
      </motion.div>
    </AppShell>
  );
}
