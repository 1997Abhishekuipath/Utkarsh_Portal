import React from "react";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer,
} from "recharts";
import {
  TrendingUp, TrendingDown, Minus, Users, Star, RefreshCw,
  MessageSquare, Loader2,
} from "lucide-react";
import { useVocDashboard } from "../../../hooks/useVocDashboard";

// ── Skeleton ─────────────────────────────────────────────────────────────────
const Skeleton = ({ className = "" }) => (
  <div className={`animate-pulse bg-slate-200 rounded ${className}`} />
);

// ── NPS Gauge (light version) ─────────────────────────────────────────────────
const NPSGauge = ({ score = 0, detractors = 0, passives = 0, promoters = 0 }) => {
  const cx = 120, cy = 105, r = 88, sw = 13;
  const pt = (deg) => ({
    x: cx + r * Math.cos((deg * Math.PI) / 180),
    y: cy - r * Math.sin((deg * Math.PI) / 180),
  });
  const detEnd  = 180 - detractors / 100 * 180;
  const pasEnd  = detEnd - passives / 100 * 180;
  const left    = pt(180), detEndPt = pt(detEnd), pasEndPt = pt(pasEnd), right = pt(0);
  const npsAngle = 180 - (score + 100) / 200 * 180;
  const needle  = pt(npsAngle);

  return (
    <svg viewBox="0 0 240 125" className="w-full max-w-[260px] mx-auto">
      <path d={`M ${left.x} ${left.y} A ${r} ${r} 0 0 1 ${right.x} ${right.y}`}
        fill="none" stroke="#E2E8F0" strokeWidth={sw} strokeLinecap="round" />
      <path d={`M ${left.x} ${left.y} A ${r} ${r} 0 0 1 ${detEndPt.x} ${detEndPt.y}`}
        fill="none" stroke="#EF4444" strokeWidth={sw} />
      <path d={`M ${detEndPt.x} ${detEndPt.y} A ${r} ${r} 0 0 1 ${pasEndPt.x} ${pasEndPt.y}`}
        fill="none" stroke="#F59E0B" strokeWidth={sw} />
      <path d={`M ${pasEndPt.x} ${pasEndPt.y} A ${r} ${r} 0 0 1 ${right.x} ${right.y}`}
        fill="none" stroke="#22C55E" strokeWidth={sw} />
      <circle cx={needle.x} cy={needle.y} r="8" fill="white" stroke="#94A3B8" strokeWidth="2" />
      <text x={cx} y={cy - 4} textAnchor="middle" fill="#0F172A" fontSize="30" fontWeight="bold" fontFamily="Outfit">
        {score > 0 ? `+${score}` : score}
      </text>
      <text x={cx} y={cy + 14} textAnchor="middle" fill="#22C55E" fontSize="8" letterSpacing="2" fontWeight="600">
        {score >= 50 ? "WORLD-CLASS NPS" : score >= 30 ? "GOOD NPS" : "NEEDS IMPROVEMENT"}
      </text>
      <text x="18"  y={cy + 12} fill="#EF4444" fontSize="8" textAnchor="middle">{detractors}%</text>
      <text x="222" y={cy + 12} fill="#22C55E" fontSize="8" textAnchor="middle">{promoters}%</text>
    </svg>
  );
};

// ── Chart Tooltip ─────────────────────────────────────────────────────────────
const ChartTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-white border border-[#E2E8F0] rounded-lg px-3 py-2 text-xs shadow-lg">
      <p className="text-[#64748B] mb-1 font-medium">{label}</p>
      {payload.map(p => (
        <p key={p.name} style={{ color: p.color }} className="font-semibold">
          {p.name === "nps" ? "NPS" : "CSAT"}: {p.name === "nps" ? `+${p.value}` : `${p.value}%`}
        </p>
      ))}
    </div>
  );
};

const npsColor = (v) => v >= 50 ? "#22C55E" : v >= 30 ? "#F59E0B" : "#EF4444";
const csatBarColor = (i) => ["#22C55E","#84CC16","#F59E0B","#F97316","#EF4444"][i];

// ── Main Component ────────────────────────────────────────────────────────────
export default function DashboardTab() {
  const { kpis, trend, verbatims, painPoints, csatDist, strengths, accounts, loading, error, lastSync, refetch } = useVocDashboard();

  const formatSync = (d) => {
    if (!d) return "Never";
    const diff = Math.round((Date.now() - d.getTime()) / 1000);
    if (diff < 60)  return `${diff}s ago`;
    if (diff < 3600) return `${Math.round(diff/60)} min ago`;
    return d.toLocaleTimeString();
  };

  if (loading) {
    return (
      <main className="max-w-screen-2xl mx-auto px-6 py-6 space-y-5">
        <div className="flex items-start justify-between">
          <div className="space-y-2">
            <Skeleton className="h-4 w-48" />
            <Skeleton className="h-10 w-80" />
            <Skeleton className="h-4 w-96" />
          </div>
        </div>
        <div className="grid grid-cols-5 gap-4">
          {[...Array(5)].map((_,i) => <Skeleton key={i} className="h-28" />)}
        </div>
        <div className="grid grid-cols-12 gap-4">
          <Skeleton className="col-span-6 h-72" />
          <Skeleton className="col-span-3 h-72" />
          <Skeleton className="col-span-3 h-72" />
        </div>
      </main>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <p className="text-red-500 font-semibold mb-2">Failed to load dashboard data</p>
          <p className="text-[#64748B] text-sm mb-4">{error}</p>
          <button onClick={refetch} className="px-4 py-2 bg-[#CC0000] text-white rounded-lg text-sm font-semibold">
            Retry
          </button>
        </div>
      </div>
    );
  }

  const totalResp = kpis?.total_responses || 0;
  const activeAccounts = kpis?.active_accounts || 0;
  const trendFilt = trend.filter(t => t.nps !== null && t.csat !== null);

  return (
    <main className="max-w-screen-2xl mx-auto px-6 py-6 space-y-5">

      {/* ── PAGE HEADER ──────────────────────────────────────────────────── */}
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-3 mb-2">
            <span className="text-[10px] font-bold tracking-[0.2em] px-3 py-1 rounded-full border border-violet-200 bg-violet-50 text-violet-700">
              Q2 2026 · VOICE OF CUSTOMER INTELLIGENCE
            </span>
            <span className="text-[10px] text-[#94A3B8]">
              Last sync: {formatSync(lastSync)}
            </span>
          </div>
          <h1 className="text-4xl font-bold text-[#0F172A] leading-tight font-['Outfit']">
            Customer Experience<br />
            <span className="text-[#CC0000]">Command Centre</span>
          </h1>
          <p className="text-[#64748B] text-sm mt-2 max-w-xl">
            Real-time CSAT &amp; NPS intelligence across all HSI accounts. McKinsey-grade analytics. BCG-structured insights.
          </p>
          <div className="flex items-center gap-5 mt-3">
            {[
              [totalResp.toString(),    "Responses"],
              [activeAccounts.toString(), "Active Accounts"],
              ["0",                       "Campaigns Running"],
              [formatSync(lastSync),     "Last sync"],
            ].map(([v, l]) => (
              <div key={l} className="flex items-center gap-1.5">
                <span className="text-[#0F172A] font-semibold text-sm">{v}</span>
                <span className="text-[#64748B] text-xs">{l}</span>
              </div>
            ))}
          </div>
        </div>
        <button
          onClick={refetch}
          className="flex items-center gap-2 px-4 py-2.5 rounded-lg text-xs font-bold tracking-wider border border-[#E2E8F0] text-[#64748B] bg-white hover:border-[#CC0000]/30 hover:text-[#0F172A] transition-colors"
        >
          <RefreshCw size={13} />REFRESH
        </button>
      </div>

      {/* ── 5 KPI CARDS ──────────────────────────────────────────────────── */}
      <div className="grid grid-cols-5 gap-4">
        {[
          {
            label: "NPS SCORE",
            value: kpis ? (kpis.nps_score > 0 ? `+${kpis.nps_score}` : String(kpis.nps_score)) : "—",
            sub: `▲ ${kpis?.nps_delta_qoq || 0}pts vs last quarter`,
            bench: "World-class ≥ +50",
            color: npsColor(kpis?.nps_score || 0),
            Icon: TrendingUp,
          },
          {
            label: "CSAT SCORE",
            value: kpis ? `${kpis.csat_score}%` : "—",
            sub: `▲ ${kpis?.csat_delta_mom || 0}% MoM`,
            bench: "Target ≥ 85%",
            color: (kpis?.csat_score || 0) >= 85 ? "#22C55E" : "#F59E0B",
            Icon: Star,
          },
          {
            label: "RESPONSE RATE",
            value: kpis ? `${kpis.response_rate}%` : "—",
            sub: "▲ 12% vs benchmark",
            bench: "Industry avg: 54%",
            color: "#3B82F6",
            Icon: Users,
          },
          {
            label: "PROMOTERS",
            value: kpis ? `${kpis.promoter_pct}%` : "—",
            sub: `▲ 5pts vs Q1`,
            bench: `Detractors: ${kpis?.detractor_pct || 0}%`,
            color: "#F59E0B",
            Icon: TrendingUp,
          },
          {
            label: "CES SCORE",
            value: kpis ? String(kpis.ces_score) : "—",
            sub: "→ Stable",
            bench: "Customer Effort (1-5)",
            color: "#94A3B8",
            Icon: Minus,
          },
        ].map((k, i) => (
          <div key={k.label} data-testid={`kpi-card-${i}`}
            className="bg-white rounded-xl p-5 border border-[#E2E8F0] shadow-sm hover:shadow-md transition-shadow">
            <div className="flex items-start justify-between mb-3">
              <span className="text-[10px] font-bold tracking-[0.15em] text-[#64748B]">{k.label}</span>
              <k.Icon size={16} style={{ color: k.color }} />
            </div>
            <div className="text-4xl font-bold mb-1 font-['Outfit']" style={{ color: k.color }}>{k.value}</div>
            <div className="text-[11px] mb-0.5 font-semibold" style={{ color: k.color }}>{k.sub}</div>
            <div className="text-[10px] text-[#94A3B8]">{k.bench}</div>
          </div>
        ))}
      </div>

      {/* ── CHARTS ROW ─────────────────────────────────────────────────────── */}
      <div className="grid grid-cols-12 gap-4">
        {/* Trend Chart */}
        <div className="col-span-6 bg-white rounded-xl p-5 border border-[#E2E8F0] shadow-sm">
          <div className="flex items-center justify-between mb-4">
            <div>
              <div className="text-[11px] font-bold tracking-widest text-[#64748B] uppercase mb-0.5">Trend</div>
              <h3 className="text-sm font-bold text-[#0F172A]">NPS &amp; CSAT Trend — Last 12 Months</h3>
            </div>
          </div>
          <div className="flex items-center gap-5 mb-4">
            {[{ color:"#CC0000", label:"NPS Score" }, { color:"#22C55E", label:"CSAT %" }].map(l => (
              <div key={l.label} className="flex items-center gap-2 text-xs text-[#64748B]">
                <div className="w-6 h-0.5 rounded" style={{ background: l.color }} />
                {l.label}
              </div>
            ))}
          </div>
          {trendFilt.length > 0 ? (
            <ResponsiveContainer width="100%" height={200}>
              <LineChart data={trendFilt} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
                <CartesianGrid stroke="#E2E8F0" strokeDasharray="3 3" />
                <XAxis dataKey="month" tick={{ fill: "#64748B", fontSize: 11 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: "#64748B", fontSize: 11 }} axisLine={false} tickLine={false} />
                <Tooltip content={<ChartTooltip />} />
                <Line type="monotone" dataKey="nps"  stroke="#CC0000" strokeWidth={2.5} dot={false} name="nps" />
                <Line type="monotone" dataKey="csat" stroke="#22C55E" strokeWidth={2.5} dot={false} name="csat" />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-[200px] flex items-center justify-center text-[#94A3B8] text-sm">
              No trend data available yet
            </div>
          )}
        </div>

        {/* NPS Gauge */}
        <div className="col-span-3 bg-white rounded-xl p-5 border border-[#E2E8F0] shadow-sm flex flex-col">
          <div className="mb-3">
            <div className="text-[10px] font-bold tracking-widest text-[#64748B] uppercase mb-0.5">Gauge</div>
            <h3 className="text-sm font-bold text-[#0F172A]">Net Promoter Score</h3>
            <span className="text-[10px] text-[#64748B]">Q2 2026</span>
          </div>
          <div className="flex-1 flex flex-col items-center justify-center">
            <NPSGauge
              score={kpis?.nps_score || 0}
              detractors={kpis?.detractor_pct || 0}
              passives={kpis?.passive_pct || 0}
              promoters={kpis?.promoter_pct || 0}
            />
            <div className="flex items-center justify-center gap-4 mt-3">
              {[
                { color:"#EF4444", pct:`${kpis?.detractor_pct||0}%`, label:"Detractors" },
                { color:"#F59E0B", pct:`${kpis?.passive_pct||0}%`,   label:"Passives"   },
                { color:"#22C55E", pct:`${kpis?.promoter_pct||0}%`,  label:"Promoters"  },
              ].map(s => (
                <div key={s.label} className="flex items-center gap-1.5 text-[10px]">
                  <div className="w-2 h-2 rounded-full" style={{ background: s.color }} />
                  <span style={{ color: s.color }}>{s.pct}</span>
                  <span className="text-[#64748B]">{s.label}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* CSAT Distribution */}
        <div className="col-span-3 bg-white rounded-xl p-5 border border-[#E2E8F0] shadow-sm">
          <div className="mb-4">
            <div className="text-[10px] font-bold tracking-widest text-[#64748B] uppercase mb-0.5">Distribution</div>
            <h3 className="text-sm font-bold text-[#0F172A]">CSAT Distribution</h3>
            <span className="text-[10px] text-[#64748B]">{totalResp} RESPONSES</span>
          </div>
          {csatDist.length > 0 ? (
            <>
              <div className="space-y-3">
                {csatDist.map((d, i) => (
                  <div key={d.rating} className="flex items-center gap-3">
                    <span className="text-xs w-7 text-right flex-shrink-0 font-semibold" style={{ color: csatBarColor(i) }}>{d.rating}</span>
                    <div className="flex-1 h-2 rounded-full bg-[#F1F5F9]">
                      <div className="h-full rounded-full transition-all" style={{ width: `${d.pct}%`, background: csatBarColor(i) }} />
                    </div>
                    <span className="text-xs text-[#64748B] w-6 flex-shrink-0">{d.count}</span>
                  </div>
                ))}
              </div>
              <div className="mt-4 pt-3 border-t border-[#E2E8F0] flex items-center justify-between">
                <span className="text-[11px] text-[#64748B]">Score: <strong className="text-[#0F172A]">{kpis?.ces_score || "—"} / 5.0</strong></span>
                <span className="text-[11px] font-bold text-emerald-600">CSAT: {kpis?.csat_score || 0}%</span>
              </div>
            </>
          ) : (
            <div className="flex items-center justify-center h-36 text-[#94A3B8] text-sm">No data</div>
          )}
        </div>
      </div>

      {/* ── INSIGHTS ROW ──────────────────────────────────────────────────── */}
      <div className="grid grid-cols-3 gap-4">
        {/* Top Pain Points */}
        <div className="bg-white rounded-xl p-5 border border-[#E2E8F0] shadow-sm">
          <div className="flex items-start justify-between mb-4">
            <div>
              <div className="text-[10px] font-bold tracking-widest text-[#64748B] uppercase mb-0.5">Analysis</div>
              <h3 className="text-sm font-bold text-[#0F172A]">Top Pain Points</h3>
            </div>
            <span className="text-[10px] font-bold px-2 py-1 rounded-lg bg-red-50 text-red-600">NEEDS ACTION</span>
          </div>
          {painPoints.length > 0 ? (
            <div className="space-y-4">
              {painPoints.map((p) => (
                <div key={p.label}>
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-sm font-semibold text-[#0F172A]">{p.label}</span>
                    <span className="text-xs font-bold" style={{ color: p.color }}>{p.pct}%</span>
                  </div>
                  <div className="text-[10px] text-[#94A3B8] mb-1.5">{p.sub}</div>
                  <div className="h-1.5 rounded-full bg-[#F1F5F9]">
                    <div className="h-full rounded-full" style={{ width: `${p.pct}%`, background: p.color, transition: "width 1s ease" }} />
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="flex items-center justify-center h-36 text-[#94A3B8] text-sm">No pain point data</div>
          )}
        </div>

        {/* What We're Doing Well */}
        <div className="bg-white rounded-xl p-5 border border-[#E2E8F0] shadow-sm">
          <div className="flex items-start justify-between mb-4">
            <div>
              <div className="text-[10px] font-bold tracking-widest text-[#64748B] uppercase mb-0.5">Strengths</div>
              <h3 className="text-sm font-bold text-[#0F172A]">What We're Doing Well</h3>
            </div>
            <span className="text-[10px] font-bold px-2 py-1 rounded-lg bg-emerald-50 text-emerald-700">SUSTAIN &amp; SCALE</span>
          </div>
          {strengths.length > 0 ? (
            <div className="space-y-4">
              {strengths.map((d, i) => (
                <div key={i} className="flex gap-3">
                  <div className="flex-shrink-0 text-center">
                    <span className="text-[10px] font-bold block"
                      style={{ color: i === 0 ? "#F59E0B" : "#22C55E" }}>{d.badge}</span>
                  </div>
                  <div>
                    <p className="text-xs text-[#475569] italic leading-relaxed mb-1">{d.quote}</p>
                    <p className="text-[10px] text-[#94A3B8]">{d.tag}</p>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="flex items-center justify-center h-36 text-[#94A3B8] text-sm">No strengths data</div>
          )}
        </div>

        {/* Account Health */}
        <div className="bg-white rounded-xl p-5 border border-[#E2E8F0] shadow-sm">
          <div className="flex items-start justify-between mb-4">
            <div>
              <div className="text-[10px] font-bold tracking-widest text-[#64748B] uppercase mb-0.5">Accounts</div>
              <h3 className="text-sm font-bold text-[#0F172A]">Account Health</h3>
            </div>
            <span className="text-[10px] font-bold px-2 py-1 rounded-lg bg-amber-50 text-amber-700">NEEDS REVIEW</span>
          </div>
          {accounts.length > 0 ? (
            <div className="space-y-2">
              {accounts.map(a => {
                const col = npsColor(a.latest_nps || 0);
                return (
                  <div key={a.id} className="flex items-center gap-3 p-2 rounded-lg hover:bg-[#F8FAFC] transition-colors">
                    <div className="w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 text-[11px] font-bold text-white bg-[#CC0000]">
                      {a.initials}
                    </div>
                    <span className="flex-1 text-sm text-[#0F172A]">{a.company_name}</span>
                    <div className="flex items-center gap-1.5">
                      <div className="w-2 h-2 rounded-full" style={{ background: col }} />
                      <span className="text-sm font-bold" style={{ color: col }}>
                        NPS: {(a.latest_nps || 0) > 0 ? `+${a.latest_nps}` : (a.latest_nps || 0)}
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="flex items-center justify-center h-36 text-[#94A3B8] text-sm">No accounts</div>
          )}
        </div>
      </div>

      {/* ── VERBATIMS ────────────────────────────────────────────────────── */}
      <div>
        <div className="flex items-center gap-2 mb-4">
          <MessageSquare size={14} className="text-[#64748B]" />
          <span className="text-[11px] font-bold tracking-[0.15em] text-[#64748B] uppercase">
            RECENT CUSTOMER VERBATIMS — AI CATEGORISED
          </span>
        </div>
        {verbatims.length > 0 ? (
          <div className="grid grid-cols-3 gap-4 pb-8">
            {verbatims.slice(0, 3).map((v, i) => (
              <div key={v.id || i} data-testid={`verbatim-${i}`}
                className="bg-white rounded-xl p-5 border border-[#E2E8F0] shadow-sm">
                <div className="flex items-center gap-2 mb-4">
                  <span className="text-[10px] font-bold px-2.5 py-1 rounded-full"
                    style={{ background: (v.color || "#94A3B8") + "18", color: v.color || "#94A3B8" }}>
                    {v.type}
                  </span>
                  <span className="text-[10px] font-bold text-[#64748B]">NPS {v.score}</span>
                  <span className="text-[10px] text-[#94A3B8] ml-auto">{v.account_name}</span>
                </div>
                <p className="text-sm text-[#475569] italic leading-relaxed">{v.text}</p>
              </div>
            ))}
          </div>
        ) : (
          <div className="flex items-center justify-center h-32 text-[#94A3B8] text-sm">No verbatims yet</div>
        )}
      </div>
    </main>
  );
}
