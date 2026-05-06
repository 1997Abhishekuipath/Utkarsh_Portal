import { useEffect, useState } from "react";
import api from "../lib/api";
import {
  ResponsiveContainer, LineChart, Line, BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, Tooltip, CartesianGrid, Legend, AreaChart, Area
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Users, KeyRound, AlertTriangle, DollarSign, TrendingUp, Box, ChevronRight } from "lucide-react";
import { StatusBadge } from "../components/StatusBadge";
import { Link } from "react-router-dom";

const COLORS = ["#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#06b6d4", "#84cc16", "#ec4899"];

function Kpi({ label, value, icon: Icon, accent, sub, testid }) {
  return (
    <Card className="glass-card border-0" data-testid={testid}>
      <CardContent className="p-6">
        <div className="flex items-start justify-between">
          <div>
            <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground font-semibold">{label}</p>
            <p className="font-display text-3xl sm:text-4xl font-bold mt-2 tracking-tight">{value}</p>
            {sub && <p className="text-xs text-muted-foreground mt-1">{sub}</p>}
          </div>
          <div className={`h-10 w-10 rounded-lg flex items-center justify-center ${accent}`}>
            <Icon className="h-5 w-5" strokeWidth={1.8} />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

export default function Dashboard() {
  const [stats, setStats] = useState(null);

  useEffect(() => {
    api.get("/dashboard/stats").then(r => setStats(r.data)).catch(() => {});
  }, []);

  if (!stats) return <div className="text-muted-foreground">Loading dashboard...</div>;

  const t = stats.totals;
  const monthsRevenue = stats.monthly_revenue.slice(-12);
  const renewals = stats.monthly_renewals.slice(-12);
  const growth = stats.customer_growth.slice(-12);
  const productPie = stats.product_stats.slice(0, 6);
  const vendorBars = stats.vendor_stats.slice(0, 8);

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between flex-wrap gap-4">
        <div>
          <h1 className="font-display text-3xl sm:text-4xl font-bold tracking-tight">Dashboard</h1>
          <p className="text-sm text-muted-foreground mt-1">Real-time overview of your customer & license portfolio</p>
        </div>
      </div>

      {/* KPI Row */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4" data-testid="kpi-row">
        <Kpi label="Customers" value={t.customers} sub={`${t.active_customers} active`} icon={Users} accent="bg-blue-500/15 text-blue-600" testid="kpi-customers" />
        <Kpi label="Products" value={t.products} icon={Box} accent="bg-purple-500/15 text-purple-600" testid="kpi-products" />
        <Kpi label="Active Licenses" value={t.active_licenses} icon={KeyRound} accent="bg-emerald-500/15 text-emerald-600" testid="kpi-active-licenses" />
        <Kpi label="Expiring 30d" value={t.expiring_30} icon={AlertTriangle} accent="bg-amber-500/15 text-amber-600" testid="kpi-expiring-30" />
        <Kpi label="Expired" value={t.expired_licenses} icon={AlertTriangle} accent="bg-red-500/15 text-red-600" testid="kpi-expired" />
        <Kpi label="Revenue" value={`$${(t.revenue_total / 1000).toFixed(1)}k`} icon={DollarSign} accent="bg-emerald-500/15 text-emerald-600" testid="kpi-revenue" />
      </div>

      {/* Main Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card className="glass-card border-0 lg:col-span-2" data-testid="chart-revenue">
          <CardHeader>
            <CardTitle className="font-display flex items-center gap-2">
              <TrendingUp className="h-5 w-5 text-blue-600" />
              Monthly Revenue Trend
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={300}>
              <AreaChart data={monthsRevenue}>
                <defs>
                  <linearGradient id="revGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#3b82f6" stopOpacity={0.4} />
                    <stop offset="100%" stopColor="#3b82f6" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.2)" />
                <XAxis dataKey="month" stroke="hsl(var(--muted-foreground))" fontSize={11} />
                <YAxis stroke="hsl(var(--muted-foreground))" fontSize={11} />
                <Tooltip contentStyle={{ background: "hsl(var(--card))", border: "1px solid hsl(var(--border))", borderRadius: 8 }} />
                <Area type="monotone" dataKey="revenue" stroke="#3b82f6" strokeWidth={2} fill="url(#revGrad)" />
              </AreaChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        <Card className="glass-card border-0" data-testid="chart-product-pie">
          <CardHeader>
            <CardTitle className="font-display">Product Distribution</CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={300}>
              <PieChart>
                <Pie data={productPie} dataKey="count" nameKey="product" innerRadius={55} outerRadius={90} paddingAngle={3}>
                  {productPie.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                </Pie>
                <Tooltip contentStyle={{ background: "hsl(var(--card))", border: "1px solid hsl(var(--border))", borderRadius: 8 }} />
                <Legend wrapperStyle={{ fontSize: 11 }} />
              </PieChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card className="glass-card border-0" data-testid="chart-renewals">
          <CardHeader>
            <CardTitle className="font-display">License Expiry Trend</CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={240}>
              <LineChart data={renewals}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.2)" />
                <XAxis dataKey="month" stroke="hsl(var(--muted-foreground))" fontSize={11} />
                <YAxis stroke="hsl(var(--muted-foreground))" fontSize={11} />
                <Tooltip contentStyle={{ background: "hsl(var(--card))", border: "1px solid hsl(var(--border))", borderRadius: 8 }} />
                <Line type="monotone" dataKey="count" stroke="#f59e0b" strokeWidth={2.5} dot={{ r: 3 }} />
              </LineChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        <Card className="glass-card border-0" data-testid="chart-vendor">
          <CardHeader>
            <CardTitle className="font-display">Vendor-wise Licenses</CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={vendorBars}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.2)" />
                <XAxis dataKey="vendor" stroke="hsl(var(--muted-foreground))" fontSize={10} angle={-15} textAnchor="end" height={50} />
                <YAxis stroke="hsl(var(--muted-foreground))" fontSize={11} />
                <Tooltip contentStyle={{ background: "hsl(var(--card))", border: "1px solid hsl(var(--border))", borderRadius: 8 }} />
                <Bar dataKey="count" fill="#8b5cf6" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        <Card className="glass-card border-0" data-testid="chart-growth">
          <CardHeader>
            <CardTitle className="font-display">Customer Growth</CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={growth}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.2)" />
                <XAxis dataKey="month" stroke="hsl(var(--muted-foreground))" fontSize={11} />
                <YAxis stroke="hsl(var(--muted-foreground))" fontSize={11} />
                <Tooltip contentStyle={{ background: "hsl(var(--card))", border: "1px solid hsl(var(--border))", borderRadius: 8 }} />
                <Bar dataKey="count" fill="#10b981" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </div>

      {/* Critical Lists */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card className="glass-card border-0" data-testid="critical-expiring">
          <CardHeader className="flex-row items-center justify-between">
            <CardTitle className="font-display flex items-center gap-2">
              <AlertTriangle className="h-5 w-5 text-amber-500" />
              Critical Expiring Licenses
            </CardTitle>
            <Link to="/licenses" className="text-xs text-blue-600 hover:underline flex items-center gap-1">View all <ChevronRight className="h-3 w-3" /></Link>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {stats.critical_expiring.length === 0 && <p className="text-sm text-muted-foreground">No critical licenses</p>}
              {stats.critical_expiring.map(l => (
                <div key={l.id} className="flex items-center justify-between p-3 rounded-lg hover:bg-accent transition-colors">
                  <div className="min-w-0">
                    <p className="text-sm font-medium truncate">{l.product_name}</p>
                    <p className="text-xs text-muted-foreground truncate">{l.customer_name} • Exp: {l.expiry_date}</p>
                  </div>
                  <StatusBadge status={l.status} />
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        <Card className="glass-card border-0" data-testid="top-customers">
          <CardHeader>
            <CardTitle className="font-display flex items-center gap-2">
              <Users className="h-5 w-5 text-blue-600" />
              Top Customers by Revenue
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {stats.top_customers.map((c, i) => (
                <div key={i} className="flex items-center justify-between p-3 rounded-lg hover:bg-accent transition-colors">
                  <div className="flex items-center gap-3 min-w-0">
                    <div className="h-8 w-8 rounded-full bg-blue-600 text-white flex items-center justify-center text-xs font-semibold flex-shrink-0">
                      {i + 1}
                    </div>
                    <span className="text-sm font-medium truncate">{c.company_name}</span>
                  </div>
                  <span className="text-sm font-semibold tabular-nums">${c.revenue.toLocaleString()}</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
