import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { api, loginRequest, logout as logoutClient, tryRestoreSession } from "../api/client";
import type { Me } from "../api/types";

interface AuthState {
  me: Me | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
  hasPerm: (codename: string) => boolean;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<Me | null>(null);
  const [loading, setLoading] = useState(true);

  const loadMe = useCallback(async () => {
    const resp = await api.get<Me>("/me/");
    setMe(resp.data);
  }, []);

  useEffect(() => {
    (async () => {
      const restored = await tryRestoreSession();
      if (restored) {
        try {
          await loadMe();
        } catch {
          setMe(null);
        }
      }
      setLoading(false);
    })();
  }, [loadMe]);

  const login = useCallback(
    async (username: string, password: string) => {
      await loginRequest(username, password);
      await loadMe();
    },
    [loadMe],
  );

  const logout = useCallback(() => {
    logoutClient();
    setMe(null);
  }, []);

  const hasPerm = useCallback(
    (codename: string) => {
      if (!me) return false;
      if (me.is_superuser) return true;
      return me.permissions.includes(codename);
    },
    [me],
  );

  return (
    <AuthContext.Provider value={{ me, loading, login, logout, hasPerm }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth AuthProvider ichida ishlatilishi kerak");
  return ctx;
}
