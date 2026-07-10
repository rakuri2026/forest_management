import React, { createContext, useContext, useState, useEffect, ReactNode, useRef } from 'react';
import { authApi } from '../services/api';
import type { User, LoginRequest, RegisterRequest } from '../types';

interface AuthContextType {
  user: User | null;
  isLoading: boolean;
  login: (credentials: LoginRequest) => Promise<void>;
  register: (userData: RegisterRequest) => Promise<void>;
  logout: () => void;
  isAuthenticated: boolean;
  refreshUser: () => Promise<void>;
  toggleRole: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

interface AuthProviderProps {
  children: ReactNode;
}

// Auto-refresh interval (check every 5 minutes)
const REFRESH_CHECK_INTERVAL = 5 * 60 * 1000;

// Idle timeout — log out after 1 hour of no API activity
const IDLE_TIMEOUT_MS = 60 * 60 * 1000;
const IDLE_CHECK_INTERVAL = 30 * 1000; // check every 30s

export const AuthProvider: React.FC<AuthProviderProps> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const refreshTimerRef = useRef<NodeJS.Timeout | null>(null);
  const idleTimerRef = useRef<NodeJS.Timeout | null>(null);

  // Check if token needs refresh (within 60 minutes of expiry)
  const checkAndRefreshToken = async () => {
    const expiryStr = localStorage.getItem('token_expiry');
    if (!expiryStr || !user) return;

    // Backoff: stop retrying after 3 consecutive failures (token truly dead)
    const failCount = parseInt(localStorage.getItem('refresh_fail_count') || '0');
    if (failCount >= 3) return;

    const expiryTime = parseInt(expiryStr);
    const now = Date.now();
    const timeUntilExpiry = expiryTime - now;

    // Only refresh if token is close to expiry (avoids unnecessary calls)
    if (timeUntilExpiry < 0) {
      // Token already expired — log out
      logout();
      return;
    }
    if (timeUntilExpiry > 60 * 60 * 1000) return;

    try {
      const tokenData = await authApi.refresh();
      localStorage.setItem('access_token', tokenData.access_token);
      const newExpiry = Date.now() + (tokenData.expires_in - 300) * 1000;
      localStorage.setItem('token_expiry', String(newExpiry));
      localStorage.removeItem('refresh_fail_count');
    } catch {
      localStorage.setItem('refresh_fail_count', String(failCount + 1));
    }
  };

  useEffect(() => {
    const loadUser = async () => {
      const token = localStorage.getItem('access_token');
      if (token) {
        try {
          const userData = await authApi.me();
          setUser(userData);
        } catch (error) {
          localStorage.removeItem('access_token');
          localStorage.removeItem('token_expiry');
        }
      }
      setIsLoading(false);
    };

    loadUser();

    // Set up periodic token expiry check
    refreshTimerRef.current = setInterval(checkAndRefreshToken, REFRESH_CHECK_INTERVAL);

    // Set up idle timeout check (every 30s)
    const checkIdle = () => {
      const lastActive = localStorage.getItem('last_active');
      if (!lastActive || !user) return;
      if (Date.now() - parseInt(lastActive) > IDLE_TIMEOUT_MS) {
        logout();
      }
    };
    idleTimerRef.current = setInterval(checkIdle, IDLE_CHECK_INTERVAL);

    return () => {
      if (refreshTimerRef.current) {
        clearInterval(refreshTimerRef.current);
      }
      if (idleTimerRef.current) {
        clearInterval(idleTimerRef.current);
      }
    };
  }, []);

  const login = async (credentials: LoginRequest) => {
    const tokenData = await authApi.login(credentials);
    localStorage.setItem('access_token', tokenData.access_token);
    // Set expiry to 5 minutes before actual expiry for safety
    const expiryTime = Date.now() + (tokenData.expires_in - 300) * 1000;
    localStorage.setItem('token_expiry', String(expiryTime));
    const userData = await authApi.me();
    setUser(userData);
  };

  const register = async (userData: RegisterRequest) => {
    await authApi.register(userData);
    // Auto-login after registration
    await login({ email: userData.email, password: userData.password });
  };

  const logout = () => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('token_expiry');
    localStorage.removeItem('last_active');
    localStorage.removeItem('refresh_fail_count');
    setUser(null);
  };

  const refreshUser = async () => {
    try {
      const userData = await authApi.me();
      setUser(userData);
    } catch {
      logout();
    }
  };

  const toggleRole = async () => {
    const updated = await authApi.toggleRole();
    setUser(updated);
  };

  const value = {
    user,
    isLoading,
    login,
    register,
    logout,
    isAuthenticated: !!user,
    refreshUser,
    toggleRole,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};
