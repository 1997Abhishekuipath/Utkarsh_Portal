import { useEffect, useState } from "react";
import api from "../lib/api";
import { Card, CardContent } from "../components/ui/card";
import { Input } from "../components/ui/input";
import { Button } from "../components/ui/button";
import { Plus, Search, Pencil, Trash2, Download } from "lucide-react";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../components/ui/table";
import { StatusBadge } from "../components/StatusBadge";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "../components/ui/dialog";
import { Label } from "../components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Textarea } from "../components/ui/textarea";
import { useAuth } from "../context/AuthContext";
import { toast } from "sonner";
import { exportCSV, exportPDF } from "../lib/export";

const empty = {
  company_name: "", customer_name: "", contact_number: "", email: "",
  address: "", country: "", state: "", city: "",
  gst_number: "", pan_number: "",
  support_contact_person: "", support_contact_number: "",
  account_manager: "", status: "Active",
};

export default function Customers() {
  const { user } = useAuth();
  const [list, setList] = useState([]);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [page, setPage] = useState(1);
  const pageSize = 10;
  const [dialogOpen, setDialogOpen] = useState(false);
  const [form, setForm] = useState(empty);
  const [editId, setEditId] = useState(null);

  const canWrite = ["admin", "manager"].includes(user?.role);
  const canDelete = user?.role === "admin";

  const load = async () => {
    const params = {};
    if (search) params.search = search;
    if (statusFilter !== "all") params.status = statusFilter;
    const { data } = await api.get("/customers", { params });
    setList(data);
  };
  useEffect(() => { load(); /* eslint-disable-next-line */ }, [search, statusFilter]);

  const openNew = () => { setForm(empty); setEditId(null); setDialogOpen(true); };
  const openEdit = (c) => { setForm({ ...c }); setEditId(c.id); setDialogOpen(true); };

  const save = async () => {
    try {
      if (editId) await api.put(`/customers/${editId}`, form);
      else await api.post("/customers", form);
      toast.success(editId ? "Customer updated" : "Customer created");
      setDialogOpen(false);
      load();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Save failed");
    }
  };

  const remove = async (id) => {
    if (!window.confirm("Delete this customer?")) return;
    try {
      await api.delete(`/customers/${id}`);
      toast.success("Customer deleted");
      load();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Delete failed");
    }
  };

  const total = list.length;
  const pages = Math.max(1, Math.ceil(total / pageSize));
  const view = list.slice((page - 1) * pageSize, page * pageSize);

  const columns = ["customer_code", "company_name", "customer_name", "email", "country", "city", "account_manager", "status"];

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between flex-wrap gap-4">
        <div>
          <h1 className="font-display text-3xl sm:text-4xl font-bold tracking-tight">Customers</h1>
          <p className="text-sm text-muted-foreground mt-1">Manage your customer accounts and relationships</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => exportCSV("customers", list, columns)} data-testid="export-csv-btn">
            <Download className="h-4 w-4 mr-2" /> CSV
          </Button>
          <Button variant="outline" onClick={() => exportPDF("Customers Report", list, columns)} data-testid="export-pdf-btn">
            <Download className="h-4 w-4 mr-2" /> PDF
          </Button>
          {canWrite && (
            <Button onClick={openNew} className="bg-blue-600 hover:bg-blue-700 text-white" data-testid="add-customer-btn">
              <Plus className="h-4 w-4 mr-2" /> Add Customer
            </Button>
          )}
        </div>
      </div>

      <Card className="glass-card border-0">
        <CardContent className="p-4 sm:p-6 space-y-4">
          <div className="flex flex-wrap gap-3">
            <div className="relative flex-1 min-w-[220px]">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input className="pl-9" placeholder="Search company, customer, email, city..." value={search} onChange={(e) => setSearch(e.target.value)} data-testid="customer-search-input" />
            </div>
            <Select value={statusFilter} onValueChange={setStatusFilter}>
              <SelectTrigger className="w-40" data-testid="customer-status-filter"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Status</SelectItem>
                <SelectItem value="Active">Active</SelectItem>
                <SelectItem value="Inactive">Inactive</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="rounded-lg overflow-hidden border border-slate-200/60 dark:border-white/10">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Code</TableHead>
                  <TableHead>Company</TableHead>
                  <TableHead>Customer</TableHead>
                  <TableHead>Email</TableHead>
                  <TableHead>Country</TableHead>
                  <TableHead>Account Mgr</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody data-testid="customers-tbody">
                {view.map(c => (
                  <TableRow key={c.id} data-testid={`customer-row-${c.id}`}>
                    <TableCell className="font-mono text-xs">{c.customer_code}</TableCell>
                    <TableCell className="font-medium">{c.company_name}</TableCell>
                    <TableCell>{c.customer_name}</TableCell>
                    <TableCell className="text-muted-foreground text-xs">{c.email}</TableCell>
                    <TableCell>{c.country}</TableCell>
                    <TableCell>{c.account_manager}</TableCell>
                    <TableCell><StatusBadge status={c.status} /></TableCell>
                    <TableCell className="text-right">
                      {canWrite && (
                        <Button variant="ghost" size="icon" onClick={() => openEdit(c)} data-testid={`edit-customer-${c.id}`}>
                          <Pencil className="h-4 w-4" />
                        </Button>
                      )}
                      {canDelete && (
                        <Button variant="ghost" size="icon" onClick={() => remove(c.id)} data-testid={`delete-customer-${c.id}`}>
                          <Trash2 className="h-4 w-4 text-red-500" />
                        </Button>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
                {view.length === 0 && (
                  <TableRow><TableCell colSpan={8} className="text-center text-muted-foreground py-8">No customers found</TableCell></TableRow>
                )}
              </TableBody>
            </Table>
          </div>

          <div className="flex items-center justify-between text-sm text-muted-foreground">
            <span>Showing {(page - 1) * pageSize + 1}-{Math.min(page * pageSize, total)} of {total}</span>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage(p => p - 1)}>Prev</Button>
              <Button variant="outline" size="sm" disabled={page >= pages} onClick={() => setPage(p => p + 1)}>Next</Button>
            </div>
          </div>
        </CardContent>
      </Card>

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="glass-strong max-w-3xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="font-display">{editId ? "Edit Customer" : "New Customer"}</DialogTitle>
          </DialogHeader>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mt-2">
            {[
              ["company_name", "Company Name *"],
              ["customer_name", "Contact Name *"],
              ["email", "Email"],
              ["contact_number", "Contact Number"],
              ["country", "Country"],
              ["state", "State"],
              ["city", "City"],
              ["gst_number", "GST Number"],
              ["pan_number", "PAN Number"],
              ["support_contact_person", "Support Contact Person"],
              ["support_contact_number", "Support Contact Number"],
              ["account_manager", "Account Manager"],
            ].map(([k, label]) => (
              <div key={k} className={k === "address" ? "sm:col-span-2" : ""}>
                <Label>{label}</Label>
                <Input className="mt-1" value={form[k]} onChange={(e) => setForm({ ...form, [k]: e.target.value })} data-testid={`field-${k}`} />
              </div>
            ))}
            <div className="sm:col-span-2">
              <Label>Address</Label>
              <Textarea className="mt-1" rows={2} value={form.address} onChange={(e) => setForm({ ...form, address: e.target.value })} />
            </div>
            <div>
              <Label>Status</Label>
              <Select value={form.status} onValueChange={(v) => setForm({ ...form, status: v })}>
                <SelectTrigger className="mt-1"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="Active">Active</SelectItem>
                  <SelectItem value="Inactive">Inactive</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)}>Cancel</Button>
            <Button onClick={save} className="bg-blue-600 hover:bg-blue-700 text-white" data-testid="save-customer-btn">Save</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
