import axios from "axios";

export function resolveApiBaseUrl(rawBackendUrl) {
  const normalized = (rawBackendUrl || "").trim().replace(/\/+$/, "");

  if (!normalized) {
    return "/api";
  }

  if (normalized === "/api" || normalized.endsWith("/api")) {
    return normalized;
  }

  return `${normalized}/api`;
}

export const API = resolveApiBaseUrl(process.env.REACT_APP_BACKEND_URL);

// Backend origin (REACT_APP_BACKEND_URL'ın "/api" soneksiz hali). Upload'lar
// backend tarafından ``/uploads/...`` path'i ile servis edilir; aynı origin
// altında reverse-proxy deploy'da relative URL yeterli, dev'de cross-origin
// (ör. http://localhost:3000 frontend + http://localhost:8000 backend) için
// absolute origin şart. Statik asset'leri çözerken PhotoUploader /
// PhotoLightbox bu sabiti kullanır — yeni paralel config sistemi açmaz.
export const BACKEND_ORIGIN = (() => {
  const raw = (process.env.REACT_APP_BACKEND_URL || "").trim().replace(/\/+$/, "");
  if (!raw) return "";
  if (raw === "/api") return "";
  if (raw.endsWith("/api")) return raw.slice(0, -"/api".length);
  return raw;
})();

const api = axios.create({
  baseURL: API,
  withCredentials: true,
});

// 401 auto-refresh interceptor — silently swap in a new access token via refresh_token cookie.
let refreshPromise = null;

api.interceptors.response.use(
  (r) => r,
  async (error) => {
    const original = error.config;
    const status = error.response?.status;
    const url = original?.url || "";

    // Don't try to refresh for auth endpoints themselves.
    const isAuthEndpoint =
      url.includes("/auth/login") ||
      url.includes("/auth/register") ||
      url.includes("/auth/refresh") ||
      url.includes("/auth/logout");

    if (status === 401 && !original._retry && !isAuthEndpoint) {
      original._retry = true;
      try {
        if (!refreshPromise) {
          refreshPromise = axios.post(`${API}/auth/refresh`, {}, { withCredentials: true })
            .finally(() => { refreshPromise = null; });
        }
        await refreshPromise;
        return api(original);
      } catch (e) {
        // Refresh failed — send user back to login.
        if (typeof window !== "undefined" && !window.location.pathname.startsWith("/login")) {
          window.location.href = "/login";
        }
      }
    }
    return Promise.reject(error);
  }
);

export default api;

export function formatApiErrorDetail(detail) {
  if (detail == null) return "Bir hata oluştu, lütfen tekrar deneyin.";
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail))
    return detail
      .map((e) => (e && typeof e.msg === "string" ? e.msg : JSON.stringify(e)))
      .filter(Boolean)
      .join(" ");
  if (detail && typeof detail.msg === "string") return detail.msg;
  return String(detail);
}
