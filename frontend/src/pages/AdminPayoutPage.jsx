import React, { useState, useEffect, useCallback } from "react";
import TopBar from "../components/TopBar";
import {
  IndianRupee, Download, FileText, CheckCircle2, AlertCircle, Users,
  Loader2, ShieldCheck, Calendar
} from "lucide-react";

const BACKEND = process.env.REACT_APP_BACKEND_URL;

export default function AdminPayoutPage() {
  const [quarters, setQuarters] = useState([]);
  const [active, setActive] = useState(null);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [downloading, setDownloading] = useState(null); // 'csv' | 'pdf' | null
  const [approving, setApproving] = useState(false);
  const [toast, setToast] = useState(null);

  const showToast = (msg, type = "success") => { setToast({ msg, type }); setTimeout(() => setToast(null), 2500); };

  const loadQuarters = useCallback(async () => {
    try {
      const res = await fetch(`${BACKEND}/api/admin/payout/quarters`, { credentials: "include" });
      if (res.ok) {
        const qs = await res.json();
        setQuarters(qs);
        if (qs.length && !active) setActive(qs[0].quarter);
      }
    } catch { /* silent */ }
  }, [active]);

  const loadPayout = useCallback(async (q) => {
    if (!q) return;
    setLoading(true);
    try {
      const res = await fetch(`${BACKEND}/api/admin/payout/${q}`, { credentials: "include" });
      if (res.ok) setData(await res.json());
    } finally { setLoading(false); }
  }, []);

  useEffect(() => { loadQuarters(); }, [loadQuarters]);
  useEffect(() => { if (active) loadPayout(active); }, [active, loadPayout]);

  const download = async (type) => {
    if (!active) return;
    setDownloading(type);
    try {
      const res = await fetch(`${BACKEND}/api/admin/payout/${active}/export.${type}`, { credentials: "include" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `payout_${active}.${type}`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      showToast(`${type.toUpperCase()} downloaded`);
    } catch (err) {
      showToast(`Download failed: ${err.message}`, "error");
    } finally { setDownloading(null); }
  };

  const approve = async () => {
    if (!active) return;
    if (!window.confirm(`Approve payout register for ${active}? This marks all ${data?.users || 0} users as approved.`)) return;
    setApproving(true);
    try {
      const res = await fetch(`${BACKEND}/api/admin/payout/${active}/approve`, {
        method: "POST", credentials: "include",
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const d = await res.json();
      showToast(`Approved ${d.approved} payout rows for ${d.quarter}`);
      loadPayout(active);
    } catch (err) {
      showToast(`Approve failed: ${err.message}`, "error");
    } finally { setApproving(false); }
  };

  return (
    <div className="min-h-screen bg-[#F1F5F9]">
      {toast && (
        <div
          role="status" aria-live="polite"
          className={`fixed top-4 right-4 z-50 px-4 py-3 rounded-lg shadow-lg text-sm font-medium flex items-center gap-2
          ${toast.type === "error" ? "bg-red-50 text-red-700 border border-red-200" : "bg-green-50 text-green-700 border border-green-200"}`}
        >
          {toast.type === "error" ? <AlertCircle size={16} aria-hidden="true" /> : <CheckCircle2 size={16} aria-hidden="true" />}
          {toast.msg}
        </div>
      )}

      <TopBar crumbs={[{ label: "Admin", to: "/admin" }, { label: "Payout" }]}>
        <div className="flex items-end justify-between gap-4 flex-wrap">
          <div>
            <h1 className="text-white text-2xl font-bold">Incentive Payout Register</h1>
            <p className="text-white/70 text-sm mt-1">Export quarterly CSV / PDF · Approve for payroll</p>
          </div>
          <div className="flex items-center gap-2">
            <label htmlFor="payout-quarter-select" className="text-white/80 text-xs font-medium">
              Quarter
            </label>
            <select
              id="payout-quarter-select"
              value={active || ""}
              onChange={(e) => setActive(e.target.value)}
              data-testid="payout-quarter-select"
              className="bg-white text-gray-800 text-sm rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-white/70"
            >
              {quarters.length === 0 && <option value="">— no data yet —</option>}
              {quarters.map(q => (
                <option key={q.quarter} value={q.quarter}>
                  {q.quarter} · {q.users} users · {q.xp_total.toLocaleString()} XP
                </option>
              ))}
            </select>
          </div>
        </div>
      </TopBar>

      <div className="max-w-7xl mx-auto px-4 py-6 space-y-6">
        {/* Summary strip */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-5">
            <div className="text-[11px] uppercase tracking-wider font-semibold text-gray-400">Quarter</div>
            <div className="text-2xl font-bold text-gray-900 mt-1 flex items-center gap-2">
              <Calendar size={18} className="text-[#CC0000]" aria-hidden="true" /> {active || "—"}
            </div>
          </div>
          <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-5">
            <div className="text-[11px] uppercase tracking-wider font-semibold text-gray-400">Users</div>
            <div className="text-2xl font-bold text-gray-900 mt-1 flex items-center gap-2">
              <Users size={18} className="text-blue-500" aria-hidden="true" /> {data?.users ?? 0}
            </div>
          </div>
          <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-5">
            <div className="text-[11px] uppercase tracking-wider font-semibold text-gray-400">Total Payout</div>
            <div className="text-2xl font-bold text-gray-900 mt-1 flex items-center gap-2 tabular-nums">
              <IndianRupee size={18} className="text-green-500" aria-hidden="true" />
              {(data?.total_inr ?? 0).toLocaleString("en-IN", { minimumFractionDigits: 2 })}
            </div>
          </div>
          <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-5">
            <div className="text-[11px] uppercase tracking-wider font-semibold text-gray-400">Rate (Repl w/ PO)</div>
            <div className="text-2xl font-bold text-gray-900 mt-1">
              ₹{data?.rates?.replication ?? "—"} <span className="text-xs text-gray-400">/XP</span>
            </div>
          </div>
        </div>

        {/* Actions */}
        <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-5 flex flex-wrap gap-3 items-center">
          <button
            type="button"
            onClick={() => download("csv")}
            disabled={!active || downloading !== null}
            data-testid="payout-export-csv"
            className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-200 rounded-lg hover:bg-gray-50 disabled:opacity-60 focus:outline-none focus:ring-2 focus:ring-[#CC0000] focus:ring-offset-2"
          >
            {downloading === "csv"
              ? <Loader2 size={14} className="animate-spin" aria-hidden="true" />
              : <Download size={14} aria-hidden="true" />}
            Export CSV
          </button>
          <button
            type="button"
            onClick={() => download("pdf")}
            disabled={!active || downloading !== null}
            data-testid="payout-export-pdf"
            className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-[#CC0000] rounded-lg hover:bg-red-700 disabled:opacity-60 focus:outline-none focus:ring-2 focus:ring-[#CC0000] focus:ring-offset-2"
          >
            {downloading === "pdf"
              ? <Loader2 size={14} className="animate-spin" aria-hidden="true" />
              : <FileText size={14} aria-hidden="true" />}
            Export PDF
          </button>
          <div className="flex-1" />
          <button
            type="button"
            onClick={approve}
            disabled={!active || approving || !data?.users}
            data-testid="payout-approve-btn"
            className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-green-700 bg-green-50 border border-green-200 rounded-lg hover:bg-green-100 disabled:opacity-60 focus:outline-none focus:ring-2 focus:ring-green-500 focus:ring-offset-2"
          >
            {approving
              ? <Loader2 size={14} className="animate-spin" aria-hidden="true" />
              : <ShieldCheck size={14} aria-hidden="true" />}
            Approve Register
          </button>
        </div>

        {/* Table */}
        <section data-testid="payout-table" className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-gray-50 text-left text-[11px] font-semibold uppercase tracking-wider text-gray-500">
                  <th className="px-5 py-2.5">Employee</th>
                  <th className="px-5 py-2.5">Dept</th>
                  <th className="px-5 py-2.5 text-right">XP Orig</th>
                  <th className="px-5 py-2.5 text-right">XP Rep</th>
                  <th className="px-5 py-2.5 text-right">XP Tech</th>
                  <th className="px-5 py-2.5 text-right">XP Other</th>
                  <th className="px-5 py-2.5 text-right">XP Total</th>
                  <th className="px-5 py-2.5 text-right">Amount (₹)</th>
                </tr>
              </thead>
              <tbody>
                {loading ? (
                  <tr><td colSpan={8} className="px-5 py-10 text-center text-gray-400 text-sm">
                    <Loader2 size={18} className="animate-spin inline-block" aria-hidden="true" /> Loading…
                  </td></tr>
                ) : (data?.items || []).length === 0 ? (
                  <tr><td colSpan={8} className="px-5 py-10 text-center text-gray-400 text-sm">
                    No payout data for this quarter
                  </td></tr>
                ) : (
                  data.items.map((i) => (
                    <tr key={i.user_id} className="border-t border-gray-50 hover:bg-gray-50/50">
                      <td className="px-5 py-3">
                        <div className="font-medium text-gray-800">{i.name}</div>
                        <div className="text-xs text-gray-400">{i.email}</div>
                      </td>
                      <td className="px-5 py-3 text-gray-600">{i.department || "—"}</td>
                      <td className="px-5 py-3 text-right tabular-nums">{i.xp_original}</td>
                      <td className="px-5 py-3 text-right tabular-nums">{i.xp_replication}</td>
                      <td className="px-5 py-3 text-right tabular-nums">{i.xp_tech_day}</td>
                      <td className="px-5 py-3 text-right tabular-nums">{i.xp_other}</td>
                      <td className="px-5 py-3 text-right tabular-nums font-semibold">{i.xp_total}</td>
                      <td className="px-5 py-3 text-right tabular-nums font-bold text-[#CC0000]">
                        ₹{i.amount_inr.toLocaleString("en-IN", { minimumFractionDigits: 2 })}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
              {data?.items?.length > 0 && (
                <tfoot>
                  <tr className="bg-gray-50 border-t border-gray-200">
                    <td colSpan={6} className="px-5 py-3 text-right text-xs font-semibold uppercase tracking-wider text-gray-500">
                      Quarter Total
                    </td>
                    <td className="px-5 py-3 text-right tabular-nums font-bold text-gray-800">
                      {data.items.reduce((s, x) => s + x.xp_total, 0).toLocaleString()}
                    </td>
                    <td className="px-5 py-3 text-right tabular-nums font-bold text-[#CC0000]">
                      ₹{data.total_inr.toLocaleString("en-IN", { minimumFractionDigits: 2 })}
                    </td>
                  </tr>
                </tfoot>
              )}
            </table>
          </div>
        </section>
      </div>
    </div>
  );
}
