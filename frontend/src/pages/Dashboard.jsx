import { useEffect, useState } from "react";
import api from "../lib/api";
import {
  ResponsiveContainer, LineChart, Line, BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, Tooltip, CartesianGrid, Legend, AreaChart, Area
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from "../components/ui/sheet";
import { Switch } from "../components/ui/switch";
import { Label } from "../components/ui/label";
import { Users, KeyRound, AlertTriangle, DollarSign, TrendingUp, Box, ChevronRight, Settings as SettingsIcon, GripVertical } from "lucide-react";
import { StatusBadge } from "../components/StatusBadge";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import {
  DndContext, closestCenter, KeyboardSensor, PointerSensor, useSensor, useSensors,
} from "@dnd-kit/core";
import {
  arrayMove, SortableContext, sortableKeyboardCoordinates, useSortable, verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";

const COLORS = ["#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#06b6d4", "#84cc16", "#ec4899"];

const WIDGET_META = {
  kpi_customers: { label: "KPI: Customers", group: "KPI" },
  kpi_products: { label: "KPI: Products", group: "KPI" },
  kpi_active_licenses: { label: "KPI: Active Licenses", group: "KPI" },
  kpi_expiring_30: { label: "KPI: Expiring 30 days", group: "KPI" },
  kpi_expired: { label: "KPI: Expired", group: "KPI" },
  kpi_revenue: { label: "KPI: Revenue", group: "KPI" },
  chart_revenue: { label: "Monthly Revenue Trend", group: "Charts" },
  chart_product_pie: { label: "Product Distribution", group: "Charts" },
  chart_renewals: { label: "License Expiry Trend", group: "Charts" },
  chart_vendor: { label: "Vendor-wise Licenses", group: "Charts" },
  chart_growth: { label: "Customer Growth", group: "Charts" },
  critical_expiring: { label: "Critical Expiring Licenses", group: "Lists" },
  top_customers: { label: "Top Customers by Revenue", group: "Lists" },
};

function Kpi({ label, value, icon: Icon, accent, sub, testid }) {
  return (
    <Card className="glass-card border-0 hover:shadow-md transition-shadow" data-testid={testid}>
      <CardContent className="p-5 sm:p-6">
        <div className="flex items-start justify-between">
          <div>
            <p className="text-[10px] uppercase tracking-[0.18em] text-muted-foreground font-semibold">{label}</p>
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

function SortableWidget({ id, on, label, group, idx, total, toggle, move }) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id });
  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.6 : 1,
  };
  return (
    <div
      ref={setNodeRef}
      style={style}
      className={`flex items-center gap-3 p-3 rounded-lg border ${on ? "border-blue-500/30 bg-blue-500/5" : "border-slate-200/60 dark:border-white/10"}`}
      data-testid={`widget-toggle-${id}`}
    >
      <button {...attributes} {...listeners} className="cursor-grab active:cursor-grabbing touch-none" data-testid={`drag-${id}`}>
        <GripVertical className="h-4 w-4 text-muted-foreground" />
      </button>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium truncate">{label}</p>
        <p className="text-[10px] uppercase tracking-wider text-muted-foreground">{group}</p>
      </div>
      {on && (
        <div className="flex gap-1">
          <Button variant="ghost" size="sm" className="h-7 w-7 p-0" onClick={() => move(id, -1)} disabled={idx === 0}>↑</Button>
          <Button variant="ghost" size="sm" className="h-7 w-7 p-0" onClick={() => move(id, 1)} disabled={idx === total - 1}>↓</Button>
        </div>
      )}
      <Switch checked={on} onCheckedChange={(v) => toggle(id, v)} />
    </div>
  );
}

export default function Dashboard() {
  const [stats, setStats] = useState(null);
  const [widgets, setWidgets] = useState(null);
  const [sheetOpen, setSheetOpen] = useState(false);

  const loadConfig = async () => {
    const { data } = await api.get("/dashboard/config");
    setWidgets(data.widgets);
  };

  useEffect(() => {
    api.get("/dashboard/stats").then(r => setStats(r.data)).catch(() => {});
    loadConfig();
  }, []);

  const isVisible = (k) => widgets?.includes(k);

  const toggle = async (k, on) => {
    const next = on
      ? Array.from(new Set([...(widgets || []), k]))
      : (widgets || []).filter(w => w !== k);
    setWidgets(next);
    await api.put("/dashboard/config", { widgets: next });
  };

  const move = async (k, dir) => {
    const i = widgets.indexOf(k);
    if (i === -1) return;
    const j = i + dir;
    if (j < 0 || j >= widgets.length) return;
    const next = [...widgets];
    [next[i], next[j]] = [next[j], next[i]];
    setWidgets(next);
    await api.put("/dashboard/config", { widgets: next });
  };

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates })
  );

  const onDragEnd = async (event) => {
    const { active, over } = event;
    if (!over || active.id === over.id) return;
    const oldIdx = widgets.indexOf(active.id);
    const newIdx = widgets.indexOf(over.id);
    if (oldIdx === -1 || newIdx === -1) return;
    const next = arrayMove(widgets, oldIdx, newIdx);
    setWidgets(next);
    await api.put("/dashboard/config", { widgets: next });
  };

  const resetDefault = async () => {
    const def = Object.keys(WIDGET_META);
    setWidgets(def);
    await api.put("/dashboard/config", { widgets: def });
    toast.success("Dashboard reset to default");
  };

  if (!stats || !widgets) return (
    <div className="space-y-6">
      <div className="h-10 w-48 bg-muted/50 rounded animate-pulse" />
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
        {Array.from({length: 6}).map((_, i) => <div key={i} className="h-28 glass-card rounded-xl animate-pulse" />)}
      </div>
    </div>
  );

  const t = stats.totals;
  const monthsRevenue = stats.monthly_revenue.slice(-12);
  const renewals = stats.monthly_renewals.slice(-12);
  const growth = stats.customer_growth.slice(-12);
  const productPie = stats.product_stats.slice(0, 6);
  const vendorBars = stats.vendor_stats.slice(0, 8);

  // Build ordered renderers based on widgets array
  const renderWidget = (key) => {
    switch (key) {
      case "kpi_customers": return <Kpi key={key} label="Customers" value={t.customers} sub={`${t.active_customers} active`} icon={Users} accent="bg-blue-500/15 text-blue-600" testid="kpi-customers" />;
      case "kpi_products": return <Kpi key={key} label="Products" value={t.products} icon={Box} accent="bg-purple-500/15 text-purple-600" testid="kpi-products" />;
      case "kpi_active_licenses": return <Kpi key={key} label="Active Licenses" value={t.active_licenses} icon={KeyRound} accent="bg-emerald-500/15 text-emerald-600" testid="kpi-active-licenses" />;
      case "kpi_expiring_30": return <Kpi key={key} label="Expiring 30d" value={t.expiring_30} icon={AlertTriangle} accent="bg-amber-500/15 text-amber-600" testid="kpi-expiring-30" />;
      case "kpi_expired": return <Kpi key={key} label="Expired" value={t.expired_licenses} icon={AlertTriangle} accent="bg-red-500/15 text-red-600" testid="kpi-expired" />;
      case "kpi_revenue": return <Kpi key={key} label="Revenue" value={`$${(t.revenue_total / 1000).toFixed(1)}k`} icon={DollarSign} accent="bg-emerald-500/15 text-emerald-600" testid="kpi-revenue" />;
      default: return null;
    }
  };

  const visibleKPIs = widgets.filter(w => w.startsWith("kpi_") && Object.keys(WIDGET_META).includes(w));

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between flex-wrap gap-4">
        <div>
          <h1 className="font-display text-3xl sm:text-4xl font-bold tracking-tight">Dashboard</h1>
          <p className="text-sm text-muted-foreground mt-1">Real-time overview of your customer & license portfolio</p>
        </div>
        <Sheet open={sheetOpen} onOpenChange={setSheetOpen}>
          <SheetTrigger asChild>
            <Button variant="outline" data-testid="customize-dashboard-btn">
              <SettingsIcon className="h-4 w-4 mr-2" /> Customize
            </Button>
          </SheetTrigger>
          <SheetContent className="glass-strong w-full sm:max-w-md overflow-y-auto">
            <SheetHeader>
              <SheetTitle className="font-display">Customize Dashboard</SheetTitle>
              <p className="text-xs text-muted-foreground">Show, hide and reorder widgets</p>
            </SheetHeader>
            <div className="mt-6 space-y-2">
              <p className="text-xs text-muted-foreground mb-3">Drag <GripVertical className="h-3 w-3 inline" /> to reorder. Toggle switches to show or hide.</p>
              <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={onDragEnd}>
                <SortableContext items={widgets} strategy={verticalListSortingStrategy}>
                  {/* Active (in widgets order) */}
                  {widgets.map((k, i) => (
                    WIDGET_META[k] && (
                      <SortableWidget
                        key={k}
                        id={k}
                        on={true}
                        label={WIDGET_META[k].label}
                        group={WIDGET_META[k].group}
                        idx={i}
                        total={widgets.length}
                        toggle={toggle}
                        move={move}
                      />
                    )
                  ))}
                </SortableContext>
              </DndContext>

              {/* Hidden widgets (not in widgets array) shown below as toggles */}
              {Object.keys(WIDGET_META).filter(k => !widgets.includes(k)).length > 0 && (
                <>
                  <p className="text-xs uppercase tracking-wider text-muted-foreground mt-5 mb-2">Hidden</p>
                  {Object.keys(WIDGET_META).filter(k => !widgets.includes(k)).map(k => (
                    <div key={k} className="flex items-center gap-3 p-3 rounded-lg border border-slate-200/60 dark:border-white/10 opacity-60" data-testid={`widget-toggle-${k}`}>
                      <GripVertical className="h-4 w-4 text-muted-foreground" />
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium truncate">{WIDGET_META[k].label}</p>
                        <p className="text-[10px] uppercase tracking-wider text-muted-foreground">{WIDGET_META[k].group}</p>
                      </div>
                      <Switch checked={false} onCheckedChange={(v) => toggle(k, v)} />
                    </div>
                  ))}
                </>
              )}
            </div>
            <Button variant="outline" className="w-full mt-6" onClick={resetDefault} data-testid="reset-widgets-btn">Reset to Default</Button>
          </SheetContent>
        </Sheet>
      </div>

      {/* KPI Row */}
      {visibleKPIs.length > 0 && (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4" data-testid="kpi-row">
          {visibleKPIs.map(k => renderWidget(k))}
        </div>
      )}

      {/* Main charts row 1 */}
      {(isVisible("chart_revenue") || isVisible("chart_product_pie")) && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {isVisible("chart_revenue") && (
            <Card className="glass-card border-0 lg:col-span-2" data-testid="chart-revenue">
              <CardHeader><CardTitle className="font-display flex items-center gap-2"><TrendingUp className="h-5 w-5 text-blue-600" />Monthly Revenue Trend</CardTitle></CardHeader>
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
          )}

          {isVisible("chart_product_pie") && (
            <Card className="glass-card border-0" data-testid="chart-product-pie">
              <CardHeader><CardTitle className="font-display">Product Distribution</CardTitle></CardHeader>
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
          )}
        </div>
      )}

      {(isVisible("chart_renewals") || isVisible("chart_vendor") || isVisible("chart_growth")) && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {isVisible("chart_renewals") && (
            <Card className="glass-card border-0" data-testid="chart-renewals">
              <CardHeader><CardTitle className="font-display">License Expiry Trend</CardTitle></CardHeader>
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
          )}

          {isVisible("chart_vendor") && (
            <Card className="glass-card border-0" data-testid="chart-vendor">
              <CardHeader><CardTitle className="font-display">Vendor-wise Licenses</CardTitle></CardHeader>
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
          )}

          {isVisible("chart_growth") && (
            <Card className="glass-card border-0" data-testid="chart-growth">
              <CardHeader><CardTitle className="font-display">Customer Growth</CardTitle></CardHeader>
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
          )}
        </div>
      )}

      {(isVisible("critical_expiring") || isVisible("top_customers")) && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {isVisible("critical_expiring") && (
            <Card className="glass-card border-0" data-testid="critical-expiring">
              <CardHeader className="flex-row items-center justify-between">
                <CardTitle className="font-display flex items-center gap-2"><AlertTriangle className="h-5 w-5 text-amber-500" />Critical Expiring Licenses</CardTitle>
                <Link to="/licenses" className="text-xs text-blue-600 hover:underline flex items-center gap-1">View all <ChevronRight className="h-3 w-3" /></Link>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
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
          )}

          {isVisible("top_customers") && (
            <Card className="glass-card border-0" data-testid="top-customers">
              <CardHeader>
                <CardTitle className="font-display flex items-center gap-2"><Users className="h-5 w-5 text-blue-600" />Top Customers by Revenue</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
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
          )}
        </div>
      )}
    </div>
  );
}
