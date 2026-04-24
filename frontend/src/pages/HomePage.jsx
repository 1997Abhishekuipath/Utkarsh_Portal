import { useState, useEffect } from "react";
import { useNavigate, Link } from "react-router-dom";
import axios from "axios";
import { useAuth } from "../contexts/AuthContext";
import {
  BookOpen, Calendar, Users, LayoutDashboard, GitBranch,
  Shield, UserCheck, GraduationCap, BarChart2, Star, Gift,
  AlertCircle, Bell, Trophy, ChevronRight, ArrowUpRight,
  Clock, LogOut, Settings, Building2, ExternalLink,
  TrendingUp, ClipboardList, Mail
} from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

// ── Helpers ─────────────────────────────────────────────────────────────────
const SectionHeader = ({ title, action, actionText }) => (
  <div className="flex items-center justify-between mb-4">
    <div className="flex items-center gap-2">
      <div className="w-0.5 h-4 bg-[#CC0000] rounded-full" />
      <span className="text-[11px] font-bold tracking-[0.12em] text-[#94A3B8] uppercase">{title}</span>
    </div>
    {action && (
      <button data-testid={`section-action-${title.toLowerCase().replace(/\s/g,'-')}`}
        onClick={action} className="text-[#CC0000] text-xs font-semibold hover:underline flex items-center gap-1">
        {actionText}<ChevronRight size={12} />
      </button>
    )}
  </div>
);

const colorMap = { red:"bg-[#EF4444]", green:"bg-[#10B981]", blue:"bg-[#3B82F6]", teal:"bg-[#14B8A6]", amber:"bg-[#F59E0B]", gray:"bg-[#64748B]" };
const textColorMap = { red:"text-red-600", green:"text-emerald-600", blue:"text-blue-600", teal:"text-teal-600", amber:"text-amber-600", gray:"text-slate-500" };

// ── Apps config ─────────────────────────────────────────────────────────────
const APPS = [
  { id:"best-practices", name:"Best Practices Repository", desc:"Submit, discover and implement best practices. Get XP incentives across 12 departments with 80 active follow-ups.", from:"#EF4444", to:"#B91C1C", count:80, countLabel:"PRACTICES", action:"KNOWLEDGE", stat:"20 HOURS", Icon:BookOpen },
  { id:"tech-days",      name:"Tech Days Manager",          desc:"Plan and execute tech day events. Track attendance, earn XP. 8 applications 80 days.", from:"#10B981", to:"#047857", count:8,  countLabel:"EVENTS",    action:"TRACK",     stat:"8 DAYS",   Icon:Calendar },
  { id:"crm",            name:"CRM & Opportunity Pipeline", desc:"Manage prospects, track opportunities, attach base publications to deals. Full pipeline visibility.", from:"#3B82F6", to:"#1D4ED8", count:142,countLabel:"ACCOUNTS",  action:"VIEW",      stat:"40 OPEN",  Icon:Users },
  { id:"productivity",   name:"Productivity Hub",           desc:"Team task management, sprint boards, time tracking, resource planning and project management.", from:"#F59E0B", to:"#B45309", count:24, countLabel:"PROJECTS",  action:"OPERATIONS",stat:"42 OPEN",  Icon:LayoutDashboard },
  { id:"workflow",       name:"Workflow Automation",        desc:"Set-up workflow approvals, change management, ITSM tickets and escalation visibility.", from:"#8B5CF6", to:"#6D28D9", count:18, countLabel:"WORKFLOWS", action:"AUTOMATE",  stat:"25 TASKS", Icon:GitBranch },
  { id:"access-rights",  name:"Access Rights Management",   desc:"Manage enterprise system access, role-based and employee-level access controls.", from:"#475569", to:"#1E293B", count:1200,countLabel:"ACCOUNTS",  action:"SECURITY",  stat:"12 ALERTS",Icon:Shield },
  { id:"visitors",       name:"Visitor Management",         desc:"Manage employee visitor registration, manage badges printing key, track visitor data.", from:"#14B8A6", to:"#0F766E", count:34, countLabel:"VISITORS",  action:"TRACK",     stat:"6 TODAY",  Icon:UserCheck },
  { id:"learning",       name:"Learning & Development",     desc:"200-level mentoring, course development, HSI certifications and L&D portfolio.", from:"#DC2626", to:"#7F1D1D", count:45, countLabel:"COURSES",   action:"ENROLL",    stat:"12 ACTIVE",Icon:GraduationCap },
  { id:"analytics",      name:"Analytics & Reports",        desc:"Cross platform analytics, XP trends, incentive reporting, KPI dashboards.", from:"#1E3A8A", to:"#1E40AF", count:28, countLabel:"REPORTS",   action:"INSIGHTS",  stat:"3 NEW",    Icon:BarChart2 },
  { id:"nps-csat",       name:"NPS & CSAT",                 desc:"Voice of Customer Intelligence. Real-time NPS/CSAT dashboards, survey builder, account health and AI-categorised verbatims.", from:"#0284C7", to:"#0C4A6E", count:62, countLabel:"NPS SCORE", action:"INSIGHTS",  stat:"+62 NPS",  Icon:TrendingUp },
  { id:"survey-builder", name:"Survey Builder",             desc:"Design and deploy intelligent survey campaigns. Multi-channel distribution with real-time response tracking.", from:"#F97316", to:"#C2410C", count:24, countLabel:"SURVEYS",   action:"CREATE",    stat:"142 RES",  Icon:ClipboardList },
  { id:"email-campaigns",name:"Email Campaigns",            desc:"Automate customer communication workflows. Drip campaigns, NPS follow-ups, and event-triggered emails.", from:"#6366F1", to:"#4338CA", count:18, countLabel:"CAMPAIGNS", action:"LAUNCH",    stat:"68% OPEN", Icon:Mail },
];

const QUICK_APPS = [
  { id:"best-practices", label:"Best Practices", color:"#EF4444", Icon:BookOpen },
  { id:"tech-days",      label:"Tech Days",      color:"#3B82F6", Icon:Calendar },
  { id:"crm",            label:"CRM",            color:"#8B5CF6", Icon:Users },
  { id:"productivity",   label:"Productivity",   color:"#10B981", Icon:LayoutDashboard },
  { id:"visitors",       label:"Visitors",       color:"#F59E0B", Icon:UserCheck },
];

// ── Sub-components ────────────────────────────────────────────────────────────
const StatBox = ({ value, label }) => (
  <div className="bg-white/20 backdrop-blur-sm rounded-lg px-3 py-2 text-center min-w-[72px]">
    <div className="text-white font-bold text-lg leading-none font-['Outfit']">{value}</div>
    <div className="text-white/65 text-[9px] mt-0.5 tracking-wider uppercase">{label}</div>
  </div>
);

const MetricCard = ({ label, value, trend, sub, Icon, iconColor }) => (
  <div className="bg-white rounded-lg border border-[#E2E8F0] p-4 hover:shadow-md transition-shadow">
    <div className="flex items-start justify-between mb-3">
      <div className="w-9 h-9 rounded-lg flex items-center justify-center" style={{ backgroundColor: iconColor + "20" }}>
        <Icon size={18} style={{ color: iconColor }} />
      </div>
      <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full ${trend === "Due" ? "bg-red-100 text-red-600" : "bg-emerald-100 text-emerald-600"}`}>
        {trend}
      </span>
    </div>
    <div className="text-2xl font-bold text-[#0F172A] font-['Outfit'] leading-none mb-1">{value}</div>
    <div className="text-[11px] font-semibold text-[#475569] uppercase tracking-wide">{label}</div>
    <div className="text-[10px] text-[#94A3B8] mt-0.5">{sub}</div>
  </div>
);

const AppCard = ({ app, navigate }) => {
  const { Icon } = app;
  return (
    <div data-testid={`app-card-${app.id}`} className="bg-white rounded-lg border border-[#E2E8F0] overflow-hidden hover:shadow-md transition-shadow cursor-pointer group"
      onClick={() => navigate(`/apps/${app.id}`)}>
      <div className="relative h-28 flex items-center justify-between px-5"
        style={{ background: `linear-gradient(135deg, ${app.from}, ${app.to})` }}>
        <div className="w-12 h-12 bg-white/20 rounded-xl flex items-center justify-center">
          <Icon size={24} className="text-white" />
        </div>
        <div className="text-right">
          <div className="text-white font-bold text-3xl font-['Outfit'] leading-none">
            {app.count >= 1000 ? `${(app.count/1000).toFixed(1)}K` : app.count}
          </div>
          <div className="text-white/70 text-[10px] tracking-widest uppercase mt-0.5">{app.countLabel}</div>
        </div>
      </div>
      <div className="p-4">
        <h3 className="font-semibold text-[#0F172A] text-sm mb-1 group-hover:text-[#CC0000] transition-colors">{app.name}</h3>
        <p className="text-[#64748B] text-[11px] leading-relaxed mb-3 line-clamp-2">{app.desc}</p>
        <div className="flex items-center justify-between">
          <button className="text-[#CC0000] text-[11px] font-bold tracking-wider hover:underline flex items-center gap-1">
            {app.action}<ArrowUpRight size={11} />
          </button>
          <span className="bg-blue-50 text-blue-600 text-[10px] font-semibold px-2 py-0.5 rounded-full">{app.stat}</span>
        </div>
      </div>
    </div>
  );
};

const ActivityDot = ({ type }) => {
  const colors = { submission:"bg-red-500", approval:"bg-green-500", tag:"bg-blue-500", visitor:"bg-teal-500", task:"bg-amber-500", review:"bg-slate-500" };
  return <div className={`w-2 h-2 rounded-full mt-1.5 flex-shrink-0 ${colors[type] || "bg-gray-400"}`} />;
};

const CircleGauge = ({ percent }) => {
  const r = 42, circ = 2 * Math.PI * r;
  const offset = circ - (percent / 100) * circ;
  return (
    <div className="relative inline-flex items-center justify-center w-28 h-28">
      <svg viewBox="0 0 100 100" className="w-full h-full -rotate-90">
        <circle cx="50" cy="50" r={r} fill="none" stroke="#E2E8F0" strokeWidth="9" />
        <circle cx="50" cy="50" r={r} fill="none" stroke="#CC0000" strokeWidth="9"
          strokeDasharray={circ} strokeDashoffset={offset} strokeLinecap="round"
          style={{ transition: "stroke-dashoffset 1s ease" }} />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-xl font-bold text-[#0F172A] font-['Outfit']">{percent}%</span>
        <span className="text-[9px] text-[#94A3B8]">SCORE</span>
      </div>
    </div>
  );
};

const RankMedal = ({ rank }) => {
  if (rank === 1) return <Trophy size={14} className="text-yellow-500" />;
  if (rank === 2) return <Trophy size={14} className="text-slate-400" />;
  if (rank === 3) return <Trophy size={14} className="text-amber-600" />;
  return <span className="text-[#94A3B8] text-xs font-bold">{rank}</span>;
};

const avatarColors = ["#EF4444","#3B82F6","#10B981","#8B5CF6","#F59E0B","#14B8A6","#EC4899","#6366F1"];

// ── Main Page ────────────────────────────────────────────────────────────────
export default function HomePage() {
  const { user, logout, authHeader } = useAuth();
  const navigate = useNavigate();
  const [stats, setStats]           = useState(null);
  const [activities, setActivities] = useState([]);
  const [leaderboard, setLeaderboard] = useState([]);
  const [announcements, setAnnouncements] = useState([]);
  const [pending, setPending]       = useState([]);
  const [upcoming, setUpcoming]     = useState([]);
  const [score, setScore]           = useState(null);
  const [showUserMenu, setShowUserMenu] = useState(false);

  useEffect(() => {
    const h = authHeader();
    Promise.all([
      axios.get(`${API}/dashboard/stats`,          { headers: h }),
      axios.get(`${API}/dashboard/activities`,     { headers: h }),
      axios.get(`${API}/dashboard/leaderboard`,    { headers: h }),
      axios.get(`${API}/dashboard/announcements`,  { headers: h }),
      axios.get(`${API}/dashboard/pending-actions`,{ headers: h }),
      axios.get(`${API}/dashboard/upcoming`,       { headers: h }),
      axios.get(`${API}/dashboard/score`,          { headers: h }),
    ]).then(([s,a,l,ann,p,u,sc]) => {
      setStats(s.data); setActivities(a.data); setLeaderboard(l.data);
      setAnnouncements(ann.data); setPending(p.data); setUpcoming(u.data); setScore(sc.data);
    }).catch(console.error);
  }, []);

  const firstName = user?.name?.split(' ')[0] || 'User';

  const topStats = [
    { value: "12",    label: "APPS" },
    { value: stats ? (stats.efforts.count >= 1000 ? `${(stats.efforts.count/1000).toFixed(1)}K` : stats.efforts.count) : "—", label: "XP" },
    { value: stats ? stats.pending_actions.count : "—", label: "PENDING" },
    { value: stats ? `₹${(stats.xp_incentive.amount/1000).toFixed(1)}K` : "—", label: "INCENTIVE" },
  ];

  const metricCards = stats ? [
    { label:"BEST PRACTICES",  value: stats.best_practices.count,  trend: stats.best_practices.trend,  sub: stats.best_practices.sub,  Icon: BookOpen,     iconColor:"#EF4444" },
    { label:"EFFORTS (XP)",    value: stats.efforts.count.toLocaleString(), trend: stats.efforts.trend, sub: stats.efforts.sub,  Icon: Star,         iconColor:"#F59E0B" },
    { label:"XP INCENTIVE",    value: `₹${(stats.xp_incentive.amount/1000).toFixed(1)}K`, trend: stats.xp_incentive.trend, sub: stats.xp_incentive.sub, Icon: Gift, iconColor:"#10B981" },
    { label:"TECH DAYS",       value: stats.tech_days.count,       trend: stats.tech_days.trend,       sub: stats.tech_days.sub,       Icon: Calendar,     iconColor:"#3B82F6" },
    { label:"PENDING ACTIONS", value: stats.pending_actions.count, trend: stats.pending_actions.trend, sub: stats.pending_actions.sub, Icon: AlertCircle,  iconColor:"#CC0000" },
  ] : [];

  const doLogout = () => { logout(); navigate("/login"); };

  return (
    <div className="min-h-screen bg-[#F1F5F9]">

      {/* ── HERO HEADER ──────────────────────────────────────────────────── */}
      <div className="bg-[#CC0000] relative overflow-hidden">
        <div className="absolute inset-0 pointer-events-none"
          style={{ backgroundImage: "radial-gradient(circle at 85% 50%, rgba(255,255,255,0.08) 0%, transparent 55%)" }} />

        {/* Top mini-bar */}
        <div className="relative border-b border-white/20">
          <div className="max-w-7xl mx-auto px-5 py-2.5 flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 bg-white/20 rounded-lg flex items-center justify-center">
                <Building2 size={16} className="text-white" />
              </div>
              <div>
                <div className="text-white font-semibold text-xs tracking-[0.12em]">HITACHI SYSTEMS INDIA</div>
                <div className="text-white/50 text-[9px] tracking-widest">HSI ENTERPRISE PLATFORM</div>
              </div>
            </div>
            <div className="flex items-center gap-2">
              {topStats.map(s => <StatBox key={s.label} value={s.value} label={s.label} />)}
              {/* User menu */}
              <div className="relative ml-2">
                <button data-testid="user-menu-button" onClick={() => setShowUserMenu(!showUserMenu)}
                  className="flex items-center gap-2 bg-white/20 hover:bg-white/30 rounded-lg px-3 py-1.5 transition-colors">
                  <div className="w-6 h-6 rounded-full bg-white/30 flex items-center justify-center">
                    <span className="text-white text-[10px] font-bold">{user?.name?.[0]}</span>
                  </div>
                  <span className="text-white text-xs font-medium hidden sm:block">{firstName}</span>
                </button>
                {showUserMenu && (
                  <div className="absolute right-0 top-full mt-2 bg-white rounded-lg shadow-lg border border-[#E2E8F0] w-48 z-50 animate-fade-in">
                    <div className="px-4 py-3 border-b border-[#E2E8F0]">
                      <div className="text-sm font-semibold text-[#0F172A]">{user?.name}</div>
                      <div className="text-xs text-[#64748B] capitalize">{user?.role}</div>
                    </div>
                    {user?.role === "admin" && (
                      <Link to="/admin" data-testid="admin-panel-link"
                        className="flex items-center gap-2 px-4 py-2.5 text-sm text-[#0F172A] hover:bg-[#F8FAFC] transition-colors">
                        <Settings size={15} /><span>Admin Panel</span>
                      </Link>
                    )}
                    <button data-testid="logout-button" onClick={doLogout}
                      className="w-full flex items-center gap-2 px-4 py-2.5 text-sm text-red-600 hover:bg-red-50 transition-colors rounded-b-lg">
                      <LogOut size={15} /><span>Sign Out</span>
                    </button>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Main hero */}
        <div className="relative max-w-7xl mx-auto px-5 py-7">
          <div className="flex items-start gap-2 mb-2">
            <h1 className="text-4xl font-bold text-white tracking-tight font-['Outfit']">
              Good morning,<br />{firstName}
            </h1>
            <span className="text-3xl mt-1">👋</span>
          </div>
          <p className="text-white/75 text-sm max-w-lg mb-5 leading-relaxed">
            Your enterprise workspace: Best practices, tech days, CRM, team productivity, visitor management and more – all in one place.
          </p>
          <div className="flex items-center gap-3">
            <button data-testid="open-best-practices-btn"
              onClick={() => navigate("/apps/best-practices")}
              className="bg-white text-[#CC0000] px-5 py-2.5 rounded-lg font-semibold text-sm hover:bg-gray-50 transition-colors shadow-sm">
              Open Best Practices
            </button>
            <button data-testid="search-everything-btn"
              className="border border-white/70 text-white px-5 py-2.5 rounded-lg font-semibold text-sm hover:bg-white/10 transition-colors">
              Search Everything
            </button>
          </div>
        </div>
      </div>

      {/* ── MAIN CONTENT ─────────────────────────────────────────────────── */}
      <main className="max-w-7xl mx-auto px-5 py-6 space-y-6">

        {/* MY DASHBOARDS */}
        <section data-testid="my-dashboards-section">
          <SectionHeader title="MY DASHBOARDS" />
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
            {metricCards.map(c => <MetricCard key={c.label} {...c} />)}
          </div>
        </section>

        {/* MY APPS - QUICK ACCESS */}
        <section data-testid="quick-access-section">
          <SectionHeader title="MY APPS — QUICK ACCESS" />
          <div className="flex items-center gap-3 flex-wrap">
            {QUICK_APPS.map(a => (
              <button key={a.id} data-testid={`quick-app-${a.id}`}
                onClick={() => navigate(`/apps/${a.id}`)}
                className="flex items-center gap-2 bg-white border border-[#E2E8F0] rounded-full px-4 py-2 text-sm font-medium text-[#0F172A] hover:border-[#CC0000] hover:text-[#CC0000] transition-all shadow-sm">
                <div className="w-5 h-5 rounded-full flex items-center justify-center" style={{ backgroundColor: a.color + "20" }}>
                  <a.Icon size={12} style={{ color: a.color }} />
                </div>
                {a.label}
              </button>
            ))}
          </div>
        </section>

        {/* ALL APPLICATIONS */}
        <section data-testid="all-applications-section">
          <SectionHeader title="ALL APPLICATIONS" />
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {APPS.map(app => <AppCard key={app.id} app={app} navigate={navigate} />)}
          </div>
        </section>

        {/* RECENT ACTIVITY + RIGHT WIDGETS */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
          {/* Recent Activity */}
          <div className="lg:col-span-2 bg-white rounded-lg border border-[#E2E8F0] p-5" data-testid="recent-activity-section">
            <SectionHeader title="RECENT ACTIVITY" actionText="See all" action={() => {}} />
            <div className="space-y-4">
              {activities.map(a => (
                <div key={a.id} className="flex items-start gap-3">
                  <ActivityDot type={a.type} />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-[#0F172A] leading-snug">
                      <span className="font-semibold">{a.user}</span>{" "}{a.action}
                    </p>
                    <div className="flex items-center gap-2 mt-1">
                      <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full bg-[#F1F5F9] ${textColorMap[a.color] || "text-gray-500"}`}>
                        {a.category}
                      </span>
                      <span className="text-[10px] text-[#94A3B8] flex items-center gap-1">
                        <Clock size={9} />{a.time}
                      </span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Right column: Score + Upcoming + Pending */}
          <div className="space-y-4">
            {/* MY SCORE */}
            <div className="bg-white rounded-lg border border-[#E2E8F0] p-5" data-testid="my-score-section">
              <SectionHeader title="MY SCORE"
                actionText={`${(score?.total_xp || 0).toLocaleString()} XP`} action={() => {}} />
              <div className="flex items-center gap-5">
                <CircleGauge percent={score?.percentage || 0} />
                <div className="flex-1 space-y-2">
                  {score?.breakdown?.map(b => (
                    <div key={b.label}>
                      <div className="flex justify-between text-xs mb-0.5">
                        <span className="text-[#475569]">{b.label}</span>
                        <span className="font-semibold text-[#0F172A]">{b.value}</span>
                      </div>
                      <div className="h-1.5 bg-[#F1F5F9] rounded-full overflow-hidden">
                        <div className="h-full bg-[#CC0000] rounded-full transition-all" style={{ width: `${b.bar}%` }} />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* UPCOMING */}
            <div className="bg-white rounded-lg border border-[#E2E8F0] p-5" data-testid="upcoming-section">
              <SectionHeader title="UPCOMING" />
              <div className="space-y-3">
                {upcoming.map(u => (
                  <div key={u.id} className="flex items-start gap-3">
                    <div className={`w-2 h-2 rounded-full mt-1.5 flex-shrink-0 ${colorMap[u.color] || "bg-gray-400"}`} />
                    <div>
                      <div className="text-sm font-medium text-[#0F172A] leading-tight">{u.title}</div>
                      <div className="text-[10px] text-[#94A3B8] mt-0.5">{u.date} • {u.description}</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* PENDING ACTIONS */}
            <div className="bg-white rounded-lg border border-[#E2E8F0] p-5" data-testid="pending-actions-section">
              <SectionHeader title="PENDING ACTIONS"
                actionText={`${pending.length}`} action={() => {}} />
              <div className="space-y-3">
                {pending.map(p => (
                  <div key={p.id} className="flex items-center gap-2">
                    <div className="flex-1 min-w-0">
                      <div className="text-xs font-medium text-[#0F172A] leading-tight truncate">{p.title}</div>
                      <span className="text-[10px] text-[#94A3B8]">{p.category}</span>
                    </div>
                    <button data-testid={`act-btn-${p.id}`}
                      className="bg-[#CC0000] hover:bg-[#A30000] text-white text-[10px] font-bold px-3 py-1 rounded flex-shrink-0 transition-colors">
                      Act
                    </button>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* LEADERBOARD + ANNOUNCEMENTS */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5 pb-8">
          {/* Leaderboard */}
          <div className="bg-white rounded-lg border border-[#E2E8F0] p-5" data-testid="leaderboard-section">
            <SectionHeader title="ORGANISATION LEADERBOARD" actionText="Full Leaderboard" action={() => {}} />
            <div className="space-y-3">
              {leaderboard.map((entry, i) => (
                <div key={i} data-testid={`leaderboard-entry-${entry.rank}`}
                  className={`flex items-center gap-3 p-2 rounded-lg transition-colors ${entry.is_current_user ? "bg-red-50 border border-red-100" : "hover:bg-[#F8FAFC]"}`}>
                  <div className="w-6 flex items-center justify-center flex-shrink-0">
                    <RankMedal rank={entry.rank} />
                  </div>
                  <div className="w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 text-white text-[11px] font-bold"
                    style={{ backgroundColor: avatarColors[i % avatarColors.length] }}>
                    {entry.initials}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-semibold text-[#0F172A] truncate flex items-center gap-1">
                      {entry.name}
                      {entry.is_current_user && <span className="text-[10px] text-[#CC0000] font-normal">(You)</span>}
                    </div>
                    <div className="text-[10px] text-[#94A3B8] capitalize">{entry.role}</div>
                  </div>
                  <div className="text-sm font-bold text-[#0F172A] flex-shrink-0">{entry.xp.toLocaleString()}</div>
                </div>
              ))}
            </div>
          </div>

          {/* Announcements */}
          <div className="bg-white rounded-lg border border-[#E2E8F0] p-5" data-testid="announcements-section">
            <SectionHeader title="ANNOUNCEMENTS" actionText="All" action={() => {}} />
            <div className="space-y-4">
              {announcements.map(ann => (
                <div key={ann.id} className="flex gap-3 p-3 rounded-lg hover:bg-[#F8FAFC] transition-colors cursor-pointer">
                  <div className={`w-2 h-2 rounded-full mt-1.5 flex-shrink-0 ${colorMap[ann.color] || "bg-gray-400"}`} />
                  <div>
                    <div className="text-sm font-semibold text-[#0F172A] mb-0.5">{ann.title}</div>
                    <div className="text-[11px] text-[#64748B] leading-relaxed">{ann.body}</div>
                    <div className="text-[10px] text-[#94A3B8] mt-1 flex items-center gap-1">
                      <Clock size={9} />{ann.date}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
