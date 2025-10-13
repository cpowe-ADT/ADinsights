import {
  PropsWithChildren,
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import apiClient from "../lib/apiClient";
import useDashboardStore from "../state/useDashboardStore";

const STORAGE_KEY = "adinsights.auth";
const REFRESH_LEEWAY_MS = 60_000;

interface LoginResponse {
  access: string;
  refresh: string;
  tenant_id: string;
  user?: Record<string, unknown>;
}

type AuthStatus = "idle" | "authenticating" | "authenticated" | "error";

type AuthContextValue = {
  status: AuthStatus;
  isAuthenticated: boolean;
  accessToken?: string;
  tenantId?: string;
  user?: Record<string, unknown>;
  error?: string;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
};

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

type StoredTokens = {
  access: string;
  refresh: string;
  tenantId: string;
  user?: Record<string, unknown>;
};

function decodeJwtExpiration(token: string): number | null {
  try {
    const [, payload] = token.split(".");
    if (!payload) {
      return null;
    }
    const normalized = payload.replace(/-/g, "+").replace(/_/g, "/");
    const padding = (4 - (normalized.length % 4)) % 4;
    const padded = normalized + "=".repeat(padding);
    const decoded = atob(padded);
    const parsed = JSON.parse(decoded) as { exp?: number };
    return typeof parsed.exp === "number" ? parsed.exp : null;
  } catch (error) {
    console.warn("Unable to decode JWT payload", error);
    return null;
  }
}

function readStoredTokens(): StoredTokens | null {
  if (typeof window === "undefined" || !window.localStorage) {
    return null;
  }
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return null;
    }
    const parsed = JSON.parse(raw) as StoredTokens;
    if (typeof parsed?.access === "string" && typeof parsed?.refresh === "string") {
      return parsed;
    }
  } catch (error) {
    console.warn("Failed to parse stored auth state", error);
  }
  return null;
}

function writeStoredTokens(tokens: StoredTokens | null): void {
  if (typeof window === "undefined" || !window.localStorage) {
    return;
  }
  if (tokens) {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(tokens));
  } else {
    window.localStorage.removeItem(STORAGE_KEY);
  }
}

export function AuthProvider({ children }: PropsWithChildren): JSX.Element {
  const [status, setStatus] = useState<AuthStatus>("idle");
  const [error, setError] = useState<string>();
  const [accessToken, setAccessToken] = useState<string>();
  const [tenantId, setTenantId] = useState<string>();
  const [user, setUser] = useState<Record<string, unknown> | undefined>();
  const refreshTokenRef = useRef<string>();
  const refreshTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const clearRefreshTimer = useCallback(() => {
    if (refreshTimeoutRef.current) {
      clearTimeout(refreshTimeoutRef.current);
      refreshTimeoutRef.current = null;
    }
  }, []);

  const logout = useCallback(() => {
    clearRefreshTimer();
    refreshTokenRef.current = undefined;
    setAccessToken(undefined);
    setTenantId(undefined);
    setUser(undefined);
    setStatus("idle");
    setError(undefined);
    writeStoredTokens(null);
    useDashboardStore.getState().reset();
  }, [clearRefreshTimer]);

  const applyTokens = useCallback(
    (next: StoredTokens) => {
      setAccessToken(next.access);
      setTenantId(next.tenantId);
      setUser(next.user);
      refreshTokenRef.current = next.refresh;
      writeStoredTokens(next);
    },
    []
  );

  const refreshAccessToken = useCallback(async () => {
    const refresh = refreshTokenRef.current;
    if (!refresh) {
      logout();
      return;
    }
    try {
      const response = await fetch("/api/auth/refresh/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh }),
      });
      if (!response.ok) {
        throw new Error(`Refresh failed with status ${response.status}`);
      }
      const data = (await response.json()) as { access: string };
      const nextTokens: StoredTokens = {
        access: data.access,
        refresh,
        tenantId: tenantId ?? "",
        user,
      };
      applyTokens(nextTokens);
      setStatus("authenticated");
      setError(undefined);
    } catch (refreshError) {
      console.error("Token refresh failed", refreshError);
      logout();
    }
  }, [applyTokens, logout, tenantId, user]);

  const login = useCallback(
    async (email: string, password: string) => {
      setStatus("authenticating");
      setError(undefined);
      try {
        const response = await fetch("/api/auth/login/", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email, password }),
        });
        if (!response.ok) {
          const detail = await response.text();
          throw new Error(detail || "Invalid credentials");
        }
        const data = (await response.json()) as LoginResponse;
        const tokens: StoredTokens = {
          access: data.access,
          refresh: data.refresh,
          tenantId: data.tenant_id,
          user: data.user,
        };
        applyTokens(tokens);
        setStatus("authenticated");
        setError(undefined);
      } catch (loginError) {
        console.error("Login failed", loginError);
        const message =
          loginError instanceof Error ? loginError.message : "Unable to login.";
        logout();
        setStatus("error");
        setError(message);
        throw loginError;
      }
    },
    [applyTokens, logout]
  );

  useEffect(() => {
    const stored = readStoredTokens();
    if (stored) {
      applyTokens(stored);
      setStatus("authenticated");
    }
    return () => {
      clearRefreshTimer();
    };
  }, [applyTokens, clearRefreshTimer]);

  useEffect(() => {
    if (!accessToken) {
      clearRefreshTimer();
      return;
    }
    const exp = decodeJwtExpiration(accessToken);
    if (!exp) {
      return;
    }
    const expiresInMs = exp * 1000 - Date.now();
    const refreshIn = Math.max(expiresInMs - REFRESH_LEEWAY_MS, 5_000);
    clearRefreshTimer();
    refreshTimeoutRef.current = setTimeout(() => {
      void refreshAccessToken();
    }, refreshIn);
    return () => {
      clearRefreshTimer();
    };
  }, [accessToken, clearRefreshTimer, refreshAccessToken]);

  useEffect(() => {
    if (accessToken) {
      apiClient.defaults.headers.common.Authorization = `Bearer ${accessToken}`;
    } else {
      delete apiClient.defaults.headers.common.Authorization;
    }
  }, [accessToken]);

  const value = useMemo<AuthContextValue>(
    () => ({
      status,
      isAuthenticated: status === "authenticated",
      accessToken,
      tenantId,
      user,
      error,
      login,
      logout,
    }),
    [status, accessToken, tenantId, user, error, login, logout]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
