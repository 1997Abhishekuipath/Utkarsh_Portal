import React, { useState, useEffect, useMemo } from "react";
import axios from "axios";
import { API } from "../../../contexts/AuthContext";
import {
  Sparkles, Loader2, RefreshCw, Calendar, Building2, ChevronDown,
  TrendingUp, AlertTriangle, ThumbsUp, ListChecks, Target, Zap,
} from "lucide-react";

const authHeader = () => ({ Authorization: `Bearer ${localStorage.getItem("hsi_token")}` });

const SENT_META = {
  positive: { dot: "bg-emerald-500", text: "text-emerald-700", bg: "bg-emerald-50" },
  negative: { dot: "bg-rose-500",    text: "text-rose-700",    bg: "bg-rose-50" },
  mixed:    { dot: "bg-amber-500",   text: "text-amber-700",   bg: "bg-amber-50" },
};

const SEV_META = {
  high:   { text: "text-rose-700",   bg: "bg-rose-50",   border: "border-rose-200" },
  medium: { text: "text-amber-700",  bg: "bg-amber-50",  border: "border-amber-200" },
  low:    { text: "text-slate-600",  bg: "bg-slate-50",  border: "border-slate-200" },
};

const PRIO_META = {
  P0: { text: "text-rose-700",   bg: "bg-rose-50",   border: "border-rose-200" },
  P1: { text: "text-amber-700",  bg: "bg-amber-50",  border: "border-amber-200" },
  P2: { text: "text-slate-600",  bg: "bg-slate-50",  border: "border-slate-200" },
};

export default function AiInsightsTab() {
  const [insights, setInsights]   = useState([]);
  const [accounts, setAccounts]   = useState([]);
  const [active,   setActive]     = useState(null);     // currently displayed snapshot
  const [loading,  setLoading]    = useState(true);
  const [generating, setGenerating] = useState(false);
  const [error,    setError]      = useState(null);

  // Generate-form state
  const [period,    setPeriod]    = useState(`Q${Math.floor(new Date().getMonth() / 3) + 1} ${new Date().getFullYear()}`);
  const [days,      setDays]      = useState(90);
  const [accountId, setAccountId] = useState("");

  const load = async () => {
    try {
      const [ins, acc] = await Promise.all([
        axios.get(`${API}/voc/insights`, { headers: authHeader() }),
        axios.get(`${API}/voc/accounts`, { headers: authHeader() }),
      ]);
      setInsights(ins.data || []);
      setAccounts(acc.data?.accounts || []);
      if ((ins.data || []).length && !active) setActive(ins.data[0]);
    } catch (e) {
      setError("Failed to load insights");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); /* eslint-disable-line */ }, []);

  const handleGenerate = async () => {
    setGenerating(true); setError(null);
    try {
      const r = await axios.post(`${API}/voc/insights/generate`,
        { period, days: Number(days), account_id: accountId || null },
        { headers: authHeader() });
      setInsights(prev => [r.data, ...prev]);
      setActive(r.data);
    } catch (e) {
      setError(e?.response?.data?.detail || "Failed to generate insights");
    } finally {
      setGenerating(false);
    }
  };

  const ins = useMemo(() => active?.insights || {}, [active]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 size={28} className="animate-spin text-[#CC0000]" />
      </div>
    );
  }

  return (
    <main className="max-w-screen-2xl mx-auto px-6 py-6" data-testid="ai-insights-tab">

      {/* Header & Generate Bar */}
      <div className="flex items-start justify-between mb-6 gap-6 flex-wrap">
        <div>
          <h2 className="text-2xl font-bold text-[#0F172A] font-['Outfit'] flex items-center gap-2">
            <Sparkles size={20} className="text-violet-600" />AI Insights
          </h2>
          <p className="text-[#64748B] text-sm mt-1">
            McKinsey-style executive summary, themes, pain points and recommendations — generated from VoC responses.
          </p>
        </div>

        <div className="flex items-end gap-2 flex-wrap">
          <div>
            <label className="block text-[10px] font-bold tracking-wider text-[#64748B] mb-1">PERIOD</label>
            <div className="relative">
              <Calendar size={12} className="absolute left-3 top-1/2 -translate-y-1/2 text-[#94A3B8] pointer-events-none" />
              <input value={period} onChange={e => setPeriod(e.target.value)}
                className="pl-8 pr-3 py-2 text-xs border-2 border-[#E2E8F0] rounded-lg focus:border-violet-500 focus:outline-none w-32"
                data-testid="ai-insight-period-input" />
            </div>
          </div>
          <div>
            <label className="block text-[10px] font-bold tracking-wider text-[#64748B] mb-1">DAYS BACK</label>
            <select value={days} onChange={e => setDays(e.target.value)}
              className="px-3 py-2 text-xs border-2 border-[#E2E8F0] rounded-lg focus:border-violet-500 focus:outline-none bg-white w-24"
              data-testid="ai-insight-days-select">
              {[30, 60, 90, 120, 180].map(d => <option key={d} value={d}>{d}d</option>)}
            </select>
          </div>
          <div>
            <label className="block text-[10px] font-bold tracking-wider text-[#64748B] mb-1">ACCOUNT</label>
            <div className="relative">
              <Building2 size={12} className="absolute left-3 top-1/2 -translate-y-1/2 text-[#94A3B8] pointer-events-none" />
              <select value={accountId} onChange={e => setAccountId(e.target.value)}
                className="pl-8 pr-7 py-2 text-xs border-2 border-[#E2E8F0] rounded-lg focus:border-violet-500 focus:outline-none bg-white appearance-none w-48"
                data-testid="ai-insight-account-select">
                <option value="">All accounts</option>
                {accounts.map(a => <option key={a.id} value={a.id}>{a.company_name}</option>)}
              </select>
              <ChevronDown size={12} className="absolute right-3 top-1/2 -translate-y-1/2 text-[#94A3B8] pointer-events-none" />
            </div>
          </div>
          <button onClick={handleGenerate} disabled={generating}
            className="flex items-center gap-2 px-5 py-2 rounded-lg text-xs font-bold text-white bg-violet-600 hover:bg-violet-700 transition-colors disabled:opacity-60"
            data-testid="generate-insights-btn">
            {generating
              ? <><Loader2 size={13} className="animate-spin" />ANALYZING…</>
              : <><Zap size={13} />GENERATE INSIGHTS</>}
          </button>
        </div>
      </div>

      {error && (
        <div className="mb-4 px-4 py-3 bg-rose-50 border border-rose-200 rounded-lg text-sm text-rose-700"
          data-testid="ai-insight-error">{error}</div>
      )}

      {insights.length === 0 ? (
        <div className="flex items-center justify-center h-72 border-2 border-dashed border-[#E2E8F0] rounded-xl"
          data-testid="ai-insight-empty">
          <div className="text-center max-w-sm">
            <div className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-violet-50 flex items-center justify-center">
              <Sparkles size={28} className="text-violet-600" />
            </div>
            <h3 className="text-base font-bold text-[#0F172A] mb-1">No insights yet</h3>
            <p className="text-sm text-[#64748B]">
              Click <span className="font-bold text-violet-700">GENERATE INSIGHTS</span> to run an AI analysis on your latest VoC responses.
            </p>
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-12 gap-5">

          {/* Snapshots side panel */}
          <aside className="col-span-3" data-testid="ai-insight-history">
            <div className="text-[10px] font-bold tracking-widest text-[#64748B] uppercase mb-3 flex items-center gap-1.5">
              <RefreshCw size={11} />Recent runs ({insights.length})
            </div>
            <div className="space-y-2 max-h-[700px] overflow-y-auto pr-1">
              {insights.map(s => {
                const isActive = active?.id === s.id;
                return (
                  <button key={s.id}
                    onClick={() => setActive(s)}
                    data-testid={`insight-history-${s.id}`}
                    className={`w-full text-left px-3 py-2.5 rounded-lg border transition-all ${
                      isActive
                        ? "border-violet-500 bg-violet-50 shadow-sm"
                        : "border-[#E2E8F0] bg-white hover:border-violet-200"
                    }`}>
                    <div className="text-xs font-bold text-[#0F172A] mb-0.5">{s.period || "Untitled period"}</div>
                    <div className="text-[10px] text-[#64748B] flex items-center gap-2">
                      <span>{s.total_responses ?? 0} resp</span>
                      {s.nps_score !== null && <span>· NPS {s.nps_score}</span>}
                    </div>
                    <div className="text-[9px] text-[#94A3B8] mt-1">
                      {s.generated_at ? new Date(s.generated_at).toLocaleString() : ""}
                    </div>
                  </button>
                );
              })}
            </div>
          </aside>

          {/* Active snapshot */}
          <section className="col-span-9 space-y-5">

            {/* Top KPI strip */}
            <div className="grid grid-cols-4 gap-4">
              {[
                { label: "PERIOD",        value: active?.period || "—" },
                { label: "RESPONSES",     value: active?.total_responses ?? "—" },
                { label: "NPS",           value: active?.nps_score ?? "—" },
                { label: "CSAT",          value: active?.csat_score ?? "—" },
              ].map(k => (
                <div key={k.label} className="bg-white rounded-xl border border-[#E2E8F0] px-5 py-4 shadow-sm">
                  <div className="text-[10px] font-bold tracking-widest text-[#64748B] mb-1">{k.label}</div>
                  <div className="text-xl font-bold text-[#0F172A]">{k.value}</div>
                </div>
              ))}
            </div>

            {/* Executive summary */}
            <div className="bg-gradient-to-br from-violet-600 via-violet-700 to-indigo-700 rounded-xl p-6 text-white shadow-lg"
              data-testid="executive-summary">
              <div className="flex items-center gap-2 mb-3 text-violet-200 text-[10px] font-bold tracking-widest">
                <Target size={12} />EXECUTIVE SUMMARY · MCKINSEY SCR
              </div>
              <p className="text-base leading-relaxed">{ins.executive_summary || "No summary generated."}</p>
              <div className="mt-4 pt-3 border-t border-white/15 text-[10px] tracking-wider text-violet-200 flex items-center gap-3">
                <span>MODEL · {active?.model_used || "—"}</span>
                {active?.generated_at && (<span>· {new Date(active.generated_at).toLocaleString()}</span>)}
              </div>
            </div>

            <div className="grid grid-cols-2 gap-5">

              {/* Themes */}
              <div className="bg-white rounded-xl border border-[#E2E8F0] p-5 shadow-sm" data-testid="themes-card">
                <div className="flex items-center gap-2 mb-3">
                  <TrendingUp size={14} className="text-violet-600" />
                  <h3 className="text-sm font-bold text-[#0F172A]">Key Themes</h3>
                  <span className="text-[10px] text-[#64748B] ml-auto">{ins.key_themes?.length || 0}</span>
                </div>
                <div className="space-y-2">
                  {(ins.key_themes || []).map((t, i) => {
                    const meta = SENT_META[t.sentiment] || SENT_META.mixed;
                    return (
                      <div key={i} className={`flex items-center justify-between px-3 py-2.5 rounded-lg ${meta.bg}`}>
                        <div className="flex items-center gap-2">
                          <span className={`w-1.5 h-1.5 rounded-full ${meta.dot}`} />
                          <span className="text-sm font-semibold text-[#0F172A]">{t.theme}</span>
                        </div>
                        <span className={`text-[10px] font-bold ${meta.text}`}>×{t.frequency || 0}</span>
                      </div>
                    );
                  })}
                  {(!ins.key_themes || ins.key_themes.length === 0) && (
                    <p className="text-xs text-[#94A3B8] italic">No themes identified.</p>
                  )}
                </div>
              </div>

              {/* Strengths */}
              <div className="bg-white rounded-xl border border-[#E2E8F0] p-5 shadow-sm" data-testid="strengths-card">
                <div className="flex items-center gap-2 mb-3">
                  <ThumbsUp size={14} className="text-emerald-600" />
                  <h3 className="text-sm font-bold text-[#0F172A]">Strengths</h3>
                  <span className="text-[10px] text-[#64748B] ml-auto">{ins.strengths?.length || 0}</span>
                </div>
                <div className="space-y-2">
                  {(ins.strengths || []).map((s, i) => (
                    <div key={i} className="px-3 py-2.5 rounded-lg bg-emerald-50/50 border border-emerald-100">
                      <div className="text-sm font-semibold text-[#0F172A]">{s.strength}</div>
                      {s.evidence && <div className="text-[11px] text-[#64748B] mt-0.5">"{s.evidence}"</div>}
                    </div>
                  ))}
                  {(!ins.strengths || ins.strengths.length === 0) && (
                    <p className="text-xs text-[#94A3B8] italic">No strengths flagged.</p>
                  )}
                </div>
              </div>
            </div>

            {/* Pain points */}
            <div className="bg-white rounded-xl border border-[#E2E8F0] p-5 shadow-sm" data-testid="pain-points-card">
              <div className="flex items-center gap-2 mb-3">
                <AlertTriangle size={14} className="text-rose-600" />
                <h3 className="text-sm font-bold text-[#0F172A]">Pain Points</h3>
                <span className="text-[10px] text-[#64748B] ml-auto">{ins.pain_points?.length || 0}</span>
              </div>
              <div className="space-y-2">
                {(ins.pain_points || []).map((p, i) => {
                  const meta = SEV_META[p.severity] || SEV_META.medium;
                  return (
                    <div key={i} className={`px-4 py-3 rounded-lg border ${meta.bg} ${meta.border}`}>
                      <div className="flex items-start justify-between gap-3">
                        <div className="flex-1">
                          <div className="text-sm font-semibold text-[#0F172A]">{p.issue}</div>
                          {p.evidence && <div className="text-[11px] text-[#64748B] mt-1">{p.evidence}</div>}
                        </div>
                        <span className={`text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded ${meta.text}`}>
                          {p.severity}
                        </span>
                      </div>
                    </div>
                  );
                })}
                {(!ins.pain_points || ins.pain_points.length === 0) && (
                  <p className="text-xs text-[#94A3B8] italic">No pain points found.</p>
                )}
              </div>
            </div>

            {/* Recommendations */}
            <div className="bg-white rounded-xl border border-[#E2E8F0] p-5 shadow-sm" data-testid="recommendations-card">
              <div className="flex items-center gap-2 mb-3">
                <ListChecks size={14} className="text-violet-600" />
                <h3 className="text-sm font-bold text-[#0F172A]">Recommendations</h3>
                <span className="text-[10px] text-[#64748B] ml-auto">{ins.recommendations?.length || 0}</span>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-left">
                  <thead>
                    <tr className="text-[10px] font-bold tracking-widest text-[#64748B] uppercase border-b border-[#E2E8F0]">
                      <th className="py-2 pr-3">Priority</th>
                      <th className="py-2 pr-3">Action</th>
                      <th className="py-2 pr-3">Owner</th>
                      <th className="py-2">Expected Impact</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(ins.recommendations || []).map((r, i) => {
                      const meta = PRIO_META[r.priority] || PRIO_META.P2;
                      return (
                        <tr key={i} className="border-b border-[#F1F5F9] last:border-b-0">
                          <td className="py-3 pr-3">
                            <span className={`text-[10px] font-bold px-2 py-0.5 rounded border ${meta.bg} ${meta.text} ${meta.border}`}>
                              {r.priority}
                            </span>
                          </td>
                          <td className="py-3 pr-3 text-sm text-[#0F172A] font-semibold">{r.action}</td>
                          <td className="py-3 pr-3 text-xs text-[#475569]">{r.owner || "—"}</td>
                          <td className="py-3 text-xs text-[#475569]">{r.expected_impact || "—"}</td>
                        </tr>
                      );
                    })}
                    {(!ins.recommendations || ins.recommendations.length === 0) && (
                      <tr><td colSpan="4" className="py-3 text-xs text-[#94A3B8] italic">No recommendations generated.</td></tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Risk accounts */}
            {ins.risk_accounts && ins.risk_accounts.length > 0 && (
              <div className="bg-rose-50 border border-rose-200 rounded-xl p-5" data-testid="risk-accounts-card">
                <div className="flex items-center gap-2 mb-2 text-rose-700">
                  <AlertTriangle size={14} />
                  <h3 className="text-sm font-bold">Risk Accounts</h3>
                </div>
                <ul className="space-y-1 text-xs text-rose-900">
                  {ins.risk_accounts.map((r, i) => <li key={i}>· {r}</li>)}
                </ul>
              </div>
            )}

          </section>
        </div>
      )}
    </main>
  );
}
