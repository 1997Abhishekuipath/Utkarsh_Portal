import React, { useState, useEffect, useCallback } from "react";
import TopBar from "../components/TopBar";
import {
  Zap, TrendingUp, Award, Trophy, ChevronRight, Plus, X, CheckCircle, AlertCircle
} from "lucide-react";
import { useAuth } from "../contexts/AuthContext";

const BACKEND = process.env.REACT_APP_BACKEND_URL;

const SOURCE_LABELS = {
  original_practice: "Best Practice",
  replication: "Replication",
  tech_day: "Tech Day",
  certification: "Certification",
  birthday: "Birthday Bonus 🎂",
  referral: "Referral Bonus",
  seasonal_bonus: "Seasonal Bonus",
  admin_adjustment: "Admin Adjustment",
};
const SOURCE_COLORS = {
  original_practice: "bg-red-100 text-red-700",
  replication: "bg-blue-100 text-blue-700",
  tech_day: "bg-green-100 text-green-700",
  certification: "bg-purple-100 text-purple-700",
  birthday: "bg-pink-100 text-pink-700",
  referral: "bg-amber-100 text-amber-700",
  seasonal_bonus: "bg-teal-100 text-teal-700",
  admin_adjustment: "bg-gray-100 text-gray-600",
};

export default function MyActivityPage() {
  const { user } = useAuth();
  const [summary, setSummary] = useState(null);
  const [ledger, setLedger] = useState([]);
  const [incentive, setIncentive] = useState(null);
  const [myTechDays, setMyTechDays] = useState([]);
  const [myCerts, setMyCerts] = useState([]);
  const [myReps, setMyReps] = useState([]);
  const [activeTab, setActiveTab] = useState("overview");
  const [showTechDayForm, setShowTechDayForm] = useState(false);
  const [showCertForm, setShowCertForm] = useState(false);
  const [tdForm, setTdForm] = useState({ title: "", description: "", client_name: "", attendee_count: 0, conducted_on: "", evidence_url: "" });
  const [certForm, setCertForm] = useState({ cert_name: "", provider: "", cert_id: "", issued_on: "", expires_on: "" });
  const [submitting, setSubmitting] = useState(false);
  const [toast, setToast] = useState(null);

  const showToast = (msg, type = "success") => { setToast({ msg, type }); setTimeout(() => setToast(null), 3500); };

  const load = useCallback(async () => {
    try {
      const [sumRes, ledRes, incRes, tdRes, certRes, repRes] = await Promise.all([
        fetch(`${BACKEND}/api/xp/summary`, { credentials: "include" }),
        fetch(`${BACKEND}/api/xp/ledger?limit=30`, { credentials: "include" }),
        fetch(`${BACKEND}/api/incentive/statement`, { credentials: "include" }),
        fetch(`${BACKEND}/api/tech-days/mine`, { credentials: "include" }),
        fetch(`${BACKEND}/api/certifications/mine`, { credentials: "include" }),
        fetch(`${BACKEND}/api/replications/mine`, { credentials: "include" }),
      ]);
      if (sumRes.ok)  setSummary(await sumRes.json());
      if (ledRes.ok)  setLedger(await ledRes.json());
      if (incRes.ok)  setIncentive(await incRes.json());
      if (tdRes.ok)   setMyTechDays(await tdRes.json());
      if (certRes.ok) setMyCerts(await certRes.json());
      if (repRes.ok)  setMyReps(await repRes.json());
    } catch { /* silent */ }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleTechDay = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      const res = await fetch(`${BACKEND}/api/tech-days`, {
        method: "POST", credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...tdForm, attendee_count: Number(tdForm.attendee_count) }),
      });
      if (res.ok) {
        showToast("Tech Day submitted for approval!");
        setShowTechDayForm(false);
        setTdForm({ title: "", description: "", client_name: "", attendee_count: 0, conducted_on: "", evidence_url: "" });
        load();
      } else { const d = await res.json(); showToast(d.detail || "Failed", "error"); }
    } finally { setSubmitting(false); }
  };

  const handleCert = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      const res = await fetch(`${BACKEND}/api/certifications`, {
        method: "POST", credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(certForm),
      });
      if (res.ok) {
        const d = await res.json();
        showToast(`Certification added! +${d.xp_awarded} XP credited.`);
        setShowCertForm(false);
        setCertForm({ cert_name: "", provider: "", cert_id: "", issued_on: "", expires_on: "" });
        load();
      } else { const d = await res.json(); showToast(d.detail || "Failed", "error"); }
    } finally { setSubmitting(false); }
  };

  const xpPct = summary ? Math.min(100, Math.round(((summary.total_xp % 500) / 500) * 100)) : 0;
  const nextLevel = summary ? (summary.level || 1) * 500 : 500;

  const STATUS_COLORS = { pending: "bg-yellow-100 text-yellow-700", approved: "bg-green-100 text-green-700", rejected: "bg-red-100 text-red-700" };

  return (
    <div className="min-h-screen bg-[#F1F5F9]">
      {toast && (
        <div className={`fixed top-4 right-4 z-50 px-4 py-3 rounded-lg shadow-lg text-sm font-medium flex items-center gap-2
          ${toast.type === "error" ? "bg-red-50 text-red-700 border border-red-200" : "bg-green-50 text-green-700 border border-green-200"}`}>
          {toast.type === "error" ? <AlertCircle size={16} /> : <CheckCircle size={16} />}
          {toast.msg}
        </div>
      )}

      <TopBar crumbs={[{ label: "Home", to: "/" }, { label: "My XP & Activity" }]}>
        <div className="flex items-end justify-between">
          <div>
            <h1 className="text-white text-2xl font-bold">My XP & Activity</h1>
            <p className="text-white/70 text-sm mt-1">Track your contributions and earnings</p>
          </div>
          <div className="flex items-end gap-2 text-right">
            <div>
              <div className="text-white text-3xl font-bold">{summary?.total_xp?.toLocaleString() || 0}</div>
              <div className="text-white/60 text-xs">TOTAL XP</div>
            </div>
            <div className="px-4 border-l border-white/20">
              <div className="text-white text-2xl font-bold">#{summary?.rank || "—"}</div>
              <div className="text-white/60 text-xs">RANK</div>
            </div>
          </div>
        </div>
      </TopBar>

      <div className="max-w-7xl mx-auto px-4 py-6">
        {/* Level card */}
        {summary && (
          <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-5 mb-6">
            <div className="flex items-center gap-4">
              <div className="w-14 h-14 bg-gradient-to-br from-[#CC0000] to-red-700 rounded-xl flex items-center justify-center shadow-md">
                <span className="text-white text-xl font-bold">L{summary.level}</span>
              </div>
              <div className="flex-1">
                <div className="flex items-center justify-between mb-1.5">
                  <span className="text-sm font-semibold text-gray-800">Level {summary.level} — {summary.total_xp} XP</span>
                  <span className="text-xs text-gray-400">{nextLevel - summary.total_xp} XP to Level {summary.level + 1}</span>
                </div>
                <div className="w-full bg-gray-100 rounded-full h-2.5">
                  <div className="bg-gradient-to-r from-[#CC0000] to-red-500 h-2.5 rounded-full transition-all duration-500"
                    style={{ width: `${xpPct}%` }} />
                </div>
                <div className="flex items-center gap-4 mt-2 text-xs text-gray-500">
                  <span>Rank #{summary.rank} of {summary.total_users}</span>
                  <span>{summary.quarter_xp} XP this {summary.quarter}</span>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Tabs */}
        <div className="flex gap-1 bg-white rounded-xl p-1 shadow-sm border border-gray-100 w-fit mb-6">
          {[["overview","Overview"],["ledger","XP Ledger"],["incentive","Incentive Statement"],
            ["techdays","Tech Days"],["certs","Certifications"],["replications","Replications"]].map(([id,label]) => (
            <button key={id} onClick={() => setActiveTab(id)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${activeTab === id ? "bg-[#CC0000] text-white shadow-sm" : "text-gray-500 hover:text-gray-700"}`}>
              {label}
            </button>
          ))}
        </div>

        {/* Overview */}
        {activeTab === "overview" && summary && (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            {Object.entries(summary.breakdown || {}).map(([type, xp]) => (
              <div key={type} className="bg-white rounded-xl border border-gray-100 shadow-sm p-4">
                <div className="text-xs text-gray-500 mb-1">{SOURCE_LABELS[type] || type}</div>
                <div className="text-2xl font-bold text-gray-800">{xp}</div>
                <div className="text-xs text-gray-400">XP earned</div>
              </div>
            ))}
          </div>
        )}

        {/* XP Ledger */}
        {activeTab === "ledger" && (
          <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b border-gray-100">
                <tr>
                  {["Date","Type","XP","Balance","Description"].map(h => (
                    <th key={h} className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {ledger.map(r => (
                  <tr key={r.id} className="border-b border-gray-50 hover:bg-gray-50 transition-colors">
                    <td className="px-4 py-3 text-xs text-gray-500">{r.created_at ? new Date(r.created_at).toLocaleDateString("en-IN") : "—"}</td>
                    <td className="px-4 py-3">
                      <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${SOURCE_COLORS[r.source_type] || "bg-gray-100 text-gray-600"}`}>
                        {SOURCE_LABELS[r.source_type] || r.source_type}
                      </span>
                    </td>
                    <td className={`px-4 py-3 font-bold text-sm ${r.xp_delta >= 0 ? "text-green-600" : "text-red-600"}`}>
                      {r.xp_delta >= 0 ? "+" : ""}{r.xp_delta}
                    </td>
                    <td className="px-4 py-3 text-sm font-medium text-gray-700">{r.xp_balance}</td>
                    <td className="px-4 py-3 text-xs text-gray-500 max-w-xs truncate">{r.description || "—"}</td>
                  </tr>
                ))}
                {ledger.length === 0 && (
                  <tr><td colSpan={5} className="text-center py-8 text-gray-400">No XP transactions yet</td></tr>
                )}
              </tbody>
            </table>
          </div>
        )}

        {/* Incentive Statement */}
        {activeTab === "incentive" && incentive && (
          <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-6 max-w-lg">
            <div className="flex items-center gap-3 mb-5">
              <Award size={24} className="text-amber-500" />
              <div>
                <h3 className="text-lg font-bold text-gray-900">Incentive Statement</h3>
                <p className="text-xs text-gray-500">{incentive.quarter} · Status: <span className="font-medium capitalize">{incentive.status}</span></p>
              </div>
            </div>
            <div className="space-y-3 mb-5">
              {[
                ["Best Practices", incentive.xp_original, incentive.rate_original],
                ["Replications", incentive.xp_replication, incentive.rate_replication],
                ["Tech Days", incentive.xp_tech_day, incentive.rate_tech_day],
              ].map(([label, xp, rate]) => (
                <div key={label} className="flex items-center justify-between py-2 border-b border-gray-50">
                  <span className="text-sm text-gray-600">{label}</span>
                  <div className="text-right">
                    <div className="text-sm font-medium text-gray-800">{xp} XP × ₹{rate}/XP</div>
                    <div className="text-xs text-gray-500">= ₹{(xp * rate).toLocaleString("en-IN")}</div>
                  </div>
                </div>
              ))}
            </div>
            <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 flex items-center justify-between">
              <div>
                <div className="text-xs text-amber-700 font-medium">Total Incentive ({incentive.quarter})</div>
                <div className="text-xs text-amber-600 mt-0.5">{incentive.xp_total} XP total</div>
              </div>
              <div className="text-2xl font-bold text-amber-700">₹{Number(incentive.amount_inr).toLocaleString("en-IN", { maximumFractionDigits: 0 })}</div>
            </div>
          </div>
        )}

        {/* Tech Days */}
        {activeTab === "techdays" && (
          <div>
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-semibold text-gray-700">My Tech Days</h3>
              <button onClick={() => setShowTechDayForm(true)}
                className="flex items-center gap-1.5 bg-[#CC0000] text-white px-3 py-1.5 rounded-lg text-xs font-medium hover:bg-red-700">
                <Plus size={13} />Submit Tech Day
              </button>
            </div>
            <div className="space-y-3">
              {myTechDays.map(td => (
                <div key={td.id} className="bg-white rounded-xl border border-gray-100 shadow-sm p-4 flex items-center justify-between">
                  <div>
                    <div className="text-sm font-semibold text-gray-800">{td.title}</div>
                    <div className="text-xs text-gray-500 mt-0.5">
                      {td.client_name && <span className="mr-3">{td.client_name}</span>}
                      {td.conducted_on && <span>{td.conducted_on}</span>}
                    </div>
                  </div>
                  <div className="flex items-center gap-3 text-right">
                    {td.xp_awarded > 0 && <span className="text-xs font-bold text-amber-600">+{td.xp_awarded} XP</span>}
                    <span className={`text-xs px-2 py-0.5 rounded-full ${STATUS_COLORS[td.status] || "bg-gray-100 text-gray-600"}`}>{td.status}</span>
                  </div>
                </div>
              ))}
              {myTechDays.length === 0 && <p className="text-center text-gray-400 text-sm py-8">No tech days submitted yet.</p>}
            </div>
          </div>
        )}

        {/* Certifications */}
        {activeTab === "certs" && (
          <div>
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-semibold text-gray-700">My Certifications</h3>
              <button onClick={() => setShowCertForm(true)}
                className="flex items-center gap-1.5 bg-[#CC0000] text-white px-3 py-1.5 rounded-lg text-xs font-medium hover:bg-red-700">
                <Plus size={13} />Add Certification
              </button>
            </div>
            <div className="space-y-3">
              {myCerts.map(c => (
                <div key={c.id} className="bg-white rounded-xl border border-gray-100 shadow-sm p-4 flex items-center justify-between">
                  <div>
                    <div className="text-sm font-semibold text-gray-800">{c.cert_name}</div>
                    <div className="text-xs text-gray-500 mt-0.5">{c.provider && <span className="mr-3">{c.provider}</span>}{c.issued_on && <span>Issued: {c.issued_on}</span>}</div>
                  </div>
                  <span className="text-xs font-bold text-amber-600">+{c.xp_awarded} XP</span>
                </div>
              ))}
              {myCerts.length === 0 && <p className="text-center text-gray-400 text-sm py-8">No certifications added yet.</p>}
            </div>
          </div>
        )}

        {/* Replications */}
        {activeTab === "replications" && (
          <div>
            <h3 className="text-sm font-semibold text-gray-700 mb-4">My Replications</h3>
            <div className="space-y-3">
              {myReps.map(r => (
                <div key={r.id} className="bg-white rounded-xl border border-gray-100 shadow-sm p-4 flex items-center justify-between">
                  <div>
                    <div className="text-sm font-semibold text-gray-800">{r.practice_title}</div>
                    <div className="text-xs text-gray-500 mt-0.5">Client: {r.client_name} {r.po_number && `· PO: ${r.po_number}`}</div>
                  </div>
                  <div className="flex items-center gap-3">
                    {r.xp_awarded > 0 && <span className="text-xs font-bold text-amber-600">+{r.xp_awarded} XP</span>}
                    <span className={`text-xs px-2 py-0.5 rounded-full ${STATUS_COLORS[r.status] || "bg-gray-100 text-gray-600"}`}>{r.status}</span>
                  </div>
                </div>
              ))}
              {myReps.length === 0 && <p className="text-center text-gray-400 text-sm py-8">No replications submitted yet.</p>}
            </div>
          </div>
        )}
      </div>

      {/* Tech Day Form Modal */}
      {showTechDayForm && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md">
            <div className="flex items-center justify-between p-5 border-b border-gray-100">
              <h3 className="font-bold text-gray-900">Submit Tech Day</h3>
              <button onClick={() => setShowTechDayForm(false)} className="text-gray-400 hover:text-gray-600"><X size={18} /></button>
            </div>
            <form onSubmit={handleTechDay} className="p-5 space-y-3">
              {[["Title","title","text",true],["Client Name","client_name"],["Evidence URL","evidence_url"]].map(([label, name, type, req]) => (
                <div key={name}>
                  <label className="block text-xs font-semibold text-gray-600 mb-1">{label}{req ? " *" : ""}</label>
                  <input value={tdForm[name]} onChange={e => setTdForm(p => ({ ...p, [name]: e.target.value }))} required={!!req}
                    className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-red-200 outline-none" />
                </div>
              ))}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-gray-600 mb-1">Date Conducted *</label>
                  <input type="date" value={tdForm.conducted_on} required onChange={e => setTdForm(p => ({ ...p, conducted_on: e.target.value }))}
                    className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-red-200 outline-none" />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-gray-600 mb-1">Attendees</label>
                  <input type="number" min="0" value={tdForm.attendee_count} onChange={e => setTdForm(p => ({ ...p, attendee_count: e.target.value }))}
                    className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-red-200 outline-none" />
                </div>
              </div>
              <div className="bg-green-50 border border-green-200 rounded-lg p-2 text-xs text-green-700">
                XP: 25 + (2 × attendees) capped at 75 XP per event
              </div>
              <div className="flex justify-end gap-2 pt-1">
                <button type="button" onClick={() => setShowTechDayForm(false)} className="px-4 py-2 text-sm border border-gray-200 rounded-lg text-gray-600">Cancel</button>
                <button type="submit" disabled={submitting} className="px-4 py-2 bg-[#CC0000] text-white rounded-lg text-sm font-medium hover:bg-red-700 disabled:opacity-60">
                  {submitting ? "Submitting…" : "Submit"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Cert Form Modal */}
      {showCertForm && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md">
            <div className="flex items-center justify-between p-5 border-b border-gray-100">
              <h3 className="font-bold text-gray-900">Add Certification</h3>
              <button onClick={() => setShowCertForm(false)} className="text-gray-400 hover:text-gray-600"><X size={18} /></button>
            </div>
            <form onSubmit={handleCert} className="p-5 space-y-3">
              {[["Certification Name","cert_name",true],["Provider","provider"],["Certificate ID","cert_id"]].map(([label, name, req]) => (
                <div key={name}>
                  <label className="block text-xs font-semibold text-gray-600 mb-1">{label}{req ? " *" : ""}</label>
                  <input value={certForm[name]} onChange={e => setCertForm(p => ({ ...p, [name]: e.target.value }))} required={!!req}
                    className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-red-200 outline-none" />
                </div>
              ))}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-gray-600 mb-1">Issue Date</label>
                  <input type="date" value={certForm.issued_on} onChange={e => setCertForm(p => ({ ...p, issued_on: e.target.value }))}
                    className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-red-200 outline-none" />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-gray-600 mb-1">Expiry Date</label>
                  <input type="date" value={certForm.expires_on} onChange={e => setCertForm(p => ({ ...p, expires_on: e.target.value }))}
                    className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-red-200 outline-none" />
                </div>
              </div>
              <div className="bg-purple-50 border border-purple-200 rounded-lg p-2 text-xs text-purple-700">
                +{50} XP credited immediately upon submission
              </div>
              <div className="flex justify-end gap-2 pt-1">
                <button type="button" onClick={() => setShowCertForm(false)} className="px-4 py-2 text-sm border border-gray-200 rounded-lg text-gray-600">Cancel</button>
                <button type="submit" disabled={submitting} className="px-4 py-2 bg-[#CC0000] text-white rounded-lg text-sm font-medium hover:bg-red-700 disabled:opacity-60">
                  {submitting ? "Adding…" : "Add Certification"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
