import { useEffect, useState } from "react";
import api from "../lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../components/ui/tabs";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../components/ui/table";
import { Download, FileBarChart2 } from "lucide-react";
import { exportCSV, exportPDF } from "../lib/export";
import { StatusBadge } from "../components/StatusBadge";

const REPORTS = [
  { key: "monthly-expiry", label: "Monthly Expiry", desc: "Licenses expiring within 30 days" },
  { key: "customer-license", label: "Customer Licenses", desc: "All licenses by customer" },
  { key: "vendor", label: "Vendor Report", desc: "Aggregated vendor statistics" },
  { key: "revenue", label: "Revenue Report", desc: "Cost breakdown across licenses" },
  { key: "renewal", label: "Renewal Report", desc: "Licenses requiring renewal" },
  { key: "expired", label: "Expired Licenses", desc: "All expired licenses" },
];

export default function Reports() {
  const [active, setActive] = useState("monthly-expiry");
  const [rows, setRows] = useState([]);

  useEffect(() => {
    api.get(`/reports/${active}`).then(r => setRows(r.data)).catch(() => setRows([]));
  }, [active]);

  const cols = active === "vendor"
    ? ["vendor", "count", "active", "expired", "revenue"]
    : ["license_key", "customer_name", "product_name", "vendor", "license_count", "expiry_date", "cost", "currency", "status"];
  const meta = REPORTS.find(r => r.key === active);

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between flex-wrap gap-4">
        <div>
          <h1 className="font-display text-3xl sm:text-4xl font-bold tracking-tight">Reports</h1>
          <p className="text-sm text-muted-foreground mt-1">Generate and export operational reports</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => exportCSV(active, rows, cols)} data-testid="report-export-csv">
            <Download className="h-4 w-4 mr-2" /> Export CSV
          </Button>
          <Button variant="outline" onClick={() => exportPDF(meta?.label || "Report", rows, cols)} data-testid="report-export-pdf">
            <Download className="h-4 w-4 mr-2" /> Export PDF
          </Button>
        </div>
      </div>

      <Card className="glass-card border-0">
        <CardHeader>
          <CardTitle className="font-display flex items-center gap-2">
            <FileBarChart2 className="h-5 w-5 text-blue-600" />
            {meta?.label}
          </CardTitle>
          <p className="text-xs text-muted-foreground">{meta?.desc}</p>
        </CardHeader>
        <CardContent>
          <Tabs value={active} onValueChange={setActive}>
            <TabsList className="flex-wrap h-auto gap-1 bg-transparent">
              {REPORTS.map(r => (
                <TabsTrigger key={r.key} value={r.key} data-testid={`report-tab-${r.key}`} className="data-[state=active]:bg-blue-600 data-[state=active]:text-white">
                  {r.label}
                </TabsTrigger>
              ))}
            </TabsList>

            {REPORTS.map(r => (
              <TabsContent key={r.key} value={r.key} className="mt-4">
                <div className="rounded-lg overflow-hidden border border-slate-200/60 dark:border-white/10 overflow-x-auto">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        {cols.map(c => <TableHead key={c}>{c.replace(/_/g, " ").replace(/\b\w/g, l => l.toUpperCase())}</TableHead>)}
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {rows.map((row, i) => (
                        <TableRow key={i}>
                          {cols.map(c => (
                            <TableCell key={c}>
                              {c === "status" ? <StatusBadge status={row[c]} /> :
                               c === "cost" || c === "revenue" ? Number(row[c] || 0).toLocaleString() :
                               row[c] ?? ""}
                            </TableCell>
                          ))}
                        </TableRow>
                      ))}
                      {rows.length === 0 && <TableRow><TableCell colSpan={cols.length} className="text-center text-muted-foreground py-8">No data</TableCell></TableRow>}
                    </TableBody>
                  </Table>
                </div>
              </TabsContent>
            ))}
          </Tabs>
        </CardContent>
      </Card>
    </div>
  );
}
