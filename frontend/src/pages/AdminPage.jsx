import { useState, useEffect } from "react";
import { useNavigate, Link } from "react-router-dom";
import axios from "axios";
import { useAuth } from "../contexts/AuthContext";
import {
  Building2, Users, Shield, Trash2, ArrowLeft, LogOut,
  ChevronDown, Search, UserCheck, UserX, Crown
} from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const ROLE_COLORS = { super_admin: "bg-purple-100 text-purple-700", admin: "bg-red-100 text-red-700", manager: "bg-blue-100 text-blue-700", employee: "bg-emerald-100 text-emerald-700" };

export default function AdminPage() {
  const { user, logout, authHeader } = useAuth();
  const navigate = useNavigate();
  const [users, setUsers]         = useState([]);
  const [loading, setLoading]     = useState(true);
  const [statsLoaded, setStatsLoaded] = useState(false);
  const [search, setSearch]     = useState("");
  const [roleFilter, setRoleFilter] = useState("all");
  const [deleteId, setDeleteId] = useState(null);

  const fetchUsers = () => {
    axios.get(`${API}/admin/users`, { headers: authHeader() })
      .then(r => setUsers(r.data))
      .catch(console.error)
      .finally(() => { setLoading(false); setStatsLoaded(true); });
  };

  useEffect(() => { fetchUsers(); }, []);

  const handleDelete = async (id) => {
    try {
      await axios.delete(`${API}/admin/users/${id}`, { headers: authHeader() });
      setDeleteId(null);
      fetchUsers();
    } catch (e) {
      alert(e.response?.data?.detail || "Delete failed");
    }
  };

  const handleRoleChange = async (id, newRole) => {
    try {
      await axios.put(`${API}/admin/users/${id}/role`, { role: newRole }, { headers: authHeader() });
      fetchUsers();
    } catch (e) {
      alert(e.response?.data?.detail || "Role update failed");
    }
  };

  const filtered = users.filter(u =>
    (roleFilter === "all" || u.role === roleFilter) &&
    (u.name.toLowerCase().includes(search.toLowerCase()) || u.email.toLowerCase().includes(search.toLowerCase()))
  );

  const stats = { total: users.length, admin: users.filter(u=>u.role==="admin").length, manager: users.filter(u=>u.role==="manager").length, employee: users.filter(u=>u.role==="employee").length };

  return (
    <div className="min-h-screen bg-[#F1F5F9]">
      {/* Header */}
      <div className="bg-[#CC0000]">
        <div className="max-w-7xl mx-auto px-5 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 bg-white/20 rounded-lg flex items-center justify-center">
              <Building2 size={16} className="text-white" />
            </div>
            <div>
              <div className="text-white font-semibold text-xs tracking-wider">HITACHI SYSTEMS INDIA</div>
              <div className="text-white/50 text-[9px] tracking-widest">ADMIN PANEL</div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Link to="/admin/content" data-testid="admin-content-link"
              className="flex items-center gap-1.5 text-white/80 hover:text-white text-xs bg-white/10 hover:bg-white/20 px-3 py-1.5 rounded-lg transition-colors focus:outline-none focus:ring-2 focus:ring-white/70">
              <ChevronDown size={13} className="rotate-[-90deg]" aria-hidden="true" /><span>Content</span>
            </Link>
            <Link to="/admin/analytics" data-testid="admin-analytics-link"
              className="flex items-center gap-1.5 text-white/80 hover:text-white text-xs bg-white/10 hover:bg-white/20 px-3 py-1.5 rounded-lg transition-colors focus:outline-none focus:ring-2 focus:ring-white/70">
              <span aria-hidden="true">📊</span><span>Analytics</span>
            </Link>
            <Link to="/admin/payout" data-testid="admin-payout-link"
              className="flex items-center gap-1.5 text-white/80 hover:text-white text-xs bg-white/10 hover:bg-white/20 px-3 py-1.5 rounded-lg transition-colors focus:outline-none focus:ring-2 focus:ring-white/70">
              <span aria-hidden="true">💰</span><span>Payout</span>
            </Link>
            <Link to="/admin/notifications"
              className="flex items-center gap-1.5 text-white/80 hover:text-white text-xs bg-white/10 hover:bg-white/20 px-3 py-1.5 rounded-lg transition-colors focus:outline-none focus:ring-2 focus:ring-white/70">
              <span aria-hidden="true">🔔</span><span>Notifications</span>
            </Link>
            <Link to="/" data-testid="back-to-dashboard-btn"
              className="flex items-center gap-1.5 text-white/80 hover:text-white text-xs bg-white/10 hover:bg-white/20 px-3 py-1.5 rounded-lg transition-colors">
              <ArrowLeft size={13} /><span>Dashboard</span>
            </Link>
            <button data-testid="admin-logout-btn" onClick={() => { logout(); navigate("/login"); }}
              className="flex items-center gap-1.5 text-white/80 hover:text-white text-xs bg-white/10 hover:bg-white/20 px-3 py-1.5 rounded-lg transition-colors">
              <LogOut size={13} /><span>Sign Out</span>
            </button>
          </div>
        </div>
      </div>

      <main className="max-w-7xl mx-auto px-5 py-6">
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-[#0F172A] font-['Outfit'] flex items-center gap-2">
            <Crown size={22} className="text-[#CC0000]" />Admin Panel
          </h1>
          <p className="text-[#475569] text-sm mt-1">Manage users, roles and system access</p>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-4 gap-4 mb-6">
          {[["Total Users", stats.total, Users, "#3B82F6"], ["Admins", stats.admin, Shield, "#CC0000"], ["Managers", stats.manager, UserCheck, "#8B5CF6"], ["Employees", stats.employee, UserX, "#10B981"]].map(([label, val, Icon, color]) => (
            <div key={label} className="bg-white rounded-lg border border-[#E2E8F0] p-4 flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg flex items-center justify-center" style={{ backgroundColor: color + "20" }}>
                <Icon size={20} style={{ color }} />
              </div>
              <div>
                <div className="text-2xl font-bold text-[#0F172A] font-['Outfit']">{val}</div>
                <div className="text-xs text-[#64748B]">{label}</div>
              </div>
            </div>
          ))}
        </div>

        {/* User Table */}
        <div className="bg-white rounded-lg border border-[#E2E8F0] overflow-hidden">
          <div className="p-4 border-b border-[#E2E8F0] flex items-center gap-3 flex-wrap">
            <div className="relative flex-1 min-w-48">
              <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-[#94A3B8]" />
              <input data-testid="admin-search-input" placeholder="Search users..."
                value={search} onChange={e => setSearch(e.target.value)}
                className="w-full pl-9 pr-4 py-2 border border-[#E2E8F0] rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[#CC0000]/20 focus:border-[#CC0000]" />
            </div>
            <div className="flex gap-1">
              {["all","admin","manager","employee"].map(r => (
                <button key={r} data-testid={`filter-${r}`}
                  onClick={() => setRoleFilter(r)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors capitalize ${roleFilter===r ? "bg-[#CC0000] text-white" : "bg-[#F1F5F9] text-[#475569] hover:bg-[#E2E8F0]"}`}>
                  {r}
                </button>
              ))}
            </div>
          </div>

          {loading ? (
            <div className="flex items-center justify-center py-16">
              <div className="w-8 h-8 border-3 border-[#CC0000] border-t-transparent rounded-full animate-spin" />
            </div>
          ) : (
            <table className="w-full">
              <thead>
                <tr className="border-b border-[#E2E8F0] bg-[#F8FAFC]">
                  {["Name", "Email", "Role", "Department", "XP Points", "Actions"].map(h => (
                    <th key={h} className="text-left text-[11px] font-bold text-[#64748B] uppercase tracking-wider px-4 py-3">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {filtered.map(u => (
                  <tr key={u.id} data-testid={`user-row-${u.id}`}
                    className="border-b border-[#F1F5F9] hover:bg-[#FAFAFA] transition-colors">
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2.5">
                        <div className="w-8 h-8 rounded-full bg-[#CC0000]/10 flex items-center justify-center">
                          <span className="text-[#CC0000] text-[11px] font-bold">
                            {u.name.split(' ').map(p=>p[0]).slice(0,2).join('')}
                          </span>
                        </div>
                        <div>
                          <div className="text-sm font-medium text-[#0F172A]">{u.name}</div>
                          {u.id === user?.id && <div className="text-[10px] text-[#CC0000]">You</div>}
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-sm text-[#475569]">{u.email}</td>
                    <td className="px-4 py-3">
                      <select data-testid={`role-select-${u.id}`}
                        value={u.role} onChange={e => handleRoleChange(u.id, e.target.value)}
                        disabled={u.id === user?.id}
                        className={`text-xs font-semibold px-2.5 py-1 rounded-full border-0 cursor-pointer focus:outline-none focus:ring-2 focus:ring-[#CC0000]/20 ${ROLE_COLORS[u.role]} disabled:opacity-60 disabled:cursor-not-allowed`}>
                        <option value="employee">Employee</option>
                        <option value="manager">Manager</option>
                        <option value="admin">Admin</option>
                        {user?.role === "super_admin" && <option value="super_admin">Super Admin</option>}
                      </select>
                    </td>
                    <td className="px-4 py-3 text-sm text-[#475569]">{u.department || "—"}</td>
                    <td className="px-4 py-3 text-sm font-semibold text-[#0F172A]">{u.xp_points.toLocaleString()}</td>
                    <td className="px-4 py-3">
                      {u.id !== user?.id ? (
                        <button data-testid={`delete-user-${u.id}`}
                          onClick={() => setDeleteId(u.id)}
                          className="p-1.5 text-[#94A3B8] hover:text-red-500 hover:bg-red-50 rounded transition-colors">
                          <Trash2 size={15} />
                        </button>
                      ) : <span className="text-[10px] text-[#94A3B8]">—</span>}
                    </td>
                  </tr>
                ))}
                {filtered.length === 0 && (
                  <tr><td colSpan={6} className="text-center py-10 text-[#94A3B8] text-sm">No users found</td></tr>
                )}
              </tbody>
            </table>
          )}
        </div>
      </main>

      {/* Delete confirm modal */}
      {deleteId && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50" data-testid="delete-confirm-modal">
          <div className="bg-white rounded-xl p-6 max-w-sm w-full mx-4 shadow-xl">
            <h3 className="font-bold text-[#0F172A] text-lg mb-2">Delete User?</h3>
            <p className="text-[#475569] text-sm mb-5">This action cannot be undone.</p>
            <div className="flex gap-3">
              <button data-testid="confirm-delete-btn" onClick={() => handleDelete(deleteId)}
                className="flex-1 bg-red-600 hover:bg-red-700 text-white py-2.5 rounded-lg font-semibold text-sm transition-colors">
                Delete
              </button>
              <button data-testid="cancel-delete-btn" onClick={() => setDeleteId(null)}
                className="flex-1 border border-[#E2E8F0] text-[#475569] py-2.5 rounded-lg font-semibold text-sm hover:bg-[#F8FAFC] transition-colors">
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
