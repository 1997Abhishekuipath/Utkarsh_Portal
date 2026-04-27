import React, { useState, useEffect, useCallback } from "react";
import TopBar from "../components/TopBar";
import { Send, Bell, AlertCircle, CheckCircle, Users, User, Briefcase, Building } from "lucide-react";

const BACKEND = process.env.REACT_APP_BACKEND_URL;

const CATEGORIES = ["announcement","incentive","approved","replication","new_practice","award","reminder","birthday"];
const TARGET_TYPES = [
  { value: "all", label: "All Users", icon: Users },
  { value: "user", label: "Specific User", icon: User },
  { value: "role", label: "By Role", icon: Briefcase },
  { value: "department", label: "By Department", icon: Building },
];
const ROLES = ["employee","manager","admin","super_admin"];

export default function AdminNotificationsPage() {
  const [form, setForm] = useState({
    title: "", body: "", category: "announcement",
    target_type: "all", target_id: "",
    is_urgent: false, deep_link: "", send_email: false,
  });
  const [sent, setSent] = useState([]);
  const [sending, setSending] = useState(false);
  const [toast, setToast] = useState(null);

  const showToast = (msg, type = "success") => { setToast({ msg, type }); setTimeout(() => setToast(null), 3000); };

  const loadSent = useCallback(async () => {
    try {
      const res = await fetch(`${BACKEND}/api/admin/notifications?limit=30`, { credentials: "include" });
      if (res.ok) { const d = await res.json(); setSent(d); }
    } catch { /* silent */ }
  }, []);

  useEffect(() => { loadSent(); }, [loadSent]);

  const handleSend = async (e) => {
    e.preventDefault();
    setSending(true);
    try {
      const body = { ...form };
      if (body.target_type === "all") delete body.target_id;
      if (!body.target_id) delete body.target_id;
      if (!body.deep_link) delete body.deep_link;
      const res = await fetch(`${BACKEND}/api/admin/notifications/send`, {
        method: "POST", credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (res.ok) {
        showToast(`Notification sent to ${form.target_type === "all" ? "all users" : form.target_type + " target"}.`);
        setForm({ title: "", body: "", category: "announcement", target_type: "all", target_id: "", is_urgent: false, deep_link: "", send_email: false });
        loadSent();
      } else {
        const d = await res.json();
        showToast(d.detail || "Failed to send", "error");
      }
    } finally { setSending(false); }
  };

  const CATEGORY_COLORS = {
    birthday: "bg-pink-100 text-pink-700", approved: "bg-green-100 text-green-700",
    replication: "bg-blue-100 text-blue-700", announcement: "bg-gray-100 text-gray-700",
    incentive: "bg-amber-100 text-amber-700", award: "bg-purple-100 text-purple-700",
    new_practice: "bg-teal-100 text-teal-700", reminder: "bg-orange-100 text-orange-700",
  };

  return (
    <div className="min-h-screen bg-[#F1F5F9]">
      {toast && (
        <div className={`fixed top-4 right-4 z-50 px-4 py-3 rounded-lg shadow-lg text-sm font-medium flex items-center gap-2
          ${toast.type === "error" ? "bg-red-50 text-red-700 border border-red-200" : "bg-green-50 text-green-700 border border-green-200"}`}>
          {toast.type === "error" ? <AlertCircle size={16} /> : <CheckCircle size={16} />}
          {toast.msg}
        </div>
      )}
      <TopBar crumbs={[{ label: "Admin", to: "/admin" }, { label: "Notifications" }]}>
        <div>
          <h1 className="text-white text-2xl font-bold">Notification Centre</h1>
          <p className="text-white/70 text-sm mt-1">Compose and send notifications to users</p>
        </div>
      </TopBar>

      <div className="max-w-5xl mx-auto px-4 py-6 grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Compose Form */}
        <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-6">
          <h2 className="text-base font-bold text-gray-900 mb-5 flex items-center gap-2"><Send size={16} />Compose Notification</h2>
          <form onSubmit={handleSend} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold text-gray-600 mb-1">Title *</label>
              <input value={form.title} onChange={e => setForm(p => ({ ...p, title: e.target.value }))} required
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-red-200 outline-none" />
            </div>
            <div>
              <label className="block text-xs font-semibold text-gray-600 mb-1">Message *</label>
              <textarea rows={3} value={form.body} onChange={e => setForm(p => ({ ...p, body: e.target.value }))} required
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-red-200 outline-none" />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-semibold text-gray-600 mb-1">Category</label>
                <select value={form.category} onChange={e => setForm(p => ({ ...p, category: e.target.value }))}
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-red-200 outline-none">
                  {CATEGORIES.map(c => <option key={c} value={c}>{c.charAt(0).toUpperCase() + c.slice(1)}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-xs font-semibold text-gray-600 mb-1">Target</label>
                <select value={form.target_type} onChange={e => setForm(p => ({ ...p, target_type: e.target.value, target_id: "" }))}
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-red-200 outline-none">
                  {TARGET_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
                </select>
              </div>
            </div>

            {form.target_type === "role" && (
              <div>
                <label className="block text-xs font-semibold text-gray-600 mb-1">Role</label>
                <select value={form.target_id} onChange={e => setForm(p => ({ ...p, target_id: e.target.value }))}
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-red-200 outline-none">
                  <option value="">Select Role</option>
                  {ROLES.map(r => <option key={r} value={r}>{r.replace("_"," ").replace(/^./, c => c.toUpperCase())}</option>)}
                </select>
              </div>
            )}
            {form.target_type === "user" && (
              <div>
                <label className="block text-xs font-semibold text-gray-600 mb-1">User ID</label>
                <input value={form.target_id} onChange={e => setForm(p => ({ ...p, target_id: e.target.value }))}
                  placeholder="Enter user UUID"
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-red-200 outline-none" />
              </div>
            )}
            {form.target_type === "department" && (
              <div>
                <label className="block text-xs font-semibold text-gray-600 mb-1">Department</label>
                <input value={form.target_id} onChange={e => setForm(p => ({ ...p, target_id: e.target.value }))}
                  placeholder="e.g. Engineering"
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-red-200 outline-none" />
              </div>
            )}

            <div>
              <label className="block text-xs font-semibold text-gray-600 mb-1">Deep Link (optional)</label>
              <input value={form.deep_link} onChange={e => setForm(p => ({ ...p, deep_link: e.target.value }))}
                placeholder="/practices"
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-red-200 outline-none" />
            </div>

            <div className="flex items-center gap-4">
              <label className="flex items-center gap-2 cursor-pointer">
                <input type="checkbox" checked={form.is_urgent} onChange={e => setForm(p => ({ ...p, is_urgent: e.target.checked }))}
                  className="rounded border-gray-300" />
                <span className="text-xs font-medium text-red-600">Mark as Urgent</span>
              </label>
            </div>

            {/* Preview */}
            {form.title && (
              <div className={`rounded-xl p-4 border ${form.is_urgent ? "bg-red-50 border-red-200" : "bg-gray-50 border-gray-100"}`}>
                <div className="flex items-center gap-2 mb-1">
                  <span className={`text-[10px] px-2 py-0.5 rounded-full font-semibold ${CATEGORY_COLORS[form.category] || "bg-gray-100 text-gray-600"}`}>
                    {form.category}
                  </span>
                  {form.is_urgent && <span className="text-[10px] text-red-600 font-bold">URGENT</span>}
                </div>
                <div className="text-sm font-semibold text-gray-800">{form.title}</div>
                {form.body && <div className="text-xs text-gray-500 mt-1">{form.body}</div>}
              </div>
            )}

            <button type="submit" disabled={sending}
              className="w-full flex items-center justify-center gap-2 bg-[#CC0000] text-white py-2.5 rounded-xl font-semibold text-sm hover:bg-red-700 disabled:opacity-60">
              <Send size={15} />{sending ? "Sending…" : "Send Notification"}
            </button>
          </form>
        </div>

        {/* Sent Notifications */}
        <div>
          <h2 className="text-base font-bold text-gray-900 mb-4 flex items-center gap-2"><Bell size={16} />Sent Notifications</h2>
          <div className="space-y-3">
            {sent.map(n => (
              <div key={n.id} className="bg-white rounded-xl border border-gray-100 shadow-sm p-4">
                <div className="flex items-start gap-2 mb-1">
                  <span className={`text-[10px] px-2 py-0.5 rounded-full font-semibold ${CATEGORY_COLORS[n.category] || "bg-gray-100 text-gray-600"}`}>
                    {n.category}
                  </span>
                  {n.is_urgent && <span className="text-[10px] text-red-600 font-bold">URGENT</span>}
                  <span className="ml-auto text-[11px] text-gray-400">
                    {n.sent_at ? new Date(n.sent_at).toLocaleString("en-IN", { dateStyle: "short", timeStyle: "short" }) : ""}
                  </span>
                </div>
                <div className="text-sm font-semibold text-gray-800">{n.title}</div>
                <div className="text-xs text-gray-500 mt-0.5 line-clamp-2">{n.body}</div>
                <div className="mt-2 text-[11px] text-gray-400">
                  Target: <span className="font-medium text-gray-600">{n.target_type}{n.target_id ? ` → ${n.target_id}` : ""}</span>
                </div>
              </div>
            ))}
            {sent.length === 0 && <p className="text-center text-gray-400 text-sm py-8">No notifications sent yet.</p>}
          </div>
        </div>
      </div>
    </div>
  );
}
