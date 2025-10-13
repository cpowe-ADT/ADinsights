import { createContext, useContext, useEffect, useLayoutEffect, useMemo, useState } from "react";

type Theme = "light" | "dark";

type ThemeContextValue = {
  theme: Theme;
  setTheme: (next: Theme) => void;
  toggleTheme: () => void;
};

const STORAGE_KEY = "adinsights-theme";

const ThemeContext = createContext<ThemeContextValue | undefined>(undefined);

function getSystemTheme(): Theme {
  if (typeof window === "undefined") {
    return "light";
  }

  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function getStoredTheme(): Theme | null {
  if (typeof window === "undefined") {
    return null;
  }

  const stored = window.localStorage.getItem(STORAGE_KEY);
  return stored === "light" || stored === "dark" ? stored : null;
}

export const ThemeProvider = ({ children }: { children: React.ReactNode }) => {
  const [theme, setThemeState] = useState<Theme>(() => getStoredTheme() ?? getSystemTheme());
  const [isManual, setIsManual] = useState<boolean>(() => getStoredTheme() !== null);

  useEffect(() => {
    if (isManual) {
      window.localStorage.setItem(STORAGE_KEY, theme);
    } else {
      window.localStorage.removeItem(STORAGE_KEY);
    }
  }, [isManual, theme]);

  useEffect(() => {
    const mediaQuery = window.matchMedia("(prefers-color-scheme: dark)");
    const handleChange = (event: MediaQueryListEvent) => {
      if (!isManual) {
        setThemeState(event.matches ? "dark" : "light");
      }
    };

    mediaQuery.addEventListener("change", handleChange);
    return () => mediaQuery.removeEventListener("change", handleChange);
  }, [isManual]);

  useLayoutEffect(() => {
    const root = document.documentElement;
    const className = theme === "dark" ? "theme-dark" : "theme-light";

    root.classList.remove("theme-dark", "theme-light");
    root.classList.add(className);
  }, [theme]);

  const contextValue = useMemo<ThemeContextValue>(() => ({
    theme,
    setTheme: (nextTheme) => {
      setIsManual(true);
      setThemeState(nextTheme);
    },
    toggleTheme: () => {
      setIsManual(true);
      setThemeState((prev) => (prev === "dark" ? "light" : "dark"));
    },
  }), [theme]);

  return <ThemeContext.Provider value={contextValue}>{children}</ThemeContext.Provider>;
};

export function useTheme() {
  const context = useContext(ThemeContext);

  if (!context) {
    throw new Error("useTheme must be used within a ThemeProvider");
  }

  return context;
}
