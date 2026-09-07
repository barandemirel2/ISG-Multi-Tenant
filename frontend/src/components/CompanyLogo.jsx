import React from "react";
import companyLogoImg from "./company-logo.png";

// ABCD Tech Solutions şirket logosu — footer'ın soluna, v1 yazısıyla aynı hizada,
// normal akış içinde (fixed/scroll-asılı DEĞİL) gösterilir.
// ``size`` prop: "sm" (24px), "md" (32px), "lg" (40px).
const sizeClasses = {
  sm: "h-6",
  md: "h-8",
  lg: "h-9",
};

export default function CompanyLogo({ size = "md", className = "" }) {
  return (
    <img
      src={companyLogoImg}
      alt="ABCD Tech Solutions Logo"
      title="ABCD Tech Solutions SAN. VE TİC. A.Ş."
      className={`${sizeClasses[size] ?? sizeClasses.md} w-auto object-contain drop-shadow-sm dark:brightness-110 transition-all inline-block align-middle ${className}`}
    />
  );
}
