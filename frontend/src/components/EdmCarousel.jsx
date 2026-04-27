import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ChevronLeft, ChevronRight } from "lucide-react";

/**
 * Auto-rotating EDM carousel.
 * Slides: [{id, title, subtitle, gradient_from, gradient_to, image_url, link}]
 */
export default function EdmCarousel({ slides = [], height = "h-56", testid = "edm-carousel" }) {
  const [idx, setIdx] = useState(0);
  useEffect(() => {
    if (slides.length <= 1) return;
    const t = setInterval(() => setIdx(i => (i + 1) % slides.length), 6000);
    return () => clearInterval(t);
  }, [slides.length]);

  if (!slides.length) {
    return (
      <div data-testid={`${testid}-empty`}
        className={`${height} bg-[#F1F5F9] border border-dashed border-[#E2E8F0] rounded-xl flex items-center justify-center text-[#94A3B8] text-sm`}>
        No content yet — admin can add EDM slides under Admin → Content.
      </div>
    );
  }

  const s = slides[idx];
  const Wrapper = s.link ? Link : "div";
  const props = s.link ? { to: s.link } : {};

  return (
    <div data-testid={testid} className={`relative ${height} rounded-xl overflow-hidden group`}>
      <Wrapper {...props}
        className="absolute inset-0 flex items-end p-7 transition-all"
        style={{ background: `linear-gradient(135deg, ${s.gradient_from} 0%, ${s.gradient_to} 100%)` }}>
        {s.image_url && (
          <img src={s.image_url} alt="" className="absolute inset-0 w-full h-full object-cover opacity-30 mix-blend-overlay" />
        )}
        <div className="absolute inset-0 opacity-10"
          style={{ backgroundImage: "radial-gradient(circle at 80% 20%, white 0%, transparent 50%)" }} />
        <div className="relative z-10 max-w-2xl">
          <h2 className="text-3xl sm:text-4xl font-bold text-white leading-tight tracking-tight">{s.title}</h2>
          {s.subtitle && <p className="text-white/85 text-sm sm:text-base mt-2 max-w-xl">{s.subtitle}</p>}
        </div>
      </Wrapper>

      {slides.length > 1 && (
        <>
          <button onClick={() => setIdx(i => (i - 1 + slides.length) % slides.length)}
            data-testid={`${testid}-prev`}
            className="absolute left-3 top-1/2 -translate-y-1/2 w-9 h-9 rounded-full bg-white/20 hover:bg-white/35 backdrop-blur-sm text-white flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity">
            <ChevronLeft size={18} />
          </button>
          <button onClick={() => setIdx(i => (i + 1) % slides.length)}
            data-testid={`${testid}-next`}
            className="absolute right-3 top-1/2 -translate-y-1/2 w-9 h-9 rounded-full bg-white/20 hover:bg-white/35 backdrop-blur-sm text-white flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity">
            <ChevronRight size={18} />
          </button>
          <div className="absolute bottom-3 right-5 flex gap-1.5">
            {slides.map((_, i) => (
              <button key={i} onClick={() => setIdx(i)}
                aria-label={`Slide ${i + 1}`}
                className={`h-1.5 rounded-full transition-all ${i === idx ? "w-6 bg-white" : "w-1.5 bg-white/40 hover:bg-white/60"}`} />
            ))}
          </div>
        </>
      )}
    </div>
  );
}
