import React, { createContext, useContext, useState } from "react";

const BrandContext = createContext(null);

export const BRANDS_LIST = [
  { id: "burger-king", name: "Burger King", color: "#D62300", bgGlow: "rgba(214,35,0,0.15)", tag: "Alevde Izgara Ateşi" },
  { id: "popeyes", name: "Popeyes", color: "#FF6600", bgGlow: "rgba(255,102,0,0.15)", tag: "Louisiana Mutfak Lezzeti" },
  { id: "arbys", name: "Arby's", color: "#D3122A", bgGlow: "rgba(211,18,42,0.15)", tag: "Fırınlanmış Biftek Lezzeti" },
  { id: "subway", name: "Subway", color: "#008C38", bgGlow: "rgba(0,140,56,0.15)", tag: "Taze Sandviç ve Salata" },
  { id: "sbarro", name: "Sbarro", color: "#138808", bgGlow: "rgba(19,136,8,0.15)", tag: "Taze İtalyan Pizza Lezzeti" },
  { id: "usta-donerci", name: "Usta Dönerci", color: "#991B1B", bgGlow: "rgba(153,27,27,0.15)", tag: "Geleneksel Döner Lezzeti" },
  { id: "usta-pideci", name: "Usta Pideci", color: "#C2410C", bgGlow: "rgba(194,65,12,0.15)", tag: "Fırından Taze Pide Lezzeti" },
];

export function BrandProvider({ children }) {
  const [selectedBrand, setSelectedBrandState] = useState(() => {
    return localStorage.getItem("tab_selected_brand") || "";
  });

  const setSelectedBrand = (brandName) => {
    setSelectedBrandState(brandName);
    if (brandName) {
      localStorage.setItem("tab_selected_brand", brandName);
    } else {
      localStorage.removeItem("tab_selected_brand");
    }
  };

  const clearSelectedBrand = () => {
    setSelectedBrandState("");
    localStorage.removeItem("tab_selected_brand");
  };

  return (
    <BrandContext.Provider value={{ selectedBrand, setSelectedBrand, clearSelectedBrand, BRANDS_LIST }}>
      {children}
    </BrandContext.Provider>
  );
}

export function useBrand() {
  const context = useContext(BrandContext);
  if (!context) {
    return {
      selectedBrand: "",
      setSelectedBrand: () => {},
      clearSelectedBrand: () => {},
      BRANDS_LIST,
    };
  }
  return context;
}
