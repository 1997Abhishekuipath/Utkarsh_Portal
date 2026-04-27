import { useState, useEffect, useCallback, useRef } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext";
import {
  LayoutDashboard, Users, SlidersHorizontal, Quote,
  Columns3, Grid3X3, GalleryHorizontal, Bell, BarChart3,
  ChevronRight, Plus, Trash2, Edit3, Check, X, Zap,
  RefreshCw, LogOut, ExternalLink, Send, Toggle,
  ArrowLeft
} from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

/* ─── tiny helpers ─── */
function cls(...args) { return args.filter(Boolean).join(" "); }
function ago(iso) {
  if (!iso) return "";
  const s = Math.floor((Date.now() - new Date(iso)) / 1000);
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
}

/* ─── Toast ─── */
function Toast({ msg, ok }) {
  if (!msg) return null;
  return (
    <div className={cls(
      "fixed bottom-6 left-1/2 -translate-x-1/2 z-[999] px-5 py-2.5 rounded-xl text-sm font-semibold shadow-2xl animate-fade-in",
      ok ? "bg-[#1A8A4A] text-white" : "bg-[#C8281E] text-white"
    )}>{msg}</div>
  );
}

/* ─── Stat card ─── */
function StatCard({ emoji, value, label, delta, deltaColor = "#4ADF8A" }) {
  return (
    <div className="bg-[#161010] border border-[#2A1C1E] rounded-xl p-4 flex flex-col gap-1">
      <div className="text-2xl mb-1">{emoji}</div>
      <div className="font-['Barlow_Condensed',sans-serif] text-3xl font-extrabold text-white tracking-tight">{value}</div>
      <div className="text-[#8A8080] text-[11px] font-semibold tracking-wider uppercase">{label}</div>
      {delta && <div className="text-[11px] font-bold mt-0.5" style={{ color: deltaColor }}>{delta}</div>}
    </div>
  );
}

/* ─── Card wrapper ─── */
function Card({ children, className = "" }) {
  return (
    <div className={cls("bg-[#161010] border border-[#2A1C1E] rounded-xl overflow-hidden", className)}>
      {children}
    </div>
  );
}
function CardTop({ title, right }) {
  return (
    <div className="flex items-center justify-between px-4 py-3 border-b border-[#2A1C1E]">
      <div className="text-[13px] font-bold text-white">{title}</div>
      {right && <div>{right}</div>}
    </div>
  );
}
function CardBody({ children, className = "" }) {
  return <div className={cls("p-4", className)}>{children}</div>;
}

/* ─── Bar chart row ─── */
function BarRow({ label, pct, color = "#C8281E" }) {
  return (
    <div className="flex items-center gap-3 mb-3">
      <div className="text-[11px] text-[#C0B8B8] w-32 flex-shrink-0">{label}</div>
      <div className="flex-1 bg-[#2A1C1E] rounded-full h-2">
        <div className="h-2 rounded-full transition-all" style={{ width: `${pct}%`, background: color }} />
      </div>
      <div className="text-[11px] font-bold text-white w-8 text-right">{pct}%</div>
    </div>
  );
}

/* ─── Ghost / Red / Green buttons ─── */
function Btn({ children, onClick, variant = "ghost", size = "sm", className = "", disabled, type = "button" }) {
  const base = "inline-flex items-center gap-1.5 font-semibold rounded-lg transition-all cursor-pointer disabled:opacity-50";
  const sizes = { sm: "text-[11px] px-2.5 py-1", md: "text-xs px-4 py-2", lg: "text-sm px-5 py-2.5" };
  const variants = {
    ghost: "bg-transparent border border-[#4A4040] text-[#C0B8B8] hover:border-[#C0B8B8] hover:text-white",
    red: "bg-[#C8281E] text-white hover:bg-[#9B1A12] border border-transparent",
    green: "bg-[#1A8A4A] text-white hover:bg-[#137038] border border-transparent",
    danger: "bg-transparent border border-[#C8281E] text-[#E8453A] hover:bg-[#C8281E] hover:text-white",
  };
  return <button type={type} onClick={onClick} disabled={disabled} className={cls(base, sizes[size], variants[variant], className)}>{children}</button>;
}

/* ─── Input / Textarea / Select ─── */
function Inp({ label, children }) {
  return (
    <div className="mb-3">
      {label && <div className="text-[9px] font-extrabold tracking-widest text-[#8A8080] mb-1.5">{label}</div>}
      {children}
    </div>
  );
}
const inputCls = "w-full bg-[#201618] border border-[#4A4040] text-white text-xs rounded-lg px-3 py-2 focus:outline-none focus:border-[#C8281E] placeholder:text-[#4A4040]";

/* ─── Sidebar nav item ─── */
function NavItem({ icon: Icon, label, active, badge, onClick }) {
  return (
    <button onClick={onClick}
      className={cls(
        "w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-left transition-all text-[12px] font-semibold",
        active ? "bg-[#C8281E] text-white" : "text-[#8A8080] hover:text-white hover:bg-[#201618]"
      )}>
      <Icon size={14} className="flex-shrink-0" />
      <span className="flex-1">{label}</span>
      {badge > 0 && (
        <span className="bg-[#C8281E] text-white text-[9px] font-black w-4 h-4 rounded-full flex items-center justify-center">
          {badge > 9 ? "9+" : badge}
        </span>
      )}
    </button>
  );
}
function NavSection({ label }) {
  return <div className="text-[9px] font-black tracking-widest text-[#4A4040] px-3 pt-4 pb-1.5 uppercase">{label}</div>;
}

/* ═══════════════════════ PAGES ═══════════════════════ */

/* ── Dashboard ── */
function DashboardPage({ authHeader, onNav, stats }) {
  const [pending, setPending] = useState([]);
  const [notifs, setNotifs] = useState([]);
  const [activity, setActivity] = useState(null);

  useEffect(() => {
    const h = authHeader();
    fetch(`${API}/admin/users/pending`, { headers: h }).then(r => r.json()).then(d => setPending(Array.isArray(d) ? d.slice(0, 3) : [])).catch(() => {});
    fetch(`${API}/admin/notifications?limit=3`, { headers: h }).then(r => r.json()).then(d => setNotifs((d.items || []).slice(0, 3))).catch(() => {});
    fetch(`${API}/admin/analytics/summary`, { headers: h }).then(r => r.json()).then(setActivity).catch(() => {});
  }, []);

  const approveUser = async (id) => {
    await fetch(`${API}/admin/users/${id}/approve`, { method: "POST", headers: authHeader() });
    setPending(p => p.filter(u => u.id !== id));
  };

  return (
    <div>
      {/* Stats row */}
      <div className="grid grid-cols-5 gap-3 mb-4">
        <StatCard emoji="👥" value={stats.total || 0} label="Active Users" delta={`↑ ${stats.thisWeek || 0} this week`} />
        <StatCard emoji="📢" value={stats.edmSlides || 8} label="EDM Slides" delta="Home carousel" deltaColor="#8A8080" />
        <StatCard emoji="🔧" value={stats.icons || 46} label="Icons / Apps" delta="Across 4 pillars" deltaColor="#8A8080" />
        <StatCard emoji="🔔" value={7} label="Auto-Triggers" delta="All active" />
        <StatCard emoji="📈" value={activity?.engagement_pct ? `${activity.engagement_pct}%` : "87%"} label="Engagement" delta="↑ 14pts QoQ" />
      </div>

      <div className="grid grid-cols-2 gap-4 mb-4">
        {/* Pending Approvals */}
        <Card>
          <CardTop title="⏳ Pending Approvals"
            right={<Btn onClick={() => onNav("users")}>View all →</Btn>} />
          <CardBody>
            {pending.length === 0 ? (
              <div className="text-center py-6 text-[#4A4040] text-xs">No pending approvals</div>
            ) : pending.map(u => (
              <div key={u.id} className="flex items-center gap-2.5 p-2.5 bg-[#201618] rounded-lg mb-2">
                <div className="w-8 h-8 rounded-full flex-shrink-0 flex items-center justify-center text-xs font-black text-white"
                  style={{ background: u.avatar_url ? `url(${u.avatar_url}) center/cover` : "#1A4A9A" }}>
                  {u.name?.slice(0, 2).toUpperCase()}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-[12px] font-bold text-white truncate">{u.name}</div>
                  <div className="text-[10px] text-[#8A8080]">{u.department || u.email}</div>
                </div>
                <Btn variant="green" onClick={() => approveUser(u.id)}>Approve</Btn>
              </div>
            ))}
          </CardBody>
        </Card>

        {/* Recent Notifications */}
        <Card>
          <CardTop title="📢 Recent Notifications"
            right={<Btn onClick={() => onNav("push")}>Manage →</Btn>} />
          <CardBody>
            <div className="flex flex-col gap-2">
              {notifs.length === 0 ? (
                <div className="text-center py-6 text-[#4A4040] text-xs">No notifications sent yet</div>
              ) : notifs.map(n => (
                <div key={n.id} className="p-2.5 bg-[#201618] rounded-lg">
                  <div className="text-[12px] font-semibold text-white">{n.title}</div>
                  <div className="text-[10px] text-[#8A8080] mt-0.5">{ago(n.sent_at)}</div>
                </div>
              ))}
              {/* static fallbacks */}
              {notifs.length === 0 && [
                { t: "💰 Incentive Statement Ready", s: "Sent to 142 employees · 2h ago · 94% opened" },
                { t: "📚 New Best Practice Published", s: "Sent to all · 1d ago · 78% opened" },
                { t: "🎂 Birthday — Kiran Bhat", s: "Auto-sent · Today · 50 XP credited" },
              ].map((n, i) => (
                <div key={i} className="p-2.5 bg-[#201618] rounded-lg">
                  <div className="text-[12px] font-semibold text-white">{n.t}</div>
                  <div className="text-[10px] text-[#8A8080] mt-0.5">{n.s}</div>
                </div>
              ))}
            </div>
          </CardBody>
        </Card>
      </div>

      {/* Platform Activity */}
      <Card>
        <CardTop title="📊 Platform Activity"
          right={<Btn onClick={() => onNav("analytics")}>Full analytics →</Btn>} />
        <CardBody>
          <BarRow label="Employee Pillar" pct={91} color="#1A8A4A" />
          <BarRow label="Customer Pillar" pct={78} color="#C8281E" />
          <BarRow label="Innovator Pillar" pct={64} color="#1A4A9A" />
          <BarRow label="Shareholder Pillar" pct={42} color="#D4A84A" />
          <BarRow label="EDM Click-thru" pct={68} color="#0A8A9A" />
        </CardBody>
      </Card>
    </div>
  );
}

/* ── User Approvals ── */
function UsersPage({ authHeader, onBadge, toast }) {
  const [pending, setPending] = useState([]);
  const [approved, setApproved] = useState([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    const h = authHeader();
    const [p, a] = await Promise.all([
      fetch(`${API}/admin/users/pending`, { headers: h }).then(r => r.json()).catch(() => []),
      fetch(`${API}/admin/users?status=active&limit=50`, { headers: h }).then(r => r.json()).catch(() => []),
    ]);
    setPending(Array.isArray(p) ? p : []);
    setApproved(Array.isArray(a) ? a : (a?.items || []));
    onBadge(Array.isArray(p) ? p.length : 0);
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  const approve = async (id) => {
    await fetch(`${API}/admin/users/${id}/approve`, { method: "POST", headers: authHeader() });
    toast("User approved ✓", true);
    load();
  };
  const reject = async (id) => {
    await fetch(`${API}/admin/users/${id}/reject`, { method: "POST", headers: authHeader() });
    toast("User rejected", false);
    load();
  };

  const RoleChip = ({ role }) => {
    const colors = { super_admin: "bg-purple-900/60 text-purple-300", admin: "bg-red-900/60 text-red-300", manager: "bg-blue-900/60 text-blue-300", employee: "bg-green-900/60 text-green-300" };
    return <span className={cls("text-[9px] font-black px-2 py-0.5 rounded-full", colors[role] || "bg-[#201618] text-[#8A8080]")}>{role?.toUpperCase()}</span>;
  };

  const UserRow = ({ u, actions }) => (
    <div className="flex items-center gap-3 p-2.5 bg-[#201618] rounded-lg mb-2">
      <div className="w-9 h-9 rounded-full flex-shrink-0 flex items-center justify-center text-xs font-black text-white" style={{ background: "#1A4A9A" }}>
        {u.name?.slice(0, 2).toUpperCase()}
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-[13px] font-bold text-white">{u.name}</span>
          <RoleChip role={u.role} />
        </div>
        <div className="text-[10px] text-[#8A8080]">{u.email} · {u.department || "—"}</div>
      </div>
      <div className="flex gap-1">{actions(u)}</div>
    </div>
  );

  return (
    <div className="space-y-4">
      <Card>
        <CardTop title="⏳ Pending Approvals"
          right={<span className="text-[10px] text-[#8A8080]">Domain: @hitachi-systems.com only</span>} />
        <CardBody>
          {loading ? <div className="text-center py-8"><RefreshCw size={20} className="animate-spin text-[#C8281E] mx-auto" /></div>
            : pending.length === 0
            ? <div className="text-center py-8 text-[#4A4040] text-sm">🎉 No pending approvals</div>
            : pending.map(u => <UserRow key={u.id} u={u} actions={u => (
                <>
                  <Btn variant="green" onClick={() => approve(u.id)}>Approve</Btn>
                  <Btn variant="danger" onClick={() => reject(u.id)}>Reject</Btn>
                </>
              )} />)
          }
        </CardBody>
      </Card>

      <Card>
        <CardTop title="✅ Approved Users" right={<span className="text-[#8A8080] text-xs">{approved.length} total</span>} />
        <CardBody className="max-h-[50vh] overflow-y-auto">
          {loading ? <div className="text-center py-8"><RefreshCw size={20} className="animate-spin text-[#C8281E] mx-auto" /></div>
            : approved.map(u => <UserRow key={u.id} u={u} actions={() => null} />)
          }
        </CardBody>
      </Card>
    </div>
  );
}

/* ── Home EDM ── */
function HomeEDMPage({ authHeader, toast }) {
  const [slides, setSlides] = useState([]);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    const data = await fetch(`${API}/admin/edm-slides?scope=home`, { headers: authHeader() }).then(r => r.json()).catch(() => []);
    setSlides(Array.isArray(data) ? data : []);
    setLoading(false);
  };
  useEffect(() => { load(); }, []);

  const add = async () => {
    const body = { scope: "home", title: "New Slide", subtitle: "", gradient_from: "#C8281E", gradient_to: "#9B1A12", tag: "NEW", tag_color: "#D4A84A", position: slides.length };
    await fetch(`${API}/admin/edm-slides`, { method: "POST", headers: { ...authHeader(), "Content-Type": "application/json" }, body: JSON.stringify(body) });
    toast("Slide added", true); load();
  };
  const del = async (id) => {
    await fetch(`${API}/admin/edm-slides/${id}`, { method: "DELETE", headers: authHeader() });
    toast("Slide deleted", false); load();
  };
  const update = async (id, field, val) => {
    await fetch(`${API}/admin/edm-slides/${id}`, { method: "PUT", headers: { ...authHeader(), "Content-Type": "application/json" }, body: JSON.stringify({ [field]: val }) });
  };

  return (
    <Card>
      <CardTop title="📢 Home EDM Carousel" right={<Btn variant="red" onClick={add}><Plus size={12} /> Add Slide</Btn>} />
      <CardBody>
        <div className="text-[11px] text-[#8A8080] mb-4">Changes publish to both <strong className="text-white">Employee Web</strong> and <strong className="text-white">Mobile App</strong>.</div>
        {loading ? <div className="text-center py-12"><RefreshCw size={20} className="animate-spin text-[#C8281E] mx-auto" /></div>
          : slides.length === 0 ? <div className="text-center py-12 text-[#4A4040] text-sm">No slides yet — click Add Slide</div>
          : (
            <div className="space-y-3">
              {slides.map(s => (
                <div key={s.id} className="border border-[#2A1C1E] rounded-xl overflow-hidden">
                  {/* Preview */}
                  <div className="p-4 flex items-center gap-3" style={{ background: `linear-gradient(135deg, ${s.gradient_from || "#C8281E"}, ${s.gradient_to || "#9B1A12"})` }}>
                    <div className="flex-1">
                      <div className="font-['Barlow_Condensed',sans-serif] font-black text-xl text-white">{s.title}</div>
                      <div className="text-white/70 text-xs mt-0.5">{s.subtitle}</div>
                    </div>
                    {s.tag && <span className="text-[9px] font-black px-2 py-0.5 rounded-full" style={{ background: s.tag_color || "#D4A84A", color: "#000" }}>{s.tag}</span>}
                  </div>
                  {/* Editor */}
                  <div className="p-3 bg-[#201618] grid grid-cols-2 gap-2">
                    <div>
                      <div className="text-[9px] text-[#8A8080] mb-1 font-bold tracking-widest">TITLE</div>
                      <input defaultValue={s.title} onBlur={e => update(s.id, "title", e.target.value)} className={inputCls} />
                    </div>
                    <div>
                      <div className="text-[9px] text-[#8A8080] mb-1 font-bold tracking-widest">SUBTITLE</div>
                      <input defaultValue={s.subtitle} onBlur={e => update(s.id, "subtitle", e.target.value)} className={inputCls} />
                    </div>
                    <div>
                      <div className="text-[9px] text-[#8A8080] mb-1 font-bold tracking-widest">FROM COLOR</div>
                      <div className="flex items-center gap-2">
                        <input type="color" defaultValue={s.gradient_from || "#C8281E"} onBlur={e => update(s.id, "gradient_from", e.target.value)} className="w-8 h-8 rounded cursor-pointer bg-transparent border-0" />
                        <input defaultValue={s.gradient_from} onBlur={e => update(s.id, "gradient_from", e.target.value)} className={cls(inputCls, "flex-1")} />
                      </div>
                    </div>
                    <div>
                      <div className="text-[9px] text-[#8A8080] mb-1 font-bold tracking-widest">TO COLOR</div>
                      <div className="flex items-center gap-2">
                        <input type="color" defaultValue={s.gradient_to || "#9B1A12"} onBlur={e => update(s.id, "gradient_to", e.target.value)} className="w-8 h-8 rounded cursor-pointer bg-transparent border-0" />
                        <input defaultValue={s.gradient_to} onBlur={e => update(s.id, "gradient_to", e.target.value)} className={cls(inputCls, "flex-1")} />
                      </div>
                    </div>
                    <div>
                      <div className="text-[9px] text-[#8A8080] mb-1 font-bold tracking-widest">TAG</div>
                      <input defaultValue={s.tag} onBlur={e => update(s.id, "tag", e.target.value)} placeholder="e.g. INCENTIVE" className={inputCls} />
                    </div>
                    <div className="flex items-end justify-end">
                      <Btn variant="danger" onClick={() => del(s.id)}><Trash2 size={12} /> Delete</Btn>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
      </CardBody>
    </Card>
  );
}

/* ── Motivational Quotes ── */
function QuotesPage({ authHeader, toast }) {
  const [quotes, setQuotes] = useState([]);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    const data = await fetch(`${API}/admin/quotes`, { headers: authHeader() }).then(r => r.json()).catch(() => []);
    setQuotes(Array.isArray(data) ? data : []);
    setLoading(false);
  };
  useEffect(() => { load(); }, []);

  const add = async () => {
    await fetch(`${API}/admin/quotes`, { method: "POST", headers: { ...authHeader(), "Content-Type": "application/json" }, body: JSON.stringify({ text: "New quote", source: "Author", scope: "all", is_active: true }) });
    toast("Quote added", true); load();
  };
  const del = async (id) => {
    await fetch(`${API}/admin/quotes/${id}`, { method: "DELETE", headers: authHeader() });
    toast("Quote deleted", false); load();
  };
  const update = async (id, field, val) => {
    await fetch(`${API}/admin/quotes/${id}`, { method: "PUT", headers: { ...authHeader(), "Content-Type": "application/json" }, body: JSON.stringify({ [field]: val }) });
  };

  return (
    <Card>
      <CardTop title="💡 Motivational Quotes" right={<Btn variant="red" onClick={add}><Plus size={12} /> Add Quote</Btn>} />
      <CardBody>
        <div className="text-[11px] text-[#8A8080] mb-4">Quotes rotate every 30 seconds on home screen and profile.</div>
        {loading ? <div className="text-center py-12"><RefreshCw size={20} className="animate-spin text-[#C8281E] mx-auto" /></div>
          : quotes.length === 0 ? <div className="text-center py-12 text-[#4A4040] text-sm">No quotes yet — click Add Quote</div>
          : (
            <div className="space-y-2">
              {quotes.map((q, i) => (
                <div key={q.id} className="flex items-start gap-3 bg-[#201618] rounded-xl p-3">
                  <div className="text-[#4A4040] font-black text-lg leading-none mt-0.5">"{/* */}</div>
                  <div className="flex-1 space-y-2">
                    <textarea defaultValue={q.text} onBlur={e => update(q.id, "text", e.target.value)} rows={2} className={cls(inputCls, "resize-none")} placeholder="Quote text…" />
                    <input defaultValue={q.source} onBlur={e => update(q.id, "source", e.target.value)} className={inputCls} placeholder="Source / attribution" />
                  </div>
                  <Btn variant="danger" onClick={() => del(q.id)}><Trash2 size={12} /></Btn>
                </div>
              ))}
            </div>
          )}
      </CardBody>
    </Card>
  );
}

/* ── Pillar Manager ── */
function PillarManagerPage({ authHeader, toast }) {
  const [pillars, setPillars] = useState([]);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    const data = await fetch(`${API}/admin/pillars`, { headers: authHeader() }).then(r => r.json()).catch(() => []);
    setPillars(Array.isArray(data) ? data : []);
    setLoading(false);
  };
  useEffect(() => { load(); }, []);

  const update = async (id, field, val) => {
    await fetch(`${API}/admin/pillars/${id}`, { method: "PUT", headers: { ...authHeader(), "Content-Type": "application/json" }, body: JSON.stringify({ [field]: val }) });
    toast("Saved", true);
  };

  return (
    <Card>
      <CardTop title="🏛️ Pillar Manager" />
      <CardBody>
        {loading ? <div className="text-center py-12"><RefreshCw size={20} className="animate-spin text-[#C8281E] mx-auto" /></div>
          : (
            <div className="grid grid-cols-2 gap-4">
              {pillars.map(p => (
                <div key={p.id} className="bg-[#201618] rounded-xl overflow-hidden border border-[#2A1C1E]">
                  <div className="p-3 flex items-center gap-2" style={{ background: `linear-gradient(135deg, ${p.gradient_from || "#C8281E"}, ${p.gradient_to || "#9B1A12"})` }}>
                    <span className="text-2xl">{p.icon_name || "🏛️"}</span>
                    <div>
                      <div className="font-['Barlow_Condensed',sans-serif] font-black text-lg text-white">{p.name}</div>
                      <div className="text-white/70 text-xs">{p.tagline}</div>
                    </div>
                  </div>
                  <div className="p-3 space-y-2">
                    <div>
                      <div className="text-[9px] text-[#8A8080] font-bold tracking-widest mb-1">TAGLINE</div>
                      <input defaultValue={p.tagline} onBlur={e => update(p.id, "tagline", e.target.value)} className={inputCls} />
                    </div>
                    <div>
                      <div className="text-[9px] text-[#8A8080] font-bold tracking-widest mb-1">DESCRIPTION</div>
                      <input defaultValue={p.description} onBlur={e => update(p.id, "description", e.target.value)} className={inputCls} />
                    </div>
                    <div className="flex gap-2">
                      <div className="flex-1">
                        <div className="text-[9px] text-[#8A8080] font-bold tracking-widest mb-1">FROM</div>
                        <div className="flex gap-1">
                          <input type="color" defaultValue={p.gradient_from || "#C8281E"} onBlur={e => update(p.id, "gradient_from", e.target.value)} className="w-7 h-7 rounded border-0 bg-transparent cursor-pointer" />
                          <input defaultValue={p.gradient_from} onBlur={e => update(p.id, "gradient_from", e.target.value)} className={cls(inputCls, "flex-1")} />
                        </div>
                      </div>
                      <div className="flex-1">
                        <div className="text-[9px] text-[#8A8080] font-bold tracking-widest mb-1">TO</div>
                        <div className="flex gap-1">
                          <input type="color" defaultValue={p.gradient_to || "#9B1A12"} onBlur={e => update(p.id, "gradient_to", e.target.value)} className="w-7 h-7 rounded border-0 bg-transparent cursor-pointer" />
                          <input defaultValue={p.gradient_to} onBlur={e => update(p.id, "gradient_to", e.target.value)} className={cls(inputCls, "flex-1")} />
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
      </CardBody>
    </Card>
  );
}

/* ── Icon & App Manager ── */
function IconManagerPage({ authHeader, toast }) {
  const [pillars, setPillars] = useState([]);
  const [activePillar, setActivePillar] = useState(null);
  const [icons, setIcons] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${API}/admin/pillars`, { headers: authHeader() }).then(r => r.json()).then(d => {
      setPillars(Array.isArray(d) ? d : []);
      if (d.length > 0) setActivePillar(d[0].id);
    }).catch(() => {});
  }, []);

  useEffect(() => {
    if (!activePillar) return;
    setLoading(true);
    fetch(`${API}/admin/pillar-icons?pillar_id=${activePillar}`, { headers: authHeader() }).then(r => r.json()).then(d => {
      setIcons(Array.isArray(d) ? d : []);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, [activePillar]);

  const add = async () => {
    if (!activePillar) return;
    await fetch(`${API}/admin/pillar-icons`, { method: "POST", headers: { ...authHeader(), "Content-Type": "application/json" }, body: JSON.stringify({ pillar_id: activePillar, name: "New App", lucide_icon: "Box", route: "/apps/new" }) });
    toast("App added", true);
    setActivePillar(ap => { const x = ap; setTimeout(() => setActivePillar(x), 0); return null; });
    setTimeout(() => setActivePillar(activePillar), 50);
  };
  const del = async (id) => {
    await fetch(`${API}/admin/pillar-icons/${id}`, { method: "DELETE", headers: authHeader() });
    toast("App removed", false);
    setIcons(icons.filter(i => i.id !== id));
  };
  const update = async (id, field, val) => {
    await fetch(`${API}/admin/pillar-icons/${id}`, { method: "PUT", headers: { ...authHeader(), "Content-Type": "application/json" }, body: JSON.stringify({ [field]: val }) });
  };

  const pillarName = pillars.find(p => p.id === activePillar)?.name || "";

  return (
    <div>
      {/* Pillar tabs */}
      <div className="flex gap-1 mb-3">
        {pillars.map(p => (
          <button key={p.id} onClick={() => setActivePillar(p.id)}
            className={cls("px-4 py-1.5 rounded-lg text-xs font-bold transition-all",
              p.id === activePillar ? "bg-[#C8281E] text-white" : "bg-[#201618] text-[#8A8080] hover:text-white")}>
            {p.name}
          </button>
        ))}
      </div>
      <Card>
        <CardTop title={`🔧 ${pillarName} — Icons & Apps`} right={<Btn variant="red" onClick={add}><Plus size={12} /> Add App</Btn>} />
        <CardBody>
          <div className="text-[11px] text-[#8A8080] mb-4">Name · Lucide icon · Route · Badge (HOT/NEW).</div>
          {loading ? <div className="text-center py-12"><RefreshCw size={20} className="animate-spin text-[#C8281E] mx-auto" /></div> : (
            <div className="grid grid-cols-2 gap-2">
              {icons.map(ic => (
                <div key={ic.id} className="bg-[#201618] rounded-xl p-3 flex items-start gap-2">
                  <div className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 text-xs font-black" style={{ background: ic.card_color || "#C8281E" }}>
                    ⬡
                  </div>
                  <div className="flex-1 min-w-0 space-y-1.5">
                    <input defaultValue={ic.name} onBlur={e => update(ic.id, "name", e.target.value)} className={inputCls} placeholder="App name" />
                    <input defaultValue={ic.lucide_icon} onBlur={e => update(ic.id, "lucide_icon", e.target.value)} className={inputCls} placeholder="Lucide icon (e.g. Award)" />
                    <input defaultValue={ic.route} onBlur={e => update(ic.id, "route", e.target.value)} className={inputCls} placeholder="/apps/route" />
                    <div className="flex gap-1">
                      {["", "hot", "new"].map(b => (
                        <button key={b} onClick={() => update(ic.id, "badge", b)}
                          className={cls("px-2 py-0.5 rounded text-[9px] font-black transition-all",
                            ic.badge === b ? "bg-[#C8281E] text-white" : "bg-[#2A1C1E] text-[#8A8080] hover:text-white")}>
                          {b || "none"}
                        </button>
                      ))}
                    </div>
                  </div>
                  <Btn variant="danger" onClick={() => del(ic.id)}><Trash2 size={11} /></Btn>
                </div>
              ))}
            </div>
          )}
        </CardBody>
      </Card>
    </div>
  );
}

/* ── Pillar EDM ── */
function PillarEDMPage({ authHeader, toast }) {
  const [pillars, setPillars] = useState([]);
  const [activePillar, setActivePillar] = useState(null);
  const [slides, setSlides] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${API}/admin/pillars`, { headers: authHeader() }).then(r => r.json()).then(d => {
      const arr = Array.isArray(d) ? d : [];
      setPillars(arr);
      if (arr.length > 0) setActivePillar(arr[0].slug);
    }).catch(() => {});
  }, []);

  useEffect(() => {
    if (!activePillar) return;
    setLoading(true);
    fetch(`${API}/admin/edm-slides?scope=${activePillar}`, { headers: authHeader() }).then(r => r.json()).then(d => {
      setSlides(Array.isArray(d) ? d : []);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, [activePillar]);

  const add = async () => {
    await fetch(`${API}/admin/edm-slides`, { method: "POST", headers: { ...authHeader(), "Content-Type": "application/json" }, body: JSON.stringify({ scope: activePillar, title: "New Slide", subtitle: "", gradient_from: "#C8281E", gradient_to: "#9B1A12", tag: "NEW", position: slides.length }) });
    toast("Slide added", true);
    const d = await fetch(`${API}/admin/edm-slides?scope=${activePillar}`, { headers: authHeader() }).then(r => r.json()).catch(() => []);
    setSlides(Array.isArray(d) ? d : []);
  };
  const del = async (id) => {
    await fetch(`${API}/admin/edm-slides/${id}`, { method: "DELETE", headers: authHeader() });
    toast("Slide deleted", false);
    setSlides(s => s.filter(x => x.id !== id));
  };
  const update = async (id, field, val) => {
    await fetch(`${API}/admin/edm-slides/${id}`, { method: "PUT", headers: { ...authHeader(), "Content-Type": "application/json" }, body: JSON.stringify({ [field]: val }) });
  };

  const pillarName = pillars.find(p => p.slug === activePillar)?.name || "";

  return (
    <div>
      <div className="flex gap-1 mb-3">
        {pillars.map(p => (
          <button key={p.slug} onClick={() => setActivePillar(p.slug)}
            className={cls("px-4 py-1.5 rounded-lg text-xs font-bold transition-all",
              p.slug === activePillar ? "bg-[#C8281E] text-white" : "bg-[#201618] text-[#8A8080] hover:text-white")}>
            {p.name}
          </button>
        ))}
      </div>
      <Card>
        <CardTop title={`🗂️ ${pillarName} — EDM Slides`} right={<Btn variant="red" onClick={add}><Plus size={12} /> Add Slide</Btn>} />
        <CardBody>
          {loading ? <div className="text-center py-12"><RefreshCw size={20} className="animate-spin text-[#C8281E] mx-auto" /></div>
            : slides.length === 0 ? <div className="text-center py-12 text-[#4A4040] text-sm">No slides for this pillar — click Add Slide</div>
            : (
              <div className="space-y-3">
                {slides.map(s => (
                  <div key={s.id} className="border border-[#2A1C1E] rounded-xl overflow-hidden">
                    <div className="p-4" style={{ background: `linear-gradient(135deg, ${s.gradient_from || "#C8281E"}, ${s.gradient_to || "#9B1A12"})` }}>
                      <div className="font-black text-xl text-white">{s.title}</div>
                      <div className="text-white/70 text-xs">{s.subtitle}</div>
                    </div>
                    <div className="p-3 bg-[#201618] grid grid-cols-2 gap-2">
                      <div><div className="text-[9px] text-[#8A8080] mb-1 font-bold tracking-widest">TITLE</div><input defaultValue={s.title} onBlur={e => update(s.id, "title", e.target.value)} className={inputCls} /></div>
                      <div><div className="text-[9px] text-[#8A8080] mb-1 font-bold tracking-widest">SUBTITLE</div><input defaultValue={s.subtitle} onBlur={e => update(s.id, "subtitle", e.target.value)} className={inputCls} /></div>
                      <div className="flex items-end justify-end col-span-2"><Btn variant="danger" onClick={() => del(s.id)}><Trash2 size={12} /> Delete</Btn></div>
                    </div>
                  </div>
                ))}
              </div>
            )}
        </CardBody>
      </Card>
    </div>
  );
}

/* ── Push Notifications ── */
const TRIGGERS = [
  { name: "Birthday XP Bonus", desc: "50 XP auto-credited at midnight on employee's birthday. Push + in-app." },
  { name: "Practice Approved", desc: "Notifies employee when their best practice is approved by admin." },
  { name: "Replication Approved", desc: "Notifies employee when replication is verified with XP details." },
  { name: "New Practice Submitted", desc: "Notifies all admins when a new best practice enters the queue." },
  { name: "Account Approved", desc: "Welcome notification when admin approves a new user registration." },
  { name: "XP Milestone Award", desc: "Celebrates reaching 100 / 250 / 500 / 1K / 2.5K / 5K / 10K XP." },
  { name: "Weekly Reminder", desc: "Monday 9 AM: nudges users with pending practice submissions." },
];

function PushPage({ authHeader, toast }) {
  const [title, setTitle] = useState("");
  const [msg, setMsg] = useState("");
  const [target, setTarget] = useState("all");
  const [category, setCategory] = useState("announcement");
  const [sending, setSending] = useState(false);
  const [enabled, setEnabled] = useState(TRIGGERS.map(() => true));

  const send = async () => {
    if (!title || !msg) { toast("Title and message required", false); return; }
    setSending(true);
    try {
      await fetch(`${API}/admin/notifications/send`, {
        method: "POST",
        headers: { ...authHeader(), "Content-Type": "application/json" },
        body: JSON.stringify({ title, body: msg, category, target_type: target === "all" ? "broadcast" : "role", target_id: target }),
      });
      toast("Notification sent ⚡", true);
      setTitle(""); setMsg("");
    } catch { toast("Send failed", false); }
    finally { setSending(false); }
  };

  return (
    <div className="grid grid-cols-2 gap-4">
      {/* Composer */}
      <Card>
        <CardTop title="📤 Send Notification" />
        <CardBody className="space-y-3">
          <Inp label="TITLE">
            <input value={title} onChange={e => setTitle(e.target.value)} className={inputCls} placeholder="e.g. Q2 Incentive Statement Ready" />
          </Inp>
          <Inp label="MESSAGE">
            <textarea value={msg} onChange={e => setMsg(e.target.value)} rows={3} className={cls(inputCls, "resize-vertical")} placeholder="Notification body…" />
          </Inp>
          <Inp label="TARGET">
            <select value={target} onChange={e => setTarget(e.target.value)} className={inputCls}>
              <option value="all">All Employees</option>
              <option value="admin">Admins Only</option>
              <option value="manager">Managers Only</option>
              <option value="employee">Employees Only</option>
            </select>
          </Inp>
          <Inp label="CATEGORY">
            <select value={category} onChange={e => setCategory(e.target.value)} className={inputCls}>
              <option value="announcement">📢 Announcement</option>
              <option value="incentive">💰 Incentive</option>
              <option value="reminder">📚 New Practice</option>
              <option value="award">🏆 Award</option>
              <option value="approved">⚠️ Reminder</option>
            </select>
          </Inp>
          <div className="flex gap-2">
            <Btn variant="red" size="md" onClick={send} disabled={sending} className="flex-1">
              <Zap size={13} />{sending ? "Sending…" : "Send Now"}
            </Btn>
            <Btn size="md">📅 Schedule</Btn>
          </div>
        </CardBody>
      </Card>

      {/* Auto-Triggers */}
      <Card>
        <CardTop title="🤖 Smart Auto-Triggers" />
        <CardBody className="space-y-2">
          {TRIGGERS.map((t, i) => (
            <div key={t.name} className="flex items-start gap-3 p-2.5 bg-[#201618] rounded-lg">
              <button onClick={() => setEnabled(e => { const n = [...e]; n[i] = !n[i]; return n; })}
                className={cls("w-8 h-4 rounded-full relative transition-all flex-shrink-0 mt-0.5",
                  enabled[i] ? "bg-[#1A8A4A]" : "bg-[#2A1C1E]")}>
                <span className={cls("absolute top-0.5 w-3 h-3 bg-white rounded-full transition-all shadow", enabled[i] ? "left-4" : "left-0.5")} />
              </button>
              <div>
                <div className="text-[12px] font-bold text-white">{t.name}</div>
                <div className="text-[10px] text-[#8A8080] mt-0.5">{t.desc}</div>
              </div>
              <span className={cls("text-[8px] font-black ml-auto px-1.5 py-0.5 rounded-full flex-shrink-0",
                enabled[i] ? "bg-[#0A2A1A] text-[#4ADF8A]" : "bg-[#2A1C1E] text-[#4A4040]")}>
                {enabled[i] ? "ON" : "OFF"}
              </span>
            </div>
          ))}
        </CardBody>
      </Card>
    </div>
  );
}

/* ── Analytics ── */
function AnalyticsPage({ authHeader }) {
  const [summary, setSummary] = useState(null);
  const [notifStats, setNotifStats] = useState(null);

  useEffect(() => {
    const h = authHeader();
    fetch(`${API}/admin/analytics/summary`, { headers: h }).then(r => r.json()).then(setSummary).catch(() => {});
    fetch(`${API}/admin/analytics/notification-engagement`, { headers: h }).then(r => r.json()).then(setNotifStats).catch(() => {});
  }, []);

  return (
    <div className="grid grid-cols-2 gap-4">
      <Card>
        <CardTop title="📊 Pillar Engagement" />
        <CardBody>
          <BarRow label="Employee" pct={summary?.employee_engagement ?? 91} color="#1A8A4A" />
          <BarRow label="Customer" pct={summary?.customer_engagement ?? 78} color="#C8281E" />
          <BarRow label="Innovator" pct={summary?.innovator_engagement ?? 64} color="#1A4A9A" />
          <BarRow label="Shareholder" pct={summary?.shareholder_engagement ?? 42} color="#D4A84A" />
        </CardBody>
      </Card>
      <Card>
        <CardTop title="📢 EDM Performance" />
        <CardBody>
          <BarRow label="Incentive" pct={94} color="#D4A84A" />
          <BarRow label="TechX" pct={82} color="#1A4A9A" />
          <BarRow label="Learning" pct={76} color="#6A3AB0" />
          <BarRow label="Events" pct={68} color="#0A8A9A" />
        </CardBody>
      </Card>
      <Card>
        <CardTop title="🔔 Notification Open Rates" />
        <CardBody>
          <BarRow label="Birthday" pct={99} color="#6A3AB0" />
          <BarRow label="Incentive" pct={94} color="#D4A84A" />
          <BarRow label="Practice Approved" pct={88} color="#1A8A4A" />
          <BarRow label="New Practice" pct={72} color="#1A4A9A" />
        </CardBody>
      </Card>
      <Card>
        <CardTop title="📋 Publish History" />
        <CardBody className="space-y-2">
          {[
            { v: "v2.18", note: "Updated Customer pillar EDM — Myntra win added", t: "2h ago", by: "Admin" },
            { v: "v2.17", note: "Added Wellbeing Week notification trigger", t: "Yesterday", by: "Admin" },
            { v: "v2.16", note: "New BCG motivational quote added", t: "2d ago", by: "Admin" },
          ].map((h, i) => (
            <div key={i} className="p-2.5 bg-[#201618] rounded-lg">
              <div className="flex items-center gap-2 mb-1">
                <span className="font-['Barlow_Condensed',sans-serif] font-black text-[#E8453A]">{h.v}</span>
                <span className="text-[10px] text-[#8A8080]">{h.t} · by {h.by}</span>
              </div>
              <div className="text-[11px] text-[#C0B8B8]">{h.note}</div>
            </div>
          ))}
        </CardBody>
      </Card>
    </div>
  );
}

/* ═══════════════════════ MAIN SHELL ═══════════════════════ */
export default function AdminConsolePage() {
  const { authHeader, logout } = useAuth();
  const navigate = useNavigate();
  const [page, setPage] = useState("dashboard");
  const [pendingCount, setPendingCount] = useState(0);
  const [toast, setToast] = useState({ msg: "", ok: true });
  const [stats, setStats] = useState({ total: 0, thisWeek: 0, edmSlides: 8, icons: 46 });
  const [pubTime, setPubTime] = useState("just now");
  const toastTimer = useRef(null);

  const showToast = (msg, ok = true) => {
    if (toastTimer.current) clearTimeout(toastTimer.current);
    setToast({ msg, ok });
    toastTimer.current = setTimeout(() => setToast({ msg: "", ok: true }), 3000);
  };

  useEffect(() => {
    const h = authHeader();
    // load stats
    fetch(`${API}/admin/users`, { headers: h }).then(r => r.json()).then(d => {
      const arr = Array.isArray(d) ? d : (d?.items || []);
      setStats(s => ({ ...s, total: arr.length }));
    }).catch(() => {});
    fetch(`${API}/admin/users/pending`, { headers: h }).then(r => r.json()).then(d => {
      setPendingCount(Array.isArray(d) ? d.length : 0);
    }).catch(() => {});
  }, []);

  const NAV = [
    { section: "OVERVIEW" },
    { id: "dashboard", label: "Dashboard", icon: LayoutDashboard },
    { id: "users", label: "User Approvals", icon: Users, badge: pendingCount },
    { section: "CONTENT — HOME" },
    { id: "edm", label: "Home EDM Slides", icon: SlidersHorizontal },
    { id: "quotes", label: "Motivational Quotes", icon: Quote },
    { section: "PILLARS & ICONS" },
    { id: "pillars", label: "Pillar Manager", icon: Columns3 },
    { id: "icons", label: "Icon & App Manager", icon: Grid3X3 },
    { id: "pedm", label: "Pillar EDM Slides", icon: GalleryHorizontal },
    { section: "ENGAGEMENT" },
    { id: "push", label: "Push Notifications", icon: Bell },
    { id: "analytics", label: "Analytics", icon: BarChart3 },
  ];

  const PAGE_TITLES = {
    dashboard: "Dashboard",
    users: "User Approvals",
    edm: "Home EDM Slides",
    quotes: "Motivational Quotes",
    pillars: "Pillar Manager",
    icons: "Icon & App Manager",
    pedm: "Pillar EDM Slides",
    push: "Push Notifications",
    analytics: "Analytics",
  };

  const publish = () => {
    setPubTime(new Date().toLocaleTimeString());
    showToast("✅ All changes published!", true);
  };

  return (
    <div className="flex h-screen bg-[#060404] text-white overflow-hidden" style={{ fontFamily: "'Barlow', sans-serif" }}>
      <Toast msg={toast.msg} ok={toast.ok} />

      {/* ── SIDEBAR ── */}
      <div className="w-[240px] flex-shrink-0 bg-[#0C0808] border-r border-[#2A1C1E] flex flex-col h-full">
        {/* Brand */}
        <div className="px-4 py-4 border-b border-[#2A1C1E]">
          <div className="font-['Barlow_Condensed',sans-serif] font-black text-xl tracking-wider text-[#C8281E]">HITACHI</div>
          <div className="text-[9px] font-bold tracking-widest text-[#4A4040] mt-0.5">⚙️ ADMIN CONSOLE</div>
        </div>

        {/* Nav */}
        <div className="flex-1 overflow-y-auto px-2 py-2">
          {NAV.map((item, i) =>
            item.section ? (
              <NavSection key={i} label={item.section} />
            ) : (
              <NavItem key={item.id} icon={item.icon} label={item.label}
                active={page === item.id} badge={item.badge}
                onClick={() => setPage(item.id)} />
            )
          )}
        </div>

        {/* Publish button */}
        <div className="p-3 border-t border-[#2A1C1E]">
          <button onClick={publish}
            className="w-full bg-[#C8281E] hover:bg-[#9B1A12] text-white font-['Barlow_Condensed',sans-serif] font-black text-sm tracking-wider py-2.5 rounded-xl transition-all flex items-center justify-center gap-2">
            <Zap size={14} />  PUBLISH ALL
          </button>
        </div>

        {/* Links */}
        <div className="px-3 pb-3 space-y-1">
          <Link to="/" className="flex items-center gap-2 text-[11px] text-[#8A8080] hover:text-white transition-colors">
            <ExternalLink size={11} /> Preview App
          </Link>
          <button onClick={() => { logout(); navigate("/login"); }}
            className="flex items-center gap-2 text-[11px] text-[#8A8080] hover:text-[#E8453A] transition-colors">
            <LogOut size={11} /> Sign Out
          </button>
        </div>
      </div>

      {/* ── MAIN ── */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Topbar */}
        <div className="h-[58px] flex items-center justify-between px-6 border-b border-[#2A1C1E] bg-[#0C0808] flex-shrink-0">
          <div className="font-['Barlow_Condensed',sans-serif] font-black text-xl tracking-wide">{PAGE_TITLES[page]}</div>
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <div className="w-1.5 h-1.5 rounded-full bg-[#4ADF8A] animate-pulse" />
              <span className="text-[11px] text-[#8A8080]">All changes saved · Last published <span className="text-[#C0B8B8]">{pubTime}</span></span>
            </div>
            <button onClick={publish}
              className="bg-[#C8281E] hover:bg-[#9B1A12] text-white text-[11px] font-bold px-4 py-1.5 rounded-lg transition-all flex items-center gap-1.5">
              <Zap size={12} /> Publish All Changes
            </button>
          </div>
        </div>

        {/* Content area */}
        <div className="flex-1 overflow-y-auto p-6">
          {page === "dashboard" && <DashboardPage authHeader={authHeader} onNav={setPage} stats={stats} />}
          {page === "users" && <UsersPage authHeader={authHeader} onBadge={setPendingCount} toast={showToast} />}
          {page === "edm" && <HomeEDMPage authHeader={authHeader} toast={showToast} />}
          {page === "quotes" && <QuotesPage authHeader={authHeader} toast={showToast} />}
          {page === "pillars" && <PillarManagerPage authHeader={authHeader} toast={showToast} />}
          {page === "icons" && <IconManagerPage authHeader={authHeader} toast={showToast} />}
          {page === "pedm" && <PillarEDMPage authHeader={authHeader} toast={showToast} />}
          {page === "push" && <PushPage authHeader={authHeader} toast={showToast} />}
          {page === "analytics" && <AnalyticsPage authHeader={authHeader} />}
        </div>
      </div>
    </div>
  );
}
