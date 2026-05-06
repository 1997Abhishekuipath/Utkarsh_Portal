import { useEffect, useState } from "react";
import api from "../lib/api";
import { Card, CardContent } from "../components/ui/card";
import { Input } from "../components/ui/input";
import { Button } from "../components/ui/button";
import { Plus, Search, Pencil, Trash2, Download } from "lucide-react";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../components/ui/table";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "../components/ui/dialog";
import { Label } from "../components/ui/label";
import { Textarea } from "../components/ui/textarea";
import { useAuth } from "../context/AuthContext";
import { toast } from "sonner";
import { exportCSV, exportPDF } from "../lib/export";

const empty = {
  product_name: "", product_version: "", product_category: "",
  vendor: "", support_type: "", license_model: "",
  os_compatibility: "", description: "",
};

export default function Products() {
  const { user } = useAuth();
  const [list, setList] = useState([]);
  const [search, setSearch] = useState("");
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
    const { data } = await api.get("/products", { params });
    setList(data);
  };
  useEffect(() => { load(); /* eslint-disable-next-line */ }, [search]);

  const openNew = () => { setForm(empty); setEditId(null); setDialogOpen(true); };
  const openEdit = (p) => { setForm({ ...p }); setEditId(p.id); setDialogOpen(true); };

  const save = async () => {
    try {
      if (editId) await api.put(`/products/${editId}`, form);
      else await api.post("/products", form);
      toast.success(editId ? "Product updated" : "Product created");
      setDialogOpen(false);
      load();
    } catch (e) { toast.error(e.response?.data?.detail || "Save failed"); }
  };

  const remove = async (id) => {
    if (!window.confirm("Delete this product?")) return;
    try { await api.delete(`/products/${id}`); toast.success("Deleted"); load(); }
    catch (e) { toast.error(e.response?.data?.detail || "Delete failed"); }
  };

  const total = list.length;
  const pages = Math.max(1, Math.ceil(total / pageSize));
  const view = list.slice((page - 1) * pageSize, page * pageSize);
  const cols = ["product_name", "product_version", "vendor", "product_category", "support_type", "license_model", "os_compatibility"];

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between flex-wrap gap-4">
        <div>
          <h1 className="font-display text-3xl sm:text-4xl font-bold tracking-tight">Products</h1>
          <p className="text-sm text-muted-foreground mt-1">Catalog of software products and offerings</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => exportCSV("products", list, cols)}><Download className="h-4 w-4 mr-2" /> CSV</Button>
          <Button variant="outline" onClick={() => exportPDF("Products Report", list, cols)}><Download className="h-4 w-4 mr-2" /> PDF</Button>
          {canWrite && (
            <Button onClick={openNew} className="bg-blue-600 hover:bg-blue-700 text-white" data-testid="add-product-btn">
              <Plus className="h-4 w-4 mr-2" /> Add Product
            </Button>
          )}
        </div>
      </div>

      <Card className="glass-card border-0">
        <CardContent className="p-4 sm:p-6 space-y-4">
          <div className="relative max-w-md">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input className="pl-9" placeholder="Search products, vendors..." value={search} onChange={(e) => setSearch(e.target.value)} data-testid="product-search-input" />
          </div>

          <div className="rounded-lg overflow-hidden border border-slate-200/60 dark:border-white/10">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Product</TableHead>
                  <TableHead>Version</TableHead>
                  <TableHead>Vendor</TableHead>
                  <TableHead>Category</TableHead>
                  <TableHead>Support</TableHead>
                  <TableHead>License Model</TableHead>
                  <TableHead>OS</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {view.map(p => (
                  <TableRow key={p.id}>
                    <TableCell className="font-medium">{p.product_name}</TableCell>
                    <TableCell>{p.product_version}</TableCell>
                    <TableCell>{p.vendor}</TableCell>
                    <TableCell>{p.product_category}</TableCell>
                    <TableCell>{p.support_type}</TableCell>
                    <TableCell>{p.license_model}</TableCell>
                    <TableCell className="text-xs text-muted-foreground">{p.os_compatibility}</TableCell>
                    <TableCell className="text-right">
                      {canWrite && <Button variant="ghost" size="icon" onClick={() => openEdit(p)} data-testid={`edit-product-${p.id}`}><Pencil className="h-4 w-4" /></Button>}
                      {canDelete && <Button variant="ghost" size="icon" onClick={() => remove(p.id)} data-testid={`delete-product-${p.id}`}><Trash2 className="h-4 w-4 text-red-500" /></Button>}
                    </TableCell>
                  </TableRow>
                ))}
                {view.length === 0 && <TableRow><TableCell colSpan={8} className="text-center text-muted-foreground py-8">No products</TableCell></TableRow>}
              </TableBody>
            </Table>
          </div>

          <div className="flex items-center justify-between text-sm text-muted-foreground">
            <span>{total} products</span>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage(p => p - 1)}>Prev</Button>
              <Button variant="outline" size="sm" disabled={page >= pages} onClick={() => setPage(p => p + 1)}>Next</Button>
            </div>
          </div>
        </CardContent>
      </Card>

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="glass-strong max-w-2xl">
          <DialogHeader><DialogTitle className="font-display">{editId ? "Edit Product" : "New Product"}</DialogTitle></DialogHeader>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mt-2">
            {[
              ["product_name", "Product Name *"],
              ["product_version", "Version"],
              ["vendor", "Vendor"],
              ["product_category", "Category"],
              ["support_type", "Support Type"],
              ["license_model", "License Model"],
              ["os_compatibility", "OS Compatibility"],
            ].map(([k, label]) => (
              <div key={k}>
                <Label>{label}</Label>
                <Input className="mt-1" value={form[k]} onChange={(e) => setForm({ ...form, [k]: e.target.value })} />
              </div>
            ))}
            <div className="sm:col-span-2">
              <Label>Description</Label>
              <Textarea rows={3} className="mt-1" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)}>Cancel</Button>
            <Button onClick={save} className="bg-blue-600 hover:bg-blue-700 text-white">Save</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
