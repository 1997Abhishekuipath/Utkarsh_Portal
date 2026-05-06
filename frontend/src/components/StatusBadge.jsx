import { Badge } from "../components/ui/badge";

export function StatusBadge({ status }) {
  const map = {
    Active: "status-active",
    Inactive: "status-muted",
    "Expiring Soon": "status-warn",
    Expired: "status-danger",
    Unknown: "status-muted",
  };
  return (
    <Badge
      data-testid={`status-badge-${String(status).toLowerCase().replace(/\s+/g, "-")}`}
      className={`${map[status] || "status-muted"} font-medium px-2.5 py-0.5 rounded-full text-xs`}
      variant="outline"
    >
      {status}
    </Badge>
  );
}
