import { useState, useEffect, useCallback } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext";
import {
  ArrowLeft, CheckCircle, XCircle, RefreshCw, Search,
  ChevronDown, FileText, RepeatIcon, CalendarDays, Award,
  Clock, User, Building2, BadgeCheck, AlertCircle
} from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const STATUS_COLORS = {
  pending: "bg-yellow-100 text-yellow-800",
  approved: "bg-emerald-100 text-emerald-700",
  rejected: "bg-red-100 text-red-700",
};

const DIFF_COLORS = {
  easy: "bg-green-100 text-green-700",
  medium: "bg-blue-100 text-blue-700",
  hard: "bg-orange-100 text-orange-700",
  expert: "bg-red-100 text-red-700",
};

function Badge({ text, colorClass }) {
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold ${colorClass}`}>
      {text}
    </span>
  );
}

function ActionButtons({ onApprove, onReject, loading, status }) {
  if (status !== "pending") return null;
  return (
    <div className="flex items-center gap-2">
      <button
        onClick={onApprove}
        disabled={loading}
        className="flex items-center gap-1 px-3 py-1.5 text-xs font-medium text-white bg-emerald-600 hover:bg-emerald-700 rounded-lg transition disabled:opacity-50"
        aria-label="Approve"
      >
        <CheckCircle size={14} />
        Approve
      </button>
      <button
        onClick={onReject}
        disabled={loading}
        className="flex items-center gap-1 px-3 py-1.5 text-xs font-medium text-white bg-red-600 hover:bg-red-700 rounded-lg transition disabled:opacity-50"
        aria-label="Reject"
      >
        <XCircle size={14} />
        Reject
      </button>
    </div>
  );
}

// ── Practices Tab ─────────────────────────────────────────────────────────────
function PracticesTab({ authHeader }) {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [actionId, setActionId] = useState(null);
  const [statusFilter, setStatusFilter] = useState("pending");
  const [search, setSearch] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API}/admin/practices?status=${statusFilter}&limit=50`, {
        headers: authHeader(),
      });
      const data = await res.json();
      setItems(data.items || []);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, [statusFilter]);

  useEffect(() => { load(); }, [load]);

  const act = async (id, action) => {
    setActionId(id);
    try {
      const url = `${API}/admin/practices/${id}/${action}`;
      await fetch(url, { method: "POST", headers: authHeader() });
      load();
    } catch (e) {
      alert(e.message);
    } finally {
      setActionId(null);
    }
  };

  const filtered = items.filter(i =>
    !search || i.title.toLowerCase().includes(search.toLowerCase()) ||
    i.author_name.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div>
      <div className="flex flex-wrap items-center gap-3 mb-4">
        <div className="relative flex-1 min-w-48">
          <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-400" />
          <input
            value={search} onChange={e => setSearch(e.target.value)}
            placeholder="Search practices…"
            className="w-full pl-8 pr-3 py-2 text-sm border rounded-lg focus:ring-2 focus:ring-red-500 focus:border-transparent"
          />
        </div>
        <select
          value={statusFilter}
          onChange={e => setStatusFilter(e.target.value)}
          className="text-sm border rounded-lg px-3 py-2 focus:ring-2 focus:ring-red-500"
        >
          <option value="pending">Pending</option>
          <option value="approved">Approved</option>
          <option value="rejected">Rejected</option>
          <option value="all">All</option>
        </select>
        <button onClick={load} className="p-2 text-gray-500 hover:text-gray-700 rounded-lg border hover:bg-gray-50">
          <RefreshCw size={14} className={loading ? "animate-spin" : ""} />
        </button>
      </div>

      {loading ? (
        <div className="flex justify-center py-12">
          <RefreshCw size={24} className="animate-spin text-red-600" />
        </div>
      ) : filtered.length === 0 ? (
        <div className="text-center py-12 text-gray-500">
          <FileText size={40} className="mx-auto mb-2 opacity-30" />
          <p>No practices found.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {filtered.map(item => (
            <div key={item.id} className="bg-white border rounded-xl p-4 hover:shadow-sm transition">
              <div className="flex items-start justify-between gap-3">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1 flex-wrap">
                    <h3 className="font-semibold text-gray-900 truncate">{item.title}</h3>
                    <Badge text={item.status} colorClass={STATUS_COLORS[item.status]} />
                    {item.difficulty && (
                      <Badge text={item.difficulty} colorClass={DIFF_COLORS[item.difficulty] || "bg-gray-100 text-gray-700"} />
                    )}
                  </div>
                  <p className="text-sm text-gray-500 line-clamp-2 mb-2">{item.summary}</p>
                  <div className="flex items-center gap-4 text-xs text-gray-500 flex-wrap">
                    <span className="flex items-center gap-1">
                      <User size={11} />
                      {item.author_name}
                    </span>
                    {item.pillar && (
                      <span className="flex items-center gap-1">
                        <Building2 size={11} />
                        {item.pillar}
                      </span>
                    )}
                    <span className="flex items-center gap-1">
                      <Clock size={11} />
                      {item.created_at ? new Date(item.created_at).toLocaleDateString("en-IN") : "—"}
                    </span>
                  </div>
                </div>
                <ActionButtons
                  status={item.status}
                  loading={actionId === item.id}
                  onApprove={() => act(item.id, "approve")}
                  onReject={() => act(item.id, "reject")}
                />
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Replications Tab ──────────────────────────────────────────────────────────
function ReplicationsTab({ authHeader }) {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [actionId, setActionId] = useState(null);
  const [statusFilter, setStatusFilter] = useState("pending");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API}/admin/replications?status=${statusFilter}&limit=50`, {
        headers: authHeader(),
      });
      const data = await res.json();
      setItems(data.items || []);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, [statusFilter]);

  useEffect(() => { load(); }, [load]);

  const act = async (id, action) => {
    setActionId(id);
    try {
      await fetch(`${API}/admin/replications/${id}/${action}`, {
        method: "POST", headers: authHeader(),
      });
      load();
    } catch (e) {
      alert(e.message);
    } finally {
      setActionId(null);
    }
  };

  return (
    <div>
      <div className="flex items-center gap-3 mb-4">
        <select
          value={statusFilter}
          onChange={e => setStatusFilter(e.target.value)}
          className="text-sm border rounded-lg px-3 py-2 focus:ring-2 focus:ring-red-500"
        >
          <option value="pending">Pending</option>
          <option value="approved">Approved</option>
          <option value="rejected">Rejected</option>
          <option value="all">All</option>
        </select>
        <button onClick={load} className="p-2 text-gray-500 hover:text-gray-700 rounded-lg border hover:bg-gray-50">
          <RefreshCw size={14} className={loading ? "animate-spin" : ""} />
        </button>
      </div>

      {loading ? (
        <div className="flex justify-center py-12">
          <RefreshCw size={24} className="animate-spin text-red-600" />
        </div>
      ) : items.length === 0 ? (
        <div className="text-center py-12 text-gray-500">
          <RepeatIcon size={40} className="mx-auto mb-2 opacity-30" />
          <p>No replications found.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {items.map(item => (
            <div key={item.id} className="bg-white border rounded-xl p-4 hover:shadow-sm transition">
              <div className="flex items-start justify-between gap-3">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1 flex-wrap">
                    <h3 className="font-semibold text-gray-900">{item.practice_title}</h3>
                    <Badge text={item.status} colorClass={STATUS_COLORS[item.status]} />
                  </div>
                  <p className="text-sm text-gray-600 mb-2">
                    Client: <span className="font-medium">{item.client_name}</span>
                    {item.po_number && <> · PO: {item.po_number}</>}
                    {item.po_value_inr && <> · ₹{Number(item.po_value_inr).toLocaleString("en-IN")}</>}
                  </p>
                  <div className="flex items-center gap-4 text-xs text-gray-500 flex-wrap">
                    <span className="flex items-center gap-1">
                      <User size={11} />
                      {item.replicator_name || "Unknown"}
                    </span>
                    <span className="flex items-center gap-1">
                      <Clock size={11} />
                      {item.created_at ? new Date(item.created_at).toLocaleDateString("en-IN") : "—"}
                    </span>
                    {item.xp_awarded && (
                      <span className="text-emerald-600 font-semibold">+{item.xp_awarded} XP</span>
                    )}
                  </div>
                </div>
                <ActionButtons
                  status={item.status}
                  loading={actionId === item.id}
                  onApprove={() => act(item.id, "approve")}
                  onReject={() => act(item.id, "reject")}
                />
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Tech Days Tab ─────────────────────────────────────────────────────────────
function TechDaysTab({ authHeader }) {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [actionId, setActionId] = useState(null);
  const [statusFilter, setStatusFilter] = useState("pending");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API}/admin/tech-days?status=${statusFilter}`, {
        headers: authHeader(),
      });
      const data = await res.json();
      setItems(Array.isArray(data) ? data : []);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, [statusFilter]);

  useEffect(() => { load(); }, [load]);

  const act = async (id, action) => {
    setActionId(id);
    try {
      await fetch(`${API}/admin/tech-days/${id}/${action}`, {
        method: "POST", headers: authHeader(),
      });
      load();
    } catch (e) {
      alert(e.message);
    } finally {
      setActionId(null);
    }
  };

  return (
    <div>
      <div className="flex items-center gap-3 mb-4">
        <select
          value={statusFilter}
          onChange={e => setStatusFilter(e.target.value)}
          className="text-sm border rounded-lg px-3 py-2 focus:ring-2 focus:ring-red-500"
        >
          <option value="pending">Pending</option>
          <option value="approved">Approved</option>
          <option value="rejected">Rejected</option>
          <option value="all">All</option>
        </select>
        <button onClick={load} className="p-2 text-gray-500 hover:text-gray-700 rounded-lg border hover:bg-gray-50">
          <RefreshCw size={14} className={loading ? "animate-spin" : ""} />
        </button>
      </div>

      {loading ? (
        <div className="flex justify-center py-12">
          <RefreshCw size={24} className="animate-spin text-red-600" />
        </div>
      ) : items.length === 0 ? (
        <div className="text-center py-12 text-gray-500">
          <CalendarDays size={40} className="mx-auto mb-2 opacity-30" />
          <p>No tech days found.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {items.map(item => (
            <div key={item.id} className="bg-white border rounded-xl p-4 hover:shadow-sm transition">
              <div className="flex items-start justify-between gap-3">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1 flex-wrap">
                    <h3 className="font-semibold text-gray-900">{item.title}</h3>
                    <Badge text={item.status} colorClass={STATUS_COLORS[item.status]} />
                  </div>
                  <p className="text-sm text-gray-600 mb-2 line-clamp-2">{item.description}</p>
                  <div className="flex items-center gap-4 text-xs text-gray-500 flex-wrap">
                    <span className="flex items-center gap-1">
                      <User size={11} />
                      {item.conductor_name || "Unknown"}
                    </span>
                    <span className="flex items-center gap-1">
                      <Building2 size={11} />
                      {item.client_name}
                    </span>
                    <span>{item.attendee_count} attendees</span>
                    <span className="flex items-center gap-1">
                      <CalendarDays size={11} />
                      {item.conducted_on || "—"}
                    </span>
                    {item.xp_awarded && (
                      <span className="text-emerald-600 font-semibold">+{item.xp_awarded} XP</span>
                    )}
                  </div>
                </div>
                <ActionButtons
                  status={item.status}
                  loading={actionId === item.id}
                  onApprove={() => act(item.id, "approve")}
                  onReject={() => act(item.id, "reject")}
                />
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Certifications Tab ────────────────────────────────────────────────────────
function CertificationsTab({ authHeader }) {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [actionId, setActionId] = useState(null);
  const [verifiedFilter, setVerifiedFilter] = useState("false");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const qs = verifiedFilter !== "all" ? `?verified=${verifiedFilter}` : "";
      const res = await fetch(`${API}/admin/certifications${qs}`, { headers: authHeader() });
      const data = await res.json();
      setItems(Array.isArray(data) ? data : []);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, [verifiedFilter]);

  useEffect(() => { load(); }, [load]);

  const act = async (id, action) => {
    setActionId(id);
    try {
      await fetch(`${API}/admin/certifications/${id}/${action}`, {
        method: "POST", headers: authHeader(),
      });
      load();
    } catch (e) {
      alert(e.message);
    } finally {
      setActionId(null);
    }
  };

  return (
    <div>
      <div className="flex items-center gap-3 mb-4">
        <select
          value={verifiedFilter}
          onChange={e => setVerifiedFilter(e.target.value)}
          className="text-sm border rounded-lg px-3 py-2 focus:ring-2 focus:ring-red-500"
        >
          <option value="false">Unverified</option>
          <option value="true">Verified</option>
          <option value="all">All</option>
        </select>
        <button onClick={load} className="p-2 text-gray-500 hover:text-gray-700 rounded-lg border hover:bg-gray-50">
          <RefreshCw size={14} className={loading ? "animate-spin" : ""} />
        </button>
      </div>

      {loading ? (
        <div className="flex justify-center py-12">
          <RefreshCw size={24} className="animate-spin text-red-600" />
        </div>
      ) : items.length === 0 ? (
        <div className="text-center py-12 text-gray-500">
          <Award size={40} className="mx-auto mb-2 opacity-30" />
          <p>No certifications found.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {items.map(item => (
            <div key={item.id} className="bg-white border rounded-xl p-4 hover:shadow-sm transition">
              <div className="flex items-start justify-between gap-3">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1 flex-wrap">
                    <h3 className="font-semibold text-gray-900">{item.cert_name}</h3>
                    {item.verified ? (
                      <Badge text="Verified" colorClass="bg-emerald-100 text-emerald-700" />
                    ) : (
                      <Badge text="Unverified" colorClass="bg-yellow-100 text-yellow-800" />
                    )}
                  </div>
                  <p className="text-sm text-gray-600 mb-2">
                    Provider: <span className="font-medium">{item.provider}</span>
                    {item.cert_id && <> · ID: {item.cert_id}</>}
                  </p>
                  <div className="flex items-center gap-4 text-xs text-gray-500 flex-wrap">
                    <span className="flex items-center gap-1">
                      <User size={11} />
                      {item.user_name || "Unknown"}
                    </span>
                    {item.issued_on && (
                      <span className="flex items-center gap-1">
                        <CalendarDays size={11} />
                        Issued: {item.issued_on}
                      </span>
                    )}
                    <span className="text-emerald-600 font-semibold">+{item.xp_awarded} XP</span>
                    {item.evidence_url && (
                      <a href={item.evidence_url} target="_blank" rel="noopener noreferrer"
                        className="text-blue-600 hover:underline flex items-center gap-1">
                        <FileText size={11} />
                        Evidence
                      </a>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {!item.verified ? (
                    <button
                      onClick={() => act(item.id, "verify")}
                      disabled={actionId === item.id}
                      className="flex items-center gap-1 px-3 py-1.5 text-xs font-medium text-white bg-emerald-600 hover:bg-emerald-700 rounded-lg transition disabled:opacity-50"
                    >
                      <BadgeCheck size={14} />
                      Verify
                    </button>
                  ) : (
                    <button
                      onClick={() => act(item.id, "unverify")}
                      disabled={actionId === item.id}
                      className="flex items-center gap-1 px-3 py-1.5 text-xs font-medium text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-lg transition disabled:opacity-50"
                    >
                      <XCircle size={14} />
                      Unverify
                    </button>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────
const TABS = [
  { id: "practices", label: "Best Practices", icon: FileText },
  { id: "replications", label: "Replications", icon: RepeatIcon },
  { id: "techdays", label: "Tech Days", icon: CalendarDays },
  { id: "certifications", label: "Certifications", icon: Award },
];

export default function AdminApprovalsPage() {
  const { authHeader } = useAuth();
  const [activeTab, setActiveTab] = useState("practices");
  const [counts, setCounts] = useState({});

  useEffect(() => {
    // Load pending counts for badge indicators
    const h = authHeader();
    Promise.all([
      fetch(`${API}/admin/practices?status=pending&limit=1`, { headers: h }).then(r => r.json()),
      fetch(`${API}/admin/replications?status=pending&limit=1`, { headers: h }).then(r => r.json()),
      fetch(`${API}/admin/tech-days?status=pending`, { headers: h }).then(r => r.json()),
      fetch(`${API}/admin/certifications?verified=false`, { headers: h }).then(r => r.json()),
    ]).then(([p, rep, td, cert]) => {
      setCounts({
        practices: p.total || 0,
        replications: rep.total || 0,
        techdays: Array.isArray(td) ? td.length : 0,
        certifications: Array.isArray(cert) ? cert.length : 0,
      });
    }).catch(() => {});
  }, []);

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-[#CC0000] text-white px-6 py-4">
        <div className="max-w-6xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Link to="/admin" className="p-1.5 rounded-lg hover:bg-white/10 transition" aria-label="Back to Admin">
              <ArrowLeft size={18} />
            </Link>
            <div>
              <h1 className="font-bold text-xl">Approval Queue</h1>
              <p className="text-red-200 text-xs mt-0.5">Review and approve employee submissions</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {Object.values(counts).some(c => c > 0) && (
              <span className="flex items-center gap-1 px-3 py-1 bg-white/20 rounded-full text-xs font-medium">
                <AlertCircle size={13} />
                {Object.values(counts).reduce((a, b) => a + b, 0)} pending
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="max-w-6xl mx-auto px-6 pt-6">
        <div className="flex gap-1 bg-white border rounded-xl p-1 mb-6 overflow-x-auto">
          {TABS.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              onClick={() => setActiveTab(id)}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition whitespace-nowrap ${
                activeTab === id
                  ? "bg-[#CC0000] text-white shadow-sm"
                  : "text-gray-600 hover:bg-gray-50"
              }`}
              aria-current={activeTab === id ? "page" : undefined}
            >
              <Icon size={15} />
              {label}
              {counts[id] > 0 && (
                <span className={`inline-flex items-center justify-center w-5 h-5 rounded-full text-xs font-bold ${
                  activeTab === id ? "bg-white text-red-600" : "bg-red-600 text-white"
                }`}>
                  {counts[id] > 9 ? "9+" : counts[id]}
                </span>
              )}
            </button>
          ))}
        </div>

        {/* Tab content */}
        <div className="pb-8">
          {activeTab === "practices" && <PracticesTab authHeader={authHeader} />}
          {activeTab === "replications" && <ReplicationsTab authHeader={authHeader} />}
          {activeTab === "techdays" && <TechDaysTab authHeader={authHeader} />}
          {activeTab === "certifications" && <CertificationsTab authHeader={authHeader} />}
        </div>
      </div>
    </div>
  );
}
