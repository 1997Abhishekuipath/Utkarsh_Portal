import { createContext, useContext, useState, useEffect } from "react";
import axios from "axios";

export const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const formatErr = (detail) => {
  if (!detail) return "Something went wrong.";
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return detail.map(e => e?.msg || JSON.stringify(e)).join(" ");
  return String(detail);
};

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem("hsi_token");
    if (!token) { setLoading(false); return; }
    axios.get(`${API}/auth/me`, { headers: { Authorization: `Bearer ${token}` } })
      .then(r => setUser(r.data))
      .catch(() => localStorage.removeItem("hsi_token"))
      .finally(() => setLoading(false));
  }, []);

  const login = async (email, password) => {
    try {
      const { data } = await axios.post(`${API}/auth/login`, { email, password });
      // Two-step MFA: backend returns {requires_otp:true, ...} — caller handles UX.
      if (data?.requires_otp) {
        return { requires_otp: true, email: data.email, expires_in_sec: data.expires_in_sec };
      }
      localStorage.setItem("hsi_token", data.access_token);
      if (data.refresh_token) localStorage.setItem("hsi_refresh", data.refresh_token);
      setUser(data.user);
      return data;
    } catch (e) {
      throw new Error(formatErr(e.response?.data?.detail) || e.message);
    }
  };

  const verifyOtp = async (email, code, purpose = "login") => {
    try {
      const { data } = await axios.post(`${API}/auth/verify-otp`, { email, code, purpose });
      if (data?.access_token) {
        localStorage.setItem("hsi_token", data.access_token);
        if (data.refresh_token) localStorage.setItem("hsi_refresh", data.refresh_token);
        setUser(data.user);
      }
      return data;
    } catch (e) {
      throw new Error(formatErr(e.response?.data?.detail) || e.message);
    }
  };

  const resendOtp = async (email, purpose = "login") => {
    try {
      const { data } = await axios.post(`${API}/auth/resend-otp`, { email, purpose });
      return data;
    } catch (e) {
      throw new Error(formatErr(e.response?.data?.detail) || e.message);
    }
  };

  const forgotPassword = async (email) => {
    try {
      const { data } = await axios.post(`${API}/auth/forgot-password`, { email });
      return data;
    } catch (e) {
      throw new Error(formatErr(e.response?.data?.detail) || e.message);
    }
  };

  const resetPassword = async (email, code, new_password) => {
    try {
      const { data } = await axios.post(`${API}/auth/reset-password`, { email, code, new_password });
      return data;
    } catch (e) {
      throw new Error(formatErr(e.response?.data?.detail) || e.message);
    }
  };

  const register = async (payload) => {
    try {
      const { data } = await axios.post(`${API}/auth/register`, payload);
      // New flow: registration is pending admin approval — no token issued.
      if (data?.access_token) {
        localStorage.setItem("hsi_token", data.access_token);
        if (data.refresh_token) localStorage.setItem("hsi_refresh", data.refresh_token);
        setUser(data.user);
      }
      return data;
    } catch (e) {
      throw new Error(formatErr(e.response?.data?.detail) || e.message);
    }
  };

  const logout = async () => {
    const t = localStorage.getItem("hsi_token");
    if (t) {
      try { await axios.post(`${API}/auth/logout`, {}, { headers: { Authorization: `Bearer ${t}` } }); }
      catch { /* ignore — tokens are cleared regardless */ }
    }
    localStorage.removeItem("hsi_token");
    localStorage.removeItem("hsi_refresh");
    setUser(null);
  };

  const authHeader = () => {
    const t = localStorage.getItem("hsi_token");
    return t ? { Authorization: `Bearer ${t}` } : {};
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, verifyOtp, resendOtp, forgotPassword, resetPassword, register, logout, authHeader, API }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => useContext(AuthContext);
