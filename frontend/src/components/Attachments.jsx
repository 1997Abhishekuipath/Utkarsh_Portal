import { useEffect, useState } from "react";
import api from "../lib/api";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Upload, FileText, Download, Trash2, Loader2, Paperclip, FileImage, FileSpreadsheet, File as FileIcon } from "lucide-react";
import { toast } from "sonner";
import { useAuth } from "../context/AuthContext";

const iconFor = (ct) => {
  if (!ct) return FileIcon;
  if (ct.startsWith("image/")) return FileImage;
  if (ct.includes("pdf")) return FileText;
  if (ct.includes("sheet") || ct.includes("excel") || ct.includes("csv")) return FileSpreadsheet;
  return FileIcon;
};

export default function Attachments({ entityType, entityId }) {
  const { user } = useAuth();
  const [files, setFiles] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [description, setDescription] = useState("");
  const canWrite = ["admin", "manager"].includes(user?.role);
  const canDelete = canWrite;

  const load = async () => {
    if (!entityId) return;
    const { data } = await api.get(`/attachments/${entityType}/${entityId}`);
    setFiles(data);
  };
  useEffect(() => { load(); /* eslint-disable-next-line */ }, [entityType, entityId]);

  const onUpload = async (e) => {
    const f = e.target.files?.[0];
    if (!f) return;
    if (f.size > 10 * 1024 * 1024) { toast.error("Max 10 MB"); return; }
    setUploading(true);
    try {
      const fd = new FormData();
      fd.append("file", f);
      fd.append("entity_type", entityType);
      fd.append("entity_id", entityId);
      fd.append("description", description);
      await api.post("/attachments/upload", fd, { headers: { "Content-Type": "multipart/form-data" } });
      toast.success("Uploaded");
      setDescription("");
      load();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Upload failed");
    } finally {
      setUploading(false);
      e.target.value = "";
    }
  };

  const onDownload = async (f) => {
    try {
      const res = await api.get(`/attachments/${f.id}/download`, { responseType: "blob" });
      const url = URL.createObjectURL(res.data);
      const a = document.createElement("a");
      a.href = url; a.download = f.filename; a.click();
      URL.revokeObjectURL(url);
    } catch {
      toast.error("Download failed");
    }
  };

  const onDelete = async (id) => {
    if (!window.confirm("Delete this attachment?")) return;
    try {
      await api.delete(`/attachments/${id}`);
      toast.success("Deleted");
      load();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Delete failed");
    }
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 text-sm font-medium">
        <Paperclip className="h-4 w-4 text-blue-600" />
        Attachments ({files.length})
      </div>

      {canWrite && (
        <div className="glass-card rounded-lg p-3 space-y-2">
          <Input
            placeholder="Optional description (e.g. Q1 invoice)"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            className="text-sm h-9"
            data-testid="attachment-desc-input"
          />
          <label className={`flex items-center justify-center gap-2 h-9 rounded-md cursor-pointer text-sm border border-dashed border-slate-300/60 dark:border-white/10 hover:border-blue-500/50 hover:bg-blue-500/5 transition-colors ${uploading ? "pointer-events-none opacity-60" : ""}`}>
            <input
              type="file"
              accept=".pdf,.png,.jpg,.jpeg,.gif,.webp,.doc,.docx,.xls,.xlsx,.txt,.csv,.ppt,.pptx"
              onChange={onUpload}
              className="hidden"
              data-testid="attachment-file-input"
            />
            {uploading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Upload className="h-4 w-4" />}
            {uploading ? "Uploading..." : "Click to upload (PDF/PNG/JPG/DOCX/XLSX up to 10 MB)"}
          </label>
        </div>
      )}

      <div className="space-y-1.5">
        {files.length === 0 && <p className="text-xs text-muted-foreground italic">No attachments yet</p>}
        {files.map(f => {
          const Icon = iconFor(f.content_type);
          return (
            <div key={f.id} className="flex items-center gap-3 p-2.5 rounded-md hover:bg-accent transition-colors" data-testid={`attachment-row-${f.id}`}>
              <Icon className="h-4 w-4 text-blue-600 flex-shrink-0" />
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium truncate">{f.filename}</p>
                <p className="text-[11px] text-muted-foreground">
                  {(f.size / 1024).toFixed(1)} KB • {f.uploaded_by} • {new Date(f.uploaded_at).toLocaleDateString()}
                  {f.description && ` • ${f.description}`}
                </p>
              </div>
              <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => onDownload(f)} data-testid={`download-attachment-${f.id}`}>
                <Download className="h-4 w-4" />
              </Button>
              {canDelete && (
                <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => onDelete(f.id)} data-testid={`delete-attachment-${f.id}`}>
                  <Trash2 className="h-4 w-4 text-red-500" />
                </Button>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
