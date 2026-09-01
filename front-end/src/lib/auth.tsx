import { useNavigate } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { getApiKey } from "./api";

export function useApiKey() {
  const [key, setKey] = useState<string | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const sync = () => setKey(getApiKey());
    sync();
    setReady(true);
    window.addEventListener("credit-yetu-auth", sync);
    window.addEventListener("storage", sync);
    return () => {
      window.removeEventListener("credit-yetu-auth", sync);
      window.removeEventListener("storage", sync);
    };
  }, []);

  return { apiKey: key, isAuthenticated: !!key, ready };
}

/** Redirects to /login when no API key is stored. */
export function useRequireAuth() {
  const { isAuthenticated, ready } = useApiKey();
  const navigate = useNavigate();

  useEffect(() => {
    if (ready && !isAuthenticated) {
      navigate({ to: "/login", search: { mode: "signin" } });
    }
  }, [ready, isAuthenticated, navigate]);

  return { isAuthenticated, ready };
}

// Verification history now comes from the real GET /api/v1/verify endpoint
// (org-scoped, server-side) rather than a client-only localStorage list —
// see routes/verify.tsx.

const OFFICER_KEY = "credit-yetu.officer";

export function getOfficerName(): string {
  if (typeof window === "undefined") return "";
  return window.localStorage.getItem(OFFICER_KEY) ?? "";
}

export function setOfficerName(name: string) {
  window.localStorage.setItem(OFFICER_KEY, name);
}
