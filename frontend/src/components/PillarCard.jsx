import { Link } from "react-router-dom";
import * as Lucide from "lucide-react";
import { ArrowRight } from "lucide-react";

/**
 * One pillar card. Used 4-up on the home page.
 * pillar = {id, slug, name, tagline, gradient_from, gradient_to, icon_name}
 */
export default function PillarCard({ pillar }) {
  const Icon = Lucide[pillar.icon_name] || Lucide.Circle;
  return (
    <Link
      to={`/pillar/${pillar.slug}`}
      data-testid={`pillar-card-${pillar.slug}`}
      className="group relative overflow-hidden rounded-2xl p-6 text-white block transition-transform hover:-translate-y-0.5"
      style={{ background: `linear-gradient(135deg, ${pillar.gradient_from} 0%, ${pillar.gradient_to} 100%)` }}>
      <div className="absolute inset-0 opacity-10"
        style={{ backgroundImage: "radial-gradient(circle at 80% 20%, white 0%, transparent 50%)" }} />
      <div className="relative z-10">
        <div className="w-11 h-11 rounded-xl bg-white/20 backdrop-blur-sm flex items-center justify-center mb-4">
          <Icon size={22} className="text-white" />
        </div>
        <div className="text-[11px] font-semibold tracking-widest text-white/70 uppercase mb-1">Pillar</div>
        <h3 className="text-2xl font-bold leading-tight mb-1.5">{pillar.name}</h3>
        {pillar.tagline && <p className="text-white/80 text-sm leading-relaxed">{pillar.tagline}</p>}
        <div className="flex items-center gap-1.5 mt-5 text-sm font-medium opacity-80 group-hover:opacity-100 group-hover:translate-x-1 transition-all">
          <span>Explore</span> <ArrowRight size={14} />
        </div>
      </div>
    </Link>
  );
}
