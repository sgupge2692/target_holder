"use client";
import { useEffect, useState, useCallback } from "react";
import { getMe, type MeResponse } from "@/lib/api";

export function useAuth() {
  const [user, setUser]     = useState<MeResponse | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
    if (!token) { setLoading(false); return; }
    try { setUser(await getMe()); } catch { localStorage.removeItem("token"); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const signOut = useCallback(() => {
    localStorage.removeItem("token");
    setUser(null);
  }, []);

  return { user, loading, reload: load, signOut };
}
