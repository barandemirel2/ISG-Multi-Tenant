import React, { createContext, useContext, useEffect, useRef, useState, useCallback } from "react";

const ThemeContext = createContext();

/**
 * Toggles the `dark` / `light` class on <html>.
 *
 * Semantics:
 *   - ``animate: false`` (default): direct synchronous class update.
 *     Used for initial mount / system-theme sync where starting a View
 *     Transition is unnecessary and unsafe (React StrictMode double-invokes
 *     mount effects in dev, which would otherwise trigger an overlapping
 *     transition runtime error: "Skipped ViewTransition due to another
 *     transition starting").
 *   - ``animate: true``: use View Transitions API when supported, with a
 *     graceful fallback to the direct update if the API throws synchronously
 *     (e.g. when another transition is in flight, or document is not in a
 *     supported state). The throw is not swallowed blindly — it is caught
 *     around the transition call only, and ``update()`` still runs so the
 *     canonical class mutation always succeeds.
 */
export function applyThemeClass(resolved, { animate = false } = {}) {
  const root = document.documentElement;
  const update = () => {
    if (resolved === "dark") {
      root.classList.add("dark");
      root.classList.remove("light");
    } else {
      root.classList.remove("dark");
      root.classList.add("light");
    }
  };

  if (animate && typeof document.startViewTransition === "function") {
    try {
      document.startViewTransition(update);
    } catch (_e) {
      // Transition API failed to start (e.g. another transition is in flight).
      // Fall back to the direct class update so theme application stays correct.
      // This is targeted around the API call only — update() is allowed to throw.
      update();
    }
  } else {
    update();
  }
}

export function ThemeProvider({ children }) {
  const [theme, setThemeState] = useState(() => {
    return localStorage.getItem("tab_isg_theme") || "dark";
  });

  const [effectiveTheme, setEffectiveTheme] = useState("dark");

  // Tracks whether the initial-sync effect has run at least once. Used to
  // decide whether to opt into the View Transitions animation path:
  //   - initial mount / system sync → animate: false (direct, no transition)
  //   - subsequent theme changes / explicit user toggle → animate: true
  // Persists across React StrictMode dev's mount/unmount/mount cycle because
  // useRef preserves identity; combined with the effect running after the
  // initial render, this also covers the StrictMode double-invoke (the first
  // invocation takes the no-animation path).
  const initialRunDone = useRef(false);

  const setTheme = useCallback((newTheme) => {
    setThemeState(newTheme);
    localStorage.setItem("tab_isg_theme", newTheme);
  }, []);

  useEffect(() => {
    const resolveTheme = () => {
      if (theme === "system") {
        return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
      }
      return theme;
    };

    const resolved = resolveTheme();
    setEffectiveTheme(resolved);
    // Initial sync (first effect run, including StrictMode dev double-invoke's
    // 2nd invocation) must not start a View Transition — that would collide
    // with any in-flight transition and surface a runtime error overlay on
    // the login screen before the user has interacted with the theme toggle.
    applyThemeClass(resolved, { animate: initialRunDone.current });
    initialRunDone.current = true;

    // Listen for OS theme changes when in "system" mode
    if (theme === "system") {
      const mediaQuery = window.matchMedia("(prefers-color-scheme: dark)");
      const handleChange = () => {
        const next = mediaQuery.matches ? "dark" : "light";
        setEffectiveTheme(next);
        applyThemeClass(next, { animate: true });
      };
      mediaQuery.addEventListener("change", handleChange);
      return () => mediaQuery.removeEventListener("change", handleChange);
    }
  }, [theme]);

  return (
    <ThemeContext.Provider value={{ theme, effectiveTheme, setTheme }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error("useTheme must be used within a ThemeProvider");
  }
  return context;
}

export default ThemeContext;
