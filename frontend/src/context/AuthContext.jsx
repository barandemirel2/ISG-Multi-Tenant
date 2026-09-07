import { createContext, useContext, useEffect, useState, useCallback } from "react";
import api, { formatApiErrorDetail } from "@/lib/api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null); // null=loading, false=guest, obj=user
  const [checked, setChecked] = useState(false);

  const check = useCallback(async () => {
    try {
      const { data } = await api.get("/auth/me");
      setUser(data);
    } catch (e) {
      setUser(false);
    } finally {
      setChecked(true);
    }
  }, []);

  useEffect(() => {
    check();
  }, [check]);

  const login = async (email, password) => {
    const { data } = await api.post("/auth/login", { email, password });
    setUser(data);
    return data;
  };

  const register = async (name, email, password) => {
    const { data } = await api.post("/auth/register", { name, email, password });
    setUser(data);
    return data;
  };

  const logout = async () => {
    try {
      await api.post("/auth/logout");
    } catch (e) {
      // Server-side session may already be gone; clear client state anyway.
      console.warn("Logout request failed:", e?.message || e);
    }
    setUser(false);
  };

  return (
    <AuthContext.Provider value={{ user, checked, login, register, logout, refetch: check, formatApiErrorDetail }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
