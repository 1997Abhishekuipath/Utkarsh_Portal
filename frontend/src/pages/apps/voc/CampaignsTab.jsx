import React, { useState, useEffect } from "react";
import axios from "axios";
import { API } from "../../../contexts/AuthContext";
import {
  Plus, Send, ExternalLink, Copy, CheckCircle2, Loader2,
  Clock, BarChart2, ChevronDown, X, Mail, Users,
} from "lucide-react";

const authHeader = () => ({ Authorization: `Bearer ${localStorage.getItem("hsi_token")}` });

const STATUS_META = {
  draft:     { label: "DRAFT",     bg: "bg-slate-100",   text: "text-slate-600" },
  scheduled: { label: "SCHEDULED", bg: "bg-blue-50",     text: "text-blue-700" },
  sending:   { label: "SENDING",   bg: "bg-amber-50",    text: "text-amber-700" },
  active:    { label: "ACTIVE",    bg: "bg-emerald-50",  text: "text-emerald-700" },
  closed:    { label: "CLOSED",    bg: "bg-slate-100",   text: "text-slate-500" },
};

const CopyBtn = ({ text }) => {
  const [copied, setCopied] = useState(false);
  const copy = () => {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true); setTimeout(() => setCopied(false), 2000);
    });
  };
  return (
    <button onClick={copy} className="ml-2 text-[#64748B] hover:text-[#CC0000] transition-colors">
      {copied ? <CheckCircle2 size={13} className="text-emerald-600" /> : <Copy size={13} />}
    </button>
  );
};

export default function CampaignsTab() {
  const [campaigns,   setCampaigns]   = useState([]);
  const [surveys,     setSurveys]     = useState([]);
  const [accounts,    setAccounts]    = useState([]);
  const [loading,     setLoading]     = useState(true);
  const [showForm,    setShowForm]    = useState(false);
  const [sendModal,   setSendModal]   = useState(null);
  const [sending,     setSending]     = useState(false);
  const [sentLinks,   setSentLinks]   = useState(null);
  const [creating,    setCreating]    = useState(false);
  const [error,       setError]       = useState(null);
  const [recipients,  setRecipients]  = useState("");

  const [form, setForm] = useState({
    name: "", survey_id: "", account_id: "", subject: "",
  });

  const loadData = async () => {
    const h = authHeader();
    try {
      const [c, s, a] = await Promise.all([
        axios.get(`${API}/voc/campaigns`, { headers: h }),
        axios.get(`${API}/voc/surveys`,   { headers: h }),
        axios.get(`${API}/voc/accounts`,  { headers: h }),
      ]);
      setCampaigns(c.data);
      setSurveys(s.data);
      setAccounts(a.data.accounts || []);
    } catch (e) {
      setError("Failed to load campaigns");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadData(); }, []);

  const handleCreate = async () => {
    if (!form.name || !form.survey_id || !form.account_id) {
      setError("Campaign name, survey and account are required."); return;
    }
    setCreating(true); setError(null);
    try {
      await axios.post(`${API}/voc/campaigns`, form, { headers: authHeader() });
      setShowForm(false);
      setForm({ name: "", survey_id: "", account_id: "", subject: "" });
      await loadData();
    } catch (e) {
      setError(e?.response?.data?.detail || "Failed to create campaign");
    } finally {
      setCreating(false);
    }
  };

  const handleSend = async () => {
    if (!sendModal) return;
    const emailList = recipients.split(/[,\n]+/).map(e => e.trim()).filter(Boolean);
    if (emailList.length === 0) { setError("Enter at least one recipient email."); return; }
    setSending(true); setError(null);
    try {
      const r = await axios.post(
        `${API}/voc/campaigns/${sendModal.id}/send`,
        { recipients: emailList },
        { headers: authHeader() },
      );
      setSentLinks(r.data);
      await loadData();
    } catch (e) {
      setError(e?.response?.data?.detail || "Failed to send campaign");
    } finally {
      setSending(false);
    }
  };

  const openSendModal = (camp) => {
    setSendModal(camp); setRecipients(""); setSentLinks(null); setError(null);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 size={28} className="animate-spin text-[#CC0000]" />
      </div>
    );
  }

  const FRONTEND_URL = process.env.REACT_APP_BACKEND_URL?.replace('/api', '').replace(':8001', '') || window.location.origin;

  return (
    <main className="max-w-screen-2xl mx-auto px-6 py-6">

      {/* Header */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <h2 className="text-2xl font-bold text-[#0F172A] font-['Outfit']">Email Campaigns</h2>
          <p className="text-[#64748B] text-sm mt-1">
            {campaigns.length} campaign{campaigns.length !== 1 ? "s" : ""} · Create, send and track survey campaigns per account
          </p>
        </div>
        <button onClick={() => { setShowForm(true); setError(null); }}
          className="flex items-center gap-2 px-5 py-2.5 rounded-lg text-xs font-bold text-white bg-[#CC0000] hover:bg-[#AA0000] transition-colors"
          data-testid="new-campaign-btn">
          <Plus size={13} />NEW CAMPAIGN
        </button>
      </div>

      {error && (
        <div className="mb-4 px-4 py-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-600">{error}</div>
      )}

      {/* Create Campaign Form */}
      {showForm && (
        <div className="bg-white rounded-xl border-2 border-[#CC0000]/20 p-5 mb-6 shadow-sm"
          data-testid="new-campaign-form">
          <div className="text-[10px] font-bold tracking-widest text-[#64748B] uppercase mb-4">New Campaign</div>
          <div className="grid grid-cols-2 gap-4 mb-4">
            <div>
              <label className="block text-xs font-semibold text-[#475569] mb-1.5">Campaign Name *</label>
              <input value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
                placeholder="Q3 2026 — Axis Bank Survey"
                className="w-full px-3 py-2.5 text-sm border-2 border-[#E2E8F0] rounded-lg focus:border-[#CC0000] focus:outline-none" />
            </div>
            <div>
              <label className="block text-xs font-semibold text-[#475569] mb-1.5">Email Subject</label>
              <input value={form.subject} onChange={e => setForm(f => ({ ...f, subject: e.target.value }))}
                placeholder="HSI Customer Satisfaction Survey — Your Feedback Matters"
                className="w-full px-3 py-2.5 text-sm border-2 border-[#E2E8F0] rounded-lg focus:border-[#CC0000] focus:outline-none" />
            </div>
            <div>
              <label className="block text-xs font-semibold text-[#475569] mb-1.5">Select Survey *</label>
              <div className="relative">
                <select value={form.survey_id} onChange={e => setForm(f => ({ ...f, survey_id: e.target.value }))}
                  className="w-full px-3 py-2.5 text-sm border-2 border-[#E2E8F0] rounded-lg focus:border-[#CC0000] focus:outline-none appearance-none bg-white">
                  <option value="">— Select a survey —</option>
                  {surveys.map(s => <option key={s.id} value={s.id}>{s.title} (v{s.version})</option>)}
                </select>
                <ChevronDown size={13} className="absolute right-3 top-1/2 -translate-y-1/2 text-[#94A3B8] pointer-events-none" />
              </div>
            </div>
            <div>
              <label className="block text-xs font-semibold text-[#475569] mb-1.5">Select Account *</label>
              <div className="relative">
                <select value={form.account_id} onChange={e => setForm(f => ({ ...f, account_id: e.target.value }))}
                  className="w-full px-3 py-2.5 text-sm border-2 border-[#E2E8F0] rounded-lg focus:border-[#CC0000] focus:outline-none appearance-none bg-white">
                  <option value="">— Select an account —</option>
                  {accounts.map(a => <option key={a.id} value={a.id}>{a.company_name}</option>)}
                </select>
                <ChevronDown size={13} className="absolute right-3 top-1/2 -translate-y-1/2 text-[#94A3B8] pointer-events-none" />
              </div>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <button onClick={handleCreate} disabled={creating}
              className="flex items-center gap-2 px-5 py-2.5 rounded-lg text-xs font-bold text-white bg-[#CC0000] hover:bg-[#AA0000] transition-colors disabled:opacity-60"
              data-testid="create-campaign-submit">
              {creating ? <Loader2 size={13} className="animate-spin" /> : <Plus size={13} />}
              {creating ? "Creating…" : "Create Campaign"}
            </button>
            <button onClick={() => setShowForm(false)}
              className="px-4 py-2.5 rounded-lg text-xs font-bold text-[#64748B] border border-[#E2E8F0] hover:text-[#0F172A] transition-colors">
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Campaigns Board */}
      {campaigns.length === 0 ? (
        <div className="flex items-center justify-center h-64 border-2 border-dashed border-[#E2E8F0] rounded-xl">
          <div className="text-center">
            <Mail size={32} className="text-[#94A3B8] mx-auto mb-3" />
            <p className="text-[#64748B] text-sm">No campaigns yet. Create your first survey campaign above.</p>
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-3 gap-4">
          {campaigns.map(c => {
            const meta = STATUS_META[c.status] || STATUS_META.draft;
            const respRate = c.sent_count > 0 ? Math.round(c.response_count / c.sent_count * 100) : 0;
            return (
              <div key={c.id} className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm hover:shadow-md transition-shadow overflow-hidden">
                <div className="px-5 pt-5 pb-3">
                  <div className="flex items-start justify-between gap-2 mb-2">
                    <h3 className="text-sm font-bold text-[#0F172A] leading-tight">{c.name}</h3>
                    <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full flex-shrink-0 ${meta.bg} ${meta.text}`}>
                      {meta.label}
                    </span>
                  </div>
                  <div className="text-[11px] text-[#64748B] space-y-0.5">
                    <div>Survey: <span className="font-semibold">{c.survey_title || "—"}</span></div>
                    <div>Account: <span className="font-semibold">{c.account_name || "—"}</span></div>
                    {c.created_at && <div className="text-[#94A3B8]">{new Date(c.created_at).toLocaleDateString()}</div>}
                  </div>
                </div>

                <div className="border-t border-[#F1F5F9] px-5 py-3 grid grid-cols-4 gap-2">
                  {[
                    [c.sent_count,     "Sent"],
                    [c.open_count,     "Opened"],
                    [c.click_count,    "Clicked"],
                    [c.response_count, "Responded"],
                  ].map(([v, l]) => (
                    <div key={l} className="text-center">
                      <div className="text-base font-bold text-[#0F172A]">{v}</div>
                      <div className="text-[9px] text-[#94A3B8]">{l}</div>
                    </div>
                  ))}
                </div>

                {c.sent_count > 0 && (
                  <div className="px-5 pb-3">
                    <div className="flex items-center justify-between text-[10px] text-[#64748B] mb-1">
                      <span>Response rate</span><span className="font-bold text-emerald-600">{respRate}%</span>
                    </div>
                    <div className="h-1.5 rounded-full bg-[#F1F5F9]">
                      <div className="h-full rounded-full bg-emerald-500" style={{ width: `${respRate}%`, transition: "width 1s" }} />
                    </div>
                  </div>
                )}

                <div className="px-5 pb-4">
                  <button onClick={() => openSendModal(c)}
                    className="w-full flex items-center justify-center gap-2 py-2 rounded-lg text-xs font-bold border border-[#E2E8F0] text-[#64748B] hover:border-[#CC0000]/30 hover:text-[#CC0000] hover:bg-red-50 transition-all"
                    data-testid={`send-campaign-${c.id}`}>
                    <Send size={12} />SEND SURVEY
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Send Modal */}
      {sendModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4"
          data-testid="send-campaign-modal">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg">
            <div className="flex items-start justify-between px-6 pt-6 pb-4 border-b border-[#E2E8F0]">
              <div>
                <h3 className="text-base font-bold text-[#0F172A]">Send Campaign</h3>
                <p className="text-xs text-[#64748B] mt-0.5">{sendModal.name}</p>
              </div>
              <button onClick={() => { setSendModal(null); setSentLinks(null); }}
                className="text-[#94A3B8] hover:text-[#0F172A] transition-colors">
                <X size={18} />
              </button>
            </div>

            <div className="px-6 py-5 space-y-4">
              {!sentLinks ? (
                <>
                  <div>
                    <label className="block text-xs font-semibold text-[#475569] mb-1.5">
                      Recipient Emails (one per line or comma-separated)
                    </label>
                    <textarea value={recipients} onChange={e => setRecipients(e.target.value)}
                      rows={5} placeholder={"john.doe@client.com\njane.smith@client.com"}
                      className="w-full px-3 py-2.5 text-sm border-2 border-[#E2E8F0] rounded-lg focus:border-[#CC0000] focus:outline-none resize-none font-mono"
                      data-testid="send-recipients-input" />
                    <p className="text-[10px] text-[#94A3B8] mt-1">
                      Single-use survey links will be generated for each email. Links expire in 72 hours.
                    </p>
                  </div>
                  {error && <p className="text-xs text-red-600">{error}</p>}
                  <div className="flex gap-3">
                    <button onClick={handleSend} disabled={sending}
                      className="flex-1 flex items-center justify-center gap-2 py-2.5 rounded-lg text-sm font-bold text-white bg-[#CC0000] hover:bg-[#AA0000] disabled:opacity-60 transition-colors"
                      data-testid="send-campaign-submit">
                      {sending ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />}
                      {sending ? "Sending…" : "Generate & Send"}
                    </button>
                    <button onClick={() => setSendModal(null)}
                      className="px-5 py-2.5 rounded-lg text-sm font-bold text-[#64748B] border border-[#E2E8F0] hover:text-[#0F172A] transition-colors">
                      Cancel
                    </button>
                  </div>
                </>
              ) : (
                <div className="space-y-4">
                  <div className="flex items-center gap-2">
                    <CheckCircle2 size={16} className="text-emerald-600" />
                    <p className="text-sm font-semibold text-emerald-700">{sentLinks.message}</p>
                  </div>
                  <div className="space-y-2">
                    <div className="text-[10px] font-bold tracking-widest text-[#64748B] uppercase">Survey Links</div>
                    {sentLinks.links.map((l, i) => (
                      <div key={i} className="bg-[#F8FAFC] rounded-lg px-3 py-2.5">
                        <div className="text-[11px] font-semibold text-[#475569] mb-1">{l.email}</div>
                        <div className="flex items-center gap-2">
                          <a href={l.url} target="_blank" rel="noopener noreferrer"
                            className="flex-1 text-xs text-[#CC0000] font-mono truncate hover:underline">
                            {l.url}
                          </a>
                          <CopyBtn text={l.url} />
                          <a href={l.url} target="_blank" rel="noopener noreferrer"
                            className="text-[#64748B] hover:text-[#CC0000] transition-colors">
                            <ExternalLink size={13} />
                          </a>
                        </div>
                      </div>
                    ))}
                  </div>
                  <button onClick={() => { setSendModal(null); setSentLinks(null); }}
                    className="w-full py-2.5 rounded-lg text-sm font-bold border border-[#E2E8F0] text-[#64748B] hover:text-[#0F172A] transition-colors">
                    Done
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </main>
  );
}
