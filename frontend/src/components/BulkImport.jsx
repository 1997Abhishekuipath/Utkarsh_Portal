import { useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from "./ui/dialog";
import { Button } from "./ui/button";
import { Label } from "./ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./ui/select";
import { Upload, FileText, Download, Loader2 } from "lucide-react";
import api from "../lib/api";
import { toast } from "sonner";

export default function BulkImport({ open, onOpenChange, entity, onDone }) {
  const [file, setFile] = useState(null);
  const [mode, setMode] = useState("upsert");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);

  const handleFile = (e) => {
    const f = e.target.files?.[0];
    if (!f) return;
    if (!f.name.toLowerCase().endsWith(".csv")) {
      toast.error("Please select a CSV file");
      return;
    }
    setFile(f);
    setResult(null);
  };

  const downloadTemplate = async () => {
    const { data } = await api.get(`/templates/${entity}.csv`, { responseType: "blob" });
    const url = URL.createObjectURL(new Blob([data]));
    const a = document.createElement("a");
    a.href = url;
    a.download = `${entity}_template.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const submit = async () => {
    if (!file) return;
    setLoading(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("mode", mode);
      const { data } = await api.post(`/${entity}/bulk-import`, fd, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      setResult(data);
      toast.success(`Imported: ${data.inserted} new, ${data.updated} updated, ${data.skipped} skipped`);
      onDone?.();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Import failed");
    } finally {
      setLoading(false);
    }
  };

  const reset = () => { setFile(null); setResult(null); setMode("upsert"); };

  return (
    <Dialog open={open} onOpenChange={(v) => { if (!v) reset(); onOpenChange(v); }}>
      <DialogContent className="glass-strong max-w-xl">
        <DialogHeader>
          <DialogTitle className="font-display capitalize">Bulk Import {entity}</DialogTitle>
          <DialogDescription>Upload a CSV file to bulk insert or update {entity} records.</DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <Button variant="outline" onClick={downloadTemplate} className="w-full" data-testid="download-template-btn">
            <Download className="h-4 w-4 mr-2" /> Download CSV Template
          </Button>

          <div>
            <Label className="text-xs uppercase tracking-wider">Mode</Label>
            <Select value={mode} onValueChange={setMode}>
              <SelectTrigger className="mt-1.5" data-testid="bulk-mode-select"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="upsert">Upsert (insert new + update existing)</SelectItem>
                <SelectItem value="insert">Insert only (skip existing)</SelectItem>
                <SelectItem value="update">Update only (skip new)</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div>
            <Label className="text-xs uppercase tracking-wider">CSV File</Label>
            <label className="mt-1.5 flex flex-col items-center justify-center border-2 border-dashed border-slate-300/60 dark:border-white/10 rounded-lg p-8 cursor-pointer hover:border-blue-500/50 transition-colors">
              <input type="file" accept=".csv" onChange={handleFile} className="hidden" data-testid="bulk-file-input" />
              {file ? (
                <div className="flex items-center gap-2 text-sm">
                  <FileText className="h-5 w-5 text-blue-600" />
                  <span className="font-medium">{file.name}</span>
                  <span className="text-muted-foreground">({(file.size / 1024).toFixed(1)} KB)</span>
                </div>
              ) : (
                <>
                  <Upload className="h-8 w-8 text-muted-foreground mb-2" />
                  <span className="text-sm text-muted-foreground">Click to upload CSV</span>
                </>
              )}
            </label>
          </div>

          {result && (
            <div className="glass-card p-4 rounded-lg space-y-2 text-sm" data-testid="bulk-result">
              <div className="grid grid-cols-4 gap-2 text-center">
                <div><p className="text-xs text-muted-foreground">Total</p><p className="font-semibold text-lg">{result.total}</p></div>
                <div><p className="text-xs text-muted-foreground">Inserted</p><p className="font-semibold text-lg text-emerald-600">{result.inserted}</p></div>
                <div><p className="text-xs text-muted-foreground">Updated</p><p className="font-semibold text-lg text-blue-600">{result.updated}</p></div>
                <div><p className="text-xs text-muted-foreground">Skipped</p><p className="font-semibold text-lg text-amber-600">{result.skipped}</p></div>
              </div>
              {result.errors && result.errors.length > 0 && (
                <div className="border-t border-slate-200/50 dark:border-white/10 pt-2 mt-2">
                  <p className="text-xs font-semibold text-red-600 mb-1">Errors:</p>
                  <ul className="text-xs space-y-0.5 max-h-32 overflow-y-auto">
                    {result.errors.map((e, i) => <li key={i} className="text-muted-foreground">• {e}</li>)}
                  </ul>
                </div>
              )}
            </div>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>Close</Button>
          <Button onClick={submit} disabled={!file || loading} className="bg-blue-600 hover:bg-blue-700 text-white" data-testid="bulk-submit-btn">
            {loading ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <Upload className="h-4 w-4 mr-2" />}
            Import
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
