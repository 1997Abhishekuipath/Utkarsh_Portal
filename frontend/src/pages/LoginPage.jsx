import { useState, useEffect, useRef } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext";
import { Eye, EyeOff, Building2, LogIn, ShieldCheck, ArrowLeft, RefreshCw } from "lucide-react";

export default function LoginPage() {
  const [stage, setStage]       = useState("creds"); // creds | otp
  const [email, setEmail]       = useState("");
  const [password, setPassword] = useState("");
  const [code, setCode]         = useState("");
  const [showPw, setShowPw]     = useState(false);
  const [error, setError]       = useState("");
  const [info, setInfo]         = useState("");
  const [loading, setLoading]   = useState(false);
  const [resendIn, setResendIn] = useState(0); // countdown to next resend
  const { login, verifyOtp, resendOtp } = useAuth();
  const navigate = useNavigate();
  const otpInputRef = useRef(null);

  // Resend countdown ticker (30s window)
  useEffect(() => {
    if (resendIn <= 0) return;
    const id = setInterval(() => setResendIn(s => Math.max(0, s - 1)), 1000);
    return () => clearInterval(id);
  }, [resendIn]);

  // Autofocus OTP field when entering OTP stage
  useEffect(() => {
    if (stage === "otp") otpInputRef.current?.focus();
  }, [stage]);

  const handleCreds = async (e) => {
    e.preventDefault();
    setError(""); setInfo(""); setLoading(true);
    try {
      const data = await login(email, password);
      if (data?.requires_otp) {
        setStage("otp");
        setInfo("Enter the 6-digit code we just sent to your email.");
        setResendIn(30);
      } else {
        navigate("/");
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleOtp = async (e) => {
    e.preventDefault();
    setError(""); setInfo(""); setLoading(true);
    try {
      await verifyOtp(email, code, "login");
      navigate("/");
    } catch (err) {
      setError(err.message);
      setCode("");
    } finally {
      setLoading(false);
    }
  };

  const handleResend = async () => {
    if (resendIn > 0 || loading) return;
    setError(""); setInfo(""); setLoading(true);
    try {
      await resendOtp(email, "login");
      setInfo("New code sent. Check your inbox.");
      setResendIn(30);
      setCode("");
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const backToCreds = () => {
    setStage("creds"); setError(""); setInfo(""); setCode("");
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
          <div className="flex items-center gap-2 mb-8 lg:hidden">
            <div className="w-8 h-8 bg-[#CC0000] rounded flex items-center justify-center">
              <Building2 size={16} className="text-white" />
            </div>
            <span className="text-[#CC0000] font-bold text-sm tracking-wider">HITACHI SYSTEMS INDIA</span>
          </div>

          <div className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm p-8">
            {stage === "creds" && (
              <div className="mb-8">
                <h2 className="text-2xl font-bold text-[#0F172A]">Welcome back</h2>
                <p className="text-[#475569] text-sm mt-1">Sign in to your HSI account</p>
              </div>
            )}

            {stage === "otp" && (
              <div className="mb-6">
                <button onClick={backToCreds} data-testid="otp-back-button"
                  className="text-[#475569] hover:text-[#0F172A] text-xs flex items-center gap-1 mb-4">
                  <ArrowLeft size={14} /> Back
                </button>
                <div className="flex items-center gap-3 mb-2">
                  <div className="w-10 h-10 rounded-lg bg-[#CC0000]/10 text-[#CC0000] flex items-center justify-center">
                    <ShieldCheck size={20} />
                  </div>
                  <h2 className="text-2xl font-bold text-[#0F172A]">Verify it's you</h2>
                </div>
                <p className="text-[#475569] text-sm mt-1">
                  We sent a 6-digit code to <span className="font-medium text-[#0F172A]">{email}</span>
                </p>
              </div>
            )}

            {error && (
              <div data-testid="login-error" className="bg-red-50 border border-red-200 text-red-700 rounded-lg px-4 py-3 text-sm mb-5">
                {error}
              </div>
            )}
            {info && !error && (
              <div data-testid="login-info" className="bg-emerald-50 border border-emerald-200 text-emerald-800 rounded-lg px-4 py-3 text-sm mb-5">
                {info}
              </div>
            )}

            {stage === "creds" ? (
              <form onSubmit={handleCreds} className="space-y-5">
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
                  <div className="flex items-center justify-between mb-1.5">
                    <label className="block text-sm font-medium text-[#0F172A]">Password</label>
                    <Link to="/forgot-password" data-testid="forgot-password-link"
                      className="text-xs text-[#CC0000] hover:underline">Forgot password?</Link>
                  </div>
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
                  {loading ? <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" /> : <><LogIn size={16} /><span>Sign In</span></>}
                </button>
              </form>
            ) : (
              <form onSubmit={handleOtp} className="space-y-5">
                <div>
                  <label className="block text-sm font-medium text-[#0F172A] mb-1.5">6-digit code</label>
                  <input
                    ref={otpInputRef}
                    data-testid="otp-code-input"
                    type="text" inputMode="numeric" pattern="[0-9]*" maxLength={6}
                    value={code}
                    onChange={e => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
                    placeholder="••••••" required
                    className="w-full px-4 py-3 text-center text-2xl font-mono tracking-[0.5em] border border-[#E2E8F0] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#CC0000]/30 focus:border-[#CC0000] bg-white"
                  />
                </div>

                <button
                  data-testid="otp-verify-button"
                  type="submit" disabled={loading || code.length < 6}
                  className="w-full bg-[#CC0000] hover:bg-[#A30000] disabled:bg-[#CC0000]/40 text-white font-semibold py-2.5 rounded-lg text-sm flex items-center justify-center gap-2 transition-colors">
                  {loading ? <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" /> : <><ShieldCheck size={16} /><span>Verify</span></>}
                </button>

                <button
                  type="button" onClick={handleResend}
                  data-testid="otp-resend-button"
                  disabled={resendIn > 0 || loading}
                  className="w-full text-xs text-[#475569] hover:text-[#CC0000] disabled:text-[#94A3B8] flex items-center justify-center gap-1.5 py-1 transition-colors">
                  <RefreshCw size={12} />
                  {resendIn > 0 ? `Resend code in ${resendIn}s` : "Resend code"}
                </button>
              </form>
            )}

            {stage === "creds" && (
              <>
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
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
