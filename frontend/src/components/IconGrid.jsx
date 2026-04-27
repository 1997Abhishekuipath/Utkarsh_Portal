import { Link } from "react-router-dom";
import * as Lucide from "lucide-react";

const BADGE_STYLES = {
  hot: "bg-red-100 text-red-700 border-red-200",
  new: "bg-amber-100 text-amber-700 border-amber-200",
};

/**
 * Responsive 6-col icon grid (drops to 3-col / 2-col on smaller screens).
 * Each icon links to icon.route. Uses lucide-react icon by name.
 */
export default function IconGrid({ icons = [] }) {
  if (!icons.length) {
    return (
      <div className="bg-[#F1F5F9] border border-dashed border-[#E2E8F0] rounded-xl py-12 text-center text-[#94A3B8] text-sm">
        No icons yet for this pillar.
      </div>
    );
  }
  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4">
      {icons.map(icon => {
        const Ico = Lucide[icon.lucide_icon] || Lucide.Box;
        const target = icon.route || "#";
        const isExt = target.startsWith("http");
        const Cmp = isExt ? "a" : Link;
        const props = isExt ? { href: target } : { to: target };
        return (
          <Cmp key={icon.id} {...props}
            data-testid={`pillar-icon-${icon.id}`}
            className="group bg-white border border-[#E2E8F0] hover:border-[#CC0000]/40 hover:shadow-md transition-all rounded-xl p-4 flex flex-col items-center text-center relative">
            {icon.badge && BADGE_STYLES[icon.badge] && (
              <span className={`absolute top-2 right-2 text-[9px] uppercase tracking-wider font-bold px-1.5 py-0.5 rounded border ${BADGE_STYLES[icon.badge]}`}>
                {icon.badge}
              </span>
            )}
            <div className="w-12 h-12 rounded-xl bg-[#F8FAFC] group-hover:bg-[#CC0000]/10 flex items-center justify-center mb-3 transition-colors">
              <Ico size={22} className="text-[#475569] group-hover:text-[#CC0000]" />
            </div>
            <div className="text-sm font-semibold text-[#0F172A] mb-1 leading-tight">{icon.name}</div>
            {icon.description && (
              <div className="text-[11px] text-[#64748B] leading-snug line-clamp-2">{icon.description}</div>
            )}
          </Cmp>
        );
      })}
    </div>
  );
}
