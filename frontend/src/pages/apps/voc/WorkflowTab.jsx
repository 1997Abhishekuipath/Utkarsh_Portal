import React, { useState, useEffect, useMemo } from "react";
import axios from "axios";
import { API } from "../../../contexts/AuthContext";
import {
  Loader2, AlertTriangle, Building2, User, Mail, X,
  CheckCircle2, Clock, PlayCircle, ChevronDown, ListTodo,
} from "lucide-react";

const authHeader = () => ({ Authorization: `Bearer ${localStorage.getItem("hsi_token")}` });

const COLUMNS = [
  { key: "open",         label: "Open",        icon: Clock,        text: "text-rose-700",   bg: "bg-rose-50",    border: "border-rose-200" },
  { key: "in_progress",  label: "In Progress", icon: PlayCircle,   text: "text-amber-700",  bg: "bg-amber-50",   border: "border-amber-200" },
  { key: "resolved",     label: "Resolved",    icon: CheckCircle2, text: "text-emerald-700",bg: "bg-emerald-50", border: "border-emerald-200" },
];

const SENT_BADGE = {
  detractor: { text: "text-rose-700",    bg: "bg-rose-100" },
  passive:   { text: "text-amber-700",   bg: "bg-amber-100" },
  promoter:  { text: "text-emerald-700", bg: "bg-emerald-100" },
};

export default function WorkflowTab() {
  const [tasks,   setTasks]   = useState([]);
  const [stats,   setStats]   = useState({ open: 0, in_progress: 0, resolved: 0, total: 0 });
  const [loading, setLoading] = useState(true);
  const [error,   setError]   = useState(null);
  const [filterAccount, setFilterAccount] = useState("");
  const [accounts, setAccounts] = useState([]);
  const [editing, setEditing] = useState(null);  // task being edited in modal
  const [saving,  setSaving]  = useState(false);
  const [notes,   setNotes]   = useState("");
  const [newStatus, setNewStatus] = useState("open");

  const load = async () => {
    try {
      const [t, s, a] = await Promise.all([
        axios.get(`${API}/voc/workflow/tasks`,
          { headers: authHeader(), params: filterAccount ? { account_id: filterAccount } : {} }),
        axios.get(`${API}/voc/workflow/stats`, { headers: authHeader() }),
        axios.get(`${API}/voc/accounts`, { headers: authHeader() }),
      ]);
      setTasks(t.data || []);
      setStats(s.data || {});
      setAccounts(a.data?.accounts || []);
    } catch (e) {
      setError("Failed to load workflow tasks");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); /* eslint-disable-line */ }, [filterAccount]);

  const grouped = useMemo(() => {
    const out = { open: [], in_progress: [], resolved: [] };
    tasks.forEach(t => { if (out[t.status]) out[t.status].push(t); });
    return out;
  }, [tasks]);

  const openEdit = (t) => {
    setEditing(t);
    setNotes(t.resolution_notes || "");
    setNewStatus(t.status);
    setError(null);
  };

  const handleSave = async () => {
    if (!editing) return;
    setSaving(true); setError(null);

    // Optimistic update — apply changes locally before API call
    const prevTasks = tasks;
    const prevStats = stats;
    const oldStatus = editing.status;
    const updatedTask = {
      ...editing,
      status: newStatus,
      resolution_notes: notes,
      resolved_at: newStatus === "resolved" ? new Date().toISOString() : null,
    };
    setTasks(ts => ts.map(t => t.id === editing.id ? updatedTask : t));
    if (oldStatus !== newStatus) {
      setStats(s => ({
        ...s,
        [oldStatus]: Math.max(0, (s[oldStatus] || 0) - 1),
        [newStatus]: (s[newStatus] || 0) + 1,
      }));
    }
    setEditing(null);

    try {
      await axios.patch(`${API}/voc/workflow/tasks/${editing.id}`,
        { status: newStatus, resolution_notes: notes },
        { headers: authHeader() });
    } catch (e) {
      // Rollback on failure
      setTasks(prevTasks);
      setStats(prevStats);
      setError(e?.response?.data?.detail || "Failed to update task");
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 size={28} className="animate-spin text-[#CC0000]" />
      </div>
    );
  }

  return (
    <main className="max-w-screen-2xl mx-auto px-6 py-6" data-testid="workflow-tab">

      {/* Header */}
      <div className="flex items-start justify-between mb-6 gap-4 flex-wrap">
        <div>
          <h2 className="text-2xl font-bold text-[#0F172A] font-['Outfit'] flex items-center gap-2">
            <ListTodo size={20} className="text-[#CC0000]" />Detractor Workflow
          </h2>
          <p className="text-[#64748B] text-sm mt-1">
            Follow-up tasks auto-created from NPS ≤ 6 responses · {stats.total || 0} total ·
            <span className="text-rose-700 font-semibold ml-1">{stats.open || 0} open</span>
            <span className="text-amber-700 font-semibold ml-2">{stats.in_progress || 0} in progress</span>
            <span className="text-emerald-700 font-semibold ml-2">{stats.resolved || 0} resolved</span>
          </p>
        </div>

        <div>
          <label className="block text-[10px] font-bold tracking-wider text-[#64748B] mb-1">FILTER ACCOUNT</label>
          <div className="relative">
            <Building2 size={12} className="absolute left-3 top-1/2 -translate-y-1/2 text-[#94A3B8] pointer-events-none" />
            <select value={filterAccount} onChange={e => setFilterAccount(e.target.value)}
              className="pl-8 pr-7 py-2 text-xs border-2 border-[#E2E8F0] rounded-lg focus:border-[#CC0000] focus:outline-none bg-white appearance-none w-56"
              data-testid="workflow-account-filter">
              <option value="">All accounts</option>
              {accounts.map(a => <option key={a.id} value={a.id}>{a.company_name}</option>)}
            </select>
            <ChevronDown size={12} className="absolute right-3 top-1/2 -translate-y-1/2 text-[#94A3B8] pointer-events-none" />
          </div>
        </div>
      </div>

      {error && (
        <div className="mb-4 px-4 py-3 bg-rose-50 border border-rose-200 rounded-lg text-sm text-rose-700"
          data-testid="workflow-error">{error}</div>
      )}

      {tasks.length === 0 ? (
        <div className="flex items-center justify-center h-64 border-2 border-dashed border-[#E2E8F0] rounded-xl"
          data-testid="workflow-empty">
          <div className="text-center">
            <CheckCircle2 size={32} className="text-emerald-500 mx-auto mb-3" />
            <p className="text-sm text-[#64748B]">No detractor tasks. Great job!</p>
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-3 gap-4">
          {COLUMNS.map(col => {
            const Icon = col.icon;
            const items = grouped[col.key] || [];
            return (
              <div key={col.key} className={`rounded-xl ${col.bg} border ${col.border}`}
                data-testid={`workflow-col-${col.key}`}>
                <div className={`flex items-center justify-between px-4 py-3 border-b ${col.border}`}>
                  <div className={`flex items-center gap-2 text-xs font-bold tracking-wider ${col.text}`}>
                    <Icon size={14} />{col.label.toUpperCase()}
                  </div>
                  <span className={`text-[11px] font-bold ${col.text}`}>{items.length}</span>
                </div>
                <div className="p-3 space-y-3 min-h-[200px]">
                  {items.length === 0 ? (
                    <p className="text-[11px] text-[#94A3B8] italic text-center py-4">No tasks</p>
                  ) : items.map(t => {
                    const r = t.response || {};
                    const sb = SENT_BADGE[r.sentiment] || SENT_BADGE.passive;
                    return (
                      <button key={t.id}
                        onClick={() => openEdit(t)}
                        data-testid={`workflow-task-${t.id}`}
                        className="w-full text-left bg-white rounded-lg border border-[#E2E8F0] p-3 shadow-sm hover:shadow-md hover:border-[#CC0000]/30 transition-all">
                        <div className="flex items-start justify-between mb-2 gap-2">
                          <div className="text-xs font-bold text-[#0F172A] flex items-center gap-1.5">
                            <Building2 size={11} className="text-[#94A3B8]" />
                            {t.account_name || "—"}
                          </div>
                          {r.sentiment && (
                            <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded ${sb.bg} ${sb.text}`}>
                              NPS {r.nps ?? "—"}
                            </span>
                          )}
                        </div>
                        {r.verbatim && (
                          <p className="text-[11px] text-[#475569] mb-2 line-clamp-3 italic">"{r.verbatim}"</p>
                        )}
                        {r.pain_tags && r.pain_tags.length > 0 && (
                          <div className="flex flex-wrap gap-1 mb-2">
                            {r.pain_tags.slice(0, 3).map((tag, i) => (
                              <span key={i} className="text-[9px] font-semibold px-1.5 py-0.5 rounded bg-[#F1F5F9] text-[#475569]">
                                {tag}
                              </span>
                            ))}
                          </div>
                        )}
                        <div className="flex items-center justify-between text-[10px] text-[#94A3B8] pt-2 border-t border-[#F1F5F9]">
                          <span className="flex items-center gap-1 truncate max-w-[60%]">
                            <Mail size={9} />{r.respondent_email || "—"}
                          </span>
                          {t.assignee_name && (
                            <span className="flex items-center gap-1">
                              <User size={9} />{t.assignee_name}
                            </span>
                          )}
                        </div>
                        {t.resolution_notes && (
                          <div className="mt-2 px-2 py-1.5 rounded bg-emerald-50 text-[10px] text-emerald-800">
                            <span className="font-bold">Note:</span> {t.resolution_notes}
                          </div>
                        )}
                      </button>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Edit Modal */}
      {editing && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4"
          data-testid="workflow-edit-modal">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg">
            <div className="flex items-start justify-between px-6 pt-6 pb-4 border-b border-[#E2E8F0]">
              <div>
                <div className="text-[10px] font-bold tracking-widest text-[#64748B] uppercase mb-1">Detractor Follow-up</div>
                <h3 className="text-base font-bold text-[#0F172A]">{editing.account_name || "Account"}</h3>
                <p className="text-xs text-[#64748B] mt-0.5">{editing.response?.respondent_email || "—"}</p>
              </div>
              <button onClick={() => setEditing(null)} className="text-[#94A3B8] hover:text-[#0F172A]" data-testid="workflow-modal-close">
                <X size={18} />
              </button>
            </div>

            <div className="px-6 py-5 space-y-4">
              {editing.response?.verbatim && (
                <div className="bg-[#F8FAFC] rounded-lg px-4 py-3">
                  <div className="text-[10px] font-bold tracking-widest text-[#64748B] uppercase mb-1">Verbatim</div>
                  <p className="text-sm text-[#0F172A] italic">"{editing.response.verbatim}"</p>
                  <div className="flex items-center gap-3 mt-2 text-[10px] text-[#64748B]">
                    {editing.response.nps !== null && <span>NPS: <strong>{editing.response.nps}</strong></span>}
                    {editing.response.csat !== null && <span>· CSAT: <strong>{editing.response.csat}</strong></span>}
                    {editing.response.sentiment && <span>· {editing.response.sentiment}</span>}
                  </div>
                </div>
              )}

              <div>
                <label className="block text-[10px] font-bold tracking-widest text-[#64748B] uppercase mb-2">Status</label>
                <div className="grid grid-cols-3 gap-2">
                  {COLUMNS.map(c => (
                    <button key={c.key}
                      onClick={() => setNewStatus(c.key)}
                      data-testid={`workflow-status-${c.key}`}
                      className={`px-3 py-2 rounded-lg text-xs font-bold border-2 transition-all ${
                        newStatus === c.key
                          ? `${c.bg} ${c.text} ${c.border}`
                          : "bg-white border-[#E2E8F0] text-[#64748B] hover:border-[#94A3B8]"
                      }`}>
                      {c.label}
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <label className="block text-[10px] font-bold tracking-widest text-[#64748B] uppercase mb-2">Resolution Notes</label>
                <textarea value={notes} onChange={e => setNotes(e.target.value)}
                  rows={4} placeholder="Reached out to CSM, scheduling QBR for next week…"
                  className="w-full px-3 py-2.5 text-sm border-2 border-[#E2E8F0] rounded-lg focus:border-[#CC0000] focus:outline-none resize-none"
                  data-testid="workflow-notes-input" />
              </div>

              {error && <p className="text-xs text-rose-600">{error}</p>}

              <div className="flex gap-3">
                <button onClick={handleSave} disabled={saving}
                  className="flex-1 flex items-center justify-center gap-2 py-2.5 rounded-lg text-sm font-bold text-white bg-[#CC0000] hover:bg-[#AA0000] disabled:opacity-60 transition-colors"
                  data-testid="workflow-save-btn">
                  {saving ? <Loader2 size={14} className="animate-spin" /> : <CheckCircle2 size={14} />}
                  {saving ? "Saving…" : "Save Changes"}
                </button>
                <button onClick={() => setEditing(null)}
                  className="px-5 py-2.5 rounded-lg text-sm font-bold text-[#64748B] border border-[#E2E8F0] hover:text-[#0F172A] transition-colors">
                  Cancel
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}
