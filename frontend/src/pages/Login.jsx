import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { useTheme } from "../context/ThemeContext";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Hexagon, Sun, Moon, Loader2, ShieldCheck, Eye, EyeOff } from "lucide-react";

export default function Login() {
  const { user, login, error } = useAuth();
  const { theme, toggle } = useTheme();
  const navigate = useNavigate();
  const [email, setEmail] = useState("admin@cmportal.com");
  const [password, setPassword] = useState("Admin@123");
  const [showPw, setShowPw] = useState(false);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (user && user !== false) navigate("/dashboard");
  }, [user, navigate]);

  const submit = async (e) => {
    e.preventDefault();
    setLoading(true);
    const ok = await login(email, password);
    setLoading(false);
    if (ok) navigate("/dashboard");
  };

  const fill = (em, pw) => { setEmail(em); setPassword(pw); };

  return (
    <div className={`min-h-screen relative ${theme === "dark" ? "auth-bg-dark" : "auth-bg-light"}`}>
      <div className="absolute inset-0 bg-black/10 dark:bg-black/40" />
      <div className="relative z-10 min-h-screen flex flex-col">
        <header className="p-6 flex justify-between items-center">
          <div className="flex items-center gap-2.5 text-white">
            <div className="h-9 w-9 rounded-lg bg-white/15 backdrop-blur border border-white/20 flex items-center justify-center">
              <Hexagon className="h-5 w-5" />
            </div>
            <div className="flex flex-col leading-none">
              <span className="font-display font-semibold text-base">CMPortal</span>
              <span className="text-[10px] uppercase tracking-[0.18em] opacity-80">Enterprise</span>
            </div>
          </div>
          <Button
            variant="ghost"
            size="icon"
            className="text-white hover:bg-white/10"
            onClick={toggle}
            data-testid="login-theme-toggle"
          >
            {theme === "dark" ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
          </Button>
        </header>

        <div className="flex-1 flex items-center justify-center p-6">
          <div className="w-full max-w-md">
            <form
              onSubmit={submit}
              className="glass-strong rounded-2xl p-8 sm:p-10 shadow-2xl"
              data-testid="login-form"
            >
              <div className="mb-6">
                <h1 className="text-3xl font-display font-bold tracking-tight">Welcome back</h1>
                <p className="text-sm text-muted-foreground mt-1">Sign in to your enterprise workspace</p>
              </div>

              <div className="space-y-4">
                <div>
                  <Label htmlFor="email" className="text-xs uppercase tracking-wider">Email</Label>
                  <Input
                    id="email"
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                    className="mt-1.5 h-11"
                    data-testid="login-email-input"
                  />
                </div>
                <div>
                  <Label htmlFor="password" className="text-xs uppercase tracking-wider">Password</Label>
                  <div className="relative mt-1.5">
                    <Input
                      id="password"
                      type={showPw ? "text" : "password"}
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      required
                      className="h-11 pr-10"
                      data-testid="login-password-input"
                    />
                    <button
                      type="button"
                      onClick={() => setShowPw(!showPw)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground"
                      data-testid="toggle-pw-visibility"
                    >
                      {showPw ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                    </button>
                  </div>
                </div>

                {error && (
                  <div className="text-sm text-red-600 dark:text-red-400 bg-red-500/10 border border-red-500/20 rounded-md px-3 py-2" data-testid="login-error">
                    {error}
                  </div>
                )}

                <Button
                  type="submit"
                  disabled={loading}
                  className="w-full h-11 bg-blue-600 hover:bg-blue-700 text-white"
                  data-testid="login-submit-btn"
                >
                  {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : "Sign in"}
                </Button>
              </div>

              <div className="mt-6 pt-6 border-t border-slate-200/50 dark:border-white/10">
                <p className="text-xs uppercase tracking-wider text-muted-foreground mb-3">Demo accounts</p>
                <div className="grid grid-cols-3 gap-2">
                  <button type="button" onClick={() => fill("admin@cmportal.com", "Admin@123")} className="text-xs glass-card rounded-md py-2 hover:bg-blue-500/10 transition" data-testid="demo-admin">Admin</button>
                  <button type="button" onClick={() => fill("manager@cmportal.com", "Manager@123")} className="text-xs glass-card rounded-md py-2 hover:bg-blue-500/10 transition" data-testid="demo-manager">Manager</button>
                  <button type="button" onClick={() => fill("viewer@cmportal.com", "Viewer@123")} className="text-xs glass-card rounded-md py-2 hover:bg-blue-500/10 transition" data-testid="demo-viewer">Viewer</button>
                </div>
              </div>
            </form>

            <div className="mt-6 flex items-center justify-center gap-2 text-xs text-white/80">
              <ShieldCheck className="h-3.5 w-3.5" />
              <span>SOC 2 Type II • ISO 27001 Compliant</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
