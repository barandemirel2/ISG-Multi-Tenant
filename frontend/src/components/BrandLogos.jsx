import React from "react";

/**
 * Marka logosu resolver — S12 ile artık tüm logolar lokal.
 *
 * 5 Wikipedia logosu `frontend/public/logos/` altında:
 *   burger-king.svg, popeyes.svg, arbys.svg, sbarro.svg, subway.svg
 * 2 inline SVG (Usta Dönerci / Usta Pideci) zaten local — değişmedi.
 *
 * S12 öncesi: Wikipedia CDN'den yükleniyordu — UAT kuralı "logolar
 * lokalde + raporlarda" gereği CDN bağımlılığı kaldırıldı.
 */
export function getBrandLogo(nameOrBrand = "", className = "w-6 h-6 object-contain") {
  const str = String(nameOrBrand).toLowerCase();

  // BURGER KING
  if (str.includes("burger") || str.includes("bk")) {
    return (
      <img
        src="/logos/burger-king.svg"
        alt="Burger King"
        className={className}
        loading="lazy"
      />
    );
  }

  // POPEYES
  if (str.includes("popeye")) {
    return (
      <img
        src="/logos/popeyes.svg"
        alt="Popeyes"
        className={className}
        loading="lazy"
      />
    );
  }

  // ARBY'S
  if (str.includes("arby")) {
    return (
      <img
        src="/logos/arbys.svg"
        alt="Arby's"
        className={className}
        loading="lazy"
      />
    );
  }

  // SBARRO
  if (str.includes("sbarro")) {
    return (
      <img
        src="/logos/sbarro.svg"
        alt="Sbarro"
        className={className}
        loading="lazy"
      />
    );
  }

  // USTA DÖNERCİ
  if (str.includes("doner") || str.includes("döner")) {
    return (
      <svg
        viewBox="0 0 100 100"
        className={className}
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
      >
        <rect width="100" height="100" rx="22" fill="#991B1B" />
        <path
          d="M25 35C25 35 35 25 50 25C65 25 75 35 75 35V50C75 63.8071 63.8071 75 50 75C36.1929 75 25 63.8071 25 50V35Z"
          fill="#F59E0B"
        />
        <rect x="46" y="15" width="8" height="25" rx="4" fill="#FFFFFF" />
        <circle cx="50" cy="50" r="10" fill="#7F1D1D" />
      </svg>
    );
  }

  // USTA PİDECİ
  if (str.includes("pide")) {
    return (
      <svg
        viewBox="0 0 100 100"
        className={className}
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
      >
        <rect width="100" height="100" rx="22" fill="#C2410C" />
        <path
          d="M15 50C15 15 30 25 50 25C70 25 85 35 85 50C85 65 70 75 50 75C30 75 15 65 15 50Z"
          fill="#FBBF24"
        />
        <path
          d="M30 50C30 42 40 37 50 37C60 37 70 42 70 50C70 58 60 63 50 63C40 63 30 58 30 50Z"
          fill="#78350F"
        />
        <circle cx="42" cy="48" r="3" fill="#F59E0B" />
        <circle cx="58" cy="52" r="3" fill="#F59E0B" />
      </svg>
    );
  }

  // SUBWAY
  if (str.includes("subway")) {
    return (
      <img
        src="/logos/subway.svg"
        alt="Subway"
        className={className}
        loading="lazy"
      />
    );
  }

  return null;
}

/**
 * Marka adından local logo dosya yolunu döndür (PDF/Excel export için).
 * `<img src={...}>` ve `RLImage(filename=...)` için uygun mutlak yol.
 */
export function getBrandLogoPath(nameOrBrand = "") {
  const str = String(nameOrBrand).toLowerCase();
  if (str.includes("burger") || str.includes("bk")) return "burger-king.svg";
  if (str.includes("popeye")) return "popeyes.svg";
  if (str.includes("arby")) return "arbys.svg";
  if (str.includes("sbarro")) return "sbarro.svg";
  if (str.includes("subway")) return "subway.svg";
  return null;
}
