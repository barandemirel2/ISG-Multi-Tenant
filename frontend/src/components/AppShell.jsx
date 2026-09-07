import CompanyLogo from "@/components/CompanyLogo";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useState } from "react";
import { useAuth } from "@/context/AuthContext";
import { useBrand } from "@/context/BrandContext";
import { getBrandLogo } from "@/components/BrandLogos";
import { ThemeToggle } from "@/components/ThemeToggle";
import {
  ShieldCheck,
  LogOut,
  LayoutDashboard,
  ShieldAlert,
  FileCheck,
  Menu,
  X,
  User as UserIcon,
  ChevronRight,
  ChevronDown,
  Store,
  Siren,
  GraduationCap,
  Wrench,
  Users,
  MapPin,
  Clock,
  BookOpen,
  Sparkles,
  FilePlus,
  HeartPulse,
  CheckSquare,
  ClipboardList,
  Briefcase,
  CalendarCheck,
  UserPlus,
} from "lucide-react";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
  SheetTrigger,
} from "@/components/ui/sheet";
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
} from "@/components/ui/dropdown-menu";

export const MODULE_NAV_CONFIG = [
  {
    id: "risk-analizi",
    label: "Risk Analizi",
    fullName: "Risk Analizi",
    icon: ShieldCheck,
    iconColor: "text-red-600 dark:text-red-400",
    headerTitle: "🛡️ Risk Analizi Modülleri",
    activeClass: "bg-risk-critical-bg text-risk-critical border-risk-critical-border",
    idleClass: "bg-surface-card-2 text-ink-secondary border-border-default hover:bg-surface-page-2",
    triggerTestId: "nav-risk-analizi-trigger",
    isModuleActive: (pathname) =>
      pathname === "/" ||
      pathname === "/dashboard" ||
      pathname === "/dof" ||
      pathname === "/uat" ||
      pathname.startsWith("/audits"),
    items: [
      {
        href: "/dashboard",
        testId: "nav-dashboard",
        mobileTestId: "mobile-nav-dashboard",
        label: "Risk Analizi Denetim Paneli",
        icon: LayoutDashboard,
        iconColor: "text-emerald-500 dark:text-emerald-400",
        isItemActive: (pathname) =>
          pathname === "/dashboard" || pathname === "/" || pathname.startsWith("/audits"),
      },
      {
        href: "/dof",
        testId: "nav-dof",
        mobileTestId: "mobile-nav-dof",
        label: "DÖF Takip Paneli",
        icon: ShieldAlert,
        iconColor: "text-amber-500 dark:text-amber-400",
        isItemActive: (pathname) => pathname === "/dof",
      },
      {
        href: "/uat",
        testId: "nav-uat",
        mobileTestId: "mobile-nav-uat",
        label: "İş Yeri Beyan Formu Paneli",
        icon: FileCheck,
        iconColor: "text-sky-500 dark:text-sky-400",
        isItemActive: (pathname) => pathname === "/uat",
      },
    ],
  },
  {
    id: "employees",
    label: "Çalışan Paneli",
    fullName: "Çalışan Paneli",
    icon: Users,
    iconColor: "text-violet-600 dark:text-violet-400",
    headerTitle: "👥 Çalışan Modülleri",
    activeClass:
      "bg-violet-500/10 dark:bg-violet-500/20 text-violet-600 dark:text-violet-400 border-violet-500/40",
    idleClass: "bg-surface-card-2 text-ink-secondary border-border-default hover:bg-surface-page-2",
    triggerTestId: "nav-employees-trigger",
    isModuleActive: (pathname) =>
      pathname === "/employees" || pathname.startsWith("/employees/"),
    items: [
      {
        href: "/employees/list",
        testId: "nav-employees-list",
        mobileTestId: "mobile-nav-employees-list",
        label: "Personel Listesi Paneli",
        icon: ClipboardList,
        iconColor: "text-violet-500",
        isItemActive: (pathname) =>
          pathname === "/employees/list" || pathname === "/employees",
      },
      {
        href: "/employees/job-descriptions",
        testId: "nav-employees-job-descriptions",
        mobileTestId: "mobile-nav-employees-job-descriptions",
        label: "Görev Tanımları Paneli",
        icon: Briefcase,
        iconColor: "text-violet-500",
        isItemActive: (pathname) => pathname === "/employees/job-descriptions",
      },
    ],
  },
  {
    id: "employee-training",
    label: "Çalışan Eğitimi Paneli",
    fullName: "Çalışan Eğitimi Paneli",
    icon: GraduationCap,
    iconColor: "text-blue-600 dark:text-blue-400",
    headerTitle: "🎓 Çalışan Eğitimi Modülleri",
    activeClass:
      "bg-blue-500/10 dark:bg-blue-500/20 text-blue-600 dark:text-blue-400 border-blue-500/40",
    idleClass: "bg-surface-card-2 text-ink-secondary border-border-default hover:bg-surface-page-2",
    triggerTestId: "nav-employee-training-trigger",
    isModuleActive: (pathname) =>
      pathname === "/employee-training" || pathname.startsWith("/employee-training/"),
    items: [
      {
        href: "/employee-training/basic",
        testId: "nav-employee-training-basic",
        mobileTestId: "mobile-nav-employee-training-basic",
        label: "İSG Temel Eğitimi Paneli",
        icon: GraduationCap,
        iconColor: "text-blue-500",
        isItemActive: (pathname) =>
          pathname === "/employee-training/basic" || pathname === "/employee-training",
      },
      {
        href: "/employee-training/orientation",
        testId: "nav-employee-training-orientation",
        mobileTestId: "mobile-nav-employee-training-orientation",
        label: "İSG Oryantasyon Eğitimi Paneli",
        icon: BookOpen,
        iconColor: "text-blue-500",
        isItemActive: (pathname) => pathname === "/employee-training/orientation",
      },
      {
        href: "/employee-training/hygiene",
        testId: "nav-employee-training-hygiene",
        mobileTestId: "mobile-nav-employee-training-hygiene",
        label: "Hijyen Eğitimi Paneli",
        icon: Sparkles,
        iconColor: "text-blue-500",
        isItemActive: (pathname) => pathname === "/employee-training/hygiene",
      },
      {
        href: "/employee-training/additional",
        testId: "nav-employee-training-additional",
        mobileTestId: "mobile-nav-employee-training-additional",
        label: "İlave Eğitim Paneli",
        icon: FilePlus,
        iconColor: "text-blue-500",
        isItemActive: (pathname) => pathname === "/employee-training/additional",
      },
      {
        href: "/employee-training/toolbox",
        testId: "nav-employee-training-toolbox",
        mobileTestId: "mobile-nav-employee-training-toolbox",
        label: "Toolbox Eğitimi Paneli",
        icon: Wrench,
        iconColor: "text-blue-500",
        isItemActive: (pathname) => pathname === "/employee-training/toolbox",
      },
      {
        href: "/employee-training/emergency",
        testId: "nav-employee-training-emergency",
        mobileTestId: "mobile-nav-employee-training-emergency",
        label: "Acil Durum Eğitimi Paneli",
        icon: Siren,
        iconColor: "text-blue-500",
        isItemActive: (pathname) => pathname === "/employee-training/emergency",
      },
      {
        href: "/employee-training/emergency-team",
        testId: "nav-employee-training-emergency-team",
        mobileTestId: "mobile-nav-employee-training-emergency-team",
        label: "Acil Durum Ekip Eğitimi Paneli",
        icon: Users,
        iconColor: "text-blue-500",
        isItemActive: (pathname) => pathname === "/employee-training/emergency-team",
      },
      {
        href: "/employee-training/risk-team",
        testId: "nav-employee-training-risk-team",
        mobileTestId: "mobile-nav-employee-training-risk-team",
        label: "Risk Analizi Ekip Eğitimi Paneli",
        icon: ShieldAlert,
        iconColor: "text-blue-500",
        isItemActive: (pathname) => pathname === "/employee-training/risk-team",
      },
      {
        href: "/employee-training/first-aid",
        testId: "nav-employee-training-first-aid",
        mobileTestId: "mobile-nav-employee-training-first-aid",
        label: "İlkyardım Eğitimi Paneli",
        icon: HeartPulse,
        iconColor: "text-blue-500",
        isItemActive: (pathname) => pathname === "/employee-training/first-aid",
      },
      {
        href: "/employee-training/entry",
        testId: "nav-employee-training-entry",
        mobileTestId: "mobile-nav-employee-training-entry",
        label: "İşe Giriş Eğitim Paneli",
        icon: UserPlus,
        iconColor: "text-blue-500",
        isItemActive: (pathname) => pathname === "/employee-training/entry",
      },
    ],
  },
  {
    id: "employee-health",
    label: "Çalışan Sağlık Gözetim Paneli",
    fullName: "Çalışan Sağlık Gözetim Paneli",
    icon: HeartPulse,
    iconColor: "text-rose-600 dark:text-rose-400",
    headerTitle: "🩺 Çalışan Sağlık Gözetim Modülleri",
    activeClass:
      "bg-rose-500/10 dark:bg-rose-500/20 text-rose-600 dark:text-rose-400 border-rose-500/40",
    idleClass: "bg-surface-card-2 text-ink-secondary border-border-default hover:bg-surface-page-2",
    triggerTestId: "nav-employee-health-trigger",
    isModuleActive: (pathname) =>
      pathname === "/employee-health" || pathname.startsWith("/employee-health/"),
    items: [
      {
        href: "/employee-health/entry-reports",
        testId: "nav-employee-health-entry-reports",
        mobileTestId: "mobile-nav-employee-health-entry-reports",
        label: "İşe Giriş Sağlık Raporları Paneli",
        icon: FileCheck,
        iconColor: "text-rose-500",
        isItemActive: (pathname) =>
          pathname === "/employee-health/entry-reports" || pathname === "/employee-health",
      },
      {
        href: "/employee-health/periodic-reports",
        testId: "nav-employee-health-periodic-reports",
        mobileTestId: "mobile-nav-employee-health-periodic-reports",
        label: "Periyodik Sağlık Raporları Paneli",
        icon: CalendarCheck,
        iconColor: "text-rose-500",
        isItemActive: (pathname) => pathname === "/employee-health/periodic-reports",
      },
    ],
  },
  {
    id: "emergency-plan",
    label: "Acil Durum Paneli",
    fullName: "Acil Durum Paneli",
    icon: Siren,
    iconColor: "text-risk-moderate",
    headerTitle: "🚨 Acil Durum Modülleri",
    activeClass: "bg-risk-moderate-bg text-risk-moderate border-risk-moderate-border",
    idleClass: "bg-surface-card-2 text-ink-secondary border-border-default hover:bg-surface-page-2",
    triggerTestId: "nav-emergency-plan-trigger",
    isModuleActive: (pathname) =>
      pathname === "/emergency-plan" || pathname.startsWith("/emergency-plan/"),
    items: [
      {
        href: "/emergency-plan/plan",
        testId: "nav-emergency-plan-plan",
        mobileTestId: "mobile-nav-emergency-plan-plan",
        label: "Acil Durum Planı Paneli",
        icon: Siren,
        iconColor: "text-amber-500",
        isItemActive: (pathname) =>
          pathname === "/emergency-plan/plan" || pathname === "/emergency-plan",
      },
      {
        href: "/emergency-plan/teams",
        testId: "nav-emergency-plan-teams",
        mobileTestId: "mobile-nav-emergency-plan-teams",
        label: "Ekipler Paneli",
        icon: Users,
        iconColor: "text-amber-500",
        isItemActive: (pathname) => pathname === "/emergency-plan/teams",
      },
      {
        href: "/emergency-plan/layout",
        testId: "nav-emergency-plan-layout",
        mobileTestId: "mobile-nav-emergency-plan-layout",
        label: "Kroki Paneli",
        icon: MapPin,
        iconColor: "text-amber-500",
        isItemActive: (pathname) => pathname === "/emergency-plan/layout",
      },
      {
        href: "/emergency-plan/drills",
        testId: "nav-emergency-plan-drills",
        mobileTestId: "mobile-nav-emergency-plan-drills",
        label: "Tatbikat Paneli",
        icon: Clock,
        iconColor: "text-amber-500",
        isItemActive: (pathname) => pathname === "/emergency-plan/drills",
      },
    ],
  },
  {
    id: "periodic-controls",
    label: "Periyodik Kontroller Paneli",
    fullName: "Periyodik Kontroller Paneli",
    icon: Wrench,
    iconColor: "text-risk-compliant",
    headerTitle: "🛠️ Periyodik Kontrol Modülleri",
    activeClass: "bg-risk-compliant-bg text-risk-compliant border-risk-compliant-border",
    idleClass: "bg-surface-card-2 text-ink-secondary border-border-default hover:bg-surface-page-2",
    triggerTestId: "nav-periodic-controls-trigger",
    isModuleActive: (pathname) =>
      pathname === "/periodic-controls" || pathname.startsWith("/periodic-controls/"),
    items: [
      {
        href: "/periodic-controls/inspection",
        testId: "nav-periodic-controls-inspection",
        mobileTestId: "mobile-nav-periodic-controls-inspection",
        label: "Periyodik Muayene Paneli",
        icon: CheckSquare,
        iconColor: "text-emerald-500",
        isItemActive: (pathname) =>
          pathname === "/periodic-controls/inspection" || pathname === "/periodic-controls",
      },
      {
        href: "/periodic-controls/maintenance",
        testId: "nav-periodic-controls-maintenance",
        mobileTestId: "mobile-nav-periodic-controls-maintenance",
        label: "Periyodik Bakım Paneli",
        icon: Wrench,
        iconColor: "text-emerald-500",
        isItemActive: (pathname) => pathname === "/periodic-controls/maintenance",
      },
    ],
  },
];

export function MobileNavList({
  modules = MODULE_NAV_CONFIG,
  navItems,
  moduleNavItems,
  onNavigate,
  rightIcon: RightIconProp,
  currentPath = "",
}) {
  const RightIcon = RightIconProp || ChevronRight;

  // Fallback for tests rendering old flat navigation prop arrays
  if (navItems || moduleNavItems) {
    return (
      <>
        {navItems &&
          navItems.map((item) => {
            const Icon = item.icon;
            return (
              <Link
                key={item.href}
                to={item.href}
                onClick={onNavigate}
                data-testid={item.mobileTestId}
                className={`flex items-center gap-3 px-3 py-2.5 rounded-card text-sm font-semibold transition-colors ${
                  item.isActive
                    ? "bg-red-50 dark:bg-red-500/10 text-red-600 dark:text-red-400 border border-red-200 dark:border-red-500/30"
                    : "text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-900/60"
                }`}
              >
                <Icon className={`w-4 h-4 ${item.iconColor || ""}`} />
                <span className="flex-1">{item.label}</span>
                <RightIcon className="w-4 h-4 opacity-50" />
              </Link>
            );
          })}

        {moduleNavItems &&
          moduleNavItems.map((item) => {
            const Icon = item.icon;
            return (
              <Link
                key={item.href}
                to={item.href}
                onClick={onNavigate}
                data-testid={item.mobileTestId}
                className={`flex items-center gap-3 px-3 py-2.5 rounded-card text-sm font-semibold transition-colors border ${
                  item.isActive
                    ? item.activeClass
                    : "text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-900/60 border-transparent"
                }`}
              >
                <Icon className={`w-4 h-4 ${item.iconColor || ""}`} />
                <span className="flex-1">{item.label}</span>
                <RightIcon className="w-4 h-4 opacity-50" />
              </Link>
            );
          })}
      </>
    );
  }

  return (
    <div className="space-y-4 py-1">
      {modules.map((module) => {
        const ModuleIcon = module.icon;

        return (
          <div key={module.id} className="space-y-1">
            <div className="flex items-center gap-2 px-2.5 py-1 text-[11px] font-black uppercase tracking-wider text-ink-tertiary">
              <ModuleIcon className={`w-3.5 h-3.5 ${module.iconColor}`} />
              <span>{module.label}</span>
            </div>
            <div className="space-y-1">
              {module.items.map((item) => {
                const Icon = item.icon;
                const isActive = item.isItemActive
                  ? item.isItemActive(currentPath)
                  : currentPath === item.href;

                return (
                  <Link
                    key={item.href}
                    to={item.href}
                    onClick={onNavigate}
                    data-testid={item.mobileTestId}
                    className={`flex items-center gap-2.5 px-3 py-2 rounded-card text-xs font-semibold transition-colors border ${
                      isActive
                        ? `${module.activeClass} font-bold shadow-sm`
                        : "text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-900/60 border-transparent"
                    }`}
                  >
                    <Icon className={`w-4 h-4 shrink-0 ${item.iconColor || module.iconColor}`} />
                    <span className="flex-1">{item.label}</span>
                    {isActive ? (
                      <div className="w-1.5 h-1.5 rounded-full bg-current shrink-0" />
                    ) : (
                      <RightIcon className="w-3.5 h-3.5 opacity-40 shrink-0" />
                    )}
                  </Link>
                );
              })}
            </div>
          </div>
        );
      })}
    </div>
  );
}

export function ModuleDropdownTrigger({
  module,
  currentPath = "",
  align = "start",
  contentWidth = "w-72",
}) {
  const ModuleIcon = module.icon;
  const isModActive = module.isModuleActive
    ? module.isModuleActive(currentPath)
    : false;

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          data-testid={module.triggerTestId}
          data-module-id={module.id}
          aria-label={`${module.label} modülü menüsü`}
          className={`inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-control text-[11px] font-extrabold font-sans transition-all cursor-pointer border active:scale-95 shadow-sm whitespace-nowrap ${
            isModActive ? module.activeClass : module.idleClass
          }`}
        >
          <ModuleIcon className={`w-3.5 h-3.5 shrink-0 ${module.iconColor}`} />
          <span className="truncate">{module.label}</span>
          <ChevronDown className="w-3 h-3 opacity-70 ml-0.5 shrink-0" />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent
        align={align}
        sideOffset={8}
        className={`${contentWidth} p-1.5 font-sans space-y-1 bg-popover text-popover-foreground border-border-default shadow-lg max-h-[70vh] overflow-y-auto`}
      >
        <div className="px-2.5 py-1.5 text-[10px] font-extrabold text-ink-tertiary uppercase tracking-wider border-b border-border-default mb-1">
          {module.headerTitle}
        </div>
        {module.items.map((item) => {
          const Icon = item.icon;
          const isChildActive = item.isItemActive
            ? item.isItemActive(currentPath)
            : item.href === currentPath;

          return (
            <DropdownMenuItem key={item.href} asChild>
              <Link
                to={item.href}
                data-testid={item.testId}
                className={`flex items-center gap-2.5 px-3 py-2 rounded-lg text-xs font-semibold cursor-pointer transition-colors ${
                  isChildActive
                    ? `${module.activeClass} font-bold`
                    : "text-ink-secondary hover:bg-surface-card-2"
                }`}
              >
                <Icon className={`w-4 h-4 shrink-0 ${item.iconColor || module.iconColor}`} />
                <span className="flex-1">{item.label}</span>
                {isChildActive && (
                  <div className="w-1.5 h-1.5 rounded-full bg-current shrink-0" />
                )}
              </Link>
            </DropdownMenuItem>
          );
        })}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

export function MobileBrandSwitch({ selectedBrand, onSelect }) {
  return (
    <button
      type="button"
      onClick={onSelect}
      data-testid="mobile-nav-brand-selection"
      className="w-full flex items-center gap-3 px-3 py-2.5 rounded-card text-sm font-semibold transition-colors border border-blue-200/60 dark:border-blue-500/30 text-blue-700 dark:text-blue-400 bg-blue-50 dark:bg-blue-500/10 hover:bg-blue-100 dark:hover:bg-blue-500/20"
    >
      <span className="w-4 h-4 flex items-center justify-center shrink-0">
        {getBrandLogo(selectedBrand, "w-4 h-4 object-contain")}
      </span>
      <span className="flex-1 text-left">
        {selectedBrand && selectedBrand !== "Tüm Markalar"
          ? `Marka: ${selectedBrand}`
          : "Marka Seç"}
      </span>
      <ChevronRight className="w-4 h-4 opacity-50" />
    </button>
  );
}

export default function AppShell({ children }) {
  const { user, logout } = useAuth();
  const { selectedBrand } = useBrand();
  const location = useLocation();
  const navigate = useNavigate();
  const [mobileOpen, setMobileOpen] = useState(false);

  const doLogout = async () => {
    setMobileOpen(false);
    await logout();
    navigate("/login");
  };

  return (
    <div className="min-h-screen bg-surface-page text-ink-primary flex flex-col font-sans selection:bg-red-500 selection:text-white transition-colors duration-300">
      {/* VERCEL / LINEAR STYLE GLASSMORPHIC HEADER */}
      <header
        data-testid="app-header"
        className="sticky top-0 z-50 border-b border-border-default surface-card transition-colors duration-standard ease-swift"
      >
        {/* PRIMARY ROW: brand + restaurant + theme + user */}
        <div className="px-4 sm:px-8 py-3">
          <div className="max-w-[1536px] mx-auto flex items-center justify-between gap-4">
            {/* LOGO & BRAND */}
            <Link
              to="/dashboard"
              className="flex items-center gap-3 group cursor-pointer shrink-0"
              data-testid="brand-link"
            >
              <div className="w-9 h-9 rounded-card bg-risk-critical flex items-center justify-center group-hover:scale-105 transition-transform">
                <ShieldCheck className="w-5 h-5 text-white" />
              </div>
              <div>
                <div className="text-[10px] font-sans font-bold text-risk-critical uppercase tracking-widest leading-none">
                  ABCD Tech Solutions
                </div>
                <div className="text-sm font-extrabold text-ink-primary tracking-tight group-hover:text-risk-critical transition-colors">
                  AI Uzman
                </div>
              </div>
            </Link>

            {/* DESKTOP UTILITY (>=xl) */}
            <div className="hidden xl:flex items-center gap-2 sm:gap-2.5">
              {/* ACTIVE BRAND BADGE / SWITCHER BUTTON */}
              <button
                type="button"
                onClick={() => navigate("/brand-selection")}
                title="Restoran Zincirini Değiştir"
                className="inline-flex items-center gap-2 px-3 py-1.5 rounded-card text-xs font-extrabold bg-blue-500/10 hover:bg-blue-500/20 text-blue-600 dark:text-blue-400 border border-blue-500/30 transition-all cursor-pointer active:scale-95 shadow-sm"
              >
                {selectedBrand && selectedBrand !== "Tüm Markalar" ? (
                  <>
                    <span className="w-4 h-4 flex items-center justify-center">
                      {getBrandLogo(selectedBrand, "w-4 h-4 object-contain")}
                    </span>
                    <span className="max-w-[120px] truncate">{selectedBrand}</span>
                  </>
                ) : (
                  <>
                    <Store className="w-4 h-4 text-blue-500" />
                    <span>{selectedBrand || "Marka Seç"}</span>
                  </>
                )}
                <ChevronRight className="w-3.5 h-3.5 text-blue-400/80" />
              </button>

              {(location.pathname === "/dashboard" || location.pathname === "/") && <ThemeToggle />}

              <div className="ml-1 pl-2 sm:pl-3 border-l border-border-default flex items-center gap-3">
                {user?.name && (
                  <div className="hidden 2xl:flex flex-col text-right">
                    <div className="text-xs font-semibold text-ink-primary font-sans leading-tight">
                      {user.name}
                    </div>
                    <div className="text-[10px] text-ink-tertiary font-sans leading-tight">
                      {user.email}
                    </div>
                  </div>
                )}
                {/* Avatar + Dropdown */}
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <button
                      type="button"
                      data-testid="user-menu-trigger"
                      className="w-9 h-9 rounded-full bg-risk-critical hover:bg-risk-critical-2 flex items-center justify-center text-white font-bold text-sm shadow-card transition-colors duration-standard ease-swift active:scale-95"
                      aria-label="Kullanıcı menüsü"
                    >
                      {user?.name ? (
                        user.name.charAt(0).toUpperCase()
                      ) : (
                        <UserIcon className="w-4 h-4" />
                      )}
                    </button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent
                    align="end"
                    sideOffset={8}
                    className="w-56 bg-popover text-popover-foreground border-border-default"
                  >
                    {user && (
                      <div className="px-3 py-2.5 border-b border-border-default mb-1">
                        <div className="text-sm font-bold text-ink-primary truncate">
                          {user.name}
                        </div>
                        <div className="text-[11px] text-ink-tertiary truncate">{user.email}</div>
                        {user.role && (
                          <div className="text-[10px] uppercase tracking-wider font-bold text-risk-critical mt-1">
                            {user.role}
                          </div>
                        )}
                      </div>
                    )}
                    <DropdownMenuItem
                      onSelect={doLogout}
                      data-testid="user-menu-logout"
                      className="flex items-center gap-2 px-3 py-2 text-xs font-semibold text-red-600 dark:text-red-400 rounded-lg cursor-pointer"
                    >
                      <LogOut className="w-3.5 h-3.5" /> Oturumu Kapat
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              </div>
            </div>

            {/* MOBILE NAV (<xl): hamburger menu */}
            <div className="flex xl:hidden items-center gap-2">
              {(location.pathname === "/dashboard" || location.pathname === "/") && <ThemeToggle />}
              <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
                <SheetTrigger asChild>
                  <button
                    type="button"
                    data-testid="mobile-menu-trigger"
                    aria-label="Menüyü aç"
                    className="p-2 rounded-card bg-surface-card-2 border border-border-default text-ink-secondary hover:bg-surface-page-2 transition-colors"
                  >
                    {mobileOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
                  </button>
                </SheetTrigger>
                <SheetContent
                  side="right"
                  className="w-[300px] sm:w-[340px] font-sans p-0 flex flex-col bg-surface-card border-l border-border-default"
                >
                  <SheetHeader className="p-5 border-b border-border-default">
                    <SheetTitle className="flex items-center gap-2 text-ink-primary">
                      <ShieldCheck className="w-5 h-5 text-risk-critical" />
                      <span className="text-sm">ABCD Tech Solutions İSG</span>
                    </SheetTitle>
                    <SheetDescription className="text-xs text-ink-tertiary">
                      AI Uzman
                    </SheetDescription>
                  </SheetHeader>

                  {/* USER INFO */}
                  {user && (
                    <div className="px-5 py-4 border-b border-border-default bg-surface-page-2">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-full bg-risk-critical flex items-center justify-center text-white font-bold text-sm shrink-0">
                          {user.name ? (
                            user.name.charAt(0).toUpperCase()
                          ) : (
                            <UserIcon className="w-5 h-5" />
                          )}
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="text-sm font-semibold text-ink-primary truncate">
                            {user.name || "Kullanıcı"}
                          </div>
                          <div className="text-[11px] text-ink-tertiary truncate">{user.email}</div>
                          {user.role && (
                            <div className="text-[10px] uppercase tracking-wider font-bold text-risk-critical mt-0.5">
                              {user.role}
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  )}

                  {/* NAV ITEMS */}
                  <nav className="flex-1 overflow-y-auto py-2 px-3 space-y-3">
                    <MobileNavList
                      modules={MODULE_NAV_CONFIG}
                      currentPath={location.pathname}
                      onNavigate={() => setMobileOpen(false)}
                    />

                    {/* BRAND SWITCH */}
                    <div className="pt-2 border-t border-border-default">
                      <MobileBrandSwitch
                        selectedBrand={selectedBrand}
                        onSelect={() => {
                          setMobileOpen(false);
                          navigate("/brand-selection");
                        }}
                      />
                    </div>
                  </nav>

                  {/* LOGOUT */}
                  <div className="p-3 border-t border-border-default">
                    <button
                      type="button"
                      onClick={doLogout}
                      data-testid="mobile-logout-btn"
                      className="w-full inline-flex items-center gap-2 px-3 py-2.5 rounded-card text-sm font-semibold text-risk-critical hover:bg-risk-critical-bg border border-transparent hover:border-risk-critical-border transition-colors"
                    >
                      <LogOut className="w-4 h-4" /> Oturumu Kapat
                    </button>
                  </div>
                </SheetContent>
              </Sheet>
            </div>
          </div>
        </div>

        {/* SECONDARY ROW (>=xl): six independent module dropdowns */}
        <div
          data-testid="module-nav-row"
          className="hidden xl:block border-t border-border-default bg-surface-page-2/40 px-4 sm:px-8 py-2"
        >
          <nav
            data-testid="module-nav"
            aria-label="Modül gezinme çubuğu"
            className="max-w-[1536px] mx-auto flex flex-wrap items-center gap-1.5"
          >
            {MODULE_NAV_CONFIG.map((module) => (
              <ModuleDropdownTrigger
                key={module.id}
                module={module}
                currentPath={location.pathname}
                align="start"
                contentWidth={module.id === "employee-training" ? "w-80" : "w-72"}
              />
            ))}
          </nav>
        </div>
      </header>

      {/* MAIN CONTENT AREA */}
      <main className="flex-1 max-w-7xl w-full mx-auto p-4 sm:p-6 lg:p-8">{children}</main>

      {/* FOOTER */}
      <footer className="border-t border-border-default mt-16 py-6 bg-surface-card-2 transition-colors duration-300">
        <div className="max-w-7xl mx-auto px-4 sm:px-8 text-xs font-sans text-ink-tertiary flex items-center justify-between gap-4">
          <div className="flex items-center gap-3 min-w-0">
            <CompanyLogo size="md" />
            <span className="truncate">ABCD Tech Solutions SAN. VE TİC. A.Ş. — İSG Risk Analizi</span>
          </div>
          <span className="tabular-nums text-red-600 dark:text-red-400/90 font-mono font-bold shrink-0">
            v1.0
          </span>
        </div>
      </footer>
    </div>
  );
}
