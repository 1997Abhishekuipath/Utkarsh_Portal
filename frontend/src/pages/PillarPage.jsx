import { useEffect, useState, useCallback } from "react";
import { useParams, Navigate } from "react-router-dom";
import * as Lucide from "lucide-react";
import axios from "axios";
import { useAuth } from "../contexts/AuthContext";
import useLiveContent from "../hooks/useLiveContent";
import TopBar from "../components/TopBar";
import EdmCarousel from "../components/EdmCarousel";
import IconGrid from "../components/IconGrid";

const VALID_SLUGS = ["customer", "innovator", "employee", "shareholder"];

export default function PillarPage() {
  const { slug } = useParams();
  const { authHeader, API } = useAuth();
  const [data, setData]     = useState(null);
  const [error, setError]   = useState("");
  const [loading, setLoad]  = useState(true);

  const refetch = useCallback(() => {
    if (!VALID_SLUGS.includes(slug)) return;
    setLoad(true); setError("");
    axios.get(`${API}/content/pillars/${slug}`, { headers: authHeader() })
      .then(r => { setData(r.data); setLoad(false); })
      .catch(e => { setError(e.response?.data?.detail || e.message); setLoad(false); });
  }, [API, authHeader, slug]);

  useEffect(() => { refetch(); }, [refetch]);

  // Live re-fetch on admin publish
  useLiveContent((evt) => {
    if (evt.scope === "all" || evt.scope === slug) refetch();
  });

  if (!VALID_SLUGS.includes(slug)) return <Navigate to="/" replace />;

  const pillar = data?.pillar;
  const HeroIcon = pillar ? (Lucide[pillar.icon_name] || Lucide.Circle) : Lucide.Circle;

  return (
    <div className="min-h-screen bg-[#F1F5F9]">
      {/* Custom-tinted top bar — switches red→pillar color via background style */}
      <div className="relative" style={pillar ? { background: `linear-gradient(135deg, ${pillar.gradient_from} 0%, ${pillar.gradient_to} 100%)` } : undefined}>
        <TopBar
          crumbs={[{ label: "Home", to: "/" }, { label: pillar?.name || "Pillar" }]}>
          {pillar && (
            <div className="flex items-end gap-5">
              <div className="w-14 h-14 rounded-2xl bg-white/20 backdrop-blur-sm flex items-center justify-center flex-shrink-0">
                <HeroIcon size={28} className="text-white" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="text-[11px] font-bold tracking-widest text-white/70 uppercase">Pillar</div>
                <h1 className="text-4xl sm:text-5xl font-bold text-white tracking-tight font-['Outfit'] leading-tight">{pillar.name}</h1>
                {pillar.tagline && <p className="text-white/80 text-sm sm:text-base mt-2 max-w-2xl">{pillar.tagline}</p>}
              </div>
            </div>
          )}
        </TopBar>
      </div>

      <main className="max-w-7xl mx-auto px-5 py-8 space-y-8">
        {error && (
          <div data-testid="pillar-error"
            className="bg-red-50 border border-red-200 text-red-700 rounded-lg px-4 py-3 text-sm">{error}</div>
        )}

        {loading && (
          <div className="flex items-center justify-center py-20">
            <div className="w-8 h-8 border-2 border-[#CC0000] border-t-transparent rounded-full animate-spin" />
          </div>
        )}

        {!loading && data && (
          <>
            {/* Sub-EDM */}
            {data.edm.length > 0 && (
              <section data-testid="pillar-edm-section">
                <SectionHeader title={`${pillar.name.toUpperCase()} HIGHLIGHTS`} />
                <EdmCarousel slides={data.edm} testid="pillar-edm" />
              </section>
            )}

            {/* 6-col Icon Grid */}
            <section data-testid="pillar-icon-grid-section">
              <SectionHeader title="APPS & TOOLS" subtitle={`${data.icons.length} item${data.icons.length === 1 ? "" : "s"} in this pillar`} />
              <IconGrid icons={data.icons} />
            </section>
          </>
        )}
      </main>
    </div>
  );
}

function SectionHeader({ title, subtitle }) {
  return (
    <div className="mb-4">
      <h2 className="text-[11px] tracking-widest font-bold text-[#475569]">{title}</h2>
      {subtitle && <p className="text-xs text-[#94A3B8] mt-0.5">{subtitle}</p>}
    </div>
  );
}
