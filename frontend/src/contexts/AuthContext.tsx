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

export const AuthProvider: React.FC<AuthProviderProps> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const refreshTimerRef = useRef<NodeJS.Timeout | null>(null);

  // Check if token needs refresh (5 minutes before expiry)
  const checkAndRefreshToken = async () => {
    const expiryStr = localStorage.getItem('token_expiry');
    if (!expiryStr) return;

    const expiryTime = parseInt(expiryStr);
    const now = Date.now();
    const timeUntilExpiry = expiryTime - now;

    // Refresh if less than 5 minutes left
    if (timeUntilExpiry < 5 * 60 * 1000) {
      try {
        const credentials = { email: user?.email || '', password: '' };
        // We can't re-login without password, so just logout
        console.log('[Auth] Token expiring soon, user needs to re-login');
      } catch (error) {
        console.error('[Auth] Token refresh failed:', error);
      }
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

    return () => {
      if (refreshTimerRef.current) {
        clearInterval(refreshTimerRef.current);
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
    setUser(null);
  };

  const value = {
    user,
    isLoading,
    login,
    register,
    logout,
    isAuthenticated: !!user,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};
