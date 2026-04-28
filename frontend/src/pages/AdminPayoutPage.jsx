import React, { useState, useEffect, useCallback } from "react";
import TopBar from "../components/TopBar";
import { useAuth } from "../contexts/AuthContext";
import {
  IndianRupee, Download, FileText, CheckCircle2, AlertCircle, Users,
  Loader2, ShieldCheck, Calendar, BadgeCheck, PauseCircle, Play, Banknote, XCircle, X
} from "lucide-react";

const BACKEND = process.env.REACT_APP_BACKEND_URL;
const STATUS_COLOR = {
  draft:     "bg-gray-100   text-gray-700   border-gray-200",
  approved:  "bg-blue-50    text-blue-700   border-blue-200",
  paid:      "bg-green-50   text-green-700  border-green-200",
  on_hold:   "bg-amber-50   text-amber-700  border-amber-200",
  cancelled: "bg-rose-50    text-rose-700   border-rose-200",
};

export default function AdminPayoutPage() {
  const { authHeader } = useAuth();
  const [quarters, setQuarters] = useState([]);
  const [active, setActive] = useState(null);
  const [data, setData] = useState(null);
  const [calcs, setCalcs] = useState({ counts: {}, items: [] });
  const [loading, setLoading] = useState(true);
  const [downloading, setDownloading] = useState(null);
  const [busy, setBusy] = useState(null);   // 'approve' | 'pay' | calcId
  const [toast, setToast] = useState(null);
  const [payrollRef, setPayrollRef] = useState("");
  // In-app confirm modal — replaces window.confirm so the page never blocks
  // on browser-native dialogs (which are not stylable + can't be tested via DOM).
  const [confirmDlg, setConfirmDlg] = useState(null);   // { title, body, danger, onYes }
  const [cancelDlg, setCancelDlg] = useState(null);     // { calc, reason }

  const showToast = (msg, type = "success") => { setToast({ msg, type }); setTimeout(() => setToast(null), 2800); };

  const apiGet = useCallback(async (path) => {
    const res = await fetch(`${BACKEND}${path}`, { headers: { ...authHeader() } });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
  }, [authHeader]);

  const apiPost = useCallback(async (path, body = null) => {
    const res = await fetch(`${BACKEND}${path}`, {
      method: "POST",
      headers: { ...authHeader(), "Content-Type": "application/json" },
      body: body ? JSON.stringify(body) : null,
    });
    if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || `HTTP ${res.status}`);
    return res.json();
  }, [authHeader]);

  const loadQuarters = useCallback(async () => {
    try {
      const qs = await apiGet(`/api/admin/payout/quarters`);
      setQuarters(qs);
      if (qs.length && !active) setActive(qs[0].quarter);
    } catch { /* ignore */ }
  }, [apiGet, active]);

  const loadAll = useCallback(async (q) => {
    if (!q) return;
    setLoading(true);
    try {
      const [summary, list] = await Promise.all([
        apiGet(`/api/admin/payout/${q}`),
        apiGet(`/api/admin/payout/${q}/calcs`),
      ]);
      setData(summary);
      setCalcs(list);
    } catch (err) {
      showToast(`Load failed: ${err.message}`, "error");
    } finally { setLoading(false); }
  }, [apiGet]);

  useEffect(() => { loadQuarters(); }, [loadQuarters]);
  useEffect(() => { if (active) loadAll(active); }, [active, loadAll]);

  const download = async (type) => {
    if (!active) return;
    setDownloading(type);
    try {
      const res = await fetch(`${BACKEND}/api/admin/payout/${active}/export.${type}`, {
        headers: { ...authHeader() },
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url; a.download = `payout_${active}.${type}`;
      document.body.appendChild(a); a.click(); a.remove();
      URL.revokeObjectURL(url);
      showToast(`${type.toUpperCase()} downloaded`);
    } catch (err) {
      showToast(`Download failed: ${err.message}`, "error");
    } finally { setDownloading(null); }
  };

  const approve = () => {
    if (!active) return;
    setConfirmDlg({
      title: `Approve payout register for ${active}?`,
      body:  "This freezes the calculation snapshot — already-paid and on-hold rows are skipped.",
      danger: false,
      ctaLabel: "Approve",
      ctaTestId: "confirm-approve-btn",
      onYes: async () => {
        setBusy("approve");
        try {
          const d = await apiPost(`/api/admin/payout/${active}/approve`);
          showToast(`Approved ${d.approved} payout rows for ${d.quarter}`);
          loadAll(active);
        } catch (err) {
          showToast(`Approve failed: ${err.message}`, "error");
        } finally { setBusy(null); }
      },
    });
  };

  const markPaid = () => {
    if (!active) return;
    setConfirmDlg({
      title: `Mark all approved rows for ${active} as PAID?`,
      body:  payrollRef
        ? `Payroll ref: ${payrollRef}. This is the final state — reverse only via payroll.`
        : "An auto-generated payroll ref will be used. This is the final state — reverse only via payroll.",
      danger: true,
      ctaLabel: "Mark Paid",
      ctaTestId: "confirm-mark-paid-btn",
      onYes: async () => {
        setBusy("pay");
        try {
          const d = await apiPost(`/api/admin/payout/${active}/mark-paid`, {
            payroll_ref: payrollRef || null,
          });
          showToast(`✓ Paid ${d.paid} rows · ref ${d.payroll_ref}`);
          setPayrollRef("");
          loadAll(active);
        } catch (err) {
          showToast(`Mark paid failed: ${err.message}`, "error");
        } finally { setBusy(null); }
      },
    });
  };

  const hold = async (calcId) => {
    setBusy(calcId);
    try {
      await apiPost(`/api/admin/payout/calc/${calcId}/hold`);
      showToast("Calc placed on hold");
      loadAll(active);
    } catch (err) {
      showToast(`Hold failed: ${err.message}`, "error");
    } finally { setBusy(null); }
  };

  const resume = async (calcId) => {
    setBusy(calcId);
    try {
      await apiPost(`/api/admin/payout/calc/${calcId}/resume`);
      showToast("Calc resumed → back to draft");
      loadAll(active);
    } catch (err) {
      showToast(`Resume failed: ${err.message}`, "error");
    } finally { setBusy(null); }
  };

  const submitCancel = async () => {
    if (!cancelDlg?.calc) return;
    setBusy(cancelDlg.calc.id);
    try {
      await apiPost(`/api/admin/payout/calc/${cancelDlg.calc.id}/cancel`, {
        reason: cancelDlg.reason || null,
      });
      showToast(`Cancelled ${cancelDlg.calc.name}'s calc`);
      setCancelDlg(null);
      loadAll(active);
    } catch (err) {
      showToast(`Cancel failed: ${err.message}`, "error");
    } finally { setBusy(null); }
  };

  const counts = calcs.counts || {};
  const hasApproved = (counts.approved || 0) > 0;

  return (
    <div className="min-h-screen bg-[#F1F5F9]">
      {/* Generic confirm modal — replaces window.confirm */}
      {confirmDlg && (
        <Modal onClose={() => setConfirmDlg(null)} testId="confirm-modal">
          <ModalHeader title={confirmDlg.title} onClose={() => setConfirmDlg(null)} />
          <div className="px-5 py-4 text-sm text-gray-600">{confirmDlg.body}</div>
          <ModalFooter>
            <button type="button"
              onClick={() => setConfirmDlg(null)}
              data-testid="confirm-cancel-btn"
              className="px-4 py-2 text-sm font-medium text-gray-600 hover:bg-gray-100 rounded-lg">
              Cancel
            </button>
            <button type="button"
              onClick={() => { const cb = confirmDlg.onYes; setConfirmDlg(null); cb && cb(); }}
              data-testid={confirmDlg.ctaTestId || "confirm-yes-btn"}
              className={`px-4 py-2 text-sm font-medium rounded-lg ${
                confirmDlg.danger
                  ? "text-white bg-[#CC0000] hover:bg-red-700"
                  : "text-white bg-blue-600 hover:bg-blue-700"
              }`}>
              {confirmDlg.ctaLabel || "Confirm"}
            </button>
          </ModalFooter>
        </Modal>
      )}

      {/* Cancel-calc modal — captures optional reason */}
      {cancelDlg && (
        <Modal onClose={() => setCancelDlg(null)} testId="cancel-calc-modal">
          <ModalHeader title={`Cancel ${cancelDlg.calc?.name}'s calc?`} onClose={() => setCancelDlg(null)} />
          <div className="px-5 py-4 space-y-3">
            <p className="text-sm text-gray-600">
              This is a <strong className="text-rose-700">terminal</strong> state — the row will be permanently
              excluded from approve / mark-paid sweeps. Use this when finance needs to void a calc that
              cannot be paid out (e.g. employee left, dispute resolved off-platform).
            </p>
            <label className="block">
              <span className="text-[11px] uppercase tracking-wider font-semibold text-gray-500">
                Reason (optional, audited)
              </span>
              <textarea rows={2}
                value={cancelDlg.reason}
                onChange={(e) => setCancelDlg({ ...cancelDlg, reason: e.target.value })}
                data-testid="cancel-reason-input"
                placeholder="e.g. Employee separated 2026-03-15 · payroll-out-of-band-settlement"
                className="mt-1 w-full text-sm border border-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-rose-300" />
            </label>
          </div>
          <ModalFooter>
            <button type="button"
              onClick={() => setCancelDlg(null)}
              className="px-4 py-2 text-sm font-medium text-gray-600 hover:bg-gray-100 rounded-lg">
              Keep
            </button>
            <button type="button"
              onClick={submitCancel}
              disabled={busy === cancelDlg.calc?.id}
              data-testid="cancel-calc-confirm-btn"
              className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-rose-600 hover:bg-rose-700 rounded-lg disabled:opacity-60">
              {busy === cancelDlg.calc?.id ? <Loader2 size={14} className="animate-spin" /> : <XCircle size={14} />}
              Cancel calc
            </button>
          </ModalFooter>
        </Modal>
      )}

      {toast && (
        <div role="status" aria-live="polite"
          data-testid="payout-toast"
          className={`fixed top-4 right-4 z-50 px-4 py-3 rounded-lg shadow-lg text-sm font-medium flex items-center gap-2
          ${toast.type === "error" ? "bg-red-50 text-red-700 border border-red-200" : "bg-green-50 text-green-700 border border-green-200"}`}>
          {toast.type === "error" ? <AlertCircle size={16} /> : <CheckCircle2 size={16} />}
          {toast.msg}
        </div>
      )}

      <TopBar crumbs={[{ label: "Admin", to: "/admin" }, { label: "Payout" }]}>
        <div className="flex items-end justify-between gap-4 flex-wrap">
          <div>
            <h1 className="text-white text-2xl font-bold">Incentive Payout Register</h1>
            <p className="text-white/70 text-sm mt-1">Quarterly state machine · Draft → Approved → Paid (or On Hold)</p>
          </div>
          <div className="flex items-center gap-2">
            <label htmlFor="payout-quarter-select" className="text-white/80 text-xs font-medium">Quarter</label>
            <select id="payout-quarter-select" value={active || ""}
              onChange={(e) => setActive(e.target.value)}
              data-testid="payout-quarter-select"
              className="bg-white text-gray-800 text-sm rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-white/70">
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
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          <SummaryTile label="Quarter" icon={<Calendar size={18} className="text-[#CC0000]" />} value={active || "—"} />
          <SummaryTile label="Users" icon={<Users size={18} className="text-blue-500" />} value={data?.users ?? 0} />
          <SummaryTile label="Total Payout" icon={<IndianRupee size={18} className="text-green-500" />}
            value={(data?.total_inr ?? 0).toLocaleString("en-IN", { minimumFractionDigits: 2 })} mono />
          <SummaryTile label="Approved" icon={<BadgeCheck size={18} className="text-blue-500" />} value={counts.approved || 0} />
          <SummaryTile label="Paid" icon={<Banknote size={18} className="text-green-600" />} value={counts.paid || 0} />
        </div>

        {/* Status legend */}
        <div className="flex flex-wrap gap-2 text-xs">
          {Object.entries(counts).map(([k, v]) => (
            <span key={k} className={`px-2.5 py-1 rounded-full border ${STATUS_COLOR[k] || ""}`}>
              {k.replace("_", " ")} · <span className="font-semibold tabular-nums">{v}</span>
            </span>
          ))}
        </div>

        {/* Actions */}
        <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-5 flex flex-wrap gap-3 items-center">
          <button type="button" onClick={() => download("csv")}
            disabled={!active || downloading !== null}
            data-testid="payout-export-csv"
            className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-200 rounded-lg hover:bg-gray-50 disabled:opacity-60">
            {downloading === "csv" ? <Loader2 size={14} className="animate-spin" /> : <Download size={14} />}
            Export CSV
          </button>
          <button type="button" onClick={() => download("pdf")}
            disabled={!active || downloading !== null}
            data-testid="payout-export-pdf"
            className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-[#CC0000] rounded-lg hover:bg-red-700 disabled:opacity-60">
            {downloading === "pdf" ? <Loader2 size={14} className="animate-spin" /> : <FileText size={14} />}
            Export PDF
          </button>

          <div className="flex-1" />

          <button type="button" onClick={approve}
            disabled={!active || busy === "approve" || !data?.users}
            data-testid="payout-approve-btn"
            className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-blue-700 bg-blue-50 border border-blue-200 rounded-lg hover:bg-blue-100 disabled:opacity-60">
            {busy === "approve" ? <Loader2 size={14} className="animate-spin" /> : <ShieldCheck size={14} />}
            Approve Register
          </button>

          <input type="text" value={payrollRef} onChange={(e) => setPayrollRef(e.target.value)}
            placeholder="Payroll ref (optional)"
            data-testid="payroll-ref-input"
            className="text-sm border border-gray-200 rounded-lg px-3 py-2 w-44 focus:outline-none focus:ring-2 focus:ring-green-300" />
          <button type="button" onClick={markPaid}
            disabled={!active || busy === "pay" || !hasApproved}
            data-testid="payout-mark-paid-btn"
            title={hasApproved ? "Mark all approved rows as paid" : "Approve register first"}
            className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-green-700 bg-green-50 border border-green-200 rounded-lg hover:bg-green-100 disabled:opacity-60">
            {busy === "pay" ? <Loader2 size={14} className="animate-spin" /> : <Banknote size={14} />}
            Mark Paid
          </button>
        </div>

        {/* Calc table with status + per-row actions */}
        <section data-testid="payout-table" className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-gray-50 text-left text-[11px] font-semibold uppercase tracking-wider text-gray-500">
                  <th className="px-5 py-2.5">Employee</th>
                  <th className="px-5 py-2.5">Status</th>
                  <th className="px-5 py-2.5 text-right">XP Total</th>
                  <th className="px-5 py-2.5 text-right">Amount (₹)</th>
                  <th className="px-5 py-2.5">Payroll Ref</th>
                  <th className="px-5 py-2.5">Paid On</th>
                  <th className="px-5 py-2.5 text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {loading ? (
                  <tr><td colSpan={7} className="px-5 py-10 text-center text-gray-400 text-sm">
                    <Loader2 size={18} className="animate-spin inline-block" /> Loading…
                  </td></tr>
                ) : (calcs.items || []).length === 0 ? (
                  <tr><td colSpan={7} className="px-5 py-10 text-center text-gray-400 text-sm">
                    No incentive calculations yet — Approve Register to generate rows for this quarter.
                  </td></tr>
                ) : (
                  calcs.items.map((c) => {
                    const xpTotal = c.xp_original + c.xp_replication + c.xp_tech_day + c.xp_other;
                    return (
                      <tr key={c.id} className="border-t border-gray-50 hover:bg-gray-50/50" data-testid={`calc-row-${c.id}`}>
                        <td className="px-5 py-3">
                          <div className="font-medium text-gray-800">{c.name}</div>
                          <div className="text-xs text-gray-400">{c.email}</div>
                        </td>
                        <td className="px-5 py-3">
                          <span data-testid={`calc-status-${c.id}`}
                            className={`text-[11px] font-semibold px-2 py-0.5 rounded-full border ${STATUS_COLOR[c.status] || ""}`}>
                            {c.status?.replace("_", " ")}
                          </span>
                        </td>
                        <td className="px-5 py-3 text-right tabular-nums font-semibold">{xpTotal}</td>
                        <td className="px-5 py-3 text-right tabular-nums font-bold text-[#CC0000]">
                          ₹{c.amount_inr.toLocaleString("en-IN", { minimumFractionDigits: 2 })}
                        </td>
                        <td className="px-5 py-3 text-xs text-gray-500">{c.payroll_ref || "—"}</td>
                        <td className="px-5 py-3 text-xs text-gray-500">{c.payout_date || "—"}</td>
                        <td className="px-5 py-3 text-right">
                          {c.status === "paid" ? (
                            <span className="text-xs text-gray-400">paid · final</span>
                          ) : c.status === "cancelled" ? (
                            <span className="text-xs text-rose-500">cancelled</span>
                          ) : (
                            <div className="inline-flex gap-1">
                              {c.status === "on_hold" ? (
                                <button type="button" onClick={() => resume(c.id)}
                                  disabled={busy === c.id}
                                  data-testid={`calc-resume-${c.id}`}
                                  className="inline-flex items-center gap-1 text-xs px-2 py-1 rounded border border-blue-200 text-blue-700 hover:bg-blue-50 disabled:opacity-50">
                                  {busy === c.id ? <Loader2 size={11} className="animate-spin" /> : <Play size={11} />}
                                  Resume
                                </button>
                              ) : (
                                <button type="button" onClick={() => hold(c.id)}
                                  disabled={busy === c.id}
                                  data-testid={`calc-hold-${c.id}`}
                                  className="inline-flex items-center gap-1 text-xs px-2 py-1 rounded border border-amber-200 text-amber-700 hover:bg-amber-50 disabled:opacity-50">
                                  {busy === c.id ? <Loader2 size={11} className="animate-spin" /> : <PauseCircle size={11} />}
                                  Hold
                                </button>
                              )}
                              <button type="button"
                                onClick={() => setCancelDlg({ calc: c, reason: "" })}
                                disabled={busy === c.id}
                                data-testid={`calc-cancel-${c.id}`}
                                title="Permanently void this calc"
                                className="inline-flex items-center gap-1 text-xs px-2 py-1 rounded border border-rose-200 text-rose-700 hover:bg-rose-50 disabled:opacity-50">
                                <XCircle size={11} /> Cancel
                              </button>
                            </div>
                          )}
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </section>
      </div>
    </div>
  );
}

function SummaryTile({ label, icon, value, mono }) {
  return (
    <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-5">
      <div className="text-[11px] uppercase tracking-wider font-semibold text-gray-400">{label}</div>
      <div className={`text-2xl font-bold text-gray-900 mt-1 flex items-center gap-2 ${mono ? "tabular-nums" : ""}`}>
        {icon} {value}
      </div>
    </div>
  );
}

/* ── In-app modal primitives (tiny — no extra dependency) ─────────────── */
function Modal({ children, onClose, testId }) {
  return (
    <div role="dialog" aria-modal="true"
      data-testid={testId}
      className="fixed inset-0 z-[300] flex items-center justify-center p-4">
      {/* Backdrop */}
      <button type="button"
        aria-label="Dismiss dialog"
        onClick={onClose}
        className="absolute inset-0 bg-black/40 backdrop-blur-sm cursor-default" />
      <div className="relative bg-white rounded-xl shadow-2xl border border-gray-100 w-full max-w-md animate-in fade-in zoom-in-95 duration-150">
        {children}
      </div>
    </div>
  );
}
function ModalHeader({ title, onClose }) {
  return (
    <div className="flex items-center justify-between px-5 py-3 border-b border-gray-100">
      <h2 className="text-sm font-semibold text-gray-900">{title}</h2>
      <button type="button" onClick={onClose}
        aria-label="Close dialog"
        className="text-gray-400 hover:text-gray-700 p-1 rounded">
        <X size={16} />
      </button>
    </div>
  );
}
function ModalFooter({ children }) {
  return (
    <div className="flex justify-end gap-2 px-5 py-3 border-t border-gray-100 bg-gray-50/50 rounded-b-xl">
      {children}
    </div>
  );
}
