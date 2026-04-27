import { useEffect, useState, useRef } from "react";
import { Quote } from "lucide-react";

/**
 * Auto-rotating motivational quotes ribbon. Crossfade between quotes.
 */
export default function QuoteRibbon({ quotes = [] }) {
  const [idx, setIdx] = useState(0);
  const ref = useRef(null);
  useEffect(() => {
    if (quotes.length <= 1) return;
    const t = setInterval(() => setIdx(i => (i + 1) % quotes.length), 8000);
    return () => clearInterval(t);
  }, [quotes.length]);

  if (!quotes.length) return null;
  const q = quotes[idx];

  return (
    <div ref={ref} data-testid="quote-ribbon"
      className="bg-gradient-to-r from-[#0F172A] to-[#1E293B] rounded-xl p-6 flex items-start gap-4 text-white relative overflow-hidden">
      <div className="absolute inset-0 opacity-10"
        style={{ backgroundImage: "radial-gradient(circle at 90% 10%, #CC0000 0%, transparent 60%)" }} />
      <div className="relative z-10 w-10 h-10 rounded-full bg-[#CC0000]/20 flex items-center justify-center flex-shrink-0">
        <Quote size={18} className="text-[#FCA5A5]" />
      </div>
      <div className="relative z-10 flex-1 min-w-0">
        <p key={q.id} className="text-base sm:text-lg font-medium leading-snug animate-[fadeIn_0.4s_ease]">
          "{q.text}"
        </p>
        {q.author && <p className="text-white/60 text-xs mt-2">— {q.author}</p>}
      </div>
    </div>
  );
}
