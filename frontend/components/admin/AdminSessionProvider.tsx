"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState, type PropsWithChildren } from "react";
import { getCurrentAdmin, loginAdmin, type AdminIdentity } from "@/services/adminApi";

type AuthState = "checking" | "unauthenticated" | "authenticated";
type AdminSession = { authState: AuthState; token?: string; admin?: AdminIdentity; authenticate: (email: string, password: string) => Promise<void>; logout: () => void };

const tokenKey = "dien-bien-admin-token";
const AdminSessionContext = createContext<AdminSession | undefined>(undefined);

export function AdminSessionProvider({ children }: PropsWithChildren) {
  const [authState, setAuthState] = useState<AuthState>("checking");
  const [token, setToken] = useState<string>();
  const [admin, setAdmin] = useState<AdminIdentity>();

  useEffect(() => {
    let active = true;
    const savedToken = window.sessionStorage.getItem(tokenKey);
    if (!savedToken) { setAuthState("unauthenticated"); return () => { active = false; }; }
    void getCurrentAdmin(savedToken).then((identity) => {
      if (!active) return;
      setToken(savedToken); setAdmin(identity); setAuthState("authenticated");
    }).catch(() => {
      if (!active) return;
      window.sessionStorage.removeItem(tokenKey); setAuthState("unauthenticated");
    });
    return () => { active = false; };
  }, []);

  const authenticate = useCallback(async (email: string, password: string) => {
    const nextToken = await loginAdmin(email, password);
    const identity = await getCurrentAdmin(nextToken);
    window.sessionStorage.setItem(tokenKey, nextToken);
    setToken(nextToken); setAdmin(identity); setAuthState("authenticated");
  }, []);
  const logout = useCallback(() => {
    window.sessionStorage.removeItem(tokenKey);
    setToken(undefined); setAdmin(undefined); setAuthState("unauthenticated");
  }, []);
  const value = useMemo(() => ({ authState, token, admin, authenticate, logout }), [admin, authState, authenticate, logout, token]);
  return <AdminSessionContext.Provider value={value}>{children}</AdminSessionContext.Provider>;
}

export function useAdminSession() {
  const session = useContext(AdminSessionContext);
  if (!session) throw new Error("useAdminSession must be used within AdminSessionProvider");
  return session;
}
