import React, { useState, useEffect } from "react";
import { useParams } from "react-router-dom";
import axios from "axios";
import { API } from "../contexts/AuthContext";
import { Star, ArrowRight, CheckCircle2, Loader2, AlertCircle } from "lucide-react";

// NPS Component
const NPSInput = ({ score, onChange }) => (
  <div>
    <div className="flex gap-2 flex-wrap justify-center mb-3">
      {[...Array(11)].map((_, i) => (
        <button key={i} type="button" onClick={() => onChange(i)}
          className={`w-10 h-10 rounded-xl text-sm font-bold border-2 transition-all select-none ${
            score === i
              ? "border-[#CC0000] bg-[#CC0000] text-white scale-110 shadow-md"
              : i <= 6
                ? "border-red-200 bg-red-50 text-red-600 hover:border-red-400"
                : i <= 8
                  ? "border-amber-200 bg-amber-50 text-amber-600 hover:border-amber-400"
                  : "border-emerald-200 bg-emerald-50 text-emerald-600 hover:border-emerald-400"
          }`}>
          {i}
        </button>
      ))}
    </div>
    <div className="flex justify-between text-[11px] text-slate-400 px-1">
      <span>Not at all likely</span><span>Extremely likely</span>
    </div>
  </div>
);

// CSAT Stars Component
const CSATInput = ({ score, onChange }) => (
  <div>
    <div className="flex gap-4 justify-center mb-2">
      {[1,2,3,4,5].map(i => (
        <button key={i} type="button" onClick={() => onChange(i)}
          className={`transition-all hover:scale-125 ${
            i <= (score || 0) ? "text-amber-400" : "text-slate-200"
          }`}>
          <Star size={40} fill={i <= (score||0) ? "currentColor" : "none"} strokeWidth={1.5} />
        </button>
      ))}
    </div>
    <div className="flex justify-between text-[11px] text-slate-400 px-4">
      <span>Very dissatisfied</span><span>Very satisfied</span>
    </div>
  </div>
);

// CES Scale Component
const CESInput = ({ score, onChange }) => {
  const labels = [
    "1 — Strongly Agree",
    "2 — Agree",
    "3 — Somewhat Agree",
    "4 — Neutral",
    "5 — Somewhat Disagree",
    "6 — Disagree",
    "7 — Strongly Disagree",
  ];
  return (
    <div className="space-y-2">
      {labels.map((label, i) => (
        <button key={i} type="button" onClick={() => onChange(i + 1)}
          className={`w-full text-left px-5 py-3 rounded-xl text-sm font-medium border-2 transition-all ${
            score === i + 1
              ? "border-[#CC0000] bg-red-50 text-[#CC0000] font-bold"
              : "border-slate-200 hover:border-slate-300 text-slate-600"
          }`}>
          {label}
        </button>
      ))}
    </div>
  );
};

// Thank You Screen
const ThankYou = ({ message }) => (
  <div className="min-h-screen bg-gradient-to-br from-[#F1F5F9] to-white flex items-center justify-center p-6">
    <div className="bg-white rounded-3xl shadow-xl border border-[#E2E8F0] max-w-md w-full overflow-hidden">
      <div className="bg-[#CC0000] px-8 py-6">
        <div className="text-white text-[11px] font-bold tracking-[0.2em]">HITACHI SYSTEMS INDIA</div>
        <div className="text-red-200 text-[9px] tracking-wider">VOICE OF CUSTOMER</div>
      </div>
      <div className="px-8 py-10 text-center">
        <div className="w-16 h-16 rounded-full bg-emerald-100 flex items-center justify-center mx-auto mb-5">
          <CheckCircle2 size={32} className="text-emerald-600" />
        </div>
        <h2 className="text-xl font-bold text-[#0F172A] mb-3">Response Submitted!</h2>
        <p className="text-[#64748B] text-sm leading-relaxed">
          {message || "Thank you for your valuable feedback! Your insights help us serve you better."}
        </p>
        <div className="mt-6 pt-6 border-t border-[#F1F5F9]">
          <p className="text-[10px] text-[#94A3B8]">© Hitachi Systems India · VoC Intelligence Platform</p>
        </div>
      </div>
    </div>
  </div>
);

// Error Screen
const ErrorScreen = ({ message }) => (
  <div className="min-h-screen bg-gradient-to-br from-[#F1F5F9] to-white flex items-center justify-center p-6">
    <div className="bg-white rounded-3xl shadow-xl border border-[#E2E8F0] max-w-md w-full overflow-hidden">
      <div className="bg-[#CC0000] px-8 py-6">
        <div className="text-white text-[11px] font-bold tracking-[0.2em]">HITACHI SYSTEMS INDIA</div>
        <div className="text-red-200 text-[9px] tracking-wider">VOICE OF CUSTOMER</div>
      </div>
      <div className="px-8 py-10 text-center">
        <div className="w-16 h-16 rounded-full bg-red-50 flex items-center justify-center mx-auto mb-5">
          <AlertCircle size={32} className="text-red-500" />
        </div>
        <h2 className="text-xl font-bold text-[#0F172A] mb-3">Survey Unavailable</h2>
        <p className="text-[#64748B] text-sm leading-relaxed">{message}</p>
        <div className="mt-6 pt-6 border-t border-[#F1F5F9]">
          <p className="text-[10px] text-[#94A3B8]">© Hitachi Systems India</p>
        </div>
      </div>
    </div>
  </div>
);

// Main Public Survey Page
export default function SurveyResponsePage() {
  const { token } = useParams();
  const [survey,    setSurvey]    = useState(null);
  const [loading,   setLoading]   = useState(true);
  const [error,     setError]     = useState(null);
  const [submitted, setSubmitted] = useState(false);
  const [thankMsg,  setThankMsg]  = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState(null);

  // Form state
  const [npsScore,  setNpsScore]  = useState(null);
  const [csatScore, setCsatScore] = useState(null);
  const [cesScore,  setCesScore]  = useState(null);
  const [verbatim,  setVerbatim]  = useState("");

  useEffect(() => {
    if (!token) { setError("Invalid survey link."); setLoading(false); return; }
    axios.get(`${API}/voc/public/survey/${token}`)
      .then(r => setSurvey(r.data))
      .catch(e => {
        const status = e?.response?.status;
        const detail = e?.response?.data?.detail;
        if (status === 410) setError(detail || "This survey link has expired or already been used.");
        else if (status === 404) setError("Survey link not found. Please check the link and try again.");
        else setError("Unable to load survey. Please try again later.");
      })
      .finally(() => setLoading(false));
  }, [token]);

  const handleSubmit = async (e) => {
    e.preventDefault();

    // Validate at least one score
    const type = survey?.survey_type;
    if (type === "nps" && npsScore === null) { setSubmitError("Please select a score."); return; }
    if (type === "csat" && csatScore === null) { setSubmitError("Please rate your satisfaction."); return; }
    if (type === "ces" && cesScore === null) { setSubmitError("Please select an option."); return; }
    if (type === "combined" && npsScore === null && csatScore === null) {
      setSubmitError("Please answer at least one question."); return;
    }

    setSubmitting(true); setSubmitError(null);
    try {
      const r = await axios.post(`${API}/voc/public/survey/${token}`, {
        nps_score:  npsScore,
        csat_score: csatScore,
        ces_score:  cesScore,
        verbatim:   verbatim || null,
      });
      setThankMsg(r.data.thank_you_msg || "");
      setSubmitted(true);
    } catch (e) {
      const status = e?.response?.status;
      if (status === 410) {
        setError(e?.response?.data?.detail || "Survey already submitted.");
      } else {
        setSubmitError(e?.response?.data?.detail || "Submission failed. Please try again.");
      }
    } finally {
      setSubmitting(false);
    }
  };

  if (loading)  return (
    <div className="min-h-screen bg-gradient-to-br from-[#F1F5F9] to-white flex items-center justify-center">
      <Loader2 size={32} className="animate-spin text-[#CC0000]" />
    </div>
  );
  if (error)    return <ErrorScreen message={error} />;
  if (submitted) return <ThankYou message={thankMsg} />;
  if (!survey)  return <ErrorScreen message="Survey not found." />;

  const showNPS  = survey.survey_type === "nps"  || survey.survey_type === "combined";
  const showCSAT = survey.survey_type === "csat" || survey.survey_type === "combined";
  const showCES  = survey.survey_type === "ces"  || survey.survey_type === "combined";

  return (
    <div className="min-h-screen bg-gradient-to-br from-[#F1F5F9] to-white py-8 px-4">
      <div className="max-w-2xl mx-auto">

        {/* Header Card */}
        <div className="bg-white rounded-3xl shadow-xl border border-[#E2E8F0] overflow-hidden mb-0">
          <div className="bg-[#CC0000] px-8 py-6">
            <div className="text-white text-[11px] font-bold tracking-[0.2em] mb-1">HITACHI SYSTEMS INDIA</div>
            <div className="text-red-200 text-[9px] tracking-wider">VOICE OF CUSTOMER · {survey.campaign_name}</div>
          </div>
          <div className="px-8 py-6 border-b border-[#F1F5F9]">
            <div className="text-[10px] font-bold tracking-widest text-[#94A3B8] uppercase mb-1">{survey.account_name}</div>
            <h1 className="text-xl font-bold text-[#0F172A] leading-tight">{survey.title}</h1>
            <p className="text-sm text-[#64748B] mt-1">Your feedback is anonymous and takes less than 2 minutes.</p>
          </div>
        </div>

        {/* Survey Form */}
        <form onSubmit={handleSubmit}
          className="bg-white rounded-b-3xl shadow-xl border border-t-0 border-[#E2E8F0] overflow-hidden">
          <div className="px-8 py-8 space-y-8">

            {/* NPS Question */}
            {showNPS && (
              <div>
                <p className="text-base font-bold text-[#0F172A] mb-5 leading-relaxed">
                  {survey.main_question}
                </p>
                <NPSInput score={npsScore} onChange={setNpsScore} />
                {npsScore !== null && (
                  <p className="mt-3 text-center text-xs font-semibold"
                    style={{ color: npsScore >= 9 ? "#22C55E" : npsScore >= 7 ? "#F59E0B" : "#EF4444" }}>
                    {npsScore >= 9 ? "Promoter — Thank you!" : npsScore >= 7 ? "Passive — We appreciate your feedback." : "Detractor — We'll work to improve."}
                  </p>
                )}
              </div>
            )}

            {/* CSAT Question */}
            {showCSAT && (
              <div>
                <p className="text-base font-bold text-[#0F172A] mb-5 leading-relaxed">
                  {survey.survey_type === "combined"
                    ? "How satisfied are you with our overall service quality?"
                    : survey.main_question}
                </p>
                <CSATInput score={csatScore} onChange={setCsatScore} />
              </div>
            )}

            {/* CES Question */}
            {showCES && (
              <div>
                <p className="text-base font-bold text-[#0F172A] mb-5 leading-relaxed">
                  {survey.survey_type === "combined"
                    ? "HSI made it easy for me to resolve my issues."
                    : survey.main_question}
                </p>
                <CESInput score={cesScore} onChange={setCesScore} />
              </div>
            )}

            {/* Verbatim */}
            {survey.followup_question && (
              <div>
                <label className="block text-base font-bold text-[#0F172A] mb-3">
                  {survey.followup_question}
                </label>
                <textarea value={verbatim} onChange={e => setVerbatim(e.target.value)}
                  rows={4} placeholder="Share your thoughts…"
                  className="w-full px-4 py-3 text-sm border-2 border-[#E2E8F0] rounded-xl focus:border-[#CC0000] focus:outline-none resize-none" />
              </div>
            )}

            {submitError && (
              <p className="text-sm text-red-600 font-semibold">{submitError}</p>
            )}
          </div>

          <div className="px-8 pb-8">
            <button type="submit" disabled={submitting}
              className="w-full flex items-center justify-center gap-3 py-4 rounded-2xl text-sm font-bold text-white bg-[#CC0000] hover:bg-[#AA0000] transition-colors disabled:opacity-60 shadow-lg">
              {submitting
                ? <><Loader2 size={16} className="animate-spin" /> Submitting…</>
                : <>Submit Feedback <ArrowRight size={16} /></>}
            </button>
            <p className="text-center text-[10px] text-[#94A3B8] mt-3">
              Single-use link · Expires {new Date(survey.expires_at).toLocaleString()}
            </p>
          </div>
        </form>
      </div>
    </div>
  );
}
