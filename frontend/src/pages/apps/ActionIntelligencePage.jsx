import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../../contexts/AuthContext";
import {
  Zap, AlertTriangle, CheckCircle2, Users, Calendar,
  Clock, ChevronRight, ArrowUpRight, LogOut, Building2,
  Shield, Bell, BarChart2, UserCheck
} from "lucide-react";

// ── Static mock data ──────────────────────────────────────────────────────────
const kpiData = [
  { label: "OPEN ACTIONS",     value: 6, sub: "2 overdue",           subColor: "#CC0000" },
  { label: "CRITICAL PRIORITY",value: 2, sub: "Immediate attention",  subColor: "#F97316" },
  { label: "MY OPEN ACTIONS",  value: 0, sub: "Assigned to you",      subColor: "#16A34A" },
  { label: "TOTAL MEETINGS",   value: 2, sub: "0 closed",             subColor: "#64748B" },
];

const heatmap = [
  { level:"Reminder",  count:2, overdue:"≥3d",  desc:"Auto-reminder to owner via email",  bg:"#E0EEFF", border:"#BFDBFE", numColor:"#2563EB", textColor:"#2563EB" },
  { level:"Manager",   count:0, overdue:"≥7d",  desc:"Reporting manager notified",         bg:"#FFFBEB", border:"#FDE68A", numColor:"#D97706", textColor:"#D97706" },
  { level:"Escalated", count:0, overdue:"≥14d", desc:"Skip-level + stakeholder alert",     bg:"#FFF3E0", border:"#FDBA74", numColor:"#EA580C", textColor:"#EA580C" },
  { level:"Critical",  count:0, overdue:"≥21d", desc:"CEO / Leadership board alert",       bg:"#FFF1F0", border:"#FECACA", numColor:"#DC2626", textColor:"#DC2626" },
];

const meetings = [
  { id:1, title:"GCC Transformation Steering", date:"18 Apr 2026", chair:"Harsh Singla",  overdueActions:1, completedActions:0, totalActions:2 },
  { id:2, title:"FY26-27 Q1 Strategy Review",  date:"16 Apr 2026", chair:"Raj Singhal",   overdueActions:1, completedActions:0, totalActions:4 },
];

const NAV_TABS = [
  { label:"Dashboard",  badge:null },
  { label:"Meetings",   badge:null },
  { label:"Actions",    badge:6,   badgeColor:"#CC0000" },
  { label:"Ageing",     badge:2,   badgeColor:"#D97706" },
  { label:"My Team",    badge:null },
  { label:"Admin",      badge:null },
];

const TICKER_TEXT = "VISION: Services-First Business   \u00a0|\u00a0   MISSION: Power Future with AI   \u00a0|\u00a0   ART: Agility · Responsibility · Transparency   \u00a0|\u00a0   ONE HITACHI: Built for Services · Powered by AI   \u00a0\u00a0\u00a0\u00a0\u00a0";

// ── Helpers ───────────────────────────────────────────────────────────────────
const getFormattedDate = () =>
  new Date().toLocaleDateString("en-GB", { weekday:"long", day:"numeric", month:"long", year:"numeric" });

const getInitials = (name) =>
  name ? name.split(" ").slice(0,2).map(p => p[0].toUpperCase()).join("") : "U";

// ── Page Component ────────────────────────────────────────────────────────────
export default function ActionIntelligencePage() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState("Dashboard");
  const [selectedHeatmap, setSelectedHeatmap] = useState(null);

  const firstName = user?.name?.split(" ")[0] || "User";
  const initials  = getInitials(user?.name || "");

  const doLogout = () => { logout(); navigate("/login"); };

  return (
    <div style={{ background:"#EBEBEB", minHeight:"100vh", fontFamily:"'IBM Plex Sans', sans-serif" }}>

      {/* Ticker keyframes */}
      <style>{`
        @keyframes ticker-move {
          0%   { transform: translateX(0); }
          100% { transform: translateX(-50%); }
        }
        .ticker-inner { animation: ticker-move 30s linear infinite; white-space: nowrap; display: inline-block; }
        .kpi-card { border-top: 3px solid #CC0000; background:#fff; border-radius:6px; padding:24px 20px; }
        .dark-panel { background:#0A0A0A; border-radius:8px; overflow:hidden; }
        .dark-panel-header { background:#0A0A0A; padding:16px 20px; border-left:4px solid #CC0000; display:flex; align-items:center; gap:10px; }
      `}</style>

      {/* ── TOP NAV ──────────────────────────────────────────────────────── */}
      <nav style={{ background:"#fff", borderBottom:"1px solid #E5E7EB" }}>
        <div style={{ maxWidth:"1280px", margin:"0 auto", padding:"0 24px" }}
          className="flex items-center justify-between">
          {/* Logo */}
          <div className="flex items-center gap-3 py-3">
            <span style={{ color:"#CC0000", fontWeight:900, fontSize:"20px", fontFamily:"'Arial Black', Arial, sans-serif", letterSpacing:"-0.5px" }}>
              HITACHI
            </span>
            <div style={{ width:"1px", height:"20px", background:"#E5E7EB" }} />
            <span style={{ fontSize:"11px", fontWeight:700, letterSpacing:"0.1em", color:"#374151" }}>
              ACTION INTELLIGENCE PLATFORM
            </span>
          </div>

          {/* Nav tabs */}
          <div className="flex items-center">
            {NAV_TABS.map(t => (
              <button key={t.label} data-testid={`action-tab-${t.label.toLowerCase()}`}
                onClick={() => setActiveTab(t.label)}
                className="flex items-center gap-1.5 px-4 py-3.5 text-xs font-bold tracking-wide transition-colors relative"
                style={{ color: activeTab === t.label ? "#fff" : "#374151",
                         background: activeTab === t.label ? "#CC0000" : "transparent" }}>
                {t.label}
                {t.badge !== null && (
                  <span style={{ background: activeTab === t.label ? "rgba(255,255,255,0.3)" : t.badgeColor,
                                 color:"#fff", fontSize:"10px", fontWeight:700, borderRadius:"10px", padding:"1px 6px", minWidth:"18px", textAlign:"center" }}>
                    {t.badge}
                  </span>
                )}
              </button>
            ))}
          </div>

          {/* User + actions */}
          <div className="flex items-center gap-3">
            <button data-testid="back-to-portal-action-btn" onClick={() => navigate("/")}
              className="flex items-center gap-1 text-xs text-[#64748B] hover:text-[#CC0000] transition-colors font-medium">
              <Building2 size={13} /><span>Portal</span>
            </button>
            <div className="flex items-center gap-2 px-3 py-1.5 rounded border border-[#E5E7EB] bg-[#F9FAFB] cursor-pointer hover:bg-[#F1F5F9] transition-colors">
              <span style={{ fontSize:"12px", color:"#374151", fontWeight:500 }}>{user?.name || "User"}</span>
              <ChevronRight size={12} style={{ color:"#94A3B8" }} />
            </div>
            <div style={{ width:"34px", height:"34px", background:"#CC0000", borderRadius:"50%",
                          display:"flex", alignItems:"center", justifyContent:"center" }}>
              <span style={{ color:"#fff", fontSize:"11px", fontWeight:700 }}>{initials}</span>
            </div>
            <button data-testid="action-logout-btn" onClick={doLogout}
              className="text-[#94A3B8] hover:text-[#CC0000] transition-colors">
              <LogOut size={16} />
            </button>
          </div>
        </div>
      </nav>

      {/* ── MARQUEE TICKER ───────────────────────────────────────────────── */}
      <div style={{ background:"#CC0000", overflow:"hidden", height:"32px", display:"flex", alignItems:"center" }}>
        <div className="ticker-inner">
          {[1,2].map(i => (
            <span key={i} style={{ fontSize:"11px", fontWeight:600, color:"#fff", letterSpacing:"0.05em", marginRight:"80px" }}>
              <strong>VISION:</strong> Services-First Business
              &nbsp;&nbsp;|&nbsp;&nbsp;
              <strong>MISSION:</strong> Power Future with AI
              &nbsp;&nbsp;|&nbsp;&nbsp;
              <strong>ART:</strong> Agility · Responsibility · Transparency
              &nbsp;&nbsp;|&nbsp;&nbsp;
              <strong>ONE HITACHI:</strong> Built for Services · Powered by AI
              &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
            </span>
          ))}
        </div>
      </div>

      {activeTab !== "Dashboard" ? (
        <div style={{ maxWidth:"1280px", margin:"0 auto", padding:"60px 24px" }} className="flex items-center justify-center">
          <div className="text-center">
            <div className="w-14 h-14 rounded-full bg-white border border-[#E5E7EB] flex items-center justify-center mx-auto mb-4">
              <Zap size={24} style={{ color:"#CC0000" }} />
            </div>
            <h3 className="text-lg font-bold text-[#0F172A] mb-1">{activeTab}</h3>
            <p className="text-[#64748B] text-sm">This section is coming soon. Please check back later.</p>
          </div>
        </div>
      ) : (
        <main style={{ maxWidth:"1280px", margin:"0 auto", padding:"28px 24px 48px" }}>

          {/* Page title row */}
          <div className="flex items-start justify-between mb-6">
            <div>
              <h1 style={{ fontSize:"28px", fontWeight:700, color:"#0F172A", marginBottom:"4px", fontFamily:"Outfit, sans-serif" }}>
                Action Intelligence Dashboard
              </h1>
              <p style={{ fontSize:"13px", color:"#64748B" }}>
                Welcome back, {user?.name || "User"} · {getFormattedDate()}
              </p>
            </div>
            <div className="flex items-center gap-3">
              <div style={{ background:"#FFF1F0", border:"1px solid #FECACA", borderRadius:"6px",
                            padding:"6px 14px", display:"flex", alignItems:"center", gap:"6px" }}>
                <AlertTriangle size={13} style={{ color:"#CC0000" }} />
                <span style={{ fontSize:"12px", fontWeight:700, color:"#CC0000" }}>2 Overdue</span>
              </div>
              <div style={{ background:"#F0FDF4", border:"1px solid #BBF7D0", borderRadius:"6px",
                            padding:"6px 14px", display:"flex", alignItems:"center", gap:"6px" }}>
                <CheckCircle2 size={13} style={{ color:"#16A34A" }} />
                <span style={{ fontSize:"12px", fontWeight:700, color:"#16A34A" }}>0 Closed Today</span>
              </div>
            </div>
          </div>

          {/* ── 4 KPI CARDS ────────────────────────────────────────────── */}
          <div style={{ display:"grid", gridTemplateColumns:"repeat(4, 1fr)", gap:"16px", marginBottom:"20px" }}>
            {kpiData.map((k, i) => (
              <div key={i} data-testid={`action-kpi-${i}`} className="kpi-card shadow-sm hover:shadow-md transition-shadow">
                <div style={{ fontSize:"52px", fontWeight:900, lineHeight:1, color:"#0F172A", fontFamily:"Outfit, sans-serif", marginBottom:"8px" }}>
                  {k.value}
                </div>
                <div style={{ fontSize:"11px", fontWeight:700, letterSpacing:"0.1em", color:"#374151", marginBottom:"6px" }}>
                  {k.label}
                </div>
                <div style={{ fontSize:"12px", fontWeight:600, color:k.subColor }}>{k.sub}</div>
              </div>
            ))}
          </div>

          {/* ── ESCALATION HEATMAP ─────────────────────────────────────── */}
          <div className="dark-panel shadow-md mb-5" data-testid="escalation-heatmap">
            <div className="dark-panel-header">
              <div style={{ background:"#CC0000", borderRadius:"4px", padding:"4px 6px" }}>
                <Zap size={14} style={{ color:"#fff" }} />
              </div>
              <div>
                <div style={{ fontSize:"12px", fontWeight:700, letterSpacing:"0.12em", color:"#fff" }}>ESCALATION HEATMAP</div>
                <div style={{ fontSize:"11px", color:"#4B5563", marginTop:"1px" }}>
                  BCG-style real-time risk distribution — click any level to filter
                </div>
              </div>
            </div>
            <div style={{ padding:"20px", display:"grid", gridTemplateColumns:"repeat(4,1fr)", gap:"16px" }}>
              {heatmap.map((h, i) => (
                <button key={i} data-testid={`heatmap-${h.level.toLowerCase()}`}
                  onClick={() => setSelectedHeatmap(selectedHeatmap === h.level ? null : h.level)}
                  style={{ background:h.bg, border:`2px solid ${selectedHeatmap === h.level ? h.numColor : h.border}`,
                           borderRadius:"10px", padding:"28px 20px", textAlign:"center", cursor:"pointer",
                           transition:"all 0.2s", outline:"none" }}>
                  <div style={{ fontSize:"48px", fontWeight:900, color:h.numColor, lineHeight:1, marginBottom:"8px", fontFamily:"Outfit, sans-serif" }}>
                    {h.count}
                  </div>
                  <div style={{ fontSize:"14px", fontWeight:700, color:h.textColor, marginBottom:"6px" }}>{h.level}</div>
                  <div style={{ fontSize:"11px", color:"#6B7280", marginBottom:"4px" }}>{h.overdue} overdue</div>
                  <div style={{ fontSize:"10px", color:"#9CA3AF" }}>{h.desc}</div>
                </button>
              ))}
            </div>
          </div>

          {/* ── MY ACTIONS + RECENT MEETINGS ──────────────────────────── */}
          <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:"16px" }}>

            {/* MY ACTIONS */}
            <div className="dark-panel shadow-md" data-testid="my-actions-panel">
              <div className="dark-panel-header">
                <div style={{ background:"#CC0000", borderRadius:"4px", width:"28px", height:"28px",
                              display:"flex", alignItems:"center", justifyContent:"center" }}>
                  <span style={{ color:"#fff", fontSize:"13px", fontWeight:700 }}>0</span>
                </div>
                <div>
                  <div style={{ fontSize:"12px", fontWeight:700, letterSpacing:"0.12em", color:"#fff" }}>MY ACTIONS</div>
                  <div style={{ fontSize:"11px", color:"#4B5563" }}>Click any action to open · Update status</div>
                </div>
              </div>
              <div style={{ padding:"48px 24px", textAlign:"center" }}>
                <div style={{ fontSize:"28px", marginBottom:"8px" }}>🎉</div>
                <p style={{ fontSize:"14px", fontWeight:600, color:"#6B7280" }}>All clear — no open actions!</p>
              </div>
            </div>

            {/* RECENT MEETINGS */}
            <div className="dark-panel shadow-md" data-testid="recent-meetings-panel">
              <div className="dark-panel-header">
                <div style={{ background:"#CC0000", borderRadius:"4px", width:"28px", height:"28px",
                              display:"flex", alignItems:"center", justifyContent:"center" }}>
                  <Calendar size={14} style={{ color:"#fff" }} />
                </div>
                <div>
                  <div style={{ fontSize:"12px", fontWeight:700, letterSpacing:"0.12em", color:"#fff" }}>RECENT MEETINGS</div>
                  <div style={{ fontSize:"11px", color:"#4B5563" }}>Click any meeting to open consolidated view</div>
                </div>
              </div>
              <div style={{ padding:"0" }}>
                {meetings.map((m, i) => (
                  <div key={m.id} data-testid={`meeting-row-${m.id}`}
                    style={{ padding:"18px 20px", borderBottom: i < meetings.length-1 ? "1px solid #1E1E1E" : "none",
                             display:"flex", alignItems:"center", justifyContent:"space-between",
                             cursor:"pointer", transition:"background 0.15s" }}
                    onMouseEnter={e => e.currentTarget.style.background = "#161616"}
                    onMouseLeave={e => e.currentTarget.style.background = "transparent"}>
                    <div style={{ flex:1, minWidth:0 }}>
                      <div style={{ display:"flex", alignItems:"center", gap:"6px", marginBottom:"4px" }}>
                        <span style={{ fontSize:"14px", fontWeight:600, color:"#CC0000" }}>
                          {m.title}
                        </span>
                        <ArrowUpRight size={13} style={{ color:"#CC0000", flexShrink:0 }} />
                      </div>
                      <div style={{ fontSize:"12px", color:"#4B5563", marginBottom:"4px" }}>
                        {m.date} · Chair: {m.chair}
                      </div>
                      {m.overdueActions > 0 && (
                        <div style={{ display:"flex", alignItems:"center", gap:"4px" }}>
                          <Zap size={11} style={{ color:"#F97316" }} />
                          <span style={{ fontSize:"11px", fontWeight:600, color:"#F97316" }}>
                            {m.overdueActions} action(s) overdue
                          </span>
                        </div>
                      )}
                    </div>
                    <div style={{ textAlign:"right", flexShrink:0, marginLeft:"16px" }}>
                      <div style={{ fontSize:"20px", fontWeight:700, color:"#CC0000", lineHeight:1, fontFamily:"Outfit, sans-serif" }}>
                        {Math.round((m.completedActions / m.totalActions) * 100)}%
                      </div>
                      <div style={{ fontSize:"11px", color:"#4B5563", marginTop:"2px" }}>
                        {m.completedActions}/{m.totalActions}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

        </main>
      )}

      {/* ── FOOTER ──────────────────────────────────────────────────────── */}
      <footer style={{ background:"#0A0A0A", borderTop:"3px solid #CC0000", padding:"16px 24px" }}>
        <div style={{ maxWidth:"1280px", margin:"0 auto", display:"flex", alignItems:"center", justifyContent:"space-between" }}>
          <div style={{ display:"flex", alignItems:"center", gap:"8px" }}>
            <span style={{ color:"#CC0000", fontWeight:900, fontSize:"14px", fontFamily:"'Arial Black', Arial, sans-serif" }}>HITACHI</span>
            <span style={{ color:"#374151", fontSize:"11px" }}>Action Intelligence Platform · FY26-27 · Confidential</span>
          </div>
          <div className="flex items-center gap-4">
            {["Cloud","Cybersecurity","Data Centre","Observability","DB Modernisation"].map(s => (
              <span key={s} style={{ fontSize:"11px", color:"#374151", cursor:"pointer" }} className="hover:text-[#CC0000] transition-colors">{s}</span>
            ))}
          </div>
          <span style={{ fontSize:"11px", color:"#374151" }}>©Hitachi Systems India Pvt. Ltd. 2026</span>
        </div>
      </footer>
    </div>
  );
}
