import { useEffect, useState } from "react";
import api from "../lib/api";
import { Card, CardContent } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Plus, Pencil, Trash2 } from "lucide-react";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../components/ui/table";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "../components/ui/dialog";
import { Label } from "../components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Badge } from "../components/ui/badge";
import { toast } from "sonner";

const empty = { name: "", email: "", password: "", role: "viewer" };

export default function Users() {
  const [list, setList] = useState([]);
  const [logs, setLogs] = useState([]);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [form, setForm] = useState(empty);
  const [editId, setEditId] = useState(null);

  const load = async () => {
    const u = await api.get("/users"); setList(u.data);
    const l = await api.get("/activity-logs"); setLogs(l.data);
  };
  useEffect(() => { load(); }, []);

  const openNew = () => { setForm(empty); setEditId(null); setDialogOpen(true); };
  const openEdit = (u) => { setForm({ name: u.name, email: u.email, password: "", role: u.role }); setEditId(u.id); setDialogOpen(true); };

  const save = async () => {
    try {
      if (editId) {
        const payload = { name: form.name, role: form.role };
        if (form.password) payload.password = form.password;
        await api.put(`/users/${editId}`, payload);
      } else {
        await api.post("/users", form);
      }
      toast.success(editId ? "User updated" : "User created");
      setDialogOpen(false);
      load();
    } catch (e) { toast.error(e.response?.data?.detail || "Save failed"); }
  };

  const remove = async (id) => {
    if (!window.confirm("Delete this user?")) return;
    try { await api.delete(`/users/${id}`); toast.success("Deleted"); load(); }
    catch (e) { toast.error(e.response?.data?.detail || "Delete failed"); }
  };

  const roleClass = { admin: "bg-blue-500/15 text-blue-600 border-blue-500/30", manager: "bg-purple-500/15 text-purple-600 border-purple-500/30", viewer: "bg-slate-500/15 text-slate-600 border-slate-500/30" };

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between flex-wrap gap-4">
        <div>
          <h1 className="font-display text-3xl sm:text-4xl font-bold tracking-tight">User Management</h1>
          <p className="text-sm text-muted-foreground mt-1">Manage portal users and view audit trail</p>
        </div>
        <Button onClick={openNew} className="bg-blue-600 hover:bg-blue-700 text-white" data-testid="add-user-btn">
          <Plus className="h-4 w-4 mr-2" /> Add User
        </Button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card className="glass-card border-0 lg:col-span-2">
          <CardContent className="p-4 sm:p-6">
            <h2 className="font-display text-lg font-semibold mb-3">Users</h2>
            <div className="rounded-lg overflow-hidden border border-slate-200/60 dark:border-white/10">
              <Table>
                <TableHeader>
                  <TableRow><TableHead>Name</TableHead><TableHead>Email</TableHead><TableHead>Role</TableHead><TableHead>Created</TableHead><TableHead className="text-right">Actions</TableHead></TableRow>
                </TableHeader>
                <TableBody>
                  {list.map(u => (
                    <TableRow key={u.id} data-testid={`user-row-${u.id}`}>
                      <TableCell className="font-medium">{u.name}</TableCell>
                      <TableCell>{u.email}</TableCell>
                      <TableCell><Badge variant="outline" className={roleClass[u.role]}>{u.role}</Badge></TableCell>
                      <TableCell className="text-xs text-muted-foreground">{u.created_at?.slice(0, 10)}</TableCell>
                      <TableCell className="text-right">
                        <Button variant="ghost" size="icon" onClick={() => openEdit(u)} data-testid={`edit-user-${u.id}`}><Pencil className="h-4 w-4" /></Button>
                        <Button variant="ghost" size="icon" onClick={() => remove(u.id)} data-testid={`delete-user-${u.id}`}><Trash2 className="h-4 w-4 text-red-500" /></Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </CardContent>
        </Card>

        <Card className="glass-card border-0">
          <CardContent className="p-4 sm:p-6">
            <h2 className="font-display text-lg font-semibold mb-3">Activity Log</h2>
            <div className="space-y-3 max-h-[500px] overflow-y-auto">
              {logs.length === 0 && <p className="text-sm text-muted-foreground">No activity yet</p>}
              {logs.map(l => (
                <div key={l.id} className="text-xs border-l-2 border-blue-500/40 pl-3 py-1">
                  <div className="font-medium">{l.user_email}</div>
                  <div className="text-muted-foreground">
                    <span className="font-semibold uppercase">{l.action}</span> {l.entity}
                    {l.details && ` • ${l.details}`}
                  </div>
                  <div className="text-[10px] text-muted-foreground mt-0.5">{new Date(l.timestamp).toLocaleString()}</div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="glass-strong">
          <DialogHeader><DialogTitle className="font-display">{editId ? "Edit User" : "New User"}</DialogTitle></DialogHeader>
          <div className="space-y-3 mt-2">
            <div><Label>Name *</Label><Input className="mt-1" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} data-testid="user-name-input" /></div>
            <div><Label>Email *</Label><Input className="mt-1" type="email" disabled={!!editId} value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} data-testid="user-email-input" /></div>
            <div><Label>{editId ? "New Password (leave blank to keep)" : "Password *"}</Label><Input className="mt-1" type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} data-testid="user-password-input" /></div>
            <div>
              <Label>Role *</Label>
              <Select value={form.role} onValueChange={(v) => setForm({ ...form, role: v })}>
                <SelectTrigger className="mt-1" data-testid="user-role-select"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="admin">Admin</SelectItem>
                  <SelectItem value="manager">Manager</SelectItem>
                  <SelectItem value="viewer">Viewer (Read-only)</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)}>Cancel</Button>
            <Button onClick={save} className="bg-blue-600 hover:bg-blue-700 text-white" data-testid="save-user-btn">Save</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
