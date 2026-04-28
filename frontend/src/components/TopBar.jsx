import { useState, useEffect, useCallback } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Building2, Settings, LogOut, ChevronRight, Bell } from "lucide-react";
import { useAuth } from "../contexts/AuthContext";

const BACKEND = process.env.REACT_APP_BACKEND_URL;

export default function TopBar({ stats = [], crumbs = null, children = null }) {
  const { user, logout, authHeader } = useAuth();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [notifOpen, setNotifOpen] = useState(false);
  const [unread, setUnread] = useState(0);
  const [notifs, setNotifs] = useState([]);
  const [loadingNotifs, setLoadingNotifs] = useState(false);
  const firstName = user?.name?.split(" ")[0] || "User";
  const isAdmin = user && (user.role === "admin" || user.role === "super_admin");

  const doLogout = async () => { await logout(); navigate("/login"); };

  const fetchUnread = useCallback(async () => {
    try {
      const res = await fetch(`${BACKEND}/api/notifications/unread-count`, { headers: { ...authHeader() } });
      if (res.ok) { const d = await res.json(); setUnread(d.count || 0); }
    } catch { /* silent */ }
  }, [authHeader]);

  const fetchNotifs = async () => {
    if (loadingNotifs) return;
    setLoadingNotifs(true);
    try {
      const res = await fetch(`${BACKEND}/api/notifications?limit=10`, { headers: { ...authHeader() } });
      if (res.ok) { const d = await res.json(); setNotifs(d.items || []); }
    } catch { /* silent */ } finally { setLoadingNotifs(false); }
  };

  const markRead = async (id) => {
    await fetch(`${BACKEND}/api/notifications/${id}/read`, { method: "PUT", headers: { ...authHeader() } });
    setNotifs(prev => prev.map(n => n.id === id ? { ...n, is_read: true } : n));
    setUnread(prev => Math.max(0, prev - 1));
  };

  const markAllRead = async () => {
    await fetch(`${BACKEND}/api/notifications/read-all`, { method: "PUT", headers: { ...authHeader() } });
    setNotifs(prev => prev.map(n => ({ ...n, is_read: true })));
    setUnread(0);
  };

  useEffect(() => {
    if (user) { fetchUnread(); const t = setInterval(fetchUnread, 30000); return () => clearInterval(t); }
  }, [user, fetchUnread]);

  const toggleNotif = () => {
    const next = !notifOpen;
    setNotifOpen(next);
    setOpen(false);
    if (next) fetchNotifs();
  };

  const CATEGORY_COLORS = {
    birthday: "bg-pink-100 text-pink-700", approved: "bg-green-100 text-green-700",
    replication: "bg-blue-100 text-blue-700", announcement: "bg-gray-100 text-gray-700",
    incentive: "bg-amber-100 text-amber-700", award: "bg-purple-100 text-purple-700",
    new_practice: "bg-teal-100 text-teal-700", reminder: "bg-orange-100 text-orange-700",
  };

  return (
    <div className="bg-[#CC0000] relative">
      <div className="absolute inset-0 pointer-events-none overflow-hidden"
        style={{ backgroundImage: "radial-gradient(circle at 85% 50%, rgba(255,255,255,0.08) 0%, transparent 55%)" }} />

      {/* Brand row */}
      <div className="relative border-b border-white/20">
        <div className="max-w-7xl mx-auto px-5 py-2.5 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2.5">
            <div className="w-8 h-8 bg-white/20 rounded-lg flex items-center justify-center">
              <Building2 size={16} className="text-white" />
            </div>
            <div>
              <div className="text-white font-semibold text-xs tracking-[0.12em]">HITACHI SYSTEMS INDIA</div>
              <div className="text-white/50 text-[9px] tracking-widest">HSI EMPLOYEE ENGAGEMENT PLATFORM</div>
            </div>
          </Link>

          <div className="flex items-center gap-2">
            {stats.map(s => (
              <div key={s.label} className="hidden sm:block text-right px-3">
                <div className="text-white text-sm font-bold leading-none">{s.value}</div>
                <div className="text-white/60 text-[9px] tracking-widest mt-0.5">{s.label}</div>
              </div>
            ))}

            {/* Notification Bell */}
            <div className="relative">
              <button onClick={toggleNotif}
                aria-label={unread > 0 ? `Notifications, ${unread} unread` : "Notifications"}
                aria-haspopup="true" aria-expanded={notifOpen}
                data-testid="notification-bell"
                className="relative flex items-center justify-center w-9 h-9 bg-white/20 hover:bg-white/30 rounded-lg transition-colors focus:outline-none focus:ring-2 focus:ring-white/70 focus:ring-offset-2 focus:ring-offset-[#CC0000]">
                <Bell size={16} className="text-white" aria-hidden="true" />
                {unread > 0 && (
                  <span className="absolute -top-1 -right-1 bg-yellow-400 text-black text-[9px] font-bold rounded-full min-w-[16px] h-4 flex items-center justify-center px-1"
                    aria-hidden="true">
                    {unread > 99 ? "99+" : unread}
                  </span>
                )}
              </button>
              {notifOpen && (
                <div role="menu" aria-label="Notifications menu"
                  className="absolute right-0 top-full mt-2 bg-white rounded-xl shadow-2xl border border-gray-100 w-80 sm:w-96 z-[200] max-h-[80vh] flex flex-col">
                  <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100">
                    <span className="text-sm font-semibold text-gray-800">Notifications</span>
                    {unread > 0 && (
                      <button onClick={markAllRead} className="text-xs text-[#CC0000] hover:underline focus:outline-none focus:ring-2 focus:ring-[#CC0000] rounded">Mark all read</button>
                    )}
                  </div>
                  <div className="overflow-y-auto flex-1">
                    {loadingNotifs && <div className="text-center py-6 text-gray-400 text-sm" role="status">Loading…</div>}
                    {!loadingNotifs && notifs.length === 0 && (
                      <div className="text-center py-8 text-gray-400 text-sm">No notifications yet</div>
                    )}
                    {notifs.map(n => (
                      <button type="button" role="menuitem" key={n.id}
                        onClick={() => !n.is_read && markRead(n.id)}
                        className={`w-full text-left flex gap-3 px-4 py-3 border-b border-gray-50 hover:bg-gray-50 transition-colors focus:outline-none focus:bg-gray-100 ${!n.is_read ? "bg-red-50" : ""}`}>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-start gap-2">
                            <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${CATEGORY_COLORS[n.category] || "bg-gray-100 text-gray-600"}`}>
                              {n.category || "info"}
                            </span>
                            {n.is_urgent && <span className="text-[10px] text-red-600 font-bold">URGENT</span>}
                            {!n.is_read && <span className="w-2 h-2 rounded-full bg-[#CC0000] mt-1 flex-shrink-0" aria-label="Unread" />}
                          </div>
                          <div className="text-xs font-semibold text-gray-800 mt-1 truncate">{n.title}</div>
                          <div className="text-[11px] text-gray-500 mt-0.5 line-clamp-2">{n.body}</div>
                        </div>
                      </button>
                    ))}
                  </div>
                  <div className="px-4 py-2 border-t border-gray-100">
                    <Link to="/notifications" onClick={() => setNotifOpen(false)}
                      className="block text-center text-xs text-[#CC0000] hover:underline py-1 focus:outline-none focus:ring-2 focus:ring-[#CC0000] rounded">
                      View all notifications →
                    </Link>
                  </div>
                </div>
              )}
            </div>

            <div className="relative ml-1">
              <button data-testid="user-menu-button" onClick={() => { setOpen(!open); setNotifOpen(false); }}
                aria-haspopup="true" aria-expanded={open} aria-label={`User menu for ${user?.name || 'user'}`}
                className="flex items-center gap-2 bg-white/20 hover:bg-white/30 rounded-lg px-3 py-1.5 transition-colors focus:outline-none focus:ring-2 focus:ring-white/70 focus:ring-offset-2 focus:ring-offset-[#CC0000]">
                <div className="w-6 h-6 rounded-full bg-white/30 flex items-center justify-center" aria-hidden="true">
                  <span className="text-white text-[10px] font-bold">{user?.name?.[0]}</span>
                </div>
                <span className="text-white text-xs font-medium hidden sm:block">{firstName}</span>
              </button>
              {open && (
                <div className="absolute right-0 top-full mt-2 bg-white rounded-lg shadow-lg border border-[#E2E8F0] w-56 z-[200] max-h-[80vh] overflow-y-auto">
                  <div className="px-4 py-3 border-b border-[#E2E8F0]">
                    <div className="text-sm font-semibold text-[#0F172A]">{user?.name}</div>
                    <div className="text-xs text-[#64748B] capitalize">{user?.role?.replace("_", " ")}</div>
                    {user?.last_login_at && (
                      <div className="text-[10px] text-[#94A3B8] mt-0.5">
                        Last login: {new Date(user.last_login_at).toLocaleString("en-IN", { dateStyle: "short", timeStyle: "short" })}
                      </div>
                    )}
                  </div>
                  <Link to="/profile" onClick={() => setOpen(false)}
                    className="flex items-center gap-2 px-4 py-2.5 text-sm text-[#0F172A] hover:bg-[#F8FAFC] transition-colors">
                    <span>👤</span><span>My Profile</span>
                  </Link>
                  <Link to="/practices" onClick={() => setOpen(false)}
                    className="flex items-center gap-2 px-4 py-2.5 text-sm text-[#0F172A] hover:bg-[#F8FAFC] transition-colors">
                    <span>📚</span><span>Best Practices</span>
                  </Link>
                  <Link to="/my-activity" onClick={() => setOpen(false)}
                    className="flex items-center gap-2 px-4 py-2.5 text-sm text-[#0F172A] hover:bg-[#F8FAFC] transition-colors">
                    <span>⭐</span><span>My XP & Activity</span>
                  </Link>
                  {isAdmin && (
                    <>
                      <Link to="/admin" data-testid="admin-panel-link" onClick={() => setOpen(false)}
                        className="flex items-center gap-2 px-4 py-2.5 text-sm text-[#0F172A] hover:bg-[#F8FAFC] transition-colors">
                        <Settings size={15} /><span>Admin Panel</span>
                      </Link>
                      <Link to="/admin/console" onClick={() => setOpen(false)}
                        className="flex items-center gap-2 px-4 py-2.5 text-sm text-[#0F172A] hover:bg-[#F8FAFC] transition-colors">
                        <span className="text-sm">🖥️</span><span>Admin Console</span>
                      </Link>
                    </>
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

      {/* Optional breadcrumbs row */}
      {crumbs?.length > 0 && (
        <div className="relative max-w-7xl mx-auto px-5 py-2 flex items-center gap-1 text-white/85 text-xs">
          {crumbs.map((c, i) => (
            <div key={i} className="flex items-center gap-1">
              {i > 0 && <ChevronRight size={12} className="text-white/50" />}
              {c.to ? (
                <Link to={c.to} className="hover:text-white">{c.label}</Link>
              ) : (
                <span className="font-semibold">{c.label}</span>
              )}
            </div>
          ))}
        </div>
      )}

      {children && (
        <div className="relative max-w-7xl mx-auto px-5 py-7">{children}</div>
      )}
    </div>
  );
}
