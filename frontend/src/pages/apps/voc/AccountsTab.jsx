import React, { useState, useEffect } from "react";
import axios from "axios";
import { API } from "../../../contexts/AuthContext";
import { Building2, TrendingUp, TrendingDown, Minus, Loader2, AlertCircle } from "lucide-react";

const authHeader = () => ({
  Authorization: `Bearer ${localStorage.getItem("hsi_token")}`,
});

const npsColor = (v) => v >= 50 ? "#22C55E" : v >= 30 ? "#F59E0B" : "#EF4444";
const ragBadge = {
  green:  { bg: "bg-emerald-50",  text: "text-emerald-700",  dot: "bg-emerald-500",  label: "HEALTHY"        },
  amber:  { bg: "bg-amber-50",    text: "text-amber-700",    dot: "bg-amber-500",    label: "NEEDS ATTENTION" },
  red:    { bg: "bg-red-50",      text: "text-red-600",      dot: "bg-red-500",      label: "CRITICAL"       },
};

export default function AccountsTab() {
  const [accounts, setAccounts] = useState([]);
  const [loading,  setLoading]  = useState(true);
  const [error,    setError]    = useState(null);

  useEffect(() => {
    axios.get(`${API}/voc/accounts`, { headers: authHeader() })
      .then(r => setAccounts(r.data.accounts || []))
      .catch(e => setError(e?.response?.data?.detail || "Failed to load accounts"))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 size={28} className="animate-spin text-[#CC0000]" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-64 gap-3 text-red-500">
        <AlertCircle size={20} />
        <span>{error}</span>
      </div>
    );
  }

  return (
    <main className="max-w-screen-2xl mx-auto px-6 py-6">
      <div className="mb-6">
        <h2 className="text-2xl font-bold text-[#0F172A] font-['Outfit']">Account Health Overview</h2>
        <p className="text-[#64748B] text-sm mt-1">
          {accounts.length} active accounts · RAG status automatically computed from latest NPS/CSAT
        </p>
      </div>

      <div className="grid grid-cols-3 gap-4">
        {accounts.map(a => {
          const rag = ragBadge[a.rag_status || "green"];
          const col = npsColor(a.latest_nps || 0);
          const NpsIcon = (a.latest_nps || 0) >= 50 ? TrendingUp : (a.latest_nps || 0) >= 30 ? Minus : TrendingDown;

          return (
            <div key={a.id}
              className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm hover:shadow-md transition-shadow overflow-hidden">
              {/* Card header */}
              <div className="flex items-center justify-between px-5 pt-5 pb-3">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0 text-sm font-bold text-white bg-[#CC0000]">
                    {a.initials}
                  </div>
                  <div>
                    <div className="text-sm font-bold text-[#0F172A]">{a.company_name}</div>
                    <div className="text-[10px] text-[#64748B]">{a.industry}</div>
                  </div>
                </div>
                <span className={`inline-flex items-center gap-1.5 text-[10px] font-bold px-2.5 py-1 rounded-full ${rag.bg} ${rag.text}`}>
                  <span className={`w-1.5 h-1.5 rounded-full ${rag.dot}`} />
                  {rag.label}
                </span>
              </div>

              {/* Metrics */}
              <div className="px-5 pb-5 grid grid-cols-3 gap-3 border-t border-[#F1F5F9] pt-4">
                <div>
                  <div className="text-[10px] font-bold tracking-wider text-[#64748B] mb-1">NPS</div>
                  <div className="flex items-center gap-1">
                    <NpsIcon size={13} style={{ color: col }} />
                    <span className="text-lg font-bold" style={{ color: col }}>
                      {(a.latest_nps || 0) > 0 ? `+${a.latest_nps}` : (a.latest_nps || 0)}
                    </span>
                  </div>
                </div>
                <div>
                  <div className="text-[10px] font-bold tracking-wider text-[#64748B] mb-1">CSAT</div>
                  <div className="text-lg font-bold text-emerald-600">
                    {a.latest_csat ? `${a.latest_csat.toFixed(1)}%` : "—"}
                  </div>
                </div>
                <div>
                  <div className="text-[10px] font-bold tracking-wider text-[#64748B] mb-1">Responses</div>
                  <div className="text-lg font-bold text-[#0F172A]">{a.total_responses}</div>
                </div>
              </div>

              {/* Practice badge */}
              {a.practice && (
                <div className="px-5 pb-4">
                  <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-1 rounded bg-slate-100 text-[#64748B]">
                    {a.practice}
                  </span>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </main>
  );
}
