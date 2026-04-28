import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useAuth } from "../../contexts/AuthContext";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, BarChart, Bar, Cell
} from "recharts";
import {
  ArrowLeft, Building2, LogOut, Settings, TrendingUp,
  TrendingDown, Minus, AlertTriangle, CheckCircle,
  Zap, Radio, Send, Plus, ChevronRight, Users,
  MessageSquare, Star
} from "lucide-react";

// ── Mock Data ────────────────────────────────────────────────────────────────
const trendData = [
  { month: "May",  nps: 48, csat: 79 },
  { month: "Jun",  nps: 52, csat: 81 },
  { month: "Jul",  nps: 55, csat: 83 },
  { month: "Aug",  nps: 53, csat: 82 },
  { month: "Sep",  nps: 57, csat: 84 },
  { month: "Oct",  nps: 58, csat: 85 },
  { month: "Nov",  nps: 56, csat: 84 },
  { month: "Dec",  nps: 59, csat: 86 },
  { month: "Jan",  nps: 60, csat: 86 },
  { month: "Feb",  nps: 61, csat: 87 },
  { month: "Mar",  nps: 62, csat: 87 },
];

const csatData = [
  { rating: "5★", count: 82, pct: 58 },
  { rating: "4★", count: 38, pct: 27 },
  { rating: "3★", count: 12, pct: 8  },
  { rating: "2★", count: 7,  pct: 5  },
  { rating: "1★", count: 3,  pct: 2  },
];

const painPoints = [
  { label: "Response Time",      sub: "Mentioned 28 times · Cybersecurity tickets", pct: 34, color: "#EF4444" },
  { label: "Reporting Clarity",  sub: "Mentioned 19 times · Cloud practice",         pct: 23, color: "#F97316" },
  { label: "Escalation Process", sub: "Mentioned 14 times · Data Centre",            pct: 17, color: "#F59E0B" },
  { label: "Communication Gaps", sub: "Mentioned 11 times · All practices",          pct: 13, color: "#EAB308" },
  { label: "Documentation",      sub: "Mentioned 9 times · Observability",           pct: 11, color: "#84CC16" },
];

const doingWell = [
  { count: 41, badge: "TOP MENTION", quote: '"The HSI team is highly knowledgeable and goes beyond scope to solve our problems proactively."', tag: "Technical expertise · Cybersecurity & Cloud" },
  { count: 29, badge: "29 MENTIONS",  quote: '"Implementation was smooth — no surprises on timeline or cost. Exactly what was promised."',      tag: "Delivery reliability · Data Centre" },
  { count: 24, badge: "24 MENTIONS",  quote: '"The AIOps dashboard has transformed how we manage incidents. Night and day difference."',         tag: "Innovation impact · Observability" },
  { count: 18, badge: "18 MENTIONS",  quote: '"Senior team is genuinely accessible and accountable. Rare in this industry."',                    tag: "Relationship quality · All practices" },
];

const accounts = [
  { name: "Reliance Petro",  initials: "RP", nps: 12  },
  { name: "Axis Bank",       initials: "AB", nps: 38  },
  { name: "L&T Constructs",  initials: "LT", nps: 41  },
  { name: "HCL Unistore",    initials: "HC", nps: 72  },
  { name: "Tata Motors",     initials: "TM", nps: 68  },
  { name: "SBI Life",        initials: "SB", nps: 81  },
];

const verbatims = [
  { type: "PROMOTER",  score: 10, color: "#22C55E", text: '"HSI\'s Cybersecurity team didn\'t just implement zero-trust — they educated our internal team and built our capability. The engagement was transformational, not just transactional."' },
  { type: "PROMOTER",  score: 9,  color: "#22C55E", text: '"Cloud migration was on time, under budget, and the FinOps controls they put in have already saved us ₹1.2Cr in the first quarter. Hard to argue with that ROI."' },
  { type: "DETRACTOR", score: 4,  color: "#EF4444", text: '"The solution is good but the ticket response times during the first two weeks post-go-live were frustrating. We expected better support SLAs given what we\'re paying."' },
];

const NAV_TABS = ["DASHBOARD","SURVEY BUILDER","EMAIL CAMPAIGNS","ACCOUNTS","AI INSIGHTS","WORKFLOW"];

const npsColor = (v) => v >= 50 ? "#22C55E" : v >= 30 ? "#F59E0B" : "#EF4444";
const csatBarColor = (i) => ["#22C55E","#84CC16","#F59E0B","#F97316","#EF4444"][i];

// ── NPS Gauge (light version) ─────────────────────────────────────────────────
const NPSGauge = ({ score = 62, detractors = 12, passives = 14, promoters = 74 }) => {
  const cx = 120, cy = 105, r = 88, sw = 13;
  const pt = (deg) => ({
    x: cx + r * Math.cos((deg * Math.PI) / 180),
    y: cy - r * Math.sin((deg * Math.PI) / 180),
  });
  const detEnd  = 180 - detractors / 100 * 180;
  const pasEnd  = detEnd - passives / 100 * 180;
  const left    = pt(180), detEndPt = pt(detEnd), pasEndPt = pt(pasEnd), right = pt(0);
  const npsAngle = 180 - (score + 100) / 200 * 180;
  const needle  = pt(npsAngle);

  return (
    <svg viewBox="0 0 240 125" className="w-full max-w-[260px] mx-auto">
      {/* Track */}
      <path d={`M ${left.x} ${left.y} A ${r} ${r} 0 0 1 ${right.x} ${right.y}`}
        fill="none" stroke="#E2E8F0" strokeWidth={sw} strokeLinecap="round" />
      {/* Detractors */}
      <path d={`M ${left.x} ${left.y} A ${r} ${r} 0 0 1 ${detEndPt.x} ${detEndPt.y}`}
        fill="none" stroke="#EF4444" strokeWidth={sw} />
      {/* Passives */}
      <path d={`M ${detEndPt.x} ${detEndPt.y} A ${r} ${r} 0 0 1 ${pasEndPt.x} ${pasEndPt.y}`}
        fill="none" stroke="#F59E0B" strokeWidth={sw} />
      {/* Promoters */}
      <path d={`M ${pasEndPt.x} ${pasEndPt.y} A ${r} ${r} 0 0 1 ${right.x} ${right.y}`}
        fill="none" stroke="#22C55E" strokeWidth={sw} />
      {/* Needle dot */}
      <circle cx={needle.x} cy={needle.y} r="8" fill="white" stroke="#94A3B8" strokeWidth="2" />
      {/* Score */}
      <text x={cx} y={cy - 4} textAnchor="middle" fill="#0F172A" fontSize="30" fontWeight="bold" fontFamily="Outfit">
        {score > 0 ? `+${score}` : score}
      </text>
      <text x={cx} y={cy + 14} textAnchor="middle" fill="#22C55E" fontSize="8" letterSpacing="2" fontWeight="600">
        WORLD-CLASS NPS
      </text>
      <text x="18"  y={cy + 12} fill="#EF4444" fontSize="8" textAnchor="middle">{detractors}%</text>
      <text x="222" y={cy + 12} fill="#22C55E" fontSize="8" textAnchor="middle">{promoters}%</text>
    </svg>
  );
};

// ── Custom Tooltip (light) ────────────────────────────────────────────────────
const ChartTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-white border border-[#E2E8F0] rounded-lg px-3 py-2 text-xs shadow-lg">
      <p className="text-[#64748B] mb-1 font-medium">{label}</p>
      {payload.map(p => (
        <p key={p.name} style={{ color: p.color }} className="font-semibold">
          {p.name === "nps" ? "NPS" : "CSAT"}: {p.name === "nps" ? `+${p.value}` : `${p.value}%`}
        </p>
      ))}
    </div>
  );
};

// ── Main Page ─────────────────────────────────────────────────────────────────
export default function NPSCsatPage() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState("DASHBOARD");

  const doLogout = () => { logout(); navigate("/login"); };

  return (
    <div className="min-h-screen bg-[#F1F5F9]" style={{ fontFamily: "'IBM Plex Sans', sans-serif" }}>

      {/* ── TOP NAV ──────────────────────────────────────────────────────── */}
      <nav className="bg-white border-b border-[#E2E8F0] shadow-sm">
        <div className="max-w-screen-2xl mx-auto px-6 py-0 flex items-center justify-between">
          {/* Logo */}
          <div className="flex items-center gap-3 py-3">
            <div className="w-7 h-7 bg-[#CC0000] rounded flex items-center justify-center flex-shrink-0">
              <Building2 size={14} className="text-white" />
            </div>
            <div>
              <div className="text-[#0F172A] text-[11px] font-bold tracking-[0.15em]">HITACHI SYSTEMS INDIA</div>
              <div className="text-[#CC0000] text-[9px] tracking-[0.2em] font-semibold">VOC INTELLIGENCE PLATFORM</div>
            </div>
          </div>

          {/* Nav tabs */}
          <div className="flex items-center gap-1">
            {NAV_TABS.map(tab => (
              <button key={tab} data-testid={`nav-tab-${tab.toLowerCase().replace(/\s/g,'-')}`}
                onClick={() => setActiveTab(tab)}
                className="px-4 py-3.5 text-[11px] font-bold tracking-wider transition-colors relative"
                style={{ color: activeTab === tab ? "#0F172A" : "#64748B" }}>
                {tab}
                {activeTab === tab && (
                  <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-[#CC0000]" />
                )}
              </button>
            ))}
          </div>

          {/* Right actions */}
          <div className="flex items-center gap-3">
            <button data-testid="back-to-portal-btn" onClick={() => navigate("/")}
              className="flex items-center gap-1.5 text-[#64748B] hover:text-[#0F172A] text-xs transition-colors py-3">
              <ArrowLeft size={13} /><span>Portal</span>
            </button>
            <div className="flex items-center gap-1.5 text-[11px] font-bold tracking-wider text-emerald-600">
              <div className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
              LIVE
            </div>
            <button data-testid="send-survey-btn"
              className="flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-bold tracking-wider text-white bg-[#CC0000] hover:bg-[#AA0000] transition-colors">
              <Send size={12} />SEND SURVEY
            </button>
            <button data-testid="logout-nps-btn" onClick={doLogout}
              className="text-[#64748B] hover:text-[#0F172A] py-3 transition-colors">
              <LogOut size={15} />
            </button>
          </div>
        </div>
      </nav>

      {activeTab !== "DASHBOARD" ? (
        <div className="flex items-center justify-center h-96">
          <div className="text-center">
            <div className="w-16 h-16 rounded-2xl bg-white border border-[#E2E8F0] shadow-sm flex items-center justify-center mx-auto mb-4">
              <Zap size={28} className="text-[#CC0000]" />
            </div>
            <h3 className="text-lg font-bold text-[#0F172A] mb-1">{activeTab}</h3>
            <p className="text-[#64748B] text-sm">This section is coming soon. Please check back later.</p>
          </div>
        </div>
      ) : (
        <main className="max-w-screen-2xl mx-auto px-6 py-6 space-y-5">

          {/* ── PAGE HEADER ────────────────────────────────────────────── */}
          <div className="flex items-start justify-between">
            <div>
              <div className="flex items-center gap-3 mb-2">
                <span className="text-[10px] font-bold tracking-[0.2em] px-3 py-1 rounded-full border border-violet-200 bg-violet-50 text-violet-700">
                  Q2 2026 · VOICE OF CUSTOMER INTELLIGENCE
                </span>
              </div>
              <h1 className="text-4xl font-bold text-[#0F172A] leading-tight font-['Outfit']">
                Customer Experience<br />
                <span className="text-[#CC0000]">Command Centre</span>
              </h1>
              <p className="text-[#64748B] text-sm mt-2 max-w-xl">
                Real-time CSAT & NPS intelligence across all HSI accounts. McKinsey-grade analytics. BCG-structured insights. Bain results-delivery framework.
              </p>
              {/* Quick stats strip */}
              <div className="flex items-center gap-5 mt-3">
                {[["142", "Responses This Month"], ["38", "Active Accounts"], ["0", "Campaigns Running"], ["4 min ago", "Last sync"]].map(([v, l]) => (
                  <div key={l} className="flex items-center gap-1.5">
                    <span className="text-[#0F172A] font-semibold text-sm">{v}</span>
                    <span className="text-[#64748B] text-xs">{l}</span>
                  </div>
                ))}
              </div>
            </div>
            <div className="flex items-center gap-3 flex-shrink-0">
              <button data-testid="new-campaign-btn"
                className="flex items-center gap-2 px-4 py-2.5 rounded-lg text-xs font-bold tracking-wider border border-[#E2E8F0] text-[#64748B] bg-white hover:border-[#CC0000]/30 hover:text-[#0F172A] transition-colors">
                <Plus size={14} />NEW CAMPAIGN
              </button>
              <button data-testid="ai-insights-btn"
                className="flex items-center gap-2 px-4 py-2.5 rounded-lg text-xs font-bold tracking-wider bg-violet-50 text-violet-700 border border-violet-200 hover:bg-violet-100 transition-colors">
                <Zap size={14} />AI INSIGHTS <ChevronRight size={12} />
              </button>
            </div>
          </div>

          {/* ── 5 KPI CARDS ──────────────────────────────────────────────── */}
          <div className="grid grid-cols-5 gap-4">
            {[
              { label: "NPS SCORE",     value: "+62", sub: "▲ 8pts vs last quarter", bench: "World-class ≥ +50",    color: "#22C55E", Icon: TrendingUp },
              { label: "CSAT SCORE",    value: "87%", sub: "▲ 3.2% MoM",             bench: "Target ≥ 85%",         color: "#22C55E", Icon: Star },
              { label: "RESPONSE RATE", value: "68%", sub: "▲ 12% vs benchmark",     bench: "Industry avg: 54%",    color: "#3B82F6", Icon: Users },
              { label: "PROMOTERS",     value: "74%", sub: "▲ 5pts vs Q1",           bench: "Detractors: 12%",      color: "#F59E0B", Icon: TrendingUp },
              { label: "CES SCORE",     value: "4.3", sub: "→ Stable",               bench: "Customer Effort (1-5)", color: "#94A3B8", Icon: Minus },
            ].map((k, i) => (
              <div key={k.label} data-testid={`kpi-card-${i}`}
                className="bg-white rounded-xl p-5 border border-[#E2E8F0] shadow-sm hover:shadow-md transition-shadow">
                <div className="flex items-start justify-between mb-3">
                  <span className="text-[10px] font-bold tracking-[0.15em] text-[#64748B]">{k.label}</span>
                  <k.Icon size={16} style={{ color: k.color }} />
                </div>
                <div className="text-4xl font-bold mb-1 font-['Outfit']" style={{ color: k.color }}>{k.value}</div>
                <div className="text-[11px] mb-0.5 font-semibold" style={{ color: k.color }}>{k.sub}</div>
                <div className="text-[10px] text-[#94A3B8]">{k.bench}</div>
              </div>
            ))}
          </div>

          {/* ── CHARTS ROW ────────────────────────────────────────────────── */}
          <div className="grid grid-cols-12 gap-4">
            {/* Trend Chart */}
            <div className="col-span-6 bg-white rounded-xl p-5 border border-[#E2E8F0] shadow-sm">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <div className="text-[11px] font-bold tracking-widest text-[#64748B] uppercase mb-0.5">Trend</div>
                  <h3 className="text-sm font-bold text-[#0F172A]">NPS & CSAT Trend — Last 12 Months</h3>
                </div>
                <button className="text-[10px] font-bold tracking-wider px-3 py-1.5 rounded-lg border border-[#E2E8F0] text-[#64748B] bg-[#F8FAFC] hover:border-[#CC0000]/30 transition-colors">
                  QUARTERLY VIEW
                </button>
              </div>
              <div className="flex items-center gap-5 mb-4">
                {[{ color:"#CC0000", label:"NPS Score" }, { color:"#22C55E", label:"CSAT %" }].map(l => (
                  <div key={l.label} className="flex items-center gap-2 text-xs text-[#64748B]">
                    <div className="w-6 h-0.5 rounded" style={{ background: l.color }} />
                    {l.label}
                  </div>
                ))}
              </div>
              <ResponsiveContainer width="100%" height={200}>
                <LineChart data={trendData} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
                  <CartesianGrid stroke="#E2E8F0" strokeDasharray="3 3" />
                  <XAxis dataKey="month" tick={{ fill: "#64748B", fontSize: 11 }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fill: "#64748B", fontSize: 11 }} axisLine={false} tickLine={false} />
                  <Tooltip content={<ChartTooltip />} />
                  <Line type="monotone" dataKey="nps"  stroke="#CC0000" strokeWidth={2.5} dot={false} name="nps" />
                  <Line type="monotone" dataKey="csat" stroke="#22C55E" strokeWidth={2.5} dot={false} name="csat" />
                </LineChart>
              </ResponsiveContainer>
            </div>

            {/* NPS Gauge */}
            <div className="col-span-3 bg-white rounded-xl p-5 border border-[#E2E8F0] shadow-sm flex flex-col">
              <div className="mb-3">
                <div className="text-[10px] font-bold tracking-widest text-[#64748B] uppercase mb-0.5">Gauge</div>
                <h3 className="text-sm font-bold text-[#0F172A]">Net Promoter Score</h3>
                <span className="text-[10px] text-[#64748B]">Q2 2026</span>
              </div>
              <div className="flex-1 flex flex-col items-center justify-center">
                <NPSGauge />
                <div className="flex items-center justify-center gap-4 mt-3">
                  {[{ color:"#EF4444", pct:"12%", label:"Detractors" }, { color:"#F59E0B", pct:"14%", label:"Passives" }, { color:"#22C55E", pct:"74%", label:"Promoters" }].map(s => (
                    <div key={s.label} className="flex items-center gap-1.5 text-[10px]">
                      <div className="w-2 h-2 rounded-full" style={{ background: s.color }} />
                      <span style={{ color: s.color }}>{s.pct}</span>
                      <span className="text-[#64748B]">{s.label}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* CSAT Distribution */}
            <div className="col-span-3 bg-white rounded-xl p-5 border border-[#E2E8F0] shadow-sm">
              <div className="mb-4">
                <div className="text-[10px] font-bold tracking-widest text-[#64748B] uppercase mb-0.5">Distribution</div>
                <h3 className="text-sm font-bold text-[#0F172A]">CSAT Distribution</h3>
                <span className="text-[10px] text-[#64748B]">142 RESPONSES</span>
              </div>
              <div className="space-y-3">
                {csatData.map((d, i) => (
                  <div key={d.rating} className="flex items-center gap-3">
                    <span className="text-xs w-7 text-right flex-shrink-0 font-semibold" style={{ color: csatBarColor(i) }}>{d.rating}</span>
                    <div className="flex-1 h-2 rounded-full bg-[#F1F5F9]">
                      <div className="h-full rounded-full transition-all" style={{ width: `${d.pct}%`, background: csatBarColor(i) }} />
                    </div>
                    <span className="text-xs text-[#64748B] w-6 flex-shrink-0">{d.count}</span>
                  </div>
                ))}
              </div>
              <div className="mt-4 pt-3 border-t border-[#E2E8F0] flex items-center justify-between">
                <span className="text-[11px] text-[#64748B]">Avg: <strong className="text-[#0F172A]">4.4 / 5.0</strong></span>
                <span className="text-[11px] font-bold text-emerald-600">CSAT: 87%</span>
              </div>
            </div>
          </div>

          {/* ── INSIGHTS ROW ─────────────────────────────────────────────── */}
          <div className="grid grid-cols-3 gap-4">
            {/* Top Pain Points */}
            <div className="bg-white rounded-xl p-5 border border-[#E2E8F0] shadow-sm">
              <div className="flex items-start justify-between mb-4">
                <div>
                  <div className="text-[10px] font-bold tracking-widest text-[#64748B] uppercase mb-0.5">Analysis</div>
                  <h3 className="text-sm font-bold text-[#0F172A]">Top Pain Points</h3>
                </div>
                <span className="text-[10px] font-bold px-2 py-1 rounded-lg bg-red-50 text-red-600">
                  NEEDS ACTION
                </span>
              </div>
              <div className="space-y-4">
                {painPoints.map((p) => (
                  <div key={p.label}>
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-sm font-semibold text-[#0F172A]">{p.label}</span>
                      <span className="text-xs font-bold" style={{ color: p.color }}>{p.pct}%</span>
                    </div>
                    <div className="text-[10px] text-[#94A3B8] mb-1.5">{p.sub}</div>
                    <div className="h-1.5 rounded-full bg-[#F1F5F9]">
                      <div className="h-full rounded-full" style={{ width: `${p.pct}%`, background: p.color, transition: "width 1s ease" }} />
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* What We're Doing Well */}
            <div className="bg-white rounded-xl p-5 border border-[#E2E8F0] shadow-sm">
              <div className="flex items-start justify-between mb-4">
                <div>
                  <div className="text-[10px] font-bold tracking-widest text-[#64748B] uppercase mb-0.5">Strengths</div>
                  <h3 className="text-sm font-bold text-[#0F172A]">What We're Doing Well</h3>
                </div>
                <span className="text-[10px] font-bold px-2 py-1 rounded-lg bg-emerald-50 text-emerald-700">
                  SUSTAIN & SCALE
                </span>
              </div>
              <div className="space-y-4">
                {doingWell.map((d, i) => (
                  <div key={i} className="flex gap-3">
                    <div className="flex-shrink-0 text-center">
                      <span className="text-[10px] font-bold block"
                        style={{ color: i === 0 ? "#F59E0B" : "#22C55E" }}>{d.badge}</span>
                    </div>
                    <div>
                      <p className="text-xs text-[#475569] italic leading-relaxed mb-1">{d.quote}</p>
                      <p className="text-[10px] text-[#94A3B8]">{d.tag}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Account Health */}
            <div className="bg-white rounded-xl p-5 border border-[#E2E8F0] shadow-sm">
              <div className="flex items-start justify-between mb-4">
                <div>
                  <div className="text-[10px] font-bold tracking-widest text-[#64748B] uppercase mb-0.5">Accounts</div>
                  <h3 className="text-sm font-bold text-[#0F172A]">Account Health</h3>
                </div>
                <span className="text-[10px] font-bold px-2 py-1 rounded-lg bg-amber-50 text-amber-700">
                  NEEDS REVIEW
                </span>
              </div>
              <div className="space-y-2">
                {accounts.map(a => {
                  const col = npsColor(a.nps);
                  return (
                    <div key={a.name} className="flex items-center gap-3 p-2 rounded-lg hover:bg-[#F8FAFC] transition-colors">
                      <div className="w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 text-[11px] font-bold text-white bg-[#CC0000]">
                        {a.initials}
                      </div>
                      <span className="flex-1 text-sm text-[#0F172A]">{a.name}</span>
                      <div className="flex items-center gap-1.5">
                        <div className="w-2 h-2 rounded-full" style={{ background: col }} />
                        <span className="text-sm font-bold" style={{ color: col }}>
                          NPS: {a.nps > 0 ? `+${a.nps}` : a.nps}
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>

          {/* ── VERBATIMS ────────────────────────────────────────────────── */}
          <div>
            <div className="flex items-center gap-2 mb-4">
              <MessageSquare size={14} className="text-[#64748B]" />
              <span className="text-[11px] font-bold tracking-[0.15em] text-[#64748B] uppercase">
                RECENT CUSTOMER VERBATIMS — AI CATEGORISED
              </span>
            </div>
            <div className="grid grid-cols-3 gap-4 pb-8">
              {verbatims.map((v, i) => (
                <div key={i} data-testid={`verbatim-${i}`}
                  className="bg-white rounded-xl p-5 border border-[#E2E8F0] shadow-sm">
                  <div className="flex items-center gap-2 mb-4">
                    <span className="text-[10px] font-bold px-2.5 py-1 rounded-full"
                      style={{ background: v.color + "18", color: v.color }}>
                      {v.type}
                    </span>
                    <span className="text-[10px] font-bold text-[#64748B]">NPS {v.score}</span>
                  </div>
                  <p className="text-sm text-[#475569] italic leading-relaxed">{v.text}</p>
                </div>
              ))}
            </div>
          </div>

        </main>
      )}
    </div>
  );
}
