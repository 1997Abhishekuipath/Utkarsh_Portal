import { useEffect, useState } from "react";
import api from "../lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../components/ui/tabs";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../components/ui/table";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from "../components/ui/sheet";
import { Checkbox } from "../components/ui/checkbox";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "../components/ui/dialog";
import { Download, FileBarChart2, SlidersHorizontal, Save, Trash2, Sparkles } from "lucide-react";
import { exportCSV, exportPDF } from "../lib/export";
import { StatusBadge } from "../components/StatusBadge";
import { toast } from "sonner";

const PRESETS = [
  { key: "monthly-expiry", label: "Monthly Expiry", desc: "Licenses expiring within 30 days" },
  { key: "customer-license", label: "Customer Licenses", desc: "All licenses by customer" },
  { key: "vendor", label: "Vendor Report", desc: "Aggregated vendor statistics" },
  { key: "revenue", label: "Revenue Report", desc: "Cost breakdown across licenses" },
  { key: "renewal", label: "Renewal Report", desc: "Licenses requiring renewal" },
  { key: "expired", label: "Expired Licenses", desc: "All expired licenses" },
];

const ENTITY_COLUMNS = {
  customers: ["customer_code", "company_name", "customer_name", "email", "contact_number", "country", "state", "city", "gst_number", "pan_number", "account_manager", "status"],
  products: ["product_name", "product_version", "vendor", "product_category", "support_type", "license_model", "os_compatibility"],
  licenses: ["license_key", "customer_name", "product_name", "vendor", "license_type", "license_count", "subscription_type", "purchase_date", "expiry_date", "renewal_date", "cost", "currency", "invoice_number", "po_number", "status", "auto_renewal"],
};

export default function Reports() {
  const [active, setActive] = useState("monthly-expiry");
  const [rows, setRows] = useState([]);

  // Custom report state
  const [savedReports, setSavedReports] = useState([]);
  const [customOpen, setCustomOpen] = useState(false);
  const [saveOpen, setSaveOpen] = useState(false);
  const [entity, setEntity] = useState("licenses");
  const [columns, setColumns] = useState(ENTITY_COLUMNS.licenses.slice(0, 6));
  const [filters, setFilters] = useState({});
  const [customRows, setCustomRows] = useState([]);
  const [reportName, setReportName] = useState("");
  const [activeCustomId, setActiveCustomId] = useState(null);

  useEffect(() => {
    if (active.startsWith("preset:")) {
      const key = active.replace("preset:", "");
      api.get(`/reports/${key}`).then(r => setRows(r.data)).catch(() => setRows([]));
    } else {
      api.get(`/reports/${active}`).then(r => setRows(r.data)).catch(() => setRows([]));
    }
  }, [active]);

  useEffect(() => {
    api.get("/custom-reports").then(r => setSavedReports(r.data)).catch(() => {});
  }, []);

  const cols = active === "vendor"
    ? ["vendor", "count", "active", "expired", "revenue"]
    : ["license_key", "customer_name", "product_name", "vendor", "license_count", "expiry_date", "cost", "currency", "status"];
  const meta = PRESETS.find(r => r.key === active);

  const onEntityChange = (v) => {
    setEntity(v);
    setColumns(ENTITY_COLUMNS[v].slice(0, 6));
    setFilters({});
  };

  const toggleCol = (c) => {
    setColumns(prev => prev.includes(c) ? prev.filter(x => x !== c) : [...prev, c]);
  };

  const runCustom = async () => {
    if (columns.length === 0) {
      toast.error("Select at least one column");
      return;
    }
    const { data } = await api.post("/custom-reports/run", { name: reportName || "Ad-hoc", entity, columns, filters });
    setCustomRows(data);
    setActive("custom");
    toast.success(`${data.length} rows`);
  };

  const saveReport = async () => {
    if (!reportName.trim()) { toast.error("Name required"); return; }
    if (columns.length === 0) { toast.error("Select columns"); return; }
    const { data } = await api.post("/custom-reports", { name: reportName, entity, columns, filters });
    setSavedReports(p => [data, ...p]);
    setSaveOpen(false);
    setReportName("");
    toast.success("Report saved");
  };

  const loadSaved = async (r) => {
    setEntity(r.entity);
    setColumns(r.columns);
    setFilters(r.filters || {});
    setActiveCustomId(r.id);
    const { data } = await api.post("/custom-reports/run", { name: r.name, entity: r.entity, columns: r.columns, filters: r.filters || {} });
    setCustomRows(data);
    setActive("custom");
  };

  const deleteSaved = async (id) => {
    if (!window.confirm("Delete this saved report?")) return;
    await api.delete(`/custom-reports/${id}`);
    setSavedReports(p => p.filter(x => x.id !== id));
    if (activeCustomId === id) setActiveCustomId(null);
    toast.success("Deleted");
  };

  const isCustom = active === "custom";
  const tableRows = isCustom ? customRows : rows;
  const tableCols = isCustom ? columns : cols;
  const exportName = isCustom ? (reportName || "custom-report") : (meta?.label || "report");

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between flex-wrap gap-4">
        <div>
          <h1 className="font-display text-3xl sm:text-4xl font-bold tracking-tight">Reports</h1>
          <p className="text-sm text-muted-foreground mt-1">Generate, customize and export operational reports</p>
        </div>
        <div className="flex gap-2 flex-wrap">
          <Sheet open={customOpen} onOpenChange={setCustomOpen}>
            <SheetTrigger asChild>
              <Button variant="outline" data-testid="custom-report-btn">
                <SlidersHorizontal className="h-4 w-4 mr-2" /> Custom Report
              </Button>
            </SheetTrigger>
            <SheetContent className="glass-strong w-full sm:max-w-lg overflow-y-auto">
              <SheetHeader>
                <SheetTitle className="font-display flex items-center gap-2"><Sparkles className="h-5 w-5 text-blue-600" />Build Custom Report</SheetTitle>
                <p className="text-xs text-muted-foreground">Pick entity, columns and filters</p>
              </SheetHeader>
              <div className="mt-6 space-y-5">
                <div>
                  <Label className="text-xs uppercase tracking-wider">Entity</Label>
                  <Select value={entity} onValueChange={onEntityChange}>
                    <SelectTrigger className="mt-1.5" data-testid="custom-entity-select"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="customers">Customers</SelectItem>
                      <SelectItem value="products">Products</SelectItem>
                      <SelectItem value="licenses">Licenses</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div>
                  <Label className="text-xs uppercase tracking-wider">Columns ({columns.length})</Label>
                  <div className="mt-2 grid grid-cols-2 gap-2 max-h-72 overflow-y-auto pr-1">
                    {ENTITY_COLUMNS[entity].map(c => (
                      <label key={c} className="flex items-center gap-2 text-sm cursor-pointer hover:bg-accent rounded px-2 py-1.5">
                        <Checkbox checked={columns.includes(c)} onCheckedChange={() => toggleCol(c)} data-testid={`col-${c}`} />
                        <span className="truncate">{c.replace(/_/g, " ")}</span>
                      </label>
                    ))}
                  </div>
                </div>

                {entity === "licenses" && (
                  <>
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <Label className="text-xs">Status</Label>
                        <Select value={filters.status || "all"} onValueChange={(v) => setFilters({ ...filters, status: v })}>
                          <SelectTrigger className="mt-1"><SelectValue /></SelectTrigger>
                          <SelectContent>
                            <SelectItem value="all">All</SelectItem>
                            <SelectItem value="Active">Active</SelectItem>
                            <SelectItem value="Expiring Soon">Expiring Soon</SelectItem>
                            <SelectItem value="Expired">Expired</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                      <div>
                        <Label className="text-xs">Vendor</Label>
                        <Input className="mt-1" placeholder="all" value={filters.vendor || ""} onChange={(e) => setFilters({ ...filters, vendor: e.target.value || "all" })} />
                      </div>
                      <div>
                        <Label className="text-xs">Expiry From</Label>
                        <Input type="date" className="mt-1" value={filters.expiry_from || ""} onChange={(e) => setFilters({ ...filters, expiry_from: e.target.value })} data-testid="filter-expiry-from" />
                      </div>
                      <div>
                        <Label className="text-xs">Expiry To</Label>
                        <Input type="date" className="mt-1" value={filters.expiry_to || ""} onChange={(e) => setFilters({ ...filters, expiry_to: e.target.value })} data-testid="filter-expiry-to" />
                      </div>
                    </div>
                  </>
                )}

                {entity === "customers" && (
                  <div>
                    <Label className="text-xs">Status</Label>
                    <Select value={filters.status || "all"} onValueChange={(v) => setFilters({ ...filters, status: v })}>
                      <SelectTrigger className="mt-1"><SelectValue /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="all">All</SelectItem>
                        <SelectItem value="Active">Active</SelectItem>
                        <SelectItem value="Inactive">Inactive</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                )}

                <div className="flex gap-2 pt-2">
                  <Button onClick={runCustom} className="flex-1 bg-blue-600 hover:bg-blue-700 text-white" data-testid="run-custom-report-btn">Run Report</Button>
                  <Button variant="outline" onClick={() => setSaveOpen(true)} data-testid="save-custom-report-btn"><Save className="h-4 w-4 mr-1" /> Save</Button>
                </div>

                {savedReports.length > 0 && (
                  <div className="pt-4 border-t border-slate-200/50 dark:border-white/10">
                    <Label className="text-xs uppercase tracking-wider">Saved Reports</Label>
                    <div className="mt-2 space-y-1.5">
                      {savedReports.map(r => (
                        <div key={r.id} className="flex items-center gap-2 p-2 rounded hover:bg-accent">
                          <button onClick={() => loadSaved(r)} className="flex-1 text-left text-sm" data-testid={`load-report-${r.id}`}>
                            <p className="font-medium">{r.name}</p>
                            <p className="text-xs text-muted-foreground">{r.entity} · {r.columns.length} cols</p>
                          </button>
                          <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => deleteSaved(r.id)}>
                            <Trash2 className="h-3.5 w-3.5 text-red-500" />
                          </Button>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </SheetContent>
          </Sheet>

          <Button variant="outline" onClick={() => exportCSV(exportName, tableRows, tableCols)} data-testid="report-export-csv">
            <Download className="h-4 w-4 mr-2" /> CSV
          </Button>
          <Button variant="outline" onClick={() => exportPDF(exportName, tableRows, tableCols)} data-testid="report-export-pdf">
            <Download className="h-4 w-4 mr-2" /> PDF
          </Button>
        </div>
      </div>

      <Card className="glass-card border-0">
        <CardHeader>
          <CardTitle className="font-display flex items-center gap-2">
            <FileBarChart2 className="h-5 w-5 text-blue-600" />
            {isCustom ? `Custom: ${reportName || "Ad-hoc"}` : meta?.label}
          </CardTitle>
          <p className="text-xs text-muted-foreground">{isCustom ? `${entity} · ${columns.length} columns · ${customRows.length} rows` : meta?.desc}</p>
        </CardHeader>
        <CardContent>
          <Tabs value={active} onValueChange={setActive}>
            <TabsList className="flex-wrap h-auto gap-1 bg-transparent p-0">
              {PRESETS.map(r => (
                <TabsTrigger key={r.key} value={r.key} data-testid={`report-tab-${r.key}`} className="data-[state=active]:bg-blue-600 data-[state=active]:text-white">
                  {r.label}
                </TabsTrigger>
              ))}
              {isCustom && (
                <TabsTrigger value="custom" className="data-[state=active]:bg-blue-600 data-[state=active]:text-white">
                  Custom
                </TabsTrigger>
              )}
            </TabsList>

            <div className="mt-4 rounded-lg overflow-hidden border border-slate-200/60 dark:border-white/10 overflow-x-auto">
              <Table>
                <TableHeader className="sticky top-0 bg-card/80 backdrop-blur z-10">
                  <TableRow>
                    {tableCols.map(c => <TableHead key={c}>{c.replace(/_/g, " ").replace(/\b\w/g, l => l.toUpperCase())}</TableHead>)}
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {tableRows.map((row, i) => (
                    <TableRow key={i}>
                      {tableCols.map(c => (
                        <TableCell key={c} className="text-sm">
                          {c === "status" ? <StatusBadge status={row[c]} /> :
                           c === "cost" || c === "revenue" ? Number(row[c] || 0).toLocaleString() :
                           c === "auto_renewal" ? (row[c] ? "Yes" : "No") :
                           row[c] ?? ""}
                        </TableCell>
                      ))}
                    </TableRow>
                  ))}
                  {tableRows.length === 0 && <TableRow><TableCell colSpan={tableCols.length} className="text-center text-muted-foreground py-12">No data</TableCell></TableRow>}
                </TableBody>
              </Table>
            </div>
          </Tabs>
        </CardContent>
      </Card>

      <Dialog open={saveOpen} onOpenChange={setSaveOpen}>
        <DialogContent className="glass-strong">
          <DialogHeader><DialogTitle className="font-display">Save Custom Report</DialogTitle></DialogHeader>
          <div>
            <Label>Report Name</Label>
            <Input className="mt-1" value={reportName} onChange={(e) => setReportName(e.target.value)} placeholder="e.g. Q1 Renewal Pipeline" data-testid="custom-report-name-input" />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setSaveOpen(false)}>Cancel</Button>
            <Button onClick={saveReport} className="bg-blue-600 hover:bg-blue-700 text-white" data-testid="confirm-save-report-btn">Save</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
