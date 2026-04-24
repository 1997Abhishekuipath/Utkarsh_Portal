import { useParams, useNavigate, Link } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext";
import {
  BookOpen, Calendar, Users, LayoutDashboard, GitBranch,
  Shield, UserCheck, GraduationCap, BarChart2, ArrowLeft,
  Building2, LogOut, Settings, Plus, Search
} from "lucide-react";

const APP_CONFIG = {
  "best-practices": {
    name: "Best Practices Repository", Icon: BookOpen, color: "#EF4444",
    gradient: "from-red-500 to-red-700", count: 80, unit: "Practices",
    desc: "Submit, discover and implement best practices. Get XP incentives across 12 departments.",
    stats: [{ label: "Submitted", value: 80 }, { label: "Approved", value: 67 }, { label: "Pending", value: 13 }, { label: "XP Earned", value: "2.4K" }],
  },
  "tech-days": {
    name: "Tech Days Manager", Icon: Calendar, color: "#10B981",
    gradient: "from-emerald-500 to-emerald-700", count: 8, unit: "Events",
    desc: "Plan and execute external facing tech day events. Track attendance, earn XP.",
    stats: [{ label: "Events", value: 8 }, { label: "Attended", value: 6 }, { label: "Upcoming", value: 2 }, { label: "XP Earned", value: "840" }],
  },
  "crm": {
    name: "CRM & Opportunity Pipeline", Icon: Users, color: "#3B82F6",
    gradient: "from-blue-500 to-blue-700", count: 142, unit: "Accounts",
    desc: "Manage prospects, track opportunities, attach base publications to deals.",
    stats: [{ label: "Accounts", value: 142 }, { label: "Open", value: 40 }, { label: "Won", value: 28 }, { label: "Pipeline", value: "₹12Cr" }],
  },
  "productivity": {
    name: "Productivity Hub", Icon: LayoutDashboard, color: "#F59E0B",
    gradient: "from-amber-500 to-amber-700", count: 24, unit: "Projects",
    desc: "Team task management, sprint boards, time tracking, resource planning.",
    stats: [{ label: "Projects", value: 24 }, { label: "Tasks", value: 678 }, { label: "Completed", value: "85%" }, { label: "On-Time", value: "91%" }],
  },
  "workflow": {
    name: "Workflow Automation", Icon: GitBranch, color: "#8B5CF6",
    gradient: "from-violet-500 to-violet-700", count: 18, unit: "Workflows",
    desc: "Setup workflow approvals, change management, ITSM tickets and escalation visibility.",
    stats: [{ label: "Workflows", value: 18 }, { label: "Active", value: 12 }, { label: "Pending", value: 25 }, { label: "Completed", value: 340 }],
  },
  "access-rights": {
    name: "Access Rights Management", Icon: Shield, color: "#475569",
    gradient: "from-slate-500 to-slate-700", count: 1200, unit: "Accounts",
    desc: "Manage enterprise system access, role-based and employee-level access controls.",
    stats: [{ label: "Users", value: "1.2K" }, { label: "Roles", value: 14 }, { label: "Alerts", value: 12 }, { label: "Reviews", value: 3 }],
  },
  "visitors": {
    name: "Visitor Management", Icon: UserCheck, color: "#14B8A6",
    gradient: "from-teal-500 to-teal-700", count: 34, unit: "Visitors",
    desc: "Manage employee visitor registration, badges printing, track visitor data.",
    stats: [{ label: "Today", value: 6 }, { label: "This Week", value: 34 }, { label: "Pre-Reg", value: 20 }, { label: "Checked-In", value: 14 }],
  },
  "learning": {
    name: "Learning & Development", Icon: GraduationCap, color: "#DC2626",
    gradient: "from-red-700 to-red-900", count: 45, unit: "Courses",
    desc: "200-level mentoring, course development, HSI certifications and L&D portfolio.",
    stats: [{ label: "Courses", value: 45 }, { label: "Enrolled", value: 12 }, { label: "Completed", value: 8 }, { label: "Certified", value: 3 }],
  },
  "analytics": {
    name: "Analytics & Reports", Icon: BarChart2, color: "#1E3A8A",
    gradient: "from-blue-900 to-indigo-900", count: 28, unit: "Reports",
    desc: "Cross platform analytics, XP trends, incentive reporting, KPI dashboards.",
    stats: [{ label: "Reports", value: 28 }, { label: "New", value: 3 }, { label: "Dashboards", value: 9 }, { label: "Exports", value: 156 }],
  },
};

export default function AppPage() {
  const { appId } = useParams();
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const config = APP_CONFIG[appId];

  if (!config) {
    return (
      <div className="flex items-center justify-center h-screen bg-[#F1F5F9]">
        <div className="text-center">
          <h2 className="text-xl font-bold text-[#0F172A] mb-2">App Not Found</h2>
          <Link to="/" className="text-[#CC0000] hover:underline text-sm">Back to Dashboard</Link>
        </div>
      </div>
    );
  }

  const { name, Icon, color, gradient, count, unit, desc, stats } = config;

  return (
    <div className="min-h-screen bg-[#F1F5F9]">
      {/* Top Nav */}
      <div className="bg-[#CC0000] border-b border-white/20">
        <div className="max-w-7xl mx-auto px-5 py-2.5 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-7 h-7 bg-white/20 rounded flex items-center justify-center">
              <Building2 size={14} className="text-white" />
            </div>
            <span className="text-white text-xs font-semibold tracking-wider">HITACHI SYSTEMS INDIA</span>
          </div>
          <div className="flex items-center gap-2">
            {user?.role === "admin" && (
              <Link to="/admin" className="text-white/70 hover:text-white text-xs px-3 py-1 rounded hover:bg-white/10 flex items-center gap-1 transition-colors">
                <Settings size={13} /><span>Admin</span>
              </Link>
            )}
            <button onClick={() => { logout(); navigate("/login"); }}
              className="text-white/70 hover:text-white text-xs px-3 py-1 rounded hover:bg-white/10 flex items-center gap-1 transition-colors">
              <LogOut size={13} /><span>Sign Out</span>
            </button>
          </div>
        </div>
      </div>

      {/* App Header */}
      <div className={`bg-gradient-to-r ${gradient} px-5 py-10`}>
        <div className="max-w-7xl mx-auto">
          <button data-testid="back-to-dashboard-btn" onClick={() => navigate("/")}
            className="flex items-center gap-2 text-white/70 hover:text-white text-sm mb-6 transition-colors">
            <ArrowLeft size={16} /><span>Back to Dashboard</span>
          </button>
          <div className="flex items-start justify-between">
            <div className="flex items-center gap-4">
              <div className="w-14 h-14 bg-white/20 rounded-xl flex items-center justify-center">
                <Icon size={28} className="text-white" />
              </div>
              <div>
                <h1 className="text-3xl font-bold text-white font-['Outfit']">{name}</h1>
                <p className="text-white/70 text-sm mt-1 max-w-lg">{desc}</p>
              </div>
            </div>
            <button data-testid="app-action-btn"
              className="bg-white text-[#CC0000] px-5 py-2.5 rounded-lg font-semibold text-sm hover:bg-gray-50 transition-colors flex items-center gap-2 shadow-sm">
              <Plus size={16} /><span>New</span>
            </button>
          </div>
          {/* Stats row */}
          <div className="grid grid-cols-4 gap-4 mt-8">
            {stats.map(s => (
              <div key={s.label} className="bg-white/15 rounded-lg p-4 text-center backdrop-blur-sm">
                <div className="text-white font-bold text-2xl font-['Outfit']">{s.value}</div>
                <div className="text-white/65 text-xs mt-0.5">{s.label}</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Content */}
      <main className="max-w-7xl mx-auto px-5 py-8">
        <div className="flex items-center gap-3 mb-6">
          <div className="flex-1 relative">
            <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-[#94A3B8]" />
            <input data-testid="app-search-input" placeholder={`Search ${name}...`}
              className="w-full pl-10 pr-4 py-2.5 border border-[#E2E8F0] rounded-lg text-sm bg-white focus:outline-none focus:ring-2 focus:ring-[#CC0000]/20 focus:border-[#CC0000]" />
          </div>
          <button data-testid="app-filter-btn"
            className="bg-white border border-[#E2E8F0] text-sm text-[#475569] px-4 py-2.5 rounded-lg hover:border-[#CC0000] transition-colors">
            Filter
          </button>
        </div>

        <div className="bg-white rounded-xl border border-[#E2E8F0] p-12 text-center">
          <div className="w-16 h-16 rounded-2xl flex items-center justify-center mx-auto mb-4"
            style={{ backgroundColor: color + "15" }}>
            <Icon size={32} style={{ color }} />
          </div>
          <h3 className="text-lg font-bold text-[#0F172A] mb-2">{name}</h3>
          <p className="text-[#475569] text-sm max-w-md mx-auto mb-6">{desc}</p>
          <div className="inline-flex items-center gap-2 bg-amber-50 border border-amber-200 text-amber-700 rounded-lg px-4 py-2 text-sm">
            <span className="font-semibold">Page under development.</span>
            <span>Screenshots will be provided to complete this page.</span>
          </div>
        </div>
      </main>
    </div>
  );
}
