import React, { useState, Suspense, lazy } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../../contexts/AuthContext";
import {
  ArrowLeft, Building2, LogOut, Send, Plus, ChevronRight,
  Zap, Loader2,
} from "lucide-react";

// Lazy-load tab components for code splitting
const DashboardTab   = lazy(() => import("./voc/DashboardTab"));
const AccountsTab    = lazy(() => import("./voc/AccountsTab"));
const SurveyBuilderTab = lazy(() => import("./voc/SurveyBuilderTab"));
const CampaignsTab   = lazy(() => import("./voc/CampaignsTab"));

// Placeholder for future tabs
const ComingSoon = ({ tab }) => (
  <div className="flex items-center justify-center h-96">
    <div className="text-center">
      <div className="w-16 h-16 rounded-2xl bg-white border border-[#E2E8F0] shadow-sm flex items-center justify-center mx-auto mb-4">
        <Zap size={28} className="text-[#CC0000]" />
      </div>
      <h3 className="text-lg font-bold text-[#0F172A] mb-1">{tab}</h3>
      <p className="text-[#64748B] text-sm">This section is coming soon. Please check back later.</p>
    </div>
  </div>
);

const TabLoader = () => (
  <div className="flex items-center justify-center h-64">
    <Loader2 size={28} className="animate-spin text-[#CC0000]" />
  </div>
);

const NAV_TABS = [
  "DASHBOARD",
  "SURVEY BUILDER",
  "EMAIL CAMPAIGNS",
  "ACCOUNTS",
  "AI INSIGHTS",
  "WORKFLOW",
];

export default function NPSCsatPage() {
  const { logout } = useAuth();
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState("DASHBOARD");

  const doLogout = () => { logout(); navigate("/login"); };

  const renderTab = () => {
    switch (activeTab) {
      case "DASHBOARD":
        return (
          <Suspense fallback={<TabLoader />}>
            <DashboardTab />
          </Suspense>
        );
      case "SURVEY BUILDER":
        return (
          <Suspense fallback={<TabLoader />}>
            <SurveyBuilderTab />
          </Suspense>
        );
      case "EMAIL CAMPAIGNS":
        return (
          <Suspense fallback={<TabLoader />}>
            <CampaignsTab />
          </Suspense>
        );
      case "ACCOUNTS":
        return (
          <Suspense fallback={<TabLoader />}>
            <AccountsTab />
          </Suspense>
        );
      default:
        return <ComingSoon tab={activeTab} />;
    }
  };

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
              <button key={tab} data-testid={`nav-tab-${tab.toLowerCase().replace(/\s/g, "-")}`}
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
            <button data-testid="new-campaign-btn"
              onClick={() => setActiveTab("EMAIL CAMPAIGNS")}
              className="flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-bold tracking-wider border border-[#E2E8F0] text-[#64748B] bg-white hover:border-[#CC0000]/30 hover:text-[#0F172A] transition-colors">
              <Plus size={12} />NEW CAMPAIGN
            </button>
            <button data-testid="send-survey-btn"
              className="flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-bold tracking-wider text-white bg-[#CC0000] hover:bg-[#AA0000] transition-colors">
              <Send size={12} />SEND SURVEY
            </button>
            <button data-testid="ai-insights-btn"
              onClick={() => setActiveTab("AI INSIGHTS")}
              className="flex items-center gap-2 px-4 py-2.5 rounded-lg text-xs font-bold tracking-wider bg-violet-50 text-violet-700 border border-violet-200 hover:bg-violet-100 transition-colors">
              <Zap size={14} />AI INSIGHTS <ChevronRight size={12} />
            </button>
            <button data-testid="logout-nps-btn" onClick={doLogout}
              className="text-[#64748B] hover:text-[#0F172A] py-3 transition-colors">
              <LogOut size={15} />
            </button>
          </div>
        </div>
      </nav>

      {/* ── TAB CONTENT ─────────────────────────────────────────────────── */}
      {renderTab()}
    </div>
  );
}
