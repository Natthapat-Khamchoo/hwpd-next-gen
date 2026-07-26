import React, { createContext, useContext, useState, useEffect } from 'react';
import type { User } from '../types';
import { setSessionExpiredHandler } from '../services/api';

interface AuthContextType {
  user: User | null;
  login: (userData: User) => void;
  logout: () => void;
  token: string | null;
}

const AuthContext = createContext<AuthContextType>({
  user: null,
  login: () => {},
  logout: () => {},
  token: null,
});

/**
 * Session tokens are `base64url(payload).hmac` with an `exp` claim (24h TTL).
 * Reading the claim client-side only decides whether to show the app shell; the
 * backend still verifies the signature on every write.
 */
const isTokenExpired = (token?: string | null): boolean => {
  if (!token) return false; // demo/offline sessions carry no real token
  const [payloadB64] = token.split('.');
  if (!payloadB64) return false;
  try {
    const padded = payloadB64.replace(/-/g, '+').replace(/_/g, '/');
    const payload = JSON.parse(atob(padded + '='.repeat((4 - (padded.length % 4)) % 4)));
    if (typeof payload?.exp !== 'number') return false;
    return payload.exp * 1000 <= Date.now();
  } catch {
    return false;
  }
};

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);

  const logout = () => {
    setUser(null);
    localStorage.removeItem('hwpd_user');
  };

  useEffect(() => {
    const saved = localStorage.getItem('hwpd_user');
    if (saved) {
      try {
        const parsed: User = JSON.parse(saved);
        if (isTokenExpired(parsed.token)) {
          localStorage.removeItem('hwpd_user');
        } else {
          setUser(parsed);
        }
      } catch (e) {
        localStorage.removeItem('hwpd_user');
      }
    }
  }, []);

  // A 401 from any write means the session died server-side; drop it here too.
  useEffect(() => {
    setSessionExpiredHandler(() => {
      setUser(null);
      localStorage.removeItem('hwpd_user');
    });
    return () => setSessionExpiredHandler(() => {});
  }, []);

  const login = (userData: User) => {
    setUser(userData);
    localStorage.setItem('hwpd_user', JSON.stringify(userData));
  };

  return (
    <AuthContext.Provider value={{ user, login, logout, token: user?.token || null }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => useContext(AuthContext);
