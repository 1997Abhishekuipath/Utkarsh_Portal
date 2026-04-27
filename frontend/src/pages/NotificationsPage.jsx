import React, { useState, useEffect, useCallback } from "react";
import TopBar from "../components/TopBar";
import { Bell, CheckCircle, Trash2 } from "lucide-react";

const BACKEND = process.env.REACT_APP_BACKEND_URL;

const CATEGORY_COLORS = {
  birthday: "bg-pink-100 text-pink-700",
  approved: "bg-green-100 text-green-700",
  replication: "bg-blue-100 text-blue-700",
  announcement: "bg-gray-100 text-gray-700",
  incentive: "bg-amber-100 text-amber-700",
  award: "bg-purple-100 text-purple-700",
  new_practice: "bg-teal-100 text-teal-700",
  reminder: "bg-orange-100 text-orange-700",
};

export default function NotificationsPage() {
  const [notifs, setNotifs] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [unreadOnly, setUnreadOnly] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const url = `${BACKEND}/api/notifications?limit=50${unreadOnly ? "&unread_only=true" : ""}`;
      const res = await fetch(url, { credentials: "include" });
      if (res.ok) { const d = await res.json(); setNotifs(d.items || []); setTotal(d.total || 0); }
    } finally { setLoading(false); }
  }, [unreadOnly]);

  useEffect(() => { load(); }, [load]);

  const markRead = async (id) => {
    await fetch(`${BACKEND}/api/notifications/${id}/read`, { method: "PUT", credentials: "include" });
    setNotifs(prev => prev.map(n => n.id === id ? { ...n, is_read: true } : n));
  };

  const markAllRead = async () => {
    await fetch(`${BACKEND}/api/notifications/read-all`, { method: "PUT", credentials: "include" });
    setNotifs(prev => prev.map(n => ({ ...n, is_read: true })));
  };

  const unreadCount = notifs.filter(n => !n.is_read).length;

  return (
    <div className="min-h-screen bg-[#F1F5F9]">
      <TopBar crumbs={[{ label: "Home", to: "/" }, { label: "Notifications" }]}>
        <div className="flex items-end justify-between">
          <div>
            <h1 className="text-white text-2xl font-bold">Notifications</h1>
            <p className="text-white/70 text-sm mt-1">{total} total &middot; {unreadCount} unread</p>
          </div>
        </div>
      </TopBar>

      <div className="max-w-3xl mx-auto px-4 py-6">
        <div className="flex items-center justify-between mb-5">
          <div className="flex items-center gap-2">
            <button onClick={() => setUnreadOnly(false)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${!unreadOnly ? "bg-[#CC0000] text-white" : "bg-white text-gray-500 border border-gray-200"}`}>
              All
            </button>
            <button onClick={() => setUnreadOnly(true)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${unreadOnly ? "bg-[#CC0000] text-white" : "bg-white text-gray-500 border border-gray-200"}`}>
              Unread {unreadCount > 0 && `(${unreadCount})`}
            </button>
          </div>
          {unreadCount > 0 && (
            <button onClick={markAllRead}
              className="flex items-center gap-1.5 text-xs text-[#CC0000] hover:underline font-medium">
              <CheckCircle size={13} />Mark all read
            </button>
          )}
        </div>

        {loading && <div className="text-center py-12 text-gray-400">Loading…</div>}
        {!loading && notifs.length === 0 && (
          <div className="text-center py-16">
            <Bell size={48} className="text-gray-200 mx-auto mb-3" />
            <p className="text-gray-500 text-sm">No notifications yet</p>
          </div>
        )}

        <div className="space-y-2">
          {notifs.map(n => (
            <div key={n.id}
              onClick={() => !n.is_read && markRead(n.id)}
              className={`bg-white rounded-xl border border-gray-100 shadow-sm p-4 cursor-pointer hover:shadow-md transition-all
                ${!n.is_read ? "border-l-4 border-l-[#CC0000] bg-red-50/30" : ""}`}>
              <div className="flex items-start gap-3">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap mb-1.5">
                    <span className={`text-[10px] px-2 py-0.5 rounded-full font-semibold ${CATEGORY_COLORS[n.category] || "bg-gray-100 text-gray-600"}`}>
                      {n.category || "notification"}
                    </span>
                    {n.is_urgent && <span className="text-[10px] text-red-600 font-bold uppercase">Urgent</span>}
                    {!n.is_read && <div className="w-2 h-2 rounded-full bg-[#CC0000]" />}
                  </div>
                  <div className="text-sm font-semibold text-gray-900">{n.title}</div>
                  <div className="text-xs text-gray-500 mt-1 leading-relaxed">{n.body}</div>
                </div>
                <div className="text-[11px] text-gray-400 flex-shrink-0">
                  {n.delivered_at ? new Date(n.delivered_at).toLocaleString("en-IN", { dateStyle: "short", timeStyle: "short" }) : ""}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
