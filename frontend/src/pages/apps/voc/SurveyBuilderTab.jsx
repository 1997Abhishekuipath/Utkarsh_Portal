import React, { useState, useEffect, useRef } from "react";
import axios from "axios";
import { API } from "../../../contexts/AuthContext";
import {
  Save, Send, Eye, EyeOff, ChevronDown, Plus, CheckCircle2,
  Star, ArrowRight, RefreshCw, Loader2,
} from "lucide-react";

const authHeader = () => ({ Authorization: `Bearer ${localStorage.getItem("hsi_token")}` });

const PRACTICE_TEMPLATES = {
  cybersecurity: {
    nps:  "How likely are you to recommend HSI's Cybersecurity practice to a colleague? (0 = Not at all likely, 10 = Extremely likely)",
    csat: "How satisfied are you with the responsiveness of our Cybersecurity support team?",
    ces:  "How much effort did you have to put in to get your cybersecurity issue resolved?",
    combined: "Based on your experience with HSI Cybersecurity, how likely are you to recommend us? (0–10)",
  },
  cloud: {
    nps:  "How likely are you to recommend HSI Cloud solutions to a peer? (0 = Not at all, 10 = Extremely likely)",
    csat: "How satisfied are you with our Cloud migration support and ongoing management?",
    ces:  "How much effort did you have to put in to manage your cloud infrastructure with HSI's help?",
    combined: "Based on your HSI Cloud experience, how likely are you to recommend us? (0–10)",
  },
  "data-centre": {
    nps:  "Would you recommend HSI Data Centre services to another enterprise? (0–10)",
    csat: "How satisfied are you with our Data Centre infrastructure and support quality?",
    ces:  "How easy was it to get your Data Centre issues resolved by HSI?",
    combined: "Based on your Data Centre experience with HSI, how likely are you to recommend us? (0–10)",
  },
  observability: {
    nps:  "How likely are you to recommend HSI's Observability platform to a colleague? (0–10)",
    csat: "How satisfied are you with the insights and visibility provided by our AIOps platform?",
    ces:  "How much effort do you have to put in to monitor your systems using HSI's observability tools?",
    combined: "Based on your HSI Observability experience, how likely are you to recommend us? (0–10)",
  },
};

const SURVEY_TYPES = [
  { key: "nps",      label: "NPS",      color: "text-red-600",    bg: "bg-red-50",      desc: "Net Promoter Score — 0 to 10 scale" },
  { key: "csat",     label: "CSAT",     color: "text-emerald-600", bg: "bg-emerald-50",  desc: "Customer Satisfaction — 1 to 5 stars" },
  { key: "ces",      label: "CES",      color: "text-blue-600",   bg: "bg-blue-50",     desc: "Customer Effort Score — 1 to 7 scale" },
  { key: "combined", label: "Combined", color: "text-violet-600", bg: "bg-violet-50",   desc: "NPS + CSAT + CES + Open verbatim" },
];

// ── NPS Preview ──────────────────────────────────────────────────────────────
const NPSPreview = ({ question, selectedScore, onSelect }) => (
  <div>
    <p className="text-sm font-semibold text-[#0F172A] mb-5 leading-relaxed">{question}</p>
    <div className="flex gap-1.5 flex-wrap mb-3">
      {[...Array(11)].map((_, i) => (
        <button key={i} onClick={() => onSelect(i)}
          className={`w-9 h-9 rounded-lg text-sm font-bold border-2 transition-all ${
            selectedScore === i
              ? "border-[#CC0000] bg-[#CC0000] text-white"
              : i <= 6 ? "border-red-200 bg-red-50 text-red-600 hover:border-red-400"
              : i <= 8 ? "border-amber-200 bg-amber-50 text-amber-600 hover:border-amber-400"
              : "border-emerald-200 bg-emerald-50 text-emerald-600 hover:border-emerald-400"
          }`}>{i}</button>
      ))}
    </div>
    <div className="flex justify-between text-[10px] text-[#94A3B8]">
      <span>0 — Not at all likely</span><span>10 — Extremely likely</span>
    </div>
  </div>
);

// ── CSAT Stars Preview ───────────────────────────────────────────────────────
const CSATPreview = ({ question, selectedScore, onSelect }) => (
  <div>
    <p className="text-sm font-semibold text-[#0F172A] mb-5 leading-relaxed">{question}</p>
    <div className="flex gap-3 justify-center mb-2">
      {[1, 2, 3, 4, 5].map(i => (
        <button key={i} onClick={() => onSelect(i)}
          className={`transition-transform hover:scale-110 ${ i <= (selectedScore || 0) ? "text-amber-400" : "text-slate-200"}`}>
          <Star size={32} fill={i <= (selectedScore || 0) ? "currentColor" : "none"} strokeWidth={1.5} />
        </button>
      ))}
    </div>
    <div className="flex justify-between text-[10px] text-[#94A3B8] px-2">
      <span>Very dissatisfied</span><span>Very satisfied</span>
    </div>
  </div>
);

// ── CES Scale Preview ────────────────────────────────────────────────────────
const CESPreview = ({ question, selectedScore, onSelect }) => {
  const labels = ["Strongly agree", "Agree", "Somewhat agree", "Neutral", "Somewhat disagree", "Disagree", "Strongly disagree"];
  return (
    <div>
      <p className="text-sm font-semibold text-[#0F172A] mb-5 leading-relaxed">{question}</p>
      <div className="space-y-2">
        {labels.map((l, i) => (
          <button key={i} onClick={() => onSelect(i + 1)}
            className={`w-full text-left px-4 py-2.5 rounded-lg text-sm border-2 transition-all ${
              selectedScore === i + 1
                ? "border-[#CC0000] bg-red-50 text-[#CC0000] font-semibold"
                : "border-[#E2E8F0] hover:border-slate-300 text-[#475569]"
            }`}>{i + 1}. {l}</button>
        ))}
      </div>
    </div>
  );
};

// ── Verbatim Preview ─────────────────────────────────────────────────────────
const VerbatimPreview = ({ question }) => (
  <div className="mt-5">
    <p className="text-sm font-semibold text-[#0F172A] mb-3">{question}</p>
    <textarea rows={3} placeholder="Share your thoughts…" disabled
      className="w-full px-3 py-2.5 text-sm border-2 border-[#E2E8F0] rounded-lg bg-[#F8FAFC] text-[#94A3B8] resize-none" />
  </div>
);

// ── Survey Preview Card ───────────────────────────────────────────────────────
const SurveyPreview = ({ form, selectedScores, onScoreSelect }) => {
  const { survey_type, main_question, followup_question, thank_you_msg } = form;
  return (
    <div className="bg-white rounded-xl border-2 border-[#E2E8F0] overflow-hidden shadow-md">
      <div className="bg-[#CC0000] px-6 py-4">
        <div className="text-white text-[11px] font-bold tracking-[0.2em]">HITACHI SYSTEMS INDIA</div>
        <div className="text-red-200 text-[10px] tracking-wider">VOICE OF CUSTOMER</div>
      </div>
      <div className="px-6 py-6 space-y-5">
        {(!survey_type || survey_type === "nps" || survey_type === "combined") && (
          <NPSPreview
            question={main_question || "How likely are you to recommend us? (0–10)"}
            selectedScore={selectedScores.nps}
            onSelect={(v) => onScoreSelect("nps", v)}
          />
        )}
        {(survey_type === "csat" || survey_type === "combined") && (
          <CSATPreview
            question={survey_type === "combined" ? "How satisfied are you with our service?" : (main_question || "How satisfied are you?")}
            selectedScore={selectedScores.csat}
            onSelect={(v) => onScoreSelect("csat", v)}
          />
        )}
        {(survey_type === "ces" || survey_type === "combined") && (
          <CESPreview
            question={survey_type === "combined" ? "How easy was it to get your issue resolved?" : (main_question || "How easy was it?")}
            selectedScore={selectedScores.ces}
            onSelect={(v) => onScoreSelect("ces", v)}
          />
        )}
        {followup_question && <VerbatimPreview question={followup_question} />}
        <button className="w-full py-3 rounded-lg bg-[#CC0000] text-white text-sm font-bold tracking-wider hover:bg-[#AA0000] transition-colors">
          Submit Feedback <ArrowRight size={14} className="inline ml-1" />
        </button>
        {thank_you_msg && (
          <p className="text-center text-[10px] text-[#94A3B8]">{thank_you_msg}</p>
        )}
      </div>
    </div>
  );
};

// ── Main Component ────────────────────────────────────────────────────────────
export default function SurveyBuilderTab() {
  const [surveys,     setSurveys]     = useState([]);
  const [loadingSurveys, setLoadingSurveys] = useState(true);
  const [showPreview, setShowPreview] = useState(true);
  const [saving,      setSaving]      = useState(false);
  const [savedId,     setSavedId]     = useState(null);
  const [error,       setError]       = useState(null);
  const [selectedScores, setSelectedScores] = useState({ nps: null, csat: null, ces: null });

  const [form, setForm] = useState({
    survey_type:       "combined",
    title:             "Q3 2026 VoC Survey — Combined NPS/CSAT/CES",
    main_question:     "On a scale of 0–10, how likely are you to recommend HSI to a colleague?",
    followup_question: "What is the primary reason for your score?",
    practice:          "",
    thank_you_msg:     "Thank you for your valuable feedback! Your insights help us serve you better.",
  });

  useEffect(() => {
    axios.get(`${API}/voc/surveys`, { headers: authHeader() })
      .then(r => setSurveys(r.data))
      .catch(() => {})
      .finally(() => setLoadingSurveys(false));
  }, [savedId]);

  const applyTemplate = (practice, type) => {
    const t = PRACTICE_TEMPLATES[practice];
    if (t && t[type]) setForm(f => ({ ...f, main_question: t[type] }));
  };

  const handleTypeChange = (type) => {
    setForm(f => ({ ...f, survey_type: type }));
    if (form.practice) applyTemplate(form.practice, type);
  };

  const handlePracticeChange = (practice) => {
    setForm(f => ({ ...f, practice }));
    if (practice) applyTemplate(practice, form.survey_type);
  };

  const handleSave = async () => {
    if (!form.title.trim() || !form.main_question.trim()) {
      setError("Title and main question are required."); return;
    }
    setSaving(true); setError(null);
    try {
      const r = await axios.post(`${API}/voc/surveys`, form, { headers: authHeader() });
      setSavedId(r.data.id);
      setError(null);
    } catch (e) {
      setError(e?.response?.data?.detail || "Failed to save survey");
    } finally {
      setSaving(false);
    }
  };

  return (
    <main className="max-w-screen-2xl mx-auto px-6 py-6">
      <div className="flex items-start justify-between mb-6">
        <div>
          <h2 className="text-2xl font-bold text-[#0F172A] font-['Outfit']">Survey Builder</h2>
          <p className="text-[#64748B] text-sm mt-1">Design surveys with live preview. Supports NPS, CSAT, CES and combined formats.</p>
        </div>
        <div className="flex items-center gap-3">
          <button onClick={() => setShowPreview(p => !p)}
            className="flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-bold border border-[#E2E8F0] text-[#64748B] hover:text-[#0F172A] transition-colors">
            {showPreview ? <EyeOff size={13} /> : <Eye size={13} />}
            {showPreview ? "Hide" : "Show"} Preview
          </button>
          <button onClick={handleSave} disabled={saving}
            className="flex items-center gap-2 px-5 py-2 rounded-lg text-xs font-bold text-white bg-[#CC0000] hover:bg-[#AA0000] transition-colors disabled:opacity-60"
            data-testid="save-survey-btn">
            {saving ? <Loader2 size={13} className="animate-spin" /> : <Save size={13} />}
            {saving ? "Saving…" : "Save Survey"}
          </button>
        </div>
      </div>

      {savedId && (
        <div className="mb-4 flex items-center gap-2 px-4 py-3 bg-emerald-50 border border-emerald-200 rounded-lg text-sm text-emerald-700"
          data-testid="save-survey-success">
          <CheckCircle2 size={16} />
          <span>Survey saved successfully! You can now create a campaign using this survey.</span>
        </div>
      )}
      {error && (
        <div className="mb-4 px-4 py-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-600">{error}</div>
      )}

      <div className="grid grid-cols-12 gap-6">
        {/* ── Form Editor ── */}
        <div className={`${showPreview ? "col-span-6" : "col-span-8"} space-y-5`}>

          {/* Survey Type */}
          <div className="bg-white rounded-xl border border-[#E2E8F0] p-5">
            <div className="text-[10px] font-bold tracking-widest text-[#64748B] uppercase mb-3">Survey Type</div>
            <div className="grid grid-cols-4 gap-2">
              {SURVEY_TYPES.map(t => (
                <button key={t.key} onClick={() => handleTypeChange(t.key)}
                  className={`p-3 rounded-lg border-2 text-center transition-all ${
                    form.survey_type === t.key
                      ? `border-[#CC0000] ${t.bg}`
                      : "border-[#E2E8F0] hover:border-slate-300"
                  }`}>
                  <div className={`text-sm font-bold ${form.survey_type === t.key ? t.color : "text-[#0F172A]"}`}>{t.label}</div>
                  <div className="text-[10px] text-[#64748B] mt-0.5 leading-tight">{t.desc}</div>
                </button>
              ))}
            </div>
          </div>

          {/* Practice Template */}
          <div className="bg-white rounded-xl border border-[#E2E8F0] p-5">
            <div className="text-[10px] font-bold tracking-widest text-[#64748B] uppercase mb-3">Practice Template (optional)</div>
            <div className="flex gap-2 flex-wrap">
              {["", "cybersecurity", "cloud", "data-centre", "observability"].map(p => (
                <button key={p || "all"} onClick={() => handlePracticeChange(p)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-bold border-2 transition-all ${
                    form.practice === p
                      ? "border-[#CC0000] bg-red-50 text-[#CC0000]"
                      : "border-[#E2E8F0] text-[#64748B] hover:border-slate-300"
                  }`}>{p || "All Practices"}</button>
              ))}
            </div>
            {form.practice && (
              <p className="text-[10px] text-[#94A3B8] mt-2">Template applied — question auto-filled. You can edit it below.</p>
            )}
          </div>

          {/* Question Editor */}
          <div className="bg-white rounded-xl border border-[#E2E8F0] p-5 space-y-4">
            <div className="text-[10px] font-bold tracking-widest text-[#64748B] uppercase">Survey Content</div>

            <div>
              <label className="block text-xs font-semibold text-[#475569] mb-1.5">Survey Title *</label>
              <input value={form.title} onChange={e => setForm(f => ({ ...f, title: e.target.value }))}
                className="w-full px-3 py-2.5 text-sm border-2 border-[#E2E8F0] rounded-lg focus:border-[#CC0000] focus:outline-none" />
            </div>

            <div>
              <label className="block text-xs font-semibold text-[#475569] mb-1.5">Main Question *</label>
              <textarea value={form.main_question} rows={3}
                onChange={e => setForm(f => ({ ...f, main_question: e.target.value }))}
                className="w-full px-3 py-2.5 text-sm border-2 border-[#E2E8F0] rounded-lg focus:border-[#CC0000] focus:outline-none resize-none" />
            </div>

            <div>
              <label className="block text-xs font-semibold text-[#475569] mb-1.5">Follow-up / Verbatim Question</label>
              <input value={form.followup_question || ""}
                onChange={e => setForm(f => ({ ...f, followup_question: e.target.value }))}
                placeholder="What is the primary reason for your score?"
                className="w-full px-3 py-2.5 text-sm border-2 border-[#E2E8F0] rounded-lg focus:border-[#CC0000] focus:outline-none" />
            </div>

            <div>
              <label className="block text-xs font-semibold text-[#475569] mb-1.5">Thank-you Message</label>
              <input value={form.thank_you_msg || ""}
                onChange={e => setForm(f => ({ ...f, thank_you_msg: e.target.value }))}
                placeholder="Thank you for your feedback!"
                className="w-full px-3 py-2.5 text-sm border-2 border-[#E2E8F0] rounded-lg focus:border-[#CC0000] focus:outline-none" />
            </div>
          </div>

          {/* Saved surveys */}
          <div className="bg-white rounded-xl border border-[#E2E8F0] p-5">
            <div className="flex items-center justify-between mb-3">
              <div className="text-[10px] font-bold tracking-widest text-[#64748B] uppercase">Saved Surveys</div>
              {loadingSurveys && <Loader2 size={13} className="animate-spin text-[#94A3B8]" />}
            </div>
            {surveys.length === 0 && !loadingSurveys ? (
              <p className="text-sm text-[#94A3B8]">No surveys yet. Create your first one above.</p>
            ) : (
              <div className="space-y-2">
                {surveys.map(s => (
                  <div key={s.id} onClick={() => setForm({
                    survey_type: s.survey_type, title: s.title,
                    main_question: s.main_question,
                    followup_question: s.followup_question || "",
                    practice: s.practice || "",
                    thank_you_msg: s.thank_you_msg || "",
                  })}
                    className="flex items-center gap-3 p-3 rounded-lg border border-[#E2E8F0] cursor-pointer hover:border-[#CC0000]/30 hover:bg-[#FEF2F2] transition-all">
                    <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                      s.survey_type === "nps" ? "bg-red-50 text-red-600"
                      : s.survey_type === "csat" ? "bg-emerald-50 text-emerald-600"
                      : s.survey_type === "ces" ? "bg-blue-50 text-blue-600"
                      : "bg-violet-50 text-violet-600"
                    }`}>{s.survey_type.toUpperCase()}</span>
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-semibold text-[#0F172A] truncate">{s.title}</div>
                      <div className="text-[10px] text-[#94A3B8]">v{s.version} · {new Date(s.created_at).toLocaleDateString()}</div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* ── Live Preview ── */}
        {showPreview && (
          <div className="col-span-6">
            <div className="sticky top-4">
              <div className="flex items-center gap-2 mb-3">
                <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                <span className="text-[10px] font-bold tracking-widest text-[#64748B] uppercase">Live Preview</span>
              </div>
              <SurveyPreview
                form={form}
                selectedScores={selectedScores}
                onScoreSelect={(type, val) => setSelectedScores(s => ({ ...s, [type]: val }))}
              />
            </div>
          </div>
        )}
      </div>
    </main>
  );
}
