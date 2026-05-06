import { useEffect, useState } from "react";
import api from "../lib/api";
import { History, ChevronRight } from "lucide-react";
import { Badge } from "./ui/badge";

export default function RenewalHistory({ licenseId }) {
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!licenseId) return;
    setLoading(true);
    api.get(`/licenses/${licenseId}/history`).then(r => {
      setHistory(r.data);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, [licenseId]);

  const fmt = (v) => {
    if (v == null || v === "") return "—";
    if (typeof v === "boolean") return v ? "Yes" : "No";
    return String(v);
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 text-sm font-medium">
        <History className="h-4 w-4 text-blue-600" />
        Renewal & Change History ({history.length})
      </div>

      {loading && <p className="text-xs text-muted-foreground">Loading...</p>}
      {!loading && history.length === 0 && (
        <p className="text-xs text-muted-foreground italic">No history yet — every edit will be tracked here.</p>
      )}

      <div className="space-y-2 max-h-[400px] overflow-y-auto pr-1">
        {history.map(h => {
          const changeKeys = Object.keys(h.changes || {});
          return (
            <div key={h.id} className="border-l-2 border-blue-500/40 pl-3 py-2 hover:bg-accent/50 rounded-r" data-testid={`history-${h.id}`}>
              <div className="flex items-center justify-between flex-wrap gap-2">
                <span className="text-xs font-medium">{h.changed_by}</span>
                <span className="text-[10px] text-muted-foreground">{new Date(h.timestamp).toLocaleString()}</span>
              </div>
              <Badge variant="outline" className="mt-1 status-info text-[10px]">{changeKeys.length} field{changeKeys.length !== 1 ? "s" : ""} changed</Badge>
              <div className="mt-1.5 space-y-1">
                {changeKeys.map(k => (
                  <div key={k} className="flex items-center gap-1.5 text-[11px]">
                    <span className="font-medium text-muted-foreground min-w-[110px]">{k.replace(/_/g, " ")}:</span>
                    <span className="text-red-500/80 line-through truncate max-w-[120px]">{fmt(h.changes[k].from)}</span>
                    <ChevronRight className="h-3 w-3 text-muted-foreground" />
                    <span className="text-emerald-600 font-medium truncate max-w-[140px]">{fmt(h.changes[k].to)}</span>
                  </div>
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
