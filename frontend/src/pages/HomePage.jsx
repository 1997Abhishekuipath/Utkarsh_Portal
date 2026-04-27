import { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { useAuth } from "../contexts/AuthContext";
import useLiveContent from "../hooks/useLiveContent";
import TopBar from "../components/TopBar";
import EdmCarousel from "../components/EdmCarousel";
import PillarCard from "../components/PillarCard";
import QuoteRibbon from "../components/QuoteRibbon";
import { Wifi, WifiOff, Trophy, Bell, Calendar, AlertCircle } from "lucide-react";

export default function HomePage() {
  const { user, authHeader, API } = useAuth();
  const [content, setContent]     = useState({ edm: [], pillars: [], quotes: [] });
  const [activities, setActivities] = useState([]);
  const [leaderboard, setLeaderboard] = useState([]);
  const [announcements, setAnnouncements] = useState([]);
  const [pending, setPending] = useState([]);
  const [upcoming, setUpcoming] = useState([]);
  const [stats, setStats]       = useState(null);

  const refetchContent = useCallback(() => {
    axios.get(`${API}/content/home`, { headers: authHeader() })
      .then(r => setContent(r.data)).catch(() => {});
  }, [API, authHeader]);

  const refetchSidebar = useCallback(() => {
    const h = authHeader();
    Promise.all([
      axios.get(`${API}/dashboard/activities`,     { headers: h }),
      axios.get(`${API}/dashboard/leaderboard`,    { headers: h }),
      axios.get(`${API}/dashboard/announcements`,  { headers: h }),
      axios.get(`${API}/dashboard/pending-actions`,{ headers: h }),
      axios.get(`${API}/dashboard/upcoming`,       { headers: h }),
      axios.get(`${API}/dashboard/stats`,          { headers: h }),
    ]).then(([a, l, ann, p, u, s]) => {
      setActivities(a.data); setLeaderboard(l.data);
      setAnnouncements(ann.data); setPending(p.data);
      setUpcoming(u.data); setStats(s.data);
    }).catch(() => {});
  }, [API, authHeader]);

  useEffect(() => { refetchContent(); refetchSidebar(); }, [refetchContent, refetchSidebar]);

  // Live update — admin's "Publish All" triggers re-fetch within ≤5s
  const wsConnected = useLiveContent((evt) => {
    if (evt.scope === "all" || evt.scope === "home") refetchContent();
  });

  const firstName = user?.name?.split(" ")[0] || "there";

  const topStats = stats ? [
    { value: stats.efforts.count >= 1000 ? `${(stats.efforts.count/1000).toFixed(1)}K` : stats.efforts.count, label: "XP" },
    { value: stats.pending_actions.count,                                                                     label: "PENDING" },
    { value: `₹${(stats.xp_incentive.amount/1000).toFixed(1)}K`,                                              label: "INCENTIVE" },
  ] : [];

  return (
    <div className="min-h-screen bg-[#F1F5F9]">
      <TopBar stats={topStats}>
        <div className="flex items-start justify-between gap-6">
          <div>
            <h1 className="text-4xl sm:text-5xl font-bold text-white tracking-tight font-['Outfit']">
              Hello, {firstName} <span className="inline-block">👋</span>
            </h1>
            <p className="text-white/75 text-sm max-w-lg mt-2 leading-relaxed">
              Your enterprise workspace built around four pillars — Customer, Innovator, Employee, Shareholder.
            </p>
          </div>
          <div className="hidden sm:flex items-center gap-1.5 text-[10px] tracking-widest font-semibold text-white/80 self-end pb-1.5"
            data-testid="ws-status-indicator" title={wsConnected ? "Live updates connected" : "Live updates reconnecting…"}>
            {wsConnected ? <Wifi size={11} /> : <WifiOff size={11} />}
            <span>{wsConnected ? "LIVE" : "OFFLINE"}</span>
          </div>
        </div>
      </TopBar>

      <main className="max-w-7xl mx-auto px-5 py-8 space-y-8">

        {/* Home EDM */}
        <section data-testid="home-edm-section">
          <EdmCarousel slides={content.edm} testid="home-edm" />
        </section>

        {/* 4 Pillar Cards */}
        <section data-testid="pillars-section">
          <SectionHeader title="THE FOUR PILLARS" subtitle="Tap a pillar to explore its apps & content" />
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {content.pillars.map(p => <PillarCard key={p.id} pillar={p} />)}
          </div>
        </section>

        {/* Motivational Quote */}
        {content.quotes.length > 0 && (
          <section data-testid="quotes-section">
            <QuoteRibbon quotes={content.quotes} />
          </section>
        )}

        {/* Activity grid */}
        <section className="grid grid-cols-1 lg:grid-cols-3 gap-6">

          {/* Recent activity */}
          <div className="lg:col-span-2 bg-white rounded-xl border border-[#E2E8F0] p-5">
            <SectionHeader title="RECENT ACTIVITY" tight />
            <ul className="space-y-3 mt-3">
              {activities.slice(0, 6).map(a => (
                <li key={a.id} data-testid={`activity-${a.id}`}
                  className="flex gap-3 items-start py-2 border-b border-[#F1F5F9] last:border-b-0">
                  <div className={`w-8 h-8 rounded-full flex-shrink-0 flex items-center justify-center text-white text-xs font-bold`}
                    style={{ background: dotColor(a.color) }}>
                    {(a.user || "?").split(" ").map(p => p[0]).join("").slice(0, 2).toUpperCase()}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-[#0F172A] leading-snug">
                      <span className="font-semibold">{a.user}</span> {a.action}
                    </p>
                    <div className="text-xs text-[#64748B] mt-0.5 flex items-center gap-2">
                      <span>{a.category}</span> · <span>{a.time}</span>
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          </div>

          {/* Right column — leaderboard / announcements / pending / upcoming */}
          <div className="space-y-4">
            <SidePanel testid="leaderboard-panel" title="LEADERBOARD" Icon={Trophy} iconColor="#F59E0B">
              <ol className="space-y-1.5">
                {leaderboard.slice(0, 5).map(l => (
                  <li key={l.rank} className={`flex items-center gap-2 text-sm py-1 px-2 rounded ${l.is_current_user ? "bg-red-50 border border-red-100" : ""}`}>
                    <div className="w-5 text-center text-[10px] font-bold text-[#94A3B8]">{l.rank}</div>
                    <div className="w-7 h-7 rounded-full bg-[#F1F5F9] flex items-center justify-center text-[10px] font-bold text-[#475569]">{l.initials}</div>
                    <div className="flex-1 min-w-0 truncate text-[#0F172A]">{l.name}</div>
                    <div className="text-xs font-semibold text-[#CC0000] tabular-nums">{l.xp.toLocaleString()}</div>
                  </li>
                ))}
              </ol>
            </SidePanel>

            <SidePanel testid="announcements-panel" title="ANNOUNCEMENTS" Icon={Bell} iconColor="#3B82F6">
              <ul className="space-y-2">
                {announcements.slice(0, 3).map(a => (
                  <li key={a.id} className="text-xs">
                    <div className="font-semibold text-[#0F172A]">{a.title}</div>
                    <div className="text-[#64748B] line-clamp-2 mt-0.5">{a.body}</div>
                  </li>
                ))}
              </ul>
            </SidePanel>

            <SidePanel testid="pending-panel" title="PENDING ACTIONS" Icon={AlertCircle} iconColor="#CC0000">
              <ul className="space-y-2">
                {pending.slice(0, 3).map(p => (
                  <li key={p.id} className="text-xs">
                    <div className="text-[#0F172A] font-medium leading-snug">{p.title}</div>
                    <div className="text-[#64748B] mt-0.5">{p.category}</div>
                  </li>
                ))}
              </ul>
            </SidePanel>

            <SidePanel testid="upcoming-panel" title="UPCOMING" Icon={Calendar} iconColor="#10B981">
              <ul className="space-y-2">
                {upcoming.slice(0, 3).map(u => (
                  <li key={u.id} className="text-xs">
                    <div className="text-[#0F172A] font-medium leading-snug">{u.title}</div>
                    <div className="text-[#64748B] mt-0.5">{u.date}</div>
                  </li>
                ))}
              </ul>
            </SidePanel>
          </div>
        </section>

      </main>
    </div>
  );
}

function SectionHeader({ title, subtitle, tight = false }) {
  return (
    <div className={`flex items-baseline justify-between ${tight ? "" : "mb-4"}`}>
      <div>
        <h2 className="text-[11px] tracking-widest font-bold text-[#475569]">{title}</h2>
        {subtitle && <p className="text-xs text-[#94A3B8] mt-0.5">{subtitle}</p>}
      </div>
    </div>
  );
}

function SidePanel({ title, Icon, iconColor, testid, children }) {
  return (
    <div data-testid={testid} className="bg-white rounded-xl border border-[#E2E8F0] p-4">
      <div className="flex items-center gap-2 mb-3">
        <Icon size={14} style={{ color: iconColor }} />
        <h3 className="text-[10px] tracking-widest font-bold text-[#475569]">{title}</h3>
      </div>
      {children}
    </div>
  );
}

function dotColor(name) {
  return ({
    red: "#CC0000", green: "#10B981", blue: "#3B82F6", teal: "#14B8A6",
    amber: "#F59E0B", gray: "#94A3B8",
  })[name] || "#94A3B8";
}
