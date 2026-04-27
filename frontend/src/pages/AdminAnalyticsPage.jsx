import React, { useState, useEffect, useCallback } from "react";
import TopBar from "../components/TopBar";
import {
  TrendingUp, Users, Award, IndianRupee, Bell, Calendar,
  Loader2, RefreshCw, AlertCircle, CheckCircle
} from "lucide-react";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  LineChart, Line, PieChart, Pie, Cell, Legend,
} from "recharts";

const BACKEND = process.env.REACT_APP_BACKEND_URL;

const PILLARS = {
  announcement: "#CC0000", incentive: "#F59E0B", birthday: "#EC4899",
  approved: "#10B981", replication: "#3B82F6", reminder: "#8B5CF6",
  new_practice: "#06B6D4", award: "#EAB308", other: "#94A3B8",
};

function KpiCard({ icon: Icon, label, value, sub, accent = "#CC0000" }) {
  return (
    <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-5">
      <div className="flex items-center justify-between">
        <div className="min-w-0">
          <div className="text-[11px] uppercase tracking-wider font-semibold text-gray-400">{label}</div>
          <div className="text-2xl font-bold text-gray-900 mt-1 tabular-nums">{value}</div>
          {sub && <div className="text-xs text-gray-500 mt-1">{sub}</div>}
        </div>
        <div
          className="w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0"
          style={{ backgroundColor: `${accent}15`, color: accent }}
          aria-hidden="true"
        >
          <Icon size={18} />
        </div>
      </div>
    </div>
  );
}

export default function AdminAnalyticsPage() {
  const [period, setPeriod] = useState("weekly");
  const [trends, setTrends] = useState(null);
  const [top, setTop] = useState(null);
  const [funnel, setFunnel] = useState(null);
  const [revenue, setRevenue] = useState(null);
  const [engagement, setEngagement] = useState(null);
  const [loading, setLoading] = useState(true);
  const [toast, setToast] = useState(null);

  const showToast = (msg, type = "success") => { setToast({ msg, type }); setTimeout(() => setToast(null), 2500); };

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [t, tp, f, r, e] = await Promise.all([
        fetch(`${BACKEND}/api/admin/analytics/xp-trends?period=${period}&buckets=12`, { credentials: "include" }),
        fetch(`${BACKEND}/api/admin/analytics/top-contributors?limit=10`, { credentials: "include" }),
        fetch(`${BACKEND}/api/admin/analytics/practice-funnel`, { credentials: "include" }),
        fetch(`${BACKEND}/api/admin/analytics/revenue`, { credentials: "include" }),
        fetch(`${BACKEND}/api/admin/analytics/notification-engagement`, { credentials: "include" }),
      ]);
      if (t.ok) setTrends(await t.json());
      if (tp.ok) setTop(await tp.json());
      if (f.ok) setFunnel(await f.json());
      if (r.ok) setRevenue(await r.json());
      if (e.ok) setEngagement(await e.json());
    } catch (err) {
      showToast("Failed to load analytics", "error");
    } finally { setLoading(false); }
  }, [period]);

  useEffect(() => { load(); }, [load]);

  const trendData = (trends?.series || []).map(s => ({
    bucket: new Date(s.bucket).toLocaleDateString("en-IN", { month: "short", day: "numeric" }),
    xp: s.xp, events: s.events,
  }));

  const funnelData = funnel ? [
    { name: "Pending", value: funnel.practices.pending, color: "#F59E0B" },
    { name: "Approved", value: funnel.practices.approved, color: "#10B981" },
    { name: "Rejected", value: funnel.practices.rejected, color: "#EF4444" },
    { name: "Draft", value: funnel.practices.draft, color: "#94A3B8" },
  ] : [];

  const engagementData = (engagement?.by_category || []).map(c => ({
    category: c.category, delivered: c.delivered, read: c.read,
    color: PILLARS[c.category] || PILLARS.other,
  }));

  return (
    <div className="min-h-screen bg-[#F1F5F9]">
      {toast && (
        <div
          role="status" aria-live="polite"
          className={`fixed top-4 right-4 z-50 px-4 py-3 rounded-lg shadow-lg text-sm font-medium flex items-center gap-2
          ${toast.type === "error" ? "bg-red-50 text-red-700 border border-red-200" : "bg-green-50 text-green-700 border border-green-200"}`}
        >
          {toast.type === "error" ? <AlertCircle size={16} aria-hidden="true" /> : <CheckCircle size={16} aria-hidden="true" />}
          {toast.msg}
        </div>
      )}

      <TopBar crumbs={[{ label: "Admin", to: "/admin" }, { label: "Analytics" }]}>
        <div className="flex items-end justify-between gap-4 flex-wrap">
          <div>
            <h1 className="text-white text-2xl font-bold">Platform Analytics</h1>
            <p className="text-white/70 text-sm mt-1">XP trends, top contributors, approval funnel and engagement</p>
          </div>
          <div className="flex items-center gap-2">
            <div role="group" aria-label="Trend period" className="flex bg-white/10 rounded-lg p-0.5">
              {["daily", "weekly", "monthly"].map(p => (
                <button
                  key={p}
                  type="button"
                  aria-pressed={period === p}
                  onClick={() => setPeriod(p)}
                  data-testid={`analytics-period-${p}`}
                  className={`px-3 py-1.5 text-xs font-medium rounded-md capitalize focus:outline-none focus:ring-2 focus:ring-white/70
                    ${period === p ? "bg-white text-[#CC0000]" : "text-white/90 hover:bg-white/10"}`}
                >
                  {p}
                </button>
              ))}
            </div>
            <button
              type="button"
              onClick={load}
              aria-label="Refresh analytics"
              data-testid="analytics-refresh"
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-white bg-white/10 hover:bg-white/20 rounded-lg focus:outline-none focus:ring-2 focus:ring-white/70"
            >
              <RefreshCw size={12} className={loading ? "animate-spin" : ""} aria-hidden="true" />
              Refresh
            </button>
          </div>
        </div>
      </TopBar>

      <div className="max-w-7xl mx-auto px-4 py-6 space-y-6">
        {/* KPI strip */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <KpiCard
            icon={TrendingUp}
            label="XP (window)"
            value={(trends?.series || []).reduce((s, x) => s + x.xp, 0).toLocaleString()}
            sub={`${period} · last 12 buckets`}
            accent="#CC0000"
          />
          <KpiCard
            icon={Users}
            label="Top Users"
            value={top?.items?.length || 0}
            sub={top?.quarter || "—"}
            accent="#3B82F6"
          />
          <KpiCard
            icon={IndianRupee}
            label="Revenue Captured"
            value={`₹${(revenue?.overall?.total_revenue || 0).toLocaleString("en-IN")}`}
            sub={`${revenue?.overall?.total_deals || 0} deals with PO`}
            accent="#10B981"
          />
          <KpiCard
            icon={Bell}
            label="Notif Read-Rate"
            value={`${engagement?.totals?.read_rate || 0}%`}
            sub={`${engagement?.totals?.delivered || 0} delivered (30d)`}
            accent="#F59E0B"
          />
        </div>

        {/* XP trend */}
        <section data-testid="analytics-trends-section" className="bg-white rounded-xl border border-gray-100 shadow-sm p-5">
          <h2 className="text-sm font-bold text-gray-800 mb-4 flex items-center gap-2">
            <TrendingUp size={14} className="text-[#CC0000]" aria-hidden="true" /> XP Trend ({period})
          </h2>
          {loading ? (
            <div className="h-64 flex items-center justify-center text-gray-400">
              <Loader2 size={22} className="animate-spin" aria-hidden="true" />
            </div>
          ) : trendData.length === 0 ? (
            <div className="h-64 flex items-center justify-center text-sm text-gray-400">No data yet</div>
          ) : (
            <ResponsiveContainer width="100%" height={260}>
              <LineChart data={trendData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#F1F5F9" />
                <XAxis dataKey="bucket" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip />
                <Line type="monotone" dataKey="xp" stroke="#CC0000" strokeWidth={2}
                      dot={{ r: 3 }} activeDot={{ r: 6 }} />
              </LineChart>
            </ResponsiveContainer>
          )}
        </section>

        {/* Funnel + Engagement */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <section data-testid="analytics-funnel-section" className="bg-white rounded-xl border border-gray-100 shadow-sm p-5">
            <h2 className="text-sm font-bold text-gray-800 mb-4 flex items-center gap-2">
              <Award size={14} className="text-[#CC0000]" aria-hidden="true" /> Best-Practice Funnel
            </h2>
            {funnelData.every(f => f.value === 0) ? (
              <div className="h-64 flex items-center justify-center text-sm text-gray-400">No submissions yet</div>
            ) : (
              <ResponsiveContainer width="100%" height={260}>
                <PieChart>
                  <Pie data={funnelData} dataKey="value" nameKey="name"
                       cx="50%" cy="50%" innerRadius={50} outerRadius={90} paddingAngle={2}>
                    {funnelData.map((d, i) => (<Cell key={i} fill={d.color} />))}
                  </Pie>
                  <Tooltip />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                </PieChart>
              </ResponsiveContainer>
            )}
          </section>

          <section data-testid="analytics-engagement-section" className="bg-white rounded-xl border border-gray-100 shadow-sm p-5">
            <h2 className="text-sm font-bold text-gray-800 mb-4 flex items-center gap-2">
              <Bell size={14} className="text-[#CC0000]" aria-hidden="true" /> Notification Engagement (30d)
            </h2>
            {engagementData.length === 0 ? (
              <div className="h-64 flex items-center justify-center text-sm text-gray-400">No notifications sent</div>
            ) : (
              <ResponsiveContainer width="100%" height={260}>
                <BarChart data={engagementData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#F1F5F9" />
                  <XAxis dataKey="category" tick={{ fontSize: 10 }} />
                  <YAxis tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  <Bar dataKey="delivered" fill="#CBD5E1" />
                  <Bar dataKey="read" fill="#CC0000" />
                </BarChart>
              </ResponsiveContainer>
            )}
          </section>
        </div>

        {/* Top contributors */}
        <section data-testid="analytics-top-section" className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden">
          <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
            <h2 className="text-sm font-bold text-gray-800 flex items-center gap-2">
              <Users size={14} className="text-[#CC0000]" aria-hidden="true" /> Top Contributors — {top?.quarter || "—"}
            </h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-gray-50 text-left text-[11px] font-semibold uppercase tracking-wider text-gray-500">
                  <th className="px-5 py-2.5 w-10">#</th>
                  <th className="px-5 py-2.5">Name</th>
                  <th className="px-5 py-2.5">Department</th>
                  <th className="px-5 py-2.5 text-right">XP</th>
                </tr>
              </thead>
              <tbody>
                {(top?.items || []).map((u, idx) => (
                  <tr key={u.user_id} className="border-t border-gray-50 hover:bg-gray-50/50">
                    <td className="px-5 py-3 tabular-nums text-gray-500">{idx + 1}</td>
                    <td className="px-5 py-3">
                      <div className="font-medium text-gray-800">{u.name}</div>
                      <div className="text-xs text-gray-400">{u.email}</div>
                    </td>
                    <td className="px-5 py-3 text-gray-600">{u.department || "—"}</td>
                    <td className="px-5 py-3 text-right font-bold text-[#CC0000] tabular-nums">{u.xp.toLocaleString()}</td>
                  </tr>
                ))}
                {(!top?.items || top.items.length === 0) && (
                  <tr><td colSpan={4} className="px-5 py-8 text-center text-gray-400 text-sm">No contributors yet</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </section>

        {/* Revenue by quarter */}
        <section data-testid="analytics-revenue-section" className="bg-white rounded-xl border border-gray-100 shadow-sm p-5">
          <h2 className="text-sm font-bold text-gray-800 mb-4 flex items-center gap-2">
            <IndianRupee size={14} className="text-[#CC0000]" aria-hidden="true" /> PO-backed Revenue by Quarter
          </h2>
          {(!revenue?.by_quarter || revenue.by_quarter.length === 0) ? (
            <div className="h-48 flex items-center justify-center text-sm text-gray-400">No PO-backed replications yet</div>
          ) : (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={revenue.by_quarter.slice().reverse().map(r => ({
                q: new Date(r.quarter_start).toLocaleDateString("en-IN", { year: "2-digit", month: "short" }),
                revenue: r.revenue, deals: r.deals,
              }))}>
                <CartesianGrid strokeDasharray="3 3" stroke="#F1F5F9" />
                <XAxis dataKey="q" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip />
                <Bar dataKey="revenue" fill="#10B981" />
              </BarChart>
            </ResponsiveContainer>
          )}
        </section>
      </div>
    </div>
  );
}
