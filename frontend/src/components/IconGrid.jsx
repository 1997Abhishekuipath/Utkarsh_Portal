import { Link } from "react-router-dom";
import * as Lucide from "lucide-react";

const BADGE_STYLES = {
  hot: "bg-red-500 text-white",
  new: "bg-amber-400 text-black",
};

/**
 * App card grid — 4 cols desktop, 2 cols mobile.
 * Each card has a coloured banner (icon + stat) + white body (title, desc, footer).
 */
export default function IconGrid({ icons = [] }) {
  if (!icons.length) {
    return (
      <div className="bg-[#F1F5F9] border border-dashed border-[#E2E8F0] rounded-xl py-12 text-center text-[#94A3B8] text-sm">
        No apps yet for this pillar.
      </div>
    );
  }

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-3">
      {icons.map(icon => (
        <AppCard key={icon.id} icon={icon} />
      ))}
    </div>
  );
}

function AppCard({ icon }) {
  const Ico = Lucide[icon.lucide_icon] || Lucide.Box;
  const target = icon.route || "#";
  const isExt = target.startsWith("http");
  const Cmp = isExt ? "a" : Link;
  const linkProps = isExt ? { href: target, target: "_blank", rel: "noopener noreferrer" } : { to: target };
  const color = icon.card_color || "#CC0000";

  return (
    <Cmp
      {...linkProps}
      data-testid={`pillar-icon-${icon.id}`}
      className="group block bg-white rounded-xl overflow-hidden border border-[#E2E8F0] hover:shadow-lg hover:-translate-y-0.5 transition-all duration-200 relative"
    >
      {/* Coloured banner */}
      <div
        className="relative px-3 pt-3 pb-2.5 flex items-start justify-between"
        style={{ background: `linear-gradient(135deg, ${color} 0%, ${adjustColor(color, -25)} 100%)` }}
      >
        {/* Icon bubble */}
        <div className="w-8 h-8 rounded-lg bg-white/20 flex items-center justify-center flex-shrink-0">
          <Ico size={16} className="text-white" />
        </div>

        {/* Stat block */}
        {icon.stat_value && (
          <div className="text-right">
            <div className="text-white font-black text-xl leading-none tracking-tight">{icon.stat_value}</div>
            <div className="text-white/70 text-[9px] tracking-widest font-semibold mt-0.5">{icon.stat_label}</div>
          </div>
        )}

        {/* Badge */}
        {icon.badge && BADGE_STYLES[icon.badge] && (
          <span className={`absolute top-1.5 left-1/2 -translate-x-1/2 text-[8px] uppercase tracking-wider font-black px-1.5 py-0.5 rounded-full ${BADGE_STYLES[icon.badge]}`}>
            {icon.badge}
          </span>
        )}
      </div>

      {/* White body */}
      <div className="px-3 pt-2 pb-3">
        <h3 className="text-[12px] font-bold text-[#0F172A] leading-tight mb-1">{icon.name}</h3>
        {icon.description && (
          <p className="text-[10px] text-[#64748B] leading-snug line-clamp-2 mb-2">{icon.description}</p>
        )}

        {/* Footer row */}
        <div className="flex items-center justify-between mt-auto pt-1.5 border-t border-[#F1F5F9]">
          {icon.action_tag ? (
            <span
              className="text-[9px] font-black tracking-wider uppercase flex items-center gap-0.5"
              style={{ color }}
            >
              {icon.action_tag} <Lucide.ArrowUpRight size={9} />
            </span>
          ) : (
            <span />
          )}
          {icon.action_stat && (
            <span className="text-[9px] font-bold text-[#2563EB] tracking-wide">{icon.action_stat}</span>
          )}
        </div>
      </div>
    </Cmp>
  );
}

/** Darken/lighten a hex colour by `amount` (negative = darken). */
function adjustColor(hex, amount) {
  const clamp = (v) => Math.max(0, Math.min(255, v));
  const h = hex.replace('#', '');
  if (h.length !== 6) return hex;
  const r = clamp(parseInt(h.slice(0, 2), 16) + amount);
  const g = clamp(parseInt(h.slice(2, 4), 16) + amount);
  const b = clamp(parseInt(h.slice(4, 6), 16) + amount);
  return `#${r.toString(16).padStart(2, '0')}${g.toString(16).padStart(2, '0')}${b.toString(16).padStart(2, '0')}`;
}
