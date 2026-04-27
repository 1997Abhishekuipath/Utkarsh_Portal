import React, { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import TopBar from "../components/TopBar";
import {
  Plus, Search, Filter, Star, Copy, ChevronRight, X, CheckCircle,
  Clock, AlertCircle, Zap, BookOpen, Users, TrendingUp, Award
} from "lucide-react";
import { useAuth } from "../contexts/AuthContext";

const BACKEND = process.env.REACT_APP_BACKEND_URL;

const DIFFICULTY_COLORS = {
  easy: "bg-green-100 text-green-700 border-green-200",
  medium: "bg-blue-100 text-blue-700 border-blue-200",
  hard: "bg-orange-100 text-orange-700 border-orange-200",
  expert: "bg-purple-100 text-purple-700 border-purple-200",
};
const STATUS_COLORS = {
  pending:  "bg-yellow-100 text-yellow-700",
  approved: "bg-green-100 text-green-700",
  rejected: "bg-red-100 text-red-700",
  draft:    "bg-gray-100 text-gray-600",
};
const PILLAR_COLORS = {
  customer:    "bg-blue-50 text-blue-700",
  innovator:   "bg-purple-50 text-purple-700",
  employee:    "bg-green-50 text-green-700",
  shareholder: "bg-amber-50 text-amber-700",
};
const ART_LABELS = { accelerate: "⚡ Accelerate (1.2×)", retain: "🔵 Retain (1.0×)", transform: "🚀 Transform (1.5×)" };
const XP_MATRIX = {
  original_practice: { easy: 80, medium: 100, hard: 120, expert: 130 },
};
const ART_MULT = { accelerate: 1.2, retain: 1.0, transform: 1.5 };

export default function PracticesPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [tab, setTab] = useState("all"); // all | mine | submit
  const [practices, setPractices] = useState([]);
  const [myPractices, setMyPractices] = useState([]);
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState("");
  const [filterPillar, setFilterPillar] = useState("");
  const [selected, setSelected] = useState(null);
  const [showSubmit, setShowSubmit] = useState(false);
  const [showReplication, setShowReplication] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [toast, setToast] = useState(null);

  // Form state
  const [form, setForm] = useState({
    title: "", summary: "", why_content: "", how_content: "",
    what_content: "", impact_content: "",
    difficulty: "medium", pillar: "customer", art_tag: "retain",
    tags: "", status: "pending",
  });
  const [repForm, setRepForm] = useState({ client_name: "", po_number: "", po_value_inr: "", notes: "" });

  const showToast = (msg, type = "success") => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 3500);
  };

  const fetchPractices = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`${BACKEND}/api/practices?status=approved&limit=50`, { credentials: "include" });
      if (res.ok) { const d = await res.json(); setPractices(d.items || []); }
    } finally { setLoading(false); }
  }, []);

  const fetchMine = useCallback(async () => {
    try {
      const res = await fetch(`${BACKEND}/api/practices?status=mine&limit=50`, { credentials: "include" });
      if (res.ok) { const d = await res.json(); setMyPractices(d.items || []); }
    } catch { /* silent */ }
  }, []);

  useEffect(() => { fetchPractices(); fetchMine(); }, [fetchPractices, fetchMine]);

  const calcXP = (difficulty, art_tag) => {
    const base = XP_MATRIX.original_practice[difficulty] || 100;
    const mult = ART_MULT[art_tag] || 1.0;
    return Math.round(base * mult);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      const body = { ...form, tags: form.tags ? form.tags.split(",").map(t => t.trim()).filter(Boolean) : [] };
      const res = await fetch(`${BACKEND}/api/practices`, {
        method: "POST", credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (res.ok) {
        showToast("Practice submitted! It will be reviewed by an admin.");
        setShowSubmit(false);
        setForm({ title: "", summary: "", why_content: "", how_content: "", what_content: "", impact_content: "", difficulty: "medium", pillar: "customer", art_tag: "retain", tags: "", status: "pending" });
        fetchMine();
        setTab("mine");
      } else {
        const d = await res.json();
        showToast(d.detail || "Failed to submit", "error");
      }
    } finally { setSubmitting(false); }
  };

  const handleReplication = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      const res = await fetch(`${BACKEND}/api/replications`, {
        method: "POST", credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ practice_id: showReplication.id, ...repForm }),
      });
      if (res.ok) {
        showToast("Replication submitted for approval!");
        setShowReplication(null);
        setRepForm({ client_name: "", po_number: "", po_value_inr: "", notes: "" });
      } else {
        const d = await res.json();
        showToast(d.detail || "Failed", "error");
      }
    } finally { setSubmitting(false); }
  };

  const filtered = (tab === "mine" ? myPractices : practices).filter(p => {
    const s = search.toLowerCase();
    const matchSearch = !s || p.title?.toLowerCase().includes(s) || p.summary?.toLowerCase().includes(s);
    const matchPillar = !filterPillar || p.pillar === filterPillar;
    return matchSearch && matchPillar;
  });

  const FormField = ({ label, name, type = "text", required, component = "input", rows = 3, options }) => (
    <div>
      <label className="block text-xs font-semibold text-gray-600 mb-1">{label}{required && " *"}</label>
      {component === "textarea" ? (
        <textarea rows={rows} value={form[name]} onChange={e => setForm(p => ({ ...p, [name]: e.target.value }))}
          className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-red-200 focus:border-red-400 outline-none" required={required} />
      ) : component === "select" ? (
        <select value={form[name]} onChange={e => setForm(p => ({ ...p, [name]: e.target.value }))}
          className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-red-200 focus:border-red-400 outline-none">
          {options.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select>
      ) : (
        <input type={type} value={form[name]} onChange={e => setForm(p => ({ ...p, [name]: e.target.value }))}
          className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-red-200 focus:border-red-400 outline-none" required={required} />
      )}
    </div>
  );

  return (
    <div className="min-h-screen bg-[#F1F5F9]">
      {toast && (
        <div className={`fixed top-4 right-4 z-50 px-4 py-3 rounded-lg shadow-lg text-sm font-medium flex items-center gap-2
          ${toast.type === "error" ? "bg-red-50 text-red-700 border border-red-200" : "bg-green-50 text-green-700 border border-green-200"}`}>
          {toast.type === "error" ? <AlertCircle size={16} /> : <CheckCircle size={16} />}
          {toast.msg}
        </div>
      )}

      <TopBar crumbs={[{ label: "Home", to: "/" }, { label: "Best Practices" }]}>
        <div className="flex items-end justify-between">
          <div>
            <h1 className="text-white text-2xl font-bold">Best Practices</h1>
            <p className="text-white/70 text-sm mt-1">Share and discover proven solutions across HSI</p>
          </div>
          <button onClick={() => setShowSubmit(true)}
            className="flex items-center gap-2 bg-white text-[#CC0000] px-4 py-2 rounded-lg text-sm font-semibold hover:bg-white/90 shadow transition-all">
            <Plus size={16} /> Submit Practice
          </button>
        </div>
      </TopBar>

      <div className="max-w-7xl mx-auto px-4 py-6">
        {/* Tabs */}
        <div className="flex gap-1 bg-white rounded-xl p-1 shadow-sm border border-gray-100 w-fit mb-5">
          {[["all", "All Approved", BookOpen], ["mine", "My Submissions", Users]].map(([id, label, Icon]) => (
            <button key={id} onClick={() => setTab(id)}
              className={`flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium transition-all
                ${tab === id ? "bg-[#CC0000] text-white shadow-sm" : "text-gray-500 hover:text-gray-700"}`}>
              <Icon size={14} />{label}
            </button>
          ))}
        </div>

        {/* Search + Filter */}
        <div className="flex flex-col sm:flex-row gap-3 mb-6">
          <div className="relative flex-1">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
            <input placeholder="Search practices…" value={search} onChange={e => setSearch(e.target.value)}
              className="w-full pl-9 pr-3 py-2.5 border border-gray-200 rounded-xl text-sm bg-white shadow-sm focus:ring-2 focus:ring-red-100 outline-none" />
          </div>
          <select value={filterPillar} onChange={e => setFilterPillar(e.target.value)}
            className="border border-gray-200 rounded-xl px-3 py-2.5 text-sm bg-white shadow-sm focus:ring-2 focus:ring-red-100 outline-none">
            <option value="">All Pillars</option>
            {["customer", "innovator", "employee", "shareholder"].map(p => (
              <option key={p} value={p}>{p.charAt(0).toUpperCase() + p.slice(1)}</option>
            ))}
          </select>
        </div>

        {/* Cards */}
        {loading && <div className="text-center py-16 text-gray-400">Loading practices…</div>}
        {!loading && filtered.length === 0 && (
          <div className="text-center py-16">
            <BookOpen size={48} className="text-gray-200 mx-auto mb-3" />
            <p className="text-gray-500 text-sm">
              {tab === "mine" ? "You haven't submitted any practices yet." : "No approved practices found."}
            </p>
            <button onClick={() => setShowSubmit(true)}
              className="mt-4 bg-[#CC0000] text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-red-700">
              Submit First Practice
            </button>
          </div>
        )}
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {filtered.map(p => (
            <div key={p.id} className="bg-white rounded-xl border border-gray-100 shadow-sm hover:shadow-md transition-all cursor-pointer group"
              onClick={() => setSelected(p)}>
              <div className="p-5">
                <div className="flex items-start justify-between mb-3">
                  <div className="flex flex-wrap gap-1.5">
                    {p.pillar && (
                      <span className={`text-[10px] px-2 py-0.5 rounded-full font-medium border ${PILLAR_COLORS[p.pillar] || "bg-gray-50 text-gray-600"}`}>
                        {p.pillar}
                      </span>
                    )}
                    {p.difficulty && (
                      <span className={`text-[10px] px-2 py-0.5 rounded-full font-medium border ${DIFFICULTY_COLORS[p.difficulty] || ""}`}>
                        {p.difficulty}
                      </span>
                    )}
                    {tab === "mine" && (
                      <span className={`text-[10px] px-2 py-0.5 rounded-full font-medium ${STATUS_COLORS[p.status] || ""}`}>
                        {p.status}
                      </span>
                    )}
                  </div>
                  {p.is_featured && <Star size={14} className="text-amber-400 flex-shrink-0" />}
                </div>
                <h3 className="text-sm font-semibold text-gray-900 leading-snug mb-2 line-clamp-2 group-hover:text-[#CC0000] transition-colors">
                  {p.title}
                </h3>
                <p className="text-xs text-gray-500 line-clamp-2 mb-4">{p.summary}</p>
                <div className="flex items-center justify-between text-xs text-gray-400">
                  <span className="font-medium">{p.author_name}</span>
                  <div className="flex items-center gap-3">
                    {p.xp_awarded > 0 && (
                      <span className="flex items-center gap-1 text-amber-600 font-semibold">
                        <Zap size={11} />+{p.xp_awarded} XP
                      </span>
                    )}
                    {p.replication_cnt > 0 && (
                      <span className="flex items-center gap-1 text-blue-600">
                        <Copy size={11} />{p.replication_cnt}
                      </span>
                    )}
                    <ChevronRight size={14} className="text-gray-300 group-hover:text-[#CC0000] transition-colors" />
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Practice Detail Modal */}
      {selected && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto">
            <div className="flex items-start justify-between p-6 border-b border-gray-100">
              <div>
                <div className="flex flex-wrap gap-2 mb-2">
                  {selected.pillar && <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${PILLAR_COLORS[selected.pillar] || "bg-gray-100 text-gray-600"}`}>{selected.pillar}</span>}
                  {selected.difficulty && <span className={`text-xs px-2 py-0.5 rounded-full font-medium border ${DIFFICULTY_COLORS[selected.difficulty]}`}>{selected.difficulty}</span>}
                  {selected.art_tag && <span className="text-xs px-2 py-0.5 rounded-full bg-indigo-50 text-indigo-700 font-medium">{ART_LABELS[selected.art_tag] || selected.art_tag}</span>}
                </div>
                <h2 className="text-lg font-bold text-gray-900">{selected.title}</h2>
                <p className="text-sm text-gray-500 mt-0.5">by {selected.author_name}</p>
              </div>
              <button onClick={() => setSelected(null)} className="text-gray-400 hover:text-gray-600 p-1 rounded-lg hover:bg-gray-100">
                <X size={20} />
              </button>
            </div>
            <div className="p-6 space-y-5">
              {[["Summary", selected.summary], ["Why", selected.why_content],
                ["How", selected.how_content], ["What", selected.what_content],
                ["Impact", selected.impact_content]].map(([label, val]) =>
                val ? (
                  <div key={label}>
                    <h4 className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-1.5">{label}</h4>
                    <p className="text-sm text-gray-700 leading-relaxed">{val}</p>
                  </div>
                ) : null
              )}
              {selected.tags?.length > 0 && (
                <div className="flex flex-wrap gap-1.5">
                  {selected.tags.map(t => (
                    <span key={t} className="text-xs px-2 py-0.5 bg-gray-100 text-gray-600 rounded-full">{t}</span>
                  ))}
                </div>
              )}
              <div className="flex items-center justify-between pt-3 border-t border-gray-100">
                <div className="flex items-center gap-4 text-sm">
                  {selected.xp_awarded > 0 && (
                    <span className="flex items-center gap-1 text-amber-600 font-semibold">
                      <Zap size={14} />+{selected.xp_awarded} XP awarded
                    </span>
                  )}
                  {selected.replication_cnt > 0 && (
                    <span className="text-blue-600 flex items-center gap-1">
                      <Copy size={14} />{selected.replication_cnt} replications
                    </span>
                  )}
                </div>
                {selected.status === "approved" && selected.author_id !== user?.id && (
                  <button onClick={() => { setShowReplication(selected); setSelected(null); }}
                    className="flex items-center gap-1.5 bg-[#CC0000] text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-red-700 transition-colors">
                    <Copy size={14} />Replicate
                  </button>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Submit Practice Modal */}
      {showSubmit && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl max-h-[92vh] overflow-y-auto">
            <div className="flex items-center justify-between p-6 border-b border-gray-100">
              <h2 className="text-lg font-bold text-gray-900">Submit Best Practice</h2>
              <button onClick={() => setShowSubmit(false)} className="text-gray-400 hover:text-gray-600 p-1 rounded-lg hover:bg-gray-100"><X size={20} /></button>
            </div>
            <form onSubmit={handleSubmit} className="p-6 space-y-4">
              <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 text-xs text-amber-700 flex items-center gap-2">
                <Zap size={14} />
                Estimated XP: <strong>+{calcXP(form.difficulty, form.art_tag)} XP</strong> ({form.art_tag} multiplier {ART_MULT[form.art_tag]}×)
              </div>
              <FormField label="Title" name="title" required />
              <FormField label="Summary (1-2 sentences)" name="summary" component="textarea" rows={2} required />
              <div className="grid grid-cols-3 gap-3">
                <FormField label="Difficulty" name="difficulty" component="select"
                  options={[{value:"easy",label:"Easy (80 XP)"},{value:"medium",label:"Medium (100 XP)"},{value:"hard",label:"Hard (120 XP)"},{value:"expert",label:"Expert (130 XP)"}]} />
                <FormField label="Pillar" name="pillar" component="select"
                  options={["customer","innovator","employee","shareholder"].map(v => ({value:v,label:v.charAt(0).toUpperCase()+v.slice(1)}))} />
                <FormField label="ART Tag" name="art_tag" component="select"
                  options={[{value:"accelerate",label:"Accelerate (1.2×)"},{value:"retain",label:"Retain (1.0×)"},{value:"transform",label:"Transform (1.5×)"}]} />
              </div>
              <FormField label="Why? (Problem / Opportunity)" name="why_content" component="textarea" rows={2} />
              <FormField label="How? (Step-by-step approach)" name="how_content" component="textarea" rows={2} />
              <FormField label="What? (Deliverables / Tools used)" name="what_content" component="textarea" rows={2} />
              <FormField label="Impact (Measurable outcomes)" name="impact_content" component="textarea" rows={2} />
              <FormField label="Tags (comma-separated)" name="tags" />
              <div className="flex justify-end gap-3 pt-2">
                <button type="button" onClick={() => setShowSubmit(false)} className="px-4 py-2 text-sm text-gray-600 border border-gray-200 rounded-lg hover:bg-gray-50">Cancel</button>
                <button type="submit" disabled={submitting}
                  className="flex items-center gap-2 px-5 py-2 bg-[#CC0000] text-white rounded-lg text-sm font-semibold hover:bg-red-700 disabled:opacity-60">
                  {submitting ? "Submitting…" : "Submit Practice"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Replication Modal */}
      {showReplication && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg">
            <div className="flex items-center justify-between p-6 border-b border-gray-100">
              <div>
                <h2 className="text-lg font-bold text-gray-900">Submit Replication</h2>
                <p className="text-xs text-gray-500 mt-0.5">"{showReplication.title}"</p>
              </div>
              <button onClick={() => setShowReplication(null)} className="text-gray-400 hover:text-gray-600 p-1 rounded-lg hover:bg-gray-100"><X size={20} /></button>
            </div>
            <form onSubmit={handleReplication} className="p-6 space-y-4">
              <div>
                <label className="block text-xs font-semibold text-gray-600 mb-1">Client Name *</label>
                <input value={repForm.client_name} onChange={e => setRepForm(p => ({ ...p, client_name: e.target.value }))} required
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-red-200 outline-none" />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-gray-600 mb-1">PO Number (if closed)</label>
                  <input value={repForm.po_number} onChange={e => setRepForm(p => ({ ...p, po_number: e.target.value }))}
                    className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-red-200 outline-none" />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-gray-600 mb-1">PO Value (₹)</label>
                  <input value={repForm.po_value_inr} onChange={e => setRepForm(p => ({ ...p, po_value_inr: e.target.value }))}
                    className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-red-200 outline-none" />
                </div>
              </div>
              <div>
                <label className="block text-xs font-semibold text-gray-600 mb-1">Notes</label>
                <textarea value={repForm.notes} onChange={e => setRepForm(p => ({ ...p, notes: e.target.value }))} rows={2}
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-red-200 outline-none" />
              </div>
              <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 text-xs text-blue-700">
                <strong>XP earned:</strong> With PO = up to 195 XP | Without PO = up to 150 XP
              </div>
              <div className="flex justify-end gap-3">
                <button type="button" onClick={() => setShowReplication(null)} className="px-4 py-2 text-sm text-gray-600 border border-gray-200 rounded-lg hover:bg-gray-50">Cancel</button>
                <button type="submit" disabled={submitting}
                  className="flex items-center gap-2 px-5 py-2 bg-[#CC0000] text-white rounded-lg text-sm font-semibold hover:bg-red-700 disabled:opacity-60">
                  {submitting ? "Submitting…" : "Submit Replication"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
