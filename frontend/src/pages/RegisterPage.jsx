import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext";
import { Eye, EyeOff, Building2, UserPlus } from "lucide-react";

const ROLES = [
  { value: "employee", label: "Employee", desc: "Standard access to all apps and features" },
  { value: "manager",  label: "Manager",  desc: "Team management and approval capabilities" },
  { value: "admin",    label: "Admin",    desc: "Full system access and user management" },
];

export default function RegisterPage() {
  const [form, setForm]       = useState({ name: "", email: "", password: "", role: "employee", department: "" });
  const [showPw, setShowPw]   = useState(false);
  const [error, setError]     = useState("");
  const [loading, setLoading] = useState(false);
  const { register } = useAuth();
  const navigate = useNavigate();

  const set = (k) => (e) => setForm(f => ({ ...f, [k]: e.target.value }));

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(""); setLoading(true);
    try {
      await register(form);
      navigate("/");
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-6 bg-[#F1F5F9]">
      <div className="w-full max-w-lg">
        <div className="flex items-center gap-3 mb-6 justify-center">
          <div className="w-9 h-9 bg-[#CC0000] rounded-lg flex items-center justify-center">
            <Building2 size={18} className="text-white" />
          </div>
          <div className="text-center">
            <div className="text-[#CC0000] font-bold text-sm tracking-wider">HITACHI SYSTEMS INDIA</div>
            <div className="text-[#94A3B8] text-xs">HSI ENTERPRISE PLATFORM</div>
          </div>
        </div>

        <div className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm p-8">
          <div className="mb-6">
            <h2 className="text-2xl font-bold text-[#0F172A]">Create Account</h2>
            <p className="text-[#475569] text-sm mt-1">Join the HSI Enterprise Platform</p>
          </div>

          {error && (
            <div data-testid="register-error" className="bg-red-50 border border-red-200 text-red-700 rounded-lg px-4 py-3 text-sm mb-5">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="col-span-2">
                <label className="block text-sm font-medium text-[#0F172A] mb-1.5">Full Name</label>
                <input data-testid="register-name-input" type="text" value={form.name} onChange={set("name")}
                  placeholder="Arjun Mehta" required
                  className="w-full px-4 py-2.5 border border-[#E2E8F0] rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[#CC0000]/30 focus:border-[#CC0000] bg-white" />
              </div>
              <div className="col-span-2">
                <label className="block text-sm font-medium text-[#0F172A] mb-1.5">Email Address</label>
                <input data-testid="register-email-input" type="email" value={form.email} onChange={set("email")}
                  placeholder="you@hsi.com" required
                  className="w-full px-4 py-2.5 border border-[#E2E8F0] rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[#CC0000]/30 focus:border-[#CC0000] bg-white" />
              </div>
              <div className="col-span-2">
                <label className="block text-sm font-medium text-[#0F172A] mb-1.5">Password</label>
                <div className="relative">
                  <input data-testid="register-password-input" type={showPw ? "text" : "password"} value={form.password} onChange={set("password")}
                    placeholder="Min 6 characters" required minLength={6}
                    className="w-full px-4 py-2.5 pr-10 border border-[#E2E8F0] rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[#CC0000]/30 focus:border-[#CC0000] bg-white" />
                  <button type="button" onClick={() => setShowPw(!showPw)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-[#94A3B8] hover:text-[#475569]">
                    {showPw ? <EyeOff size={16} /> : <Eye size={16} />}
                  </button>
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-[#0F172A] mb-1.5">Department</label>
                <input data-testid="register-department-input" type="text" value={form.department} onChange={set("department")}
                  placeholder="Engineering"
                  className="w-full px-4 py-2.5 border border-[#E2E8F0] rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[#CC0000]/30 focus:border-[#CC0000] bg-white" />
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-[#0F172A] mb-2">Role</label>
              <div className="grid grid-cols-3 gap-2">
                {ROLES.map(r => (
                  <button key={r.value} type="button" data-testid={`role-${r.value}`}
                    onClick={() => setForm(f => ({ ...f, role: r.value }))}
                    className={`p-3 rounded-lg border-2 text-left transition-all ${form.role === r.value ? "border-[#CC0000] bg-red-50" : "border-[#E2E8F0] hover:border-[#CC0000]/40"}`}>
                    <div className={`text-sm font-semibold ${form.role === r.value ? "text-[#CC0000]" : "text-[#0F172A]"}`}>{r.label}</div>
                    <div className="text-[10px] text-[#64748B] mt-0.5 leading-tight">{r.desc}</div>
                  </button>
                ))}
              </div>
            </div>

            <button data-testid="register-submit-button" type="submit" disabled={loading}
              className="w-full bg-[#CC0000] hover:bg-[#A30000] disabled:bg-[#CC0000]/60 text-white font-semibold py-2.5 rounded-lg text-sm flex items-center justify-center gap-2 transition-colors">
              {loading ? <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" /> : <><UserPlus size={16} /><span>Create Account</span></>}
            </button>
          </form>

          <p className="text-center text-sm text-[#475569] mt-5 pt-5 border-t border-[#E2E8F0]">
            Already have an account?{" "}
            <Link to="/login" data-testid="login-link" className="text-[#CC0000] font-medium hover:underline">Sign in</Link>
          </p>
        </div>
      </div>
    </div>
  );
}
