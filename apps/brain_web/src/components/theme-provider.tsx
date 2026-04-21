"use client";

import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

type Theme = "dark" | "light";
type Density = "comfortable" | "compact";

interface ThemeContextValue {
  theme: Theme;
  density: Density;
  setTheme: (t: Theme) => void;
  setDensity: (d: Density) => void;
}

const ThemeContext = createContext<ThemeContextValue | undefined>(undefined);

export function useTheme(): ThemeContextValue {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error("useTheme must be used within ThemeProvider");
  return ctx;
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<Theme>("dark");
  const [density, setDensityState] = useState<Density>("comfortable");

  // Hydrate from localStorage on mount; default to dark/comfortable.
  useEffect(() => {
    const savedTheme = (localStorage.getItem("brain-theme") as Theme | null) ?? "dark";
    const savedDensity =
      (localStorage.getItem("brain-density") as Density | null) ?? "comfortable";
    setThemeState(savedTheme);
    setDensityState(savedDensity);
    document.documentElement.dataset.theme = savedTheme;
    document.documentElement.dataset.density = savedDensity;
  }, []);

  const setTheme = (t: Theme) => {
    localStorage.setItem("brain-theme", t);
    document.documentElement.dataset.theme = t;
    setThemeState(t);
  };

  const setDensity = (d: Density) => {
    localStorage.setItem("brain-density", d);
    document.documentElement.dataset.density = d;
    setDensityState(d);
  };

  return (
    <ThemeContext.Provider value={{ theme, density, setTheme, setDensity }}>
      {children}
    </ThemeContext.Provider>
  );
}
