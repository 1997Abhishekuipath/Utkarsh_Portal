import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { API } from "../contexts/AuthContext";

const authHeader = () => ({
  Authorization: `Bearer ${localStorage.getItem("hsi_token")}`,
});

export function useVocDashboard() {
  const [kpis, setKpis]           = useState(null);
  const [trend, setTrend]         = useState([]);
  const [verbatims, setVerbatims] = useState([]);
  const [painPoints, setPainPoints] = useState([]);
  const [csatDist, setCsatDist]   = useState([]);
  const [strengths, setStrengths] = useState([]);
  const [accounts, setAccounts]   = useState([]);
  const [loading, setLoading]     = useState(true);
  const [error, setError]         = useState(null);
  const [lastSync, setLastSync]   = useState(null);

  const fetchAll = useCallback(async () => {
    try {
      const h = authHeader();
      const [k, t, v, p, c, s, a] = await Promise.all([
        axios.get(`${API}/voc/dashboard/kpis`,             { headers: h }),
        axios.get(`${API}/voc/dashboard/trend`,            { headers: h }),
        axios.get(`${API}/voc/dashboard/verbatims?limit=6`, { headers: h }),
        axios.get(`${API}/voc/dashboard/pain-points`,      { headers: h }),
        axios.get(`${API}/voc/dashboard/csat-distribution`, { headers: h }),
        axios.get(`${API}/voc/dashboard/strengths?limit=4`, { headers: h }),
        axios.get(`${API}/voc/accounts`,                   { headers: h }),
      ]);
      setKpis(k.data);
      setTrend(t.data);
      setVerbatims(v.data);
      setPainPoints(p.data);
      setCsatDist(c.data);
      setStrengths(s.data);
      setAccounts(a.data.accounts || []);
      setLastSync(new Date());
      setError(null);
    } catch (err) {
      setError(err?.response?.data?.detail || err.message || "Failed to load data");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAll();
    // Auto-refresh every 5 minutes (FR-006)
    const interval = setInterval(fetchAll, 5 * 60 * 1000);
    return () => clearInterval(interval);
  }, [fetchAll]);

  return { kpis, trend, verbatims, painPoints, csatDist, strengths, accounts, loading, error, lastSync, refetch: fetchAll };
}
