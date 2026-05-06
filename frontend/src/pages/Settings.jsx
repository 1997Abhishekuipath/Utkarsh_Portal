import { useEffect, useState } from "react";
import api from "../lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Switch } from "../components/ui/switch";
import { Label } from "../components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Badge } from "../components/ui/badge";
import { useTheme } from "../context/ThemeContext";
import { useAuth } from "../context/AuthContext";
import { Sun, Moon, Shield, User as UserIcon, Bell, Database, Mail, Send, Loader2 } from "lucide-react";
import { toast } from "sonner";

export default function Settings() {
  const { theme, setTheme } = useTheme();
  const { user } = useAuth();
  const [alertCfg, setAlertCfg] = useState(null);
  const [recipientsInput, setRecipientsInput] = useState("");
  const [testEmail, setTestEmail] = useState("");
  const [sendingTest, setSendingTest] = useState(false);
  const [runningDigest, setRunningDigest] = useState(false);

  const isAdmin = user?.role === "admin";

  useEffect(() => {
    if (!isAdmin) return;
    api.get("/alerts/config").then(r => {
      setAlertCfg(r.data);
      setRecipientsInput((r.data.recipients || []).join(", "));
      setTestEmail(user?.email || "");
    }).catch(() => {});
  }, [isAdmin, user]);

  const saveAlertConfig = async () => {
    const recipients = recipientsInput.split(",").map(s => s.trim()).filter(Boolean);
    if (recipients.length === 0) { toast.error("At least one recipient required"); return; }
    try {
      await api.put("/alerts/config", { recipients, enabled: alertCfg?.enabled ?? true, cadence: alertCfg?.cadence || "daily" });
      toast.success("Alert config saved");
      const r = await api.get("/alerts/config");
      setAlertCfg(r.data);
    } catch (e) {
      toast.error(e.response?.data?.detail || "Save failed");
    }
  };

  const sendTest = async () => {
    if (!testEmail) return;
    setSendingTest(true);
    try {
      const { data } = await api.post("/alerts/test-email", { recipient: testEmail });
      if (data.sent) toast.success(`Test email sent to ${testEmail}`);
      else toast.warning(`Email not sent: ${data.reason}`);
    } catch (e) {
      toast.error(e.response?.data?.detail || "Test failed");
    } finally { setSendingTest(false); }
  };

  const runDigest = async () => {
    setRunningDigest(true);
    try {
      const { data } = await api.post("/alerts/run-digest");
      if (data.sent) toast.success(`Digest sent — ${data.total} licenses across ${Object.keys(data.buckets).length} buckets`);
      else toast.warning(data.reason || "No alerts sent");
    } catch (e) {
      toast.error(e.response?.data?.detail || "Digest failed");
    } finally { setRunningDigest(false); }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-display text-3xl sm:text-4xl font-bold tracking-tight">Settings</h1>
        <p className="text-sm text-muted-foreground mt-1">Manage your preferences, notifications and workspace</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card className="glass-card border-0">
          <CardHeader>
            <CardTitle className="font-display flex items-center gap-2"><UserIcon className="h-5 w-5 text-blue-600" />Profile</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex justify-between items-center"><span className="text-sm text-muted-foreground">Name</span><span className="font-medium">{user?.name}</span></div>
            <div className="flex justify-between items-center"><span className="text-sm text-muted-foreground">Email</span><span className="font-medium">{user?.email}</span></div>
            <div className="flex justify-between items-center"><span className="text-sm text-muted-foreground">Role</span><Badge variant="outline" className="status-info uppercase">{user?.role}</Badge></div>
          </CardContent>
        </Card>

        <Card className="glass-card border-0">
          <CardHeader>
            <CardTitle className="font-display flex items-center gap-2">{theme === "dark" ? <Moon className="h-5 w-5 text-blue-600" /> : <Sun className="h-5 w-5 text-blue-600" />}Appearance</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center justify-between">
              <div>
                <Label className="text-base">Dark Mode</Label>
                <p className="text-xs text-muted-foreground">Switch between light and dark themes</p>
              </div>
              <Switch checked={theme === "dark"} onCheckedChange={(v) => setTheme(v ? "dark" : "light")} data-testid="settings-theme-toggle" />
            </div>
          </CardContent>
        </Card>

        {isAdmin && (
          <Card className="glass-card border-0 lg:col-span-2">
            <CardHeader>
              <CardTitle className="font-display flex items-center gap-2"><Mail className="h-5 w-5 text-blue-600" />Email Alerts</CardTitle>
              <div className="flex items-center gap-2 mt-1">
                {alertCfg?.resend_configured ? (
                  <Badge className="status-active">Resend Connected</Badge>
                ) : (
                  <Badge className="status-warn">Set RESEND_API_KEY in backend/.env</Badge>
                )}
                {alertCfg?.last_run && <span className="text-xs text-muted-foreground">Last run: {new Date(alertCfg.last_run).toLocaleString()}</span>}
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <Label>Recipients (comma-separated)</Label>
                <Input className="mt-1" value={recipientsInput} onChange={(e) => setRecipientsInput(e.target.value)} placeholder="admin@example.com, ops@example.com" data-testid="alert-recipients-input" />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label>Cadence</Label>
                  <Select value={alertCfg?.cadence || "daily"} onValueChange={(v) => setAlertCfg({ ...alertCfg, cadence: v })}>
                    <SelectTrigger className="mt-1"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="daily">Daily Digest</SelectItem>
                      <SelectItem value="weekly">Weekly</SelectItem>
                      <SelectItem value="manual">Manual Only</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="flex items-center gap-3 mt-7">
                  <Switch checked={alertCfg?.enabled ?? true} onCheckedChange={(v) => setAlertCfg({ ...alertCfg, enabled: v })} data-testid="alerts-enabled-switch" />
                  <Label>Alerts Enabled</Label>
                </div>
              </div>
              <div className="flex gap-2 flex-wrap">
                <Button onClick={saveAlertConfig} className="bg-blue-600 hover:bg-blue-700 text-white" data-testid="save-alert-config-btn">Save Config</Button>
                <Button variant="outline" onClick={runDigest} disabled={runningDigest} data-testid="run-digest-btn">
                  {runningDigest ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <Send className="h-4 w-4 mr-2" />} Run Digest Now
                </Button>
              </div>
              <div className="border-t border-slate-200/50 dark:border-white/10 pt-4">
                <Label>Send Test Email</Label>
                <div className="flex gap-2 mt-1">
                  <Input value={testEmail} onChange={(e) => setTestEmail(e.target.value)} placeholder="recipient@example.com" data-testid="test-email-input" />
                  <Button variant="outline" onClick={sendTest} disabled={sendingTest || !testEmail} data-testid="send-test-btn">
                    {sendingTest ? <Loader2 className="h-4 w-4 animate-spin" /> : "Send"}
                  </Button>
                </div>
                <p className="text-xs text-muted-foreground mt-1.5">Fires a sample alert to the address above. Requires Resend to be configured.</p>
              </div>
            </CardContent>
          </Card>
        )}

        <Card className="glass-card border-0">
          <CardHeader>
            <CardTitle className="font-display flex items-center gap-2"><Bell className="h-5 w-5 text-blue-600" />In-App Notifications</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center justify-between">
              <div><Label>License Expiry Alerts</Label><p className="text-xs text-muted-foreground">90/60/30 day milestones in topbar</p></div>
              <Switch defaultChecked />
            </div>
            <div className="flex items-center justify-between">
              <div><Label>Renewal Reminders</Label><p className="text-xs text-muted-foreground">Daily summary widget</p></div>
              <Switch defaultChecked />
            </div>
          </CardContent>
        </Card>

        <Card className="glass-card border-0">
          <CardHeader>
            <CardTitle className="font-display flex items-center gap-2"><Shield className="h-5 w-5 text-blue-600" />Security</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex justify-between items-center"><span className="text-sm">Two-factor authentication</span><Badge className="status-warn">Recommended</Badge></div>
            <div className="flex justify-between items-center"><span className="text-sm">Session timeout</span><span className="text-sm font-medium">8 hours</span></div>
            <Button variant="outline" className="w-full" data-testid="change-password-btn">Change Password</Button>
          </CardContent>
        </Card>

        <Card className="glass-card border-0 lg:col-span-2">
          <CardHeader>
            <CardTitle className="font-display flex items-center gap-2"><Database className="h-5 w-5 text-blue-600" />Workspace</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-sm">
              <div className="glass-card p-4 rounded-lg"><p className="text-xs uppercase tracking-wider text-muted-foreground">Tier</p><p className="font-display text-lg font-semibold mt-1">Enterprise</p></div>
              <div className="glass-card p-4 rounded-lg"><p className="text-xs uppercase tracking-wider text-muted-foreground">SSL</p><p className="font-display text-lg font-semibold mt-1 text-emerald-500">Active</p></div>
              <div className="glass-card p-4 rounded-lg"><p className="text-xs uppercase tracking-wider text-muted-foreground">API Access</p><p className="font-display text-lg font-semibold mt-1">REST</p></div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
