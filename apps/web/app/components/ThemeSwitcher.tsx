"use client";
import { useEffect, useState } from "react";

export type ThemePreference = "system" | "light" | "dark";

const STORAGE_KEY = "af-theme";

function readStoredTheme(): ThemePreference {
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    if (stored === "light" || stored === "dark") return stored;
  } catch {
    /* localStorage unavailable */
  }
  return "system";
}

function applyTheme(pref: ThemePreference) {
  const root = document.documentElement;
  if (pref === "system") {
    delete root.dataset.theme;
  } else {
    root.dataset.theme = pref;
  }
}

// Theme preference picker (light | dark | system). Mirrors the RoleSwitcher
// mount-after-hydration pattern: the first render always shows the "system"
// default so SSR/CSR markup match, and the persisted value is read in an
// effect. A tiny inline script in layout.tsx pre-applies data-theme before
// paint to avoid a flash of the wrong theme.
export function ThemeSwitcher() {
  const [theme, setTheme] = useState<ThemePreference>("system");
  useEffect(() => {
    setTheme(readStoredTheme());
  }, []);

  function onChange(next: ThemePreference) {
    setTheme(next);
    try {
      if (next === "system") window.localStorage.removeItem(STORAGE_KEY);
      else window.localStorage.setItem(STORAGE_KEY, next);
    } catch {
      /* localStorage unavailable */
    }
    applyTheme(next);
  }

  return (
    <div>
      <label htmlFor="theme-switcher">Theme</label>
      <select
        id="theme-switcher"
        data-testid="theme-switcher"
        value={theme}
        onChange={(e) => onChange(e.target.value as ThemePreference)}
      >
        <option value="system">system</option>
        <option value="light">light</option>
        <option value="dark">dark</option>
      </select>
    </div>
  );
}
