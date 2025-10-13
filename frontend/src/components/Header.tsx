import { FormEvent, ReactNode, useEffect, useMemo, useRef, useState } from "react";
import { Link, NavLink } from "react-router-dom";

import styles from "./Header.module.css";

type HeaderNavLink = {
  label: string;
  to: string;
  end?: boolean;
};

type MetricOption = {
  label: string;
  value: string;
};

type HeaderProps = {
  title: ReactNode;
  subtitle?: ReactNode;
  navLinks: HeaderNavLink[];
  metricOptions?: MetricOption[];
  selectedMetric?: string;
  onMetricChange?: (value: string) => void;
  onSearch?: (query: string) => void;
  userEmail?: string;
  onLogout: () => void;
};

type ThemeMode = "light" | "dark";

const THEME_STORAGE_KEY = "adinsights:theme";

const Header = ({
  title,
  subtitle,
  navLinks,
  metricOptions,
  selectedMetric,
  onMetricChange,
  onSearch,
  userEmail,
  onLogout,
}: HeaderProps) => {
  const [searchTerm, setSearchTerm] = useState("");
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement | null>(null);
  const [theme, setTheme] = useState<ThemeMode>(() => {
    if (typeof window === "undefined") {
      return "light";
    }

    const stored = window.localStorage.getItem(THEME_STORAGE_KEY) as ThemeMode | null;
    if (stored === "light" || stored === "dark") {
      return stored;
    }

    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  });

  useEffect(() => {
    if (typeof document === "undefined") {
      return;
    }

    document.documentElement.setAttribute("data-theme", theme);
    window.localStorage.setItem(THEME_STORAGE_KEY, theme);
  }, [theme]);

  useEffect(() => {
    if (!menuOpen) {
      return undefined;
    }

    const handlePointerDown = (event: PointerEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setMenuOpen(false);
      }
    };

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setMenuOpen(false);
      }
    };

    window.addEventListener("pointerdown", handlePointerDown);
    window.addEventListener("keydown", handleKeyDown);

    return () => {
      window.removeEventListener("pointerdown", handlePointerDown);
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [menuOpen]);

  useEffect(() => {
    if (typeof window === "undefined") {
      return undefined;
    }

    const mediaQuery = window.matchMedia("(prefers-color-scheme: dark)");
    const handleChange = (event: MediaQueryListEvent) => {
      setTheme(event.matches ? "dark" : "light");
    };

    mediaQuery.addEventListener("change", handleChange);
    return () => mediaQuery.removeEventListener("change", handleChange);
  }, []);

  const handleSearchSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (onSearch) {
      onSearch(searchTerm.trim());
    }
  };

  const userInitials = useMemo(() => {
    if (!userEmail) {
      return "A";
    }

    const [name] = userEmail.split("@");
    if (!name) {
      return userEmail.charAt(0)?.toUpperCase() ?? "A";
    }

    return name
      .split(/[._-]/)
      .filter(Boolean)
      .map((token) => token.charAt(0).toUpperCase())
      .slice(0, 2)
      .join("")
      .padEnd(2, userEmail.charAt(0)?.toUpperCase() ?? "A");
  }, [userEmail]);

  const toggleTheme = () => {
    setTheme((prev) => (prev === "light" ? "dark" : "light"));
  };

  return (
    <header className={styles.header}>
      <div className={styles.primaryRow}>
        <div className={styles.brandArea}>
          <Link to="/" className={styles.logoLink} aria-label="ADinsights home">
            <span aria-hidden className={styles.logoMark}>
              AI
            </span>
          </Link>
          <div className={styles.titleBlock}>
            <span className={styles.appName}>ADinsights</span>
            <div className={styles.pageTitle}>{title}</div>
            {subtitle ? <div className={styles.subtitle}>{subtitle}</div> : null}
          </div>
        </div>
        <div className={styles.utilityArea}>
          {metricOptions && typeof selectedMetric === "string" && onMetricChange ? (
            <label className={styles.metricPicker}>
              <span className={styles.metricLabel}>Map metric</span>
              <select
                value={selectedMetric}
                onChange={(event) => onMetricChange(event.target.value)}
                className={styles.metricSelect}
              >
                {metricOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
          ) : null}
          <form className={styles.searchForm} role="search" onSubmit={handleSearchSubmit}>
            <label htmlFor="global-search" className={styles.srOnly}>
              Search dashboards
            </label>
            <div className={styles.searchField}>
              <span aria-hidden className={styles.searchIcon}>
                <svg viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <path
                    d="M13.5 12.5L17 16"
                    stroke="currentColor"
                    strokeWidth="1.5"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                  <circle
                    cx="9"
                    cy="9"
                    r="5.25"
                    stroke="currentColor"
                    strokeWidth="1.5"
                  />
                </svg>
              </span>
              <input
                id="global-search"
                name="global-search"
                value={searchTerm}
                onChange={(event) => setSearchTerm(event.target.value)}
                placeholder="Search campaigns, creatives, metrics…"
                autoComplete="off"
              />
            </div>
          </form>
          <button
            type="button"
            className={styles.themeToggle}
            onClick={toggleTheme}
            aria-pressed={theme === "dark"}
            aria-label={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
          >
            {theme === "dark" ? (
              <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path
                  d="M12 5.25V3"
                  stroke="currentColor"
                  strokeWidth="1.5"
                  strokeLinecap="round"
                />
                <path
                  d="M12 21V18.75"
                  stroke="currentColor"
                  strokeWidth="1.5"
                  strokeLinecap="round"
                />
                <path
                  d="M5.63672 5.63672L7.22797 7.22797"
                  stroke="currentColor"
                  strokeWidth="1.5"
                  strokeLinecap="round"
                />
                <path
                  d="M16.7725 16.7715L18.3637 18.3628"
                  stroke="currentColor"
                  strokeWidth="1.5"
                  strokeLinecap="round"
                />
                <path
                  d="M3 12H5.25"
                  stroke="currentColor"
                  strokeWidth="1.5"
                  strokeLinecap="round"
                />
                <path
                  d="M18.75 12H21"
                  stroke="currentColor"
                  strokeWidth="1.5"
                  strokeLinecap="round"
                />
                <path
                  d="M5.63672 18.3628L7.22797 16.7715"
                  stroke="currentColor"
                  strokeWidth="1.5"
                  strokeLinecap="round"
                />
                <path
                  d="M16.7725 7.22797L18.3637 5.63672"
                  stroke="currentColor"
                  strokeWidth="1.5"
                  strokeLinecap="round"
                />
                <circle cx="12" cy="12" r="3.75" stroke="currentColor" strokeWidth="1.5" />
              </svg>
            ) : (
              <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path
                  d="M20.25 12.5312C19.3794 12.86 18.4448 13.0295 17.502 13.0312C13.772 13.0312 10.7515 10.0108 10.7515 6.28078C10.7532 5.34366 10.9228 4.40904 11.2515 3.53845C8.51525 4.5822 6.5625 7.2297 6.5625 10.2812C6.5625 14.0112 9.58294 17.0317 13.3129 17.0317C16.3644 17.0317 19.0119 15.0789 20.0557 12.3427L20.25 12.5312Z"
                  stroke="currentColor"
                  strokeWidth="1.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            )}
          </button>
          <div className={styles.userMenu} ref={menuRef}>
            <button
              type="button"
              className={styles.userButton}
              onClick={() => setMenuOpen((open) => !open)}
              aria-haspopup="menu"
              aria-expanded={menuOpen}
            >
              <span className={styles.userAvatar} aria-hidden>
                {userInitials}
              </span>
              <span className={styles.userLabel}>{userEmail ?? "Account"}</span>
              <span className={styles.caret} aria-hidden>
                <svg viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <path d="M4 6L8 10L12 6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
                </svg>
              </span>
            </button>
            {menuOpen ? (
              <div className={styles.menuList} role="menu">
                <div className={styles.menuSection} role="none">
                  <p className={styles.menuHint} role="none">
                    Signed in as
                  </p>
                  <p className={styles.menuIdentity} role="none">{userEmail ?? "Account"}</p>
                </div>
                <button type="button" className={styles.menuItem} role="menuitem" onClick={onLogout}>
                  Sign out
                </button>
              </div>
            ) : null}
          </div>
        </div>
      </div>
      <nav className={styles.nav} aria-label="Primary">
        {navLinks.map((link) => (
          <NavLink
            key={link.to}
            to={link.to}
            end={link.end}
            className={({ isActive }) =>
              [styles.navLink, isActive ? styles.navLinkActive : undefined].filter(Boolean).join(" ")
            }
          >
            {link.label}
          </NavLink>
        ))}
      </nav>
    </header>
  );
};

export default Header;
