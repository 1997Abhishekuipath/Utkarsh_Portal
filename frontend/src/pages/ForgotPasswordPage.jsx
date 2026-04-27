import { useState, useEffect, useRef } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext";
import { Building2, Eye, EyeOff, ShieldCheck, ArrowLeft, RefreshCw } from "lucide-react";

export default function ForgotPasswordPage() {
  const [stage, setStage] = useState("email");      // email | reset | done
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [pw, setPw] = useState("");
  const [showPw, setShowPw] = useState(false);
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");
  const [loading, setLoading] = useState(false);
  const [resendIn, setResendIn] = useState(0);
  const { forgotPassword, resetPassword } = useAuth();
  const navigate = useNavigate();
  const codeRef = useRef(null);

  useEffect(() => {
    if (resendIn <= 0) return;
    const id = setInterval(() => setResendIn(s => Math.max(0, s - 1)), 1000);
    return () => clearInterval(id);
  }, [resendIn]);

  useEffect(() => { if (stage === "reset") codeRef.current?.focus(); }, [stage]);

  const sendCode = async (e) => {
    if (e) e.preventDefault();
    setError(""); setInfo(""); setLoading(true);
    try {
      await forgotPassword(email);
      setStage("reset");
      setInfo("If the account exists, a 6-digit code was sent to your email.");
      setResendIn(30);
    } catch (err) { setError(err.message); }
    finally { setLoading(false); }
  };

  const submitReset = async (e) => {
    e.preventDefault();
    setError(""); setInfo(""); setLoading(true);
    try {
      await resetPassword(email, code, pw);
      setStage("done");
    } catch (err) { setError(err.message); }
    finally { setLoading(false); }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-6 bg-[#F1F5F9]">
      <div className="w-full max-w-md">
        <div className="flex items-center gap-3 mb-6 justify-center">
          <div className="w-9 h-9 bg-[#CC0000] rounded-lg flex items-center justify-center">
            <Building2 size={18} className="text-white" />
          </div>
          <div className="text-center">
            <div className="text-[#CC0000] font-bold text-sm tracking-wider">HITACHI SYSTEMS INDIA</div>
            <div className="text-[#94A3B8] text-xs">HSI EMPLOYEE ENGAGEMENT PLATFORM</div>
          </div>
        </div>

        <div className="bg-white rounded-xl border border-[#E2E8F0] shadow-sm p-8">
          <Link to="/login" className="text-[#475569] hover:text-[#0F172A] text-xs flex items-center gap-1 mb-4">
            <ArrowLeft size={14} /> Back to login
          </Link>

          {stage === "email" && (
            <>
              <h2 className="text-2xl font-bold text-[#0F172A]">Reset password</h2>
              <p className="text-[#475569] text-sm mt-1 mb-6">Enter your account email and we'll send you a 6-digit code.</p>
            </>
          )}
          {stage === "reset" && (
            <div className="mb-6">
              <div className="flex items-center gap-3 mb-2">
                <div className="w-10 h-10 rounded-lg bg-[#CC0000]/10 text-[#CC0000] flex items-center justify-center">
                  <ShieldCheck size={20} />
                </div>
                <h2 className="text-2xl font-bold text-[#0F172A]">Set new password</h2>
              </div>
              <p className="text-[#475569] text-sm">Enter the 6-digit code sent to <span className="font-medium text-[#0F172A]">{email}</span> and choose a new password.</p>
            </div>
          )}
          {stage === "done" && (
            <div className="text-center py-6">
              <div className="w-12 h-12 bg-emerald-100 text-emerald-600 rounded-full flex items-center justify-center mx-auto mb-4">
                <ShieldCheck size={24} />
              </div>
              <h2 className="text-2xl font-bold text-[#0F172A] mb-1">Password reset</h2>
              <p className="text-[#475569] text-sm mb-6">All your sessions have been signed out. Use your new password to log in.</p>
              <button onClick={() => navigate("/login")} data-testid="forgot-back-to-login"
                className="w-full bg-[#CC0000] hover:bg-[#A30000] text-white font-semibold py-2.5 rounded-lg text-sm">
                Go to login
              </button>
            </div>
          )}

          {error && stage !== "done" && (
            <div data-testid="forgot-error" className="bg-red-50 border border-red-200 text-red-700 rounded-lg px-4 py-3 text-sm mb-5">{error}</div>
          )}
          {info && !error && stage !== "done" && (
            <div data-testid="forgot-info" className="bg-emerald-50 border border-emerald-200 text-emerald-800 rounded-lg px-4 py-3 text-sm mb-5">{info}</div>
          )}

          {stage === "email" && (
            <form onSubmit={sendCode} className="space-y-5">
              <div>
                <label className="block text-sm font-medium text-[#0F172A] mb-1.5">Email address</label>
                <input
                  data-testid="forgot-email-input"
                  type="email" required value={email} onChange={e => setEmail(e.target.value)}
                  placeholder="you@hitachi-systems.com"
                  className="w-full px-4 py-2.5 border border-[#E2E8F0] rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[#CC0000]/30 focus:border-[#CC0000] bg-white" />
              </div>
              <button data-testid="forgot-send-button" type="submit" disabled={loading}
                className="w-full bg-[#CC0000] hover:bg-[#A30000] disabled:bg-[#CC0000]/60 text-white font-semibold py-2.5 rounded-lg text-sm">
                {loading ? "Sending…" : "Send reset code"}
              </button>
            </form>
          )}

          {stage === "reset" && (
            <form onSubmit={submitReset} className="space-y-5">
              <div>
                <label className="block text-sm font-medium text-[#0F172A] mb-1.5">6-digit code</label>
                <input
                  ref={codeRef}
                  data-testid="forgot-code-input"
                  type="text" inputMode="numeric" pattern="[0-9]*" maxLength={6}
                  value={code} required
                  onChange={e => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
                  placeholder="••••••"
                  className="w-full px-4 py-3 text-center text-2xl font-mono tracking-[0.5em] border border-[#E2E8F0] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#CC0000]/30 focus:border-[#CC0000] bg-white" />
              </div>
              <div>
                <label className="block text-sm font-medium text-[#0F172A] mb-1.5">New password</label>
                <div className="relative">
                  <input
                    data-testid="forgot-password-input"
                    type={showPw ? "text" : "password"} required minLength={6}
                    value={pw} onChange={e => setPw(e.target.value)}
                    placeholder="Min 6 characters"
                    className="w-full px-4 py-2.5 pr-10 border border-[#E2E8F0] rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[#CC0000]/30 focus:border-[#CC0000] bg-white" />
                  <button type="button" onClick={() => setShowPw(!showPw)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-[#94A3B8] hover:text-[#475569]">
                    {showPw ? <EyeOff size={16} /> : <Eye size={16} />}
                  </button>
                </div>
              </div>
              <button data-testid="forgot-reset-button" type="submit" disabled={loading || code.length < 6 || pw.length < 6}
                className="w-full bg-[#CC0000] hover:bg-[#A30000] disabled:bg-[#CC0000]/40 text-white font-semibold py-2.5 rounded-lg text-sm">
                {loading ? "Resetting…" : "Reset password"}
              </button>

              <button type="button" onClick={() => sendCode()}
                data-testid="forgot-resend-button"
                disabled={resendIn > 0 || loading}
                className="w-full text-xs text-[#475569] hover:text-[#CC0000] disabled:text-[#94A3B8] flex items-center justify-center gap-1.5 py-1">
                <RefreshCw size={12} />
                {resendIn > 0 ? `Resend code in ${resendIn}s` : "Resend code"}
              </button>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}
