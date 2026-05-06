import Papa from "papaparse";
import jsPDF from "jspdf";
import autoTable from "jspdf-autotable";

export function exportCSV(name, rows, columns) {
  const data = rows.map(r => {
    const o = {};
    columns.forEach(c => { o[c] = r[c] ?? ""; });
    return o;
  });
  const csv = Papa.unparse(data);
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${name}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

export function exportPDF(title, rows, columns) {
  const doc = new jsPDF({ orientation: "landscape" });
  doc.setFontSize(14);
  doc.text(title, 14, 16);
  doc.setFontSize(9);
  doc.text(`Generated: ${new Date().toLocaleString()}`, 14, 22);
  const head = [columns.map(c => c.replace(/_/g, " ").toUpperCase())];
  const body = rows.map(r => columns.map(c => {
    const v = r[c];
    if (v == null) return "";
    if (typeof v === "number") return String(v);
    return String(v);
  }));
  autoTable(doc, {
    head, body, startY: 28,
    styles: { fontSize: 8 },
    headStyles: { fillColor: [37, 99, 235] },
  });
  doc.save(`${title.replace(/\s+/g, "_")}.pdf`);
}
