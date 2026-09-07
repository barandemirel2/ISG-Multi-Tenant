import React, { useState, useMemo } from "react";
import catalogData from "../constants/restaurantCatalog.json";
import { getBrandLogo } from "./BrandLogos";
import { useBrand } from "@/context/BrandContext";
import { Building2, MapPin, RotateCcw } from "lucide-react";

export default function CascadingRestaurantSelect({
  id = "rn",
  dataTestId = "input-restaurant",
  value,
  onChange,
  onSelectBranch,
}) {
  const { selectedBrand } = useBrand();
  const availableBrands = catalogData.brands;

  const initialBrandId = useMemo(() => {
    if (!selectedBrand || selectedBrand === "Tüm Markalar") return "";
    const match = availableBrands.find(
      (b) => b.name.toLowerCase() === selectedBrand.toLowerCase() ||
             selectedBrand.toLowerCase().includes(b.name.toLowerCase())
    );
    return match ? match.id : "";
  }, [selectedBrand, availableBrands]);

  const [selectedBrandId, setSelectedBrandId] = useState(initialBrandId);
  const [selectedCityName, setSelectedCityName] = useState("");
  const [selectedDistrictName, setSelectedDistrictName] = useState("");
  const [citySearch, setCitySearch] = useState("");
  const currentBrand = useMemo(
    () => availableBrands.find((b) => b.id === selectedBrandId),
    [availableBrands, selectedBrandId]
  );

  const availableCities = useMemo(() => currentBrand?.cities || [], [currentBrand]);
  const filteredCities = useMemo(() => {
    if (!citySearch.trim()) return availableCities;
    return availableCities.filter((c) =>
      c.name.toLowerCase().includes(citySearch.toLowerCase().trim())
    );
  }, [availableCities, citySearch]);

  const currentCity = useMemo(
    () => availableCities.find((c) => c.name === selectedCityName),
    [availableCities, selectedCityName]
  );

  const availableDistricts = useMemo(() => currentCity?.districts || [], [currentCity]);

  const handleBrandSelect = (brand) => {
    setSelectedBrandId(brand.id);
    setSelectedCityName("");
    setSelectedDistrictName("");
    const name = brand.name;
    onChange(name);
    if (onSelectBranch) {
      onSelectBranch({
        name: name,
        brand: brand.name,
        city: "",
        district: "",
        code: `${brand.id.substring(0, 3).toUpperCase()}-101`,
        address: "Türkiye Şubesi",
      });
    }
  };

  const handleCitySelect = (cityName) => {
    setSelectedCityName(cityName);
    setSelectedDistrictName("");
    const name = `${currentBrand?.name || "Restoran"} — ${cityName}`;
    onChange(name);
    if (onSelectBranch) {
      onSelectBranch({
        name: name,
        brand: currentBrand?.name || "",
        city: cityName,
        district: "",
        code: `${currentBrand?.id?.substring(0, 3).toUpperCase() || "TAB"}-101`,
        address: `${cityName}, Türkiye`,
      });
    }
  };

  const handleDistrictSelect = (districtName) => {
    setSelectedDistrictName(districtName);
    const suggestedName = `${currentBrand?.name || ""} — ${selectedCityName} / ${districtName} Şubesi`;
    onChange(suggestedName);
    if (onSelectBranch) {
      onSelectBranch({
        name: suggestedName,
        brand: currentBrand?.name || "",
        city: selectedCityName,
        district: districtName,
        code: `${currentBrand?.id?.substring(0, 3).toUpperCase()}-${Math.floor(100 + Math.random() * 900)}`,
        address: `${districtName} Mh. ${selectedCityName}`,
      });
    }
  };

  const handleReset = () => {
    setSelectedBrandId("");
    setSelectedCityName("");
    setSelectedDistrictName("");
    setCitySearch("");
    onChange("");
  };

  return (
    <div className="space-y-4 w-full font-sans">
      <input
        id={id}
        data-testid={dataTestId}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="sr-only"
        aria-hidden="true"
      />

      <div className="p-4 border border-slate-200/80 dark:border-slate-800 rounded-card bg-slate-50/50 dark:bg-slate-900/50 space-y-4">
        {/* KATMAN 1: RESTORAN ZİNCİRİ SEÇİMİ */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <label className="text-[11px] font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider flex items-center gap-1.5">
              <Building2 className="w-3.5 h-3.5 text-red-600 dark:text-red-400" /> 1. ADIM: RESTORAN ZİNCİRİ SEÇİN *
            </label>
            {selectedBrandId && (
              <button
                type="button"
                onClick={handleReset}
                className="text-[10px] text-red-600 dark:text-red-400 hover:underline flex items-center gap-1 cursor-pointer"
              >
                <RotateCcw className="w-3 h-3" /> Seçimi Sıfırla
              </button>
            )}
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
            {availableBrands.map((brand) => {
              const isSelected = selectedBrandId === brand.id;
              return (
                <button
                  key={brand.id}
                  type="button"
                  onClick={() => handleBrandSelect(brand)}
                  className={`flex items-center gap-2.5 p-2.5 rounded-card border text-xs font-semibold font-sans transition-all duration-200 cursor-pointer ${
                    isSelected
                      ? "bg-red-500/10 border-red-500 text-red-700 dark:text-red-300 shadow-sm"
                      : "bg-white dark:bg-slate-900/80 border-slate-200 dark:border-slate-800 text-slate-700 dark:text-slate-300 hover:border-red-400/50"
                  }`}
                >
                  <div className="w-6 h-6 flex items-center justify-center flex-shrink-0">
                    {getBrandLogo(brand.name, "w-6 h-6 object-contain")}
                  </div>
                  <span className="truncate">{brand.name}</span>
                </button>
              );
            })}
          </div>
        </div>

        {/* KATMAN 2: İL SEÇİMİ (81 İL) */}
        {selectedBrandId && (
          <div className="space-y-2 pt-2 border-t border-slate-200/80 dark:border-slate-800">
            <div className="flex items-center justify-between gap-2 flex-wrap">
              <label className="text-[11px] font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider flex items-center gap-1.5">
                <MapPin className="w-3.5 h-3.5 text-amber-600 dark:text-amber-400" /> 2. ADIM: İL SEÇİN (81 İL)
              </label>
              <input
                type="text"
                value={citySearch}
                onChange={(e) => setCitySearch(e.target.value)}
                placeholder="İl ara (Örn: Adana, İstanbul...)"
                className="bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-800 rounded-lg px-2.5 py-1 text-[11px] text-slate-800 dark:text-slate-200 placeholder:text-slate-400 focus:outline-none focus:border-red-500 font-sans"
              />
            </div>

            <div className="max-h-36 overflow-y-auto pr-1 grid grid-cols-3 sm:grid-cols-6 gap-1.5">
              {filteredCities.map((city) => {
                const isSelected = selectedCityName === city.name;
                return (
                  <button
                    key={city.name}
                    type="button"
                    onClick={() => handleCitySelect(city.name)}
                    className={`px-2 py-1.5 rounded-lg border text-[11px] font-medium font-sans truncate transition-all cursor-pointer ${
                      isSelected
                        ? "bg-amber-500/15 border-amber-500 text-amber-700 dark:text-amber-300 font-bold"
                        : "bg-white dark:bg-slate-900/60 border-slate-200 dark:border-slate-800 text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800"
                    }`}
                  >
                    {city.name}
                  </button>
                );
              })}
            </div>
          </div>
        )}

        {/* KATMAN 3: İLÇE SEÇİMİ */}
        {selectedCityName && availableDistricts.length > 0 && (
          <div className="space-y-2 pt-2 border-t border-slate-200/80 dark:border-slate-800">
            <label className="text-[11px] font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider flex items-center gap-1.5">
              <MapPin className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400" /> 3. ADIM: İLÇE SEÇİN ({selectedCityName})
            </label>
            <div className="max-h-32 overflow-y-auto pr-1 grid grid-cols-3 sm:grid-cols-5 gap-1.5">
              {availableDistricts.map((district) => {
                const isSelected = selectedDistrictName === district;
                return (
                  <button
                    key={district}
                    type="button"
                    onClick={() => handleDistrictSelect(district)}
                    className={`px-2 py-1.5 rounded-lg border text-[11px] font-medium font-sans truncate transition-all cursor-pointer ${
                      isSelected
                        ? "bg-emerald-500/15 border-emerald-500 text-emerald-700 dark:text-emerald-300 font-bold"
                        : "bg-white dark:bg-slate-900/60 border-slate-200 dark:border-slate-800 text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800"
                    }`}
                  >
                    {district}
                  </button>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
