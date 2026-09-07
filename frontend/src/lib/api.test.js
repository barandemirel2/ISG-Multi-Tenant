import { resolveApiBaseUrl } from "./api";

// ---------------------------------------------------------------------------
// BACKEND_ORIGIN coverage — derives the static-asset origin from the same
// REACT_APP_BACKEND_URL that resolveApiBaseUrl consumes. PhotoUploader and
// PhotoLightbox depend on it instead of hardcoded ``http://localhost:8000``.
// ---------------------------------------------------------------------------
function loadBackendOriginWith(value) {
  let loaded;
  jest.isolateModules(() => {
    if (value === undefined) {
      delete process.env.REACT_APP_BACKEND_URL;
    } else {
      process.env.REACT_APP_BACKEND_URL = value;
    }
    loaded = require("./api");
  });
  return loaded.BACKEND_ORIGIN;
}

describe("BACKEND_ORIGIN", () => {
  const ORIGINAL_ENV = process.env.REACT_APP_BACKEND_URL;

  afterEach(() => {
    if (ORIGINAL_ENV === undefined) {
      delete process.env.REACT_APP_BACKEND_URL;
    } else {
      process.env.REACT_APP_BACKEND_URL = ORIGINAL_ENV;
    }
  });

  test("unset env yields empty origin (relative paths work behind proxy)", () => {
    expect(loadBackendOriginWith(undefined)).toBe("");
  });

  test("/api yields empty origin (reverse-proxy deployment)", () => {
    expect(loadBackendOriginWith("/api")).toBe("");
  });

  test("absolute origin strips the /api suffix", () => {
    expect(loadBackendOriginWith("http://localhost:8000")).toBe(
      "http://localhost:8000"
    );
  });

  test("trailing slash on absolute origin is normalised", () => {
    expect(loadBackendOriginWith("http://localhost:8000/")).toBe(
      "http://localhost:8000"
    );
  });

  test("/api suffix on absolute origin is stripped", () => {
    expect(loadBackendOriginWith("http://localhost:8000/api")).toBe(
      "http://localhost:8000"
    );
    expect(loadBackendOriginWith("http://localhost:8000/api/")).toBe(
      "http://localhost:8000"
    );
  });
});

// ---------------------------------------------------------------------------
// Pure resolver coverage
// ---------------------------------------------------------------------------

describe("resolveApiBaseUrl", () => {
  test("missing input returns /api", () => {
    expect(resolveApiBaseUrl(undefined)).toBe("/api");
    expect(resolveApiBaseUrl(null)).toBe("/api");
  });

  test("empty input returns /api", () => {
    expect(resolveApiBaseUrl("")).toBe("/api");
  });

  test("whitespace input returns /api", () => {
    expect(resolveApiBaseUrl("   ")).toBe("/api");
    expect(resolveApiBaseUrl("\t\n")).toBe("/api");
  });

  test("/api remains /api", () => {
    expect(resolveApiBaseUrl("/api")).toBe("/api");
  });

  test("/api/ becomes /api", () => {
    expect(resolveApiBaseUrl("/api/")).toBe("/api");
  });

  test("whitespace around /api/ is normalized", () => {
    expect(resolveApiBaseUrl("  /api/  ")).toBe("/api");
    expect(resolveApiBaseUrl("\t/api/\n")).toBe("/api");
  });

  test("backend origin receives exactly one /api", () => {
    expect(resolveApiBaseUrl("http://localhost:8000")).toBe(
      "http://localhost:8000/api"
    );
  });

  test("backend origin with trailing slash receives exactly one /api", () => {
    expect(resolveApiBaseUrl("http://localhost:8000/")).toBe(
      "http://localhost:8000/api"
    );
  });

  test("origin already ending in /api is unchanged", () => {
    expect(resolveApiBaseUrl("http://localhost:8000/api")).toBe(
      "http://localhost:8000/api"
    );
  });

  test("origin ending in /api/ is normalized", () => {
    expect(resolveApiBaseUrl("http://localhost:8000/api/")).toBe(
      "http://localhost:8000/api"
    );
  });

  test("HTTPS origin behaves correctly", () => {
    expect(resolveApiBaseUrl("https://example.com")).toBe(
      "https://example.com/api"
    );
    expect(resolveApiBaseUrl("https://example.com/api")).toBe(
      "https://example.com/api"
    );
  });

  test("result never ends in /api/api", () => {
    const inputs = [
      undefined,
      null,
      "",
      "   ",
      "/api",
      "/api/",
      "  /api/  ",
      "http://localhost:8000",
      "http://localhost:8000/",
      "http://localhost:8000/api",
      "http://localhost:8000/api/",
      "https://example.com",
      "https://example.com/api",
      "https://example.com/api/",
    ];
    for (const value of inputs) {
      const result = resolveApiBaseUrl(value);
      expect(result.endsWith("/api/api")).toBe(false);
      expect(/([^/])\/api\/api$/.test(result)).toBe(false);
    }
  });
});

// ---------------------------------------------------------------------------
// Axios contract coverage with the production build argument
// ---------------------------------------------------------------------------

describe("Axios baseURL contract with REACT_APP_BACKEND_URL=/api", () => {
  const ORIGINAL_ENV = process.env.REACT_APP_BACKEND_URL;

  afterEach(() => {
    if (ORIGINAL_ENV === undefined) {
      delete process.env.REACT_APP_BACKEND_URL;
    } else {
      process.env.REACT_APP_BACKEND_URL = ORIGINAL_ENV;
    }
  });

  const loadApiWith = (value) => {
    let loaded;
    jest.isolateModules(() => {
      if (value === undefined) {
        delete process.env.REACT_APP_BACKEND_URL;
      } else {
        process.env.REACT_APP_BACKEND_URL = value;
      }
      loaded = require("./api");
    });
    return loaded;
  };

  test("api.defaults.baseURL is /api when REACT_APP_BACKEND_URL=/api", () => {
    const mod = loadApiWith("/api");
    expect(mod.default.defaults.baseURL).toBe("/api");
  });

  test("login endpoint conceptually resolves to /api/auth/login", () => {
    const mod = loadApiWith("/api");
    const baseURL = mod.default.defaults.baseURL;
    const resolved = `${baseURL}/auth/login`;
    expect(resolved).toBe("/api/auth/login");
    expect(resolved).not.toBe("/api/api/auth/login");
  });

  test("me endpoint conceptually resolves to /api/auth/me", () => {
    const mod = loadApiWith("/api");
    const baseURL = mod.default.defaults.baseURL;
    const resolved = `${baseURL}/auth/me`;
    expect(resolved).toBe("/api/auth/me");
    expect(resolved).not.toBe("/api/api/auth/me");
  });

  test("audits endpoint conceptually resolves to /api/audits", () => {
    const mod = loadApiWith("/api");
    const baseURL = mod.default.defaults.baseURL;
    const resolved = `${baseURL}/audits`;
    expect(resolved).toBe("/api/audits");
    expect(resolved).not.toBe("/api/api/audits");
  });

  test("unset REACT_APP_BACKEND_URL falls back to /api", () => {
    const mod = loadApiWith(undefined);
    expect(mod.default.defaults.baseURL).toBe("/api");
  });

  test("absolute origin still produces a single /api suffix", () => {
    const mod = loadApiWith("http://localhost:8000");
    expect(mod.default.defaults.baseURL).toBe("http://localhost:8000/api");
  });
});
