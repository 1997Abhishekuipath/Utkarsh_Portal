import { useEffect, useState } from "react";
import api from "../lib/api";
import { Card, CardContent } from "../components/ui/card";
import { Input } from "../components/ui/input";
import { Button } from "../components/ui/button";
import { Plus, Search, Pencil, Trash2, Download } from "lucide-react";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../components/ui/table";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "../components/ui/dialog";
import { Label } from "../components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Textarea } from "../components/ui/textarea";
import { Switch } from "../components/ui/switch";
import { StatusBadge } from "../components/StatusBadge";
import { useAuth } from "../context/AuthContext";
import { toast } from "sonner";
import { exportCSV, exportPDF } from "../lib/export";

const empty = {
  customer_id: "", product_id: "", license_key: "",
  license_type: "Subscription", license_count: 1, subscription_type: "Annual",
  purchase_date: "", activation_date: "", expiry_date: "", renewal_date: "",
  cost: 0, currency: "USD", invoice_number: "", po_number: "",
  support_expiry: "", warranty_expiry: "", auto_renewal: false, notes: "",
};

export default function Licenses() {
  const { user } = useAuth();
  const [list, setList] = useState([]);
  const [customers, setCustomers] = useState([]);
  const [products, setProducts] = useState([]);
  const [search, setSearch] = useState("");
  const [statusF, setStatusF] = useState("all");
  const [vendorF, setVendorF] = useState("all");
  const [categoryF, setCategoryF] = useState("all");
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
    if (statusF !== "all") params.status = statusF;
    if (vendorF !== "all") params.vendor = vendorF;
    if (categoryF !== "all") params.category = categoryF;
    const { data } = await api.get("/licenses", { params });
    setList(data);
  };
  useEffect(() => { load(); /* eslint-disable-next-line */ }, [search, statusF, vendorF, categoryF]);
  useEffect(() => {
    api.get("/customers").then(r => setCustomers(r.data));
    api.get("/products").then(r => setProducts(r.data));
  }, []);

  const vendors = Array.from(new Set(products.map(p => p.vendor).filter(Boolean)));
  const categories = Array.from(new Set(products.map(p => p.product_category).filter(Boolean)));

  const openNew = () => {
    const today = new Date().toISOString().slice(0, 10);
    setForm({ ...empty, purchase_date: today, activation_date: today, expiry_date: today });
    setEditId(null); setDialogOpen(true);
  };
  const openEdit = (l) => {
    setForm({
      customer_id: l.customer_id, product_id: l.product_id, license_key: l.license_key,
      license_type: l.license_type, license_count: l.license_count, subscription_type: l.subscription_type,
      purchase_date: l.purchase_date, activation_date: l.activation_date, expiry_date: l.expiry_date,
      renewal_date: l.renewal_date, cost: l.cost, currency: l.currency,
      invoice_number: l.invoice_number, po_number: l.po_number,
      support_expiry: l.support_expiry, warranty_expiry: l.warranty_expiry,
      auto_renewal: !!l.auto_renewal, notes: l.notes || "",
    });
    setEditId(l.id); setDialogOpen(true);
  };

  const save = async () => {
    try {
      const payload = { ...form, cost: parseFloat(form.cost) || 0, license_count: parseInt(form.license_count) || 1 };
      if (editId) await api.put(`/licenses/${editId}`, payload);
      else await api.post("/licenses", payload);
      toast.success(editId ? "License updated" : "License created");
      setDialogOpen(false);
      load();
    } catch (e) { toast.error(e.response?.data?.detail || "Save failed"); }
  };

  const remove = async (id) => {
    if (!window.confirm("Delete this license?")) return;
    try { await api.delete(`/licenses/${id}`); toast.success("Deleted"); load(); }
    catch (e) { toast.error(e.response?.data?.detail || "Delete failed"); }
  };

  const total = list.length;
  const pages = Math.max(1, Math.ceil(total / pageSize));
  const view = list.slice((page - 1) * pageSize, page * pageSize);
  const cols = ["license_key", "customer_name", "product_name", "vendor", "license_type", "license_count", "purchase_date", "expiry_date", "cost", "currency", "status"];

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between flex-wrap gap-4">
        <div>
          <h1 className="font-display text-3xl sm:text-4xl font-bold tracking-tight">Licenses</h1>
          <p className="text-sm text-muted-foreground mt-1">Track license keys, expirations, and renewals</p>
        </div>
        <div className="flex gap-2 flex-wrap">
          <Button variant="outline" onClick={() => exportCSV("licenses", list, cols)} data-testid="export-licenses-csv"><Download className="h-4 w-4 mr-2" /> CSV</Button>
          <Button variant="outline" onClick={() => exportPDF("Licenses Report", list, cols)} data-testid="export-licenses-pdf"><Download className="h-4 w-4 mr-2" /> PDF</Button>
          {canWrite && <Button onClick={openNew} className="bg-blue-600 hover:bg-blue-700 text-white" data-testid="add-license-btn"><Plus className="h-4 w-4 mr-2" /> Add License</Button>}
        </div>
      </div>

      <Card className="glass-card border-0">
        <CardContent className="p-4 sm:p-6 space-y-4">
          <div className="flex flex-wrap gap-3">
            <div className="relative flex-1 min-w-[220px]">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input className="pl-9" placeholder="Search license, customer, product..." value={search} onChange={(e) => setSearch(e.target.value)} data-testid="license-search-input" />
            </div>
            <Select value={statusF} onValueChange={setStatusF}>
              <SelectTrigger className="w-44" data-testid="license-status-filter"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Status</SelectItem>
                <SelectItem value="Active">Active</SelectItem>
                <SelectItem value="Expiring Soon">Expiring Soon</SelectItem>
                <SelectItem value="Expired">Expired</SelectItem>
              </SelectContent>
            </Select>
            <Select value={vendorF} onValueChange={setVendorF}>
              <SelectTrigger className="w-44" data-testid="license-vendor-filter"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Vendors</SelectItem>
                {vendors.map(v => <SelectItem key={v} value={v}>{v}</SelectItem>)}
              </SelectContent>
            </Select>
            <Select value={categoryF} onValueChange={setCategoryF}>
              <SelectTrigger className="w-44" data-testid="license-category-filter"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Categories</SelectItem>
                {categories.map(c => <SelectItem key={c} value={c}>{c}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>

          <div className="rounded-lg overflow-hidden border border-slate-200/60 dark:border-white/10 overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>License Key</TableHead>
                  <TableHead>Customer</TableHead>
                  <TableHead>Product</TableHead>
                  <TableHead>Vendor</TableHead>
                  <TableHead>Count</TableHead>
                  <TableHead>Expiry</TableHead>
                  <TableHead>Cost</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {view.map(l => (
                  <TableRow key={l.id} data-testid={`license-row-${l.id}`}>
                    <TableCell className="font-mono text-xs max-w-[180px] truncate">{l.license_key}</TableCell>
                    <TableCell className="font-medium">{l.customer_name}</TableCell>
                    <TableCell>{l.product_name}</TableCell>
                    <TableCell className="text-xs">{l.vendor}</TableCell>
                    <TableCell>{l.license_count}</TableCell>
                    <TableCell className="text-xs">{l.expiry_date}</TableCell>
                    <TableCell className="tabular-nums">{l.currency} {Number(l.cost).toLocaleString()}</TableCell>
                    <TableCell><StatusBadge status={l.status} /></TableCell>
                    <TableCell className="text-right">
                      {canWrite && <Button variant="ghost" size="icon" onClick={() => openEdit(l)} data-testid={`edit-license-${l.id}`}><Pencil className="h-4 w-4" /></Button>}
                      {canDelete && <Button variant="ghost" size="icon" onClick={() => remove(l.id)} data-testid={`delete-license-${l.id}`}><Trash2 className="h-4 w-4 text-red-500" /></Button>}
                    </TableCell>
                  </TableRow>
                ))}
                {view.length === 0 && <TableRow><TableCell colSpan={9} className="text-center text-muted-foreground py-8">No licenses</TableCell></TableRow>}
              </TableBody>
            </Table>
          </div>

          <div className="flex items-center justify-between text-sm text-muted-foreground">
            <span>{total} licenses</span>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage(p => p - 1)}>Prev</Button>
              <Button variant="outline" size="sm" disabled={page >= pages} onClick={() => setPage(p => p + 1)}>Next</Button>
            </div>
          </div>
        </CardContent>
      </Card>

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="glass-strong max-w-3xl max-h-[90vh] overflow-y-auto">
          <DialogHeader><DialogTitle className="font-display">{editId ? "Edit License" : "New License"}</DialogTitle></DialogHeader>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mt-2">
            <div>
              <Label>Customer *</Label>
              <Select value={form.customer_id} onValueChange={(v) => setForm({ ...form, customer_id: v })}>
                <SelectTrigger className="mt-1" data-testid="license-customer-select"><SelectValue placeholder="Select customer" /></SelectTrigger>
                <SelectContent className="max-h-72">
                  {customers.map(c => <SelectItem key={c.id} value={c.id}>{c.company_name}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label>Product *</Label>
              <Select value={form.product_id} onValueChange={(v) => setForm({ ...form, product_id: v })}>
                <SelectTrigger className="mt-1" data-testid="license-product-select"><SelectValue placeholder="Select product" /></SelectTrigger>
                <SelectContent className="max-h-72">
                  {products.map(p => <SelectItem key={p.id} value={p.id}>{p.product_name}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div className="sm:col-span-2">
              <Label>License Key *</Label>
              <Input className="mt-1 font-mono" value={form.license_key} onChange={(e) => setForm({ ...form, license_key: e.target.value })} data-testid="license-key-input" />
            </div>
            <div>
              <Label>License Type</Label>
              <Select value={form.license_type} onValueChange={(v) => setForm({ ...form, license_type: v })}>
                <SelectTrigger className="mt-1"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="Subscription">Subscription</SelectItem>
                  <SelectItem value="Perpetual">Perpetual</SelectItem>
                  <SelectItem value="Floating">Floating</SelectItem>
                  <SelectItem value="Trial">Trial</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label>Subscription Type</Label>
              <Select value={form.subscription_type} onValueChange={(v) => setForm({ ...form, subscription_type: v })}>
                <SelectTrigger className="mt-1"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="Monthly">Monthly</SelectItem>
                  <SelectItem value="Quarterly">Quarterly</SelectItem>
                  <SelectItem value="Annual">Annual</SelectItem>
                  <SelectItem value="Multi-Year">Multi-Year</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div><Label>License Count</Label><Input type="number" className="mt-1" value={form.license_count} onChange={(e) => setForm({ ...form, license_count: e.target.value })} /></div>
            <div><Label>Cost</Label><Input type="number" step="0.01" className="mt-1" value={form.cost} onChange={(e) => setForm({ ...form, cost: e.target.value })} /></div>
            <div>
              <Label>Currency</Label>
              <Select value={form.currency} onValueChange={(v) => setForm({ ...form, currency: v })}>
                <SelectTrigger className="mt-1"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="USD">USD</SelectItem>
                  <SelectItem value="EUR">EUR</SelectItem>
                  <SelectItem value="INR">INR</SelectItem>
                  <SelectItem value="GBP">GBP</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div><Label>Purchase Date</Label><Input type="date" className="mt-1" value={form.purchase_date} onChange={(e) => setForm({ ...form, purchase_date: e.target.value })} /></div>
            <div><Label>Activation Date</Label><Input type="date" className="mt-1" value={form.activation_date} onChange={(e) => setForm({ ...form, activation_date: e.target.value })} /></div>
            <div><Label>Expiry Date *</Label><Input type="date" className="mt-1" value={form.expiry_date} onChange={(e) => setForm({ ...form, expiry_date: e.target.value })} data-testid="license-expiry-input" /></div>
            <div><Label>Renewal Date</Label><Input type="date" className="mt-1" value={form.renewal_date} onChange={(e) => setForm({ ...form, renewal_date: e.target.value })} /></div>
            <div><Label>Invoice Number</Label><Input className="mt-1" value={form.invoice_number} onChange={(e) => setForm({ ...form, invoice_number: e.target.value })} /></div>
            <div><Label>PO Number</Label><Input className="mt-1" value={form.po_number} onChange={(e) => setForm({ ...form, po_number: e.target.value })} /></div>
            <div><Label>Support Expiry</Label><Input type="date" className="mt-1" value={form.support_expiry} onChange={(e) => setForm({ ...form, support_expiry: e.target.value })} /></div>
            <div><Label>Warranty Expiry</Label><Input type="date" className="mt-1" value={form.warranty_expiry} onChange={(e) => setForm({ ...form, warranty_expiry: e.target.value })} /></div>
            <div className="flex items-center gap-3 mt-6">
              <Switch checked={form.auto_renewal} onCheckedChange={(v) => setForm({ ...form, auto_renewal: v })} data-testid="auto-renewal-switch" />
              <Label>Auto-Renewal Enabled</Label>
            </div>
            <div className="sm:col-span-2"><Label>Notes</Label><Textarea rows={2} className="mt-1" value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} /></div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)}>Cancel</Button>
            <Button onClick={save} className="bg-blue-600 hover:bg-blue-700 text-white" data-testid="save-license-btn">Save</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
