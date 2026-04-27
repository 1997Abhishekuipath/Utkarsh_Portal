import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext";
import { Eye, EyeOff, Building2, LogIn } from "lucide-react";

export default function LoginPage() {
  const [email, setEmail]       = useState("");
  const [password, setPassword] = useState("");
  const [showPw, setShowPw]     = useState(false);
  const [error, setError]       = useState("");
  const [loading, setLoading]   = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(""); setLoading(true);
    try {
      await login(email, password);
      navigate("/");
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex">
      {/* Left panel */}
      <div className="hidden lg:flex lg:w-1/2 bg-[#CC0000] flex-col justify-between p-12 relative overflow-hidden">
        <div className="absolute inset-0 opacity-10"
          style={{ backgroundImage: "radial-gradient(circle at 80% 20%, #FF6B6B 0%, transparent 50%), radial-gradient(circle at 20% 80%, #FF0000 0%, transparent 50%)" }} />
        <div className="relative z-10">
          <div className="flex items-center gap-3 mb-12">
            <div className="w-10 h-10 bg-white/20 rounded-lg flex items-center justify-center">
              <Building2 size={22} className="text-white" />
            </div>
            <div>
              <div className="text-white font-bold text-base tracking-wider">HITACHI SYSTEMS INDIA</div>
              <div className="text-white/60 text-xs tracking-widest">HSI ENTERPRISE PLATFORM</div>
            </div>
          </div>
          <h1 className="text-5xl font-bold text-white leading-tight mb-4">
            Your Enterprise<br />Workspace
          </h1>
          <p className="text-white/75 text-base leading-relaxed max-w-sm">
            Best practices, tech days, CRM, team productivity, visitor management and more – all in one place.
          </p>
        </div>
        <div className="relative z-10 grid grid-cols-2 gap-4">
          {[["80+", "Best Practices"], ["2,840+", "XP Points"], ["9", "Apps"], ["4 Roles", "SuperAdmin/Admin/Manager/Employee"]].map(([v, l]) => (
            <div key={l} className="bg-white/15 rounded-lg p-4 backdrop-blur-sm">
              <div className="text-white font-bold text-2xl">{v}</div>
              <div className="text-white/70 text-xs mt-0.5">{l}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Right panel */}
      <div className="flex-1 flex items-center justify-center p-8 bg-[#F1F5F9]">
        <div className="w-full max-w-md">
          {/* Mobile logo */}
          <div className="flex items-center gap-2 mb-8 lg:hidden">
            <div className="w-8 h-8 bg-[#CC0000] rounded flex items-center justify-center">
              <Building2 size={16} className="text-white" />
            </div>
            <span className="text-[#CC0000] font-bold text-sm tracking-wider">HITACHI SYSTEMS INDIA</span>
          </div>

          <div className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm p-8">
            <div className="mb-8">
              <h2 className="text-2xl font-bold text-[#0F172A]">Welcome back</h2>
              <p className="text-[#475569] text-sm mt-1">Sign in to your HSI account</p>
            </div>

            {error && (
              <div data-testid="login-error" className="bg-red-50 border border-red-200 text-red-700 rounded-lg px-4 py-3 text-sm mb-6">
                {error}
              </div>
            )}

            <form onSubmit={handleSubmit} className="space-y-5">
              <div>
                <label className="block text-sm font-medium text-[#0F172A] mb-1.5">Email address</label>
                <input
                  data-testid="login-email-input"
                  type="email" value={email} onChange={e => setEmail(e.target.value)}
                  placeholder="you@hitachi-systems.com" required
                  className="w-full px-4 py-2.5 border border-[#E2E8F0] rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[#CC0000]/30 focus:border-[#CC0000] bg-white transition-all"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-[#0F172A] mb-1.5">Password</label>
                <div className="relative">
                  <input
                    data-testid="login-password-input"
                    type={showPw ? "text" : "password"} value={password} onChange={e => setPassword(e.target.value)}
                    placeholder="••••••••" required
                    className="w-full px-4 py-2.5 pr-10 border border-[#E2E8F0] rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[#CC0000]/30 focus:border-[#CC0000] bg-white transition-all"
                  />
                  <button type="button" onClick={() => setShowPw(!showPw)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-[#94A3B8] hover:text-[#475569]">
                    {showPw ? <EyeOff size={16} /> : <Eye size={16} />}
                  </button>
                </div>
              </div>

              <button
                data-testid="login-submit-button"
                type="submit" disabled={loading}
                className="w-full bg-[#CC0000] hover:bg-[#A30000] disabled:bg-[#CC0000]/60 text-white font-semibold py-2.5 rounded-lg text-sm flex items-center justify-center gap-2 transition-colors">
                {loading ? (
                  <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                ) : (
                  <><LogIn size={16} /><span>Sign In</span></>
                )}
              </button>
            </form>

            <div className="mt-6 pt-6 border-t border-[#E2E8F0]">
              <p className="text-center text-sm text-[#475569]">
                Don't have an account?{" "}
                <Link to="/register" data-testid="register-link" className="text-[#CC0000] font-medium hover:underline">
                  Create account
                </Link>
              </p>
            </div>

            <div className="mt-4 bg-[#F8FAFC] rounded-lg p-3 border border-[#E2E8F0]">
              <p className="text-xs text-[#64748B] font-medium mb-1.5">Demo credentials:</p>
              <div className="space-y-1">
                {[["admin@hitachi-systems.com", "Admin@123", "Admin"], ["employee@hitachi-systems.com", "Employee@123", "Employee"], ["manager@hitachi-systems.com", "Manager@123", "Manager"]].map(([e, p, r]) => (
                  <button key={r} onClick={() => { setEmail(e); setPassword(p); }}
                    className="w-full text-left text-xs text-[#475569] hover:text-[#CC0000] py-0.5 transition-colors">
                    <span className="font-medium">{r}:</span> {e} / {p}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
