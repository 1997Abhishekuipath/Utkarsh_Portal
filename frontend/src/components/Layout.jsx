import { useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import {
  LayoutDashboard, Users, Box, KeyRound, FileBarChart2, UserCog, Settings as SettingsIcon,
  Bell, Sun, Moon, LogOut, Menu, X, Hexagon, Search, ShieldCheck
} from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { useTheme } from "../context/ThemeContext";
import { Button } from "./ui/button";
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel,
  DropdownMenuSeparator, DropdownMenuTrigger
} from "./ui/dropdown-menu";
import { Avatar, AvatarFallback, AvatarImage } from "./ui/avatar";
import { Badge } from "./ui/badge";
import api from "../lib/api";
import { useEffect } from "react";

const NAV = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard, roles: ["admin", "manager", "viewer"] },
  { to: "/customers", label: "Customers", icon: Users, roles: ["admin", "manager", "viewer"] },
  { to: "/products", label: "Products", icon: Box, roles: ["admin", "manager", "viewer"] },
  { to: "/licenses", label: "Licenses", icon: KeyRound, roles: ["admin", "manager", "viewer"] },
  { to: "/reports", label: "Reports", icon: FileBarChart2, roles: ["admin", "manager", "viewer"] },
  { to: "/users", label: "User Management", icon: UserCog, roles: ["admin"] },
  { to: "/settings", label: "Settings", icon: SettingsIcon, roles: ["admin", "manager", "viewer"] },
];

export default function Layout() {
  const { user, logout } = useAuth();
  const { theme, toggle } = useTheme();
  const navigate = useNavigate();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [notifications, setNotifications] = useState([]);

  useEffect(() => {
    api.get("/notifications").then(r => setNotifications(r.data || [])).catch(() => {});
  }, []);

  const visibleNav = NAV.filter(n => n.roles.includes(user?.role || "viewer"));

  const handleLogout = async () => {
    await logout();
    navigate("/login");
  };

  return (
    <div className="min-h-screen bg-background dashboard-glow relative">
      {/* Sidebar - desktop */}
      <aside
        className={`hidden lg:flex glass-sidebar fixed left-0 top-0 h-screen w-64 flex-col z-30`}
        data-testid="sidebar-desktop"
      >
        <SidebarContent visibleNav={visibleNav} />
      </aside>

      {/* Sidebar - mobile */}
      {mobileOpen && (
        <>
          <div className="fixed inset-0 bg-black/40 z-40 lg:hidden" onClick={() => setMobileOpen(false)} />
          <aside className="fixed left-0 top-0 h-screen w-72 z-50 glass-strong flex flex-col lg:hidden" data-testid="sidebar-mobile">
            <SidebarContent visibleNav={visibleNav} onNav={() => setMobileOpen(false)} />
          </aside>
        </>
      )}

      <div className="lg:pl-64 relative z-10">
        {/* Top header */}
        <header className="glass-card border-b border-slate-200/50 dark:border-white/10 sticky top-0 z-20" data-testid="topbar">
          <div className="h-16 px-4 sm:px-6 flex items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <Button
                variant="ghost"
                size="icon"
                className="lg:hidden"
                onClick={() => setMobileOpen(true)}
                data-testid="mobile-menu-btn"
              >
                <Menu className="h-5 w-5" />
              </Button>
              <div className="hidden md:flex items-center gap-2 text-sm text-muted-foreground">
                <Search className="h-4 w-4" />
                <span>Search Cmd+K</span>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <Button
                variant="ghost"
                size="icon"
                onClick={toggle}
                data-testid="theme-toggle-btn"
                aria-label="Toggle theme"
              >
                {theme === "dark" ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
              </Button>

              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="ghost" size="icon" className="relative" data-testid="notif-btn">
                    <Bell className="h-5 w-5" />
                    {notifications.length > 0 && (
                      <span className="absolute top-1.5 right-1.5 h-2 w-2 rounded-full bg-red-500" />
                    )}
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="w-80 glass-strong">
                  <DropdownMenuLabel className="font-display">Alerts ({notifications.length})</DropdownMenuLabel>
                  <DropdownMenuSeparator />
                  {notifications.length === 0 && (
                    <div className="p-4 text-sm text-muted-foreground">No alerts</div>
                  )}
                  {notifications.slice(0, 8).map(n => (
                    <DropdownMenuItem key={n.id} className="flex flex-col items-start gap-1 py-2" data-testid={`notif-item-${n.id}`}>
                      <div className="flex items-center justify-between w-full">
                        <span className="text-sm font-medium truncate">{n.title}</span>
                        <Badge className={
                          n.level === "expired" ? "status-danger" :
                          n.level === "critical" ? "status-warn" :
                          "status-info"
                        }>{n.level}</Badge>
                      </div>
                      <span className="text-xs text-muted-foreground">{n.message}</span>
                    </DropdownMenuItem>
                  ))}
                </DropdownMenuContent>
              </DropdownMenu>

              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <button className="flex items-center gap-2 pl-2 pr-3 py-1.5 rounded-full hover:bg-accent transition-colors" data-testid="user-menu-btn">
                    <Avatar className="h-8 w-8 ring-2 ring-blue-500/20">
                      <AvatarImage src="https://static.prod-images.emergentagent.com/jobs/38498a33-99c9-4fc2-81a0-fe2164ce3341/images/33ae3465ab1e76e99c5a6a6add11ba6a74078d7751edf1a09fd4c0892ab32147.png" />
                      <AvatarFallback>{user?.name?.[0] || "U"}</AvatarFallback>
                    </Avatar>
                    <div className="hidden sm:flex flex-col items-start leading-tight">
                      <span className="text-sm font-medium">{user?.name}</span>
                      <span className="text-[10px] uppercase tracking-wider text-muted-foreground">{user?.role}</span>
                    </div>
                  </button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="glass-strong w-56">
                  <DropdownMenuLabel>{user?.email}</DropdownMenuLabel>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem onClick={() => navigate("/settings")} data-testid="menu-settings">
                    <SettingsIcon className="h-4 w-4 mr-2" /> Settings
                  </DropdownMenuItem>
                  <DropdownMenuItem onClick={handleLogout} data-testid="menu-logout">
                    <LogOut className="h-4 w-4 mr-2" /> Logout
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
          </div>
        </header>

        <main className="p-4 sm:p-6 lg:p-8 min-h-[calc(100vh-4rem)] fade-in" data-testid="main-content">
          <Outlet />
        </main>
      </div>
    </div>
  );
}

function SidebarContent({ visibleNav, onNav }) {
  return (
    <>
      <div className="h-16 flex items-center px-6 border-b border-slate-200/50 dark:border-white/10">
        <div className="flex items-center gap-2.5">
          <div className="h-9 w-9 rounded-lg bg-blue-600 flex items-center justify-center">
            <Hexagon className="h-5 w-5 text-white" strokeWidth={2.2} />
          </div>
          <div className="flex flex-col leading-none">
            <span className="font-display font-semibold text-base tracking-tight">CMPortal</span>
            <span className="text-[10px] uppercase tracking-[0.18em] text-muted-foreground">Enterprise</span>
          </div>
        </div>
      </div>

      <nav className="flex-1 overflow-y-auto p-3 space-y-1">
        {visibleNav.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            data-testid={`nav-${label.toLowerCase().replace(/\s+/g, "-")}`}
            onClick={onNav}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors duration-200 ${
                isActive
                  ? "bg-blue-600 text-white shadow-sm"
                  : "text-muted-foreground hover:text-foreground hover:bg-accent"
              }`
            }
          >
            <Icon className="h-4 w-4" strokeWidth={1.5} />
            <span>{label}</span>
          </NavLink>
        ))}
      </nav>

      <div className="p-3 border-t border-slate-200/50 dark:border-white/10">
        <div className="glass-card rounded-lg p-3 flex items-center gap-2 text-xs text-muted-foreground">
          <ShieldCheck className="h-4 w-4 text-emerald-500" />
          <span>Enterprise SSL Active</span>
        </div>
      </div>
    </>
  );
}
