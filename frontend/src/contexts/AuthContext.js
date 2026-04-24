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
      localStorage.setItem("hsi_token", data.access_token);
      setUser(data.user);
      return data;
    } catch (e) {
      throw new Error(formatErr(e.response?.data?.detail) || e.message);
    }
  };

  const register = async (payload) => {
    try {
      const { data } = await axios.post(`${API}/auth/register`, payload);
      localStorage.setItem("hsi_token", data.access_token);
      setUser(data.user);
      return data;
    } catch (e) {
      throw new Error(formatErr(e.response?.data?.detail) || e.message);
    }
  };

  const logout = () => {
    localStorage.removeItem("hsi_token");
    setUser(null);
  };

  const authHeader = () => {
    const t = localStorage.getItem("hsi_token");
    return t ? { Authorization: `Bearer ${t}` } : {};
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout, authHeader, API }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => useContext(AuthContext);
