import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Switch } from "../components/ui/switch";
import { Label } from "../components/ui/label";
import { useTheme } from "../context/ThemeContext";
import { useAuth } from "../context/AuthContext";
import { Badge } from "../components/ui/badge";
import { Sun, Moon, Shield, User as UserIcon, Bell, Database } from "lucide-react";

export default function Settings() {
  const { theme, setTheme } = useTheme();
  const { user } = useAuth();

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-display text-3xl sm:text-4xl font-bold tracking-tight">Settings</h1>
        <p className="text-sm text-muted-foreground mt-1">Manage your preferences and workspace</p>
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

        <Card className="glass-card border-0">
          <CardHeader>
            <CardTitle className="font-display flex items-center gap-2"><Bell className="h-5 w-5 text-blue-600" />Notifications</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center justify-between">
              <div><Label>License Expiry Alerts</Label><p className="text-xs text-muted-foreground">Get notified 90/60/30 days before expiry</p></div>
              <Switch defaultChecked />
            </div>
            <div className="flex items-center justify-between">
              <div><Label>Renewal Reminders</Label><p className="text-xs text-muted-foreground">Daily summary of upcoming renewals</p></div>
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
