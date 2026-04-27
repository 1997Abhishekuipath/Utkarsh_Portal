import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Building2, Settings, LogOut, ChevronRight } from "lucide-react";
import { useAuth } from "../contexts/AuthContext";

/**
 * Reusable HSI red top bar — branding, mini-stats, user menu.
 * Used by HomePage and PillarPage.
 *
 * stats: optional [{value, label}]   — shown right of the brand
 * crumbs: optional [{label, to?}]    — breadcrumbs on the second row
 * children: optional hero content    — rendered inside the red hero band
 */
export default function TopBar({ stats = [], crumbs = null, children = null }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const firstName = user?.name?.split(" ")[0] || "User";
  const isAdmin = user && (user.role === "admin" || user.role === "super_admin");

  const doLogout = async () => { await logout(); navigate("/login"); };

  return (
    <div className="bg-[#CC0000] relative overflow-hidden">
      <div className="absolute inset-0 pointer-events-none"
        style={{ backgroundImage: "radial-gradient(circle at 85% 50%, rgba(255,255,255,0.08) 0%, transparent 55%)" }} />

      {/* Brand row */}
      <div className="relative border-b border-white/20">
        <div className="max-w-7xl mx-auto px-5 py-2.5 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2.5">
            <div className="w-8 h-8 bg-white/20 rounded-lg flex items-center justify-center">
              <Building2 size={16} className="text-white" />
            </div>
            <div>
              <div className="text-white font-semibold text-xs tracking-[0.12em]">HITACHI SYSTEMS INDIA</div>
              <div className="text-white/50 text-[9px] tracking-widest">HSI ENTERPRISE PLATFORM</div>
            </div>
          </Link>

          <div className="flex items-center gap-2">
            {stats.map(s => (
              <div key={s.label} className="hidden sm:block text-right px-3">
                <div className="text-white text-sm font-bold leading-none">{s.value}</div>
                <div className="text-white/60 text-[9px] tracking-widest mt-0.5">{s.label}</div>
              </div>
            ))}
            <div className="relative ml-2">
              <button data-testid="user-menu-button" onClick={() => setOpen(!open)}
                className="flex items-center gap-2 bg-white/20 hover:bg-white/30 rounded-lg px-3 py-1.5 transition-colors">
                <div className="w-6 h-6 rounded-full bg-white/30 flex items-center justify-center">
                  <span className="text-white text-[10px] font-bold">{user?.name?.[0]}</span>
                </div>
                <span className="text-white text-xs font-medium hidden sm:block">{firstName}</span>
              </button>
              {open && (
                <div className="absolute right-0 top-full mt-2 bg-white rounded-lg shadow-lg border border-[#E2E8F0] w-48 z-50">
                  <div className="px-4 py-3 border-b border-[#E2E8F0]">
                    <div className="text-sm font-semibold text-[#0F172A]">{user?.name}</div>
                    <div className="text-xs text-[#64748B] capitalize">{user?.role?.replace("_", " ")}</div>
                  </div>
                  {isAdmin && (
                    <Link to="/admin" data-testid="admin-panel-link"
                      className="flex items-center gap-2 px-4 py-2.5 text-sm text-[#0F172A] hover:bg-[#F8FAFC] transition-colors">
                      <Settings size={15} /><span>Admin Panel</span>
                    </Link>
                  )}
                  <button data-testid="logout-button" onClick={doLogout}
                    className="w-full flex items-center gap-2 px-4 py-2.5 text-sm text-red-600 hover:bg-red-50 transition-colors rounded-b-lg">
                    <LogOut size={15} /><span>Sign Out</span>
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Optional breadcrumbs row */}
      {crumbs?.length > 0 && (
        <div className="relative max-w-7xl mx-auto px-5 py-2 flex items-center gap-1 text-white/85 text-xs">
          {crumbs.map((c, i) => (
            <div key={i} className="flex items-center gap-1">
              {i > 0 && <ChevronRight size={12} className="text-white/50" />}
              {c.to ? (
                <Link to={c.to} className="hover:text-white">{c.label}</Link>
              ) : (
                <span className="font-semibold">{c.label}</span>
              )}
            </div>
          ))}
        </div>
      )}

      {children && (
        <div className="relative max-w-7xl mx-auto px-5 py-7">{children}</div>
      )}
    </div>
  );
}
