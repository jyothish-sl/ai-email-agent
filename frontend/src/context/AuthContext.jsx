import { createContext, useContext, useState, useCallback, useEffect } from "react";
import { api, tokenStore } from "../api/client";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => tokenStore.get());
  const [user, setUser] = useState(null);
  const [initializing, setInitializing] = useState(true);

  // On first load, if we already have a token (e.g. page refresh), fetch
  // the profile once so the whole app has user info without re-fetching
  // it in every component that needs it.
  useEffect(() => {
    let cancelled = false;
    async function bootstrap() {
      if (!token) {
        setInitializing(false);
        return;
      }
      try {
        const profile = await api.me();
        if (!cancelled) setUser(profile);
      } catch (_) {
        if (!cancelled) {
          tokenStore.clear();
          setToken(null);
        }
      } finally {
        if (!cancelled) setInitializing(false);
      }
    }
    bootstrap();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const login = useCallback(async (email, password) => {
    const data = await api.login(email, password);
    tokenStore.set(data.access_token);
    setToken(data.access_token);
    const profile = await api.me();
    setUser(profile);
    return profile;
  }, []);

  const register = useCallback(async (username, email, password) => {
    await api.register(username, email, password);
    // Register endpoint doesn't return a session, so log in right after
    // for a smooth "one form, then you're in" flow.
    return login(email, password);
  }, [login]);

  const logout = useCallback(async () => {
    try {
      await api.logout();
    } catch (_) {
      // Clear the local session regardless -- a failed network call
      // shouldn't trap the user in a logged-in-looking state.
    }
    tokenStore.clear();
    setToken(null);
    setUser(null);
  }, []);

  const value = {
    token,
    user,
    isAuthenticated: Boolean(token),
    initializing,
    login,
    register,
    logout,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within an AuthProvider");
  return ctx;
}
