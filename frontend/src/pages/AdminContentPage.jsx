import { useState, useEffect, useCallback } from "react";
import { Link, useNavigate } from "react-router-dom";
import axios from "axios";
import { useAuth } from "../contexts/AuthContext";
import {
  Building2, ArrowLeft, LogOut, Users, Layers, Pencil, Trash2, Plus,
  Save, X, Send, Image as ImageIcon, Quote, Tag, FileText
} from "lucide-react";

const SCOPES   = ["home", "customer", "innovator", "employee", "shareholder"];
const PILLARS  = ["customer", "innovator", "employee", "shareholder"];

export default function AdminContentPage() {
  const { user, logout, authHeader, API } = useAuth();
  const navigate = useNavigate();

  const [tab, setTab]               = useState("pillars");   // pillars | icons | edm | quotes
  const [pillars, setPillars]       = useState([]);
  const [icons, setIcons]           = useState([]);
  const [slides, setSlides]         = useState([]);
  const [quotes, setQuotes]         = useState([]);
  const [iconPillarFilter, setIconPillarFilter] = useState("");
  const [edmScopeFilter, setEdmScopeFilter]     = useState("");
  const [publishing, setPublishing] = useState(false);
  const [toast, setToast]           = useState("");

  const headers = useCallback(() => authHeader(), [authHeader]);

  const fetchAll = useCallback(() => {
    const h = headers();
    Promise.all([
      axios.get(`${API}/admin/pillars`, { headers: h }),
      axios.get(`${API}/admin/pillar-icons`, { headers: h }),
      axios.get(`${API}/admin/edm-slides`, { headers: h }),
      axios.get(`${API}/admin/quotes`, { headers: h }),
    ]).then(([p, i, e, q]) => {
      setPillars(p.data); setIcons(i.data); setSlides(e.data); setQuotes(q.data);
    }).catch(() => {});
  }, [API, headers]);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  const showToast = (msg) => { setToast(msg); setTimeout(() => setToast(""), 2500); };

  const publish = async (scope = "all") => {
    if (!window.confirm(`Publish ${scope === "all" ? "ALL content" : scope} to live? Connected clients will refresh within 5s.`)) return;
    setPublishing(true);
    try {
      const r = await axios.post(`${API}/admin/publish`, { scope }, { headers: headers() });
      showToast(`Published — ${r.data.subscribers_notified} client(s) notified`);
    } catch (e) {
      showToast(e.response?.data?.detail || e.message);
    } finally { setPublishing(false); }
  };

  return (
    <div className="min-h-screen bg-[#F1F5F9]">
      {/* Header */}
      <div className="bg-[#CC0000]">
        <div className="max-w-7xl mx-auto px-5 py-3 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-3">
            <div className="w-8 h-8 bg-white/20 rounded-lg flex items-center justify-center">
              <Building2 size={16} className="text-white" />
            </div>
            <div>
              <div className="text-white font-semibold text-xs tracking-wider">HITACHI SYSTEMS INDIA</div>
              <div className="text-white/50 text-[9px] tracking-widest">CONTENT MANAGEMENT</div>
            </div>
          </Link>
          <div className="flex items-center gap-2">
            <button onClick={() => publish("all")} disabled={publishing}
              data-testid="publish-all-button"
              className="flex items-center gap-1.5 bg-white text-[#CC0000] hover:bg-gray-50 disabled:opacity-60 px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors">
              <Send size={13} /><span>{publishing ? "Publishing…" : "Publish All"}</span>
            </button>
            <Link to="/admin" className="flex items-center gap-1.5 text-white/80 hover:text-white text-xs bg-white/10 hover:bg-white/20 px-3 py-1.5 rounded-lg">
              <Users size={13} /><span>Users</span>
            </Link>
            <Link to="/" className="flex items-center gap-1.5 text-white/80 hover:text-white text-xs bg-white/10 hover:bg-white/20 px-3 py-1.5 rounded-lg">
              <ArrowLeft size={13} /><span>Home</span>
            </Link>
            <button onClick={() => { logout(); navigate("/login"); }}
              className="flex items-center gap-1.5 text-white/80 hover:text-white text-xs bg-white/10 hover:bg-white/20 px-3 py-1.5 rounded-lg">
              <LogOut size={13} /><span>Sign Out</span>
            </button>
          </div>
        </div>
      </div>

      <main className="max-w-7xl mx-auto px-5 py-6">
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-[#0F172A] font-['Outfit'] flex items-center gap-2">
            <Layers size={22} className="text-[#CC0000]" />Content Management
          </h1>
          <p className="text-[#475569] text-sm mt-1">Pillars, app icons, EDM slides and motivational quotes — published live to all users.</p>
        </div>

        {/* Tabs */}
        <div className="flex gap-1 mb-5 border-b border-[#E2E8F0]">
          {[
            ["pillars", "Pillars",  Layers,   pillars.length],
            ["icons",   "Icons",    Tag,      icons.length],
            ["edm",     "EDM",      ImageIcon,slides.length],
            ["quotes",  "Quotes",   Quote,    quotes.length],
          ].map(([k, label, Icon, n]) => (
            <button key={k} onClick={() => setTab(k)} data-testid={`tab-${k}`}
              className={`flex items-center gap-2 px-4 py-2.5 text-xs font-semibold border-b-2 transition-colors ${tab === k ? "border-[#CC0000] text-[#CC0000]" : "border-transparent text-[#475569] hover:text-[#0F172A]"}`}>
              <Icon size={14} /><span>{label}</span>
              <span className="bg-[#F1F5F9] text-[#475569] rounded-full px-1.5 py-0.5 text-[10px] tabular-nums">{n}</span>
            </button>
          ))}
        </div>

        {tab === "pillars" && (
          <PillarManager pillars={pillars} api={API} headers={headers} reload={fetchAll}
            onPublish={publish} onToast={showToast} />
        )}
        {tab === "icons" && (
          <IconManager icons={icons} pillars={pillars} pillarFilter={iconPillarFilter}
            setPillarFilter={setIconPillarFilter} api={API} headers={headers} reload={fetchAll}
            onPublish={publish} onToast={showToast} />
        )}
        {tab === "edm" && (
          <EdmManager slides={slides} scopeFilter={edmScopeFilter} setScopeFilter={setEdmScopeFilter}
            api={API} headers={headers} reload={fetchAll} onPublish={publish} onToast={showToast} />
        )}
        {tab === "quotes" && (
          <QuoteManager quotes={quotes} api={API} headers={headers} reload={fetchAll}
            onPublish={publish} onToast={showToast} />
        )}
      </main>

      {toast && (
        <div data-testid="toast" className="fixed bottom-6 right-6 bg-[#0F172A] text-white text-sm px-4 py-2.5 rounded-lg shadow-lg animate-fade-in">
          {toast}
        </div>
      )}
    </div>
  );
}

/* ─────────────────── Pillar manager ─────────────────── */
function PillarManager({ pillars, api, headers, reload, onPublish, onToast }) {
  const [editing, setEditing] = useState(null);   // pillar object or 'new' for create
  const blank = { slug: "", name: "", tagline: "", gradient_from: "#CC0000", gradient_to: "#7A0000",
                  icon_name: "Heart", position: 0, is_published: true };

  const save = async (form) => {
    try {
      if (editing === "new") {
        await axios.post(`${api}/admin/pillars`, form, { headers: headers() });
        onToast("Pillar created");
      } else {
        await axios.put(`${api}/admin/pillars/${editing.id}`, form, { headers: headers() });
        onToast("Pillar updated");
      }
      setEditing(null); reload();
    } catch (e) { onToast(e.response?.data?.detail || e.message); }
  };

  const remove = async (p) => {
    if (!window.confirm(`Delete pillar "${p.name}"? All its icons will also be deleted.`)) return;
    try { await axios.delete(`${api}/admin/pillars/${p.id}`, { headers: headers() }); reload(); onToast("Deleted"); }
    catch (e) { onToast(e.response?.data?.detail || e.message); }
  };

  return (
    <div>
      <Toolbar onAdd={() => setEditing("new")} onPublish={() => onPublish("all")} addLabel="Add pillar" />
      {editing === "new" && <PillarForm initial={blank} onSave={save} onCancel={() => setEditing(null)} />}
      <div className="grid sm:grid-cols-2 gap-3 mt-2">
        {pillars.map(p => editing?.id === p.id ? (
          <PillarForm key={p.id} initial={p} onSave={save} onCancel={() => setEditing(null)} />
        ) : (
          <div key={p.id} className="bg-white rounded-lg border border-[#E2E8F0] p-4">
            <div className="flex items-start justify-between gap-3">
              <div className="flex items-center gap-3 min-w-0">
                <div className="w-10 h-10 rounded-lg flex-shrink-0"
                  style={{ background: `linear-gradient(135deg, ${p.gradient_from}, ${p.gradient_to})` }} />
                <div className="min-w-0">
                  <div className="font-semibold text-[#0F172A] truncate">{p.name}</div>
                  <div className="text-xs text-[#64748B] truncate">/{p.slug} · pos {p.position}</div>
                </div>
              </div>
              <div className="flex gap-1 flex-shrink-0">
                <button onClick={() => setEditing(p)} className="p-1.5 text-[#475569] hover:text-[#CC0000] hover:bg-red-50 rounded"><Pencil size={14} /></button>
                <button onClick={() => remove(p)} className="p-1.5 text-[#475569] hover:text-red-600 hover:bg-red-50 rounded"><Trash2 size={14} /></button>
              </div>
            </div>
            {p.tagline && <p className="text-xs text-[#64748B] mt-2 leading-snug">{p.tagline}</p>}
            {!p.is_published && <span className="mt-2 inline-block text-[10px] px-1.5 py-0.5 bg-amber-100 text-amber-700 rounded">DRAFT</span>}
          </div>
        ))}
      </div>
    </div>
  );
}

function PillarForm({ initial, onSave, onCancel }) {
  const [f, setF] = useState(initial);
  const set = k => e => setF(p => ({ ...p, [k]: e.target.value }));
  return (
    <form onSubmit={e => { e.preventDefault(); onSave(f); }}
      className="bg-amber-50 border border-amber-200 rounded-lg p-4 space-y-2">
      <div className="grid grid-cols-2 gap-2">
        <Field label="Slug">
          <select value={f.slug} onChange={set("slug")} required
            className="w-full px-3 py-1.5 border border-[#E2E8F0] rounded text-sm bg-white">
            <option value="">— choose —</option>
            {PILLARS.map(s => <option key={s} value={s}>{s}</option>)}
          </select>
        </Field>
        <Field label="Name"><TextI value={f.name} onChange={set("name")} required /></Field>
        <Field label="Position"><TextI type="number" value={f.position} onChange={set("position")} /></Field>
        <Field label="Icon (lucide name)"><TextI value={f.icon_name || ""} onChange={set("icon_name")} placeholder="Heart, Lightbulb, Users…" /></Field>
        <Field label="Gradient from"><TextI value={f.gradient_from} onChange={set("gradient_from")} /></Field>
        <Field label="Gradient to"><TextI value={f.gradient_to} onChange={set("gradient_to")} /></Field>
        <Field label="Tagline" full>
          <TextI value={f.tagline || ""} onChange={set("tagline")} />
        </Field>
      </div>
      <PublishToggle value={f.is_published} onChange={v => setF(p => ({ ...p, is_published: v }))} />
      <FormActions onCancel={onCancel} />
    </form>
  );
}

/* ─────────────────── Icon manager ─────────────────── */
function IconManager({ icons, pillars, pillarFilter, setPillarFilter, api, headers, reload, onPublish, onToast }) {
  const [editing, setEditing] = useState(null);
  const blank = { pillar_id: pillars[0]?.id || "", name: "", description: "", lucide_icon: "Box",
                  route: "", badge: null, position: 0, is_published: true };

  const save = async (form) => {
    try {
      if (editing === "new") {
        await axios.post(`${api}/admin/pillar-icons`, form, { headers: headers() });
        onToast("Icon created");
      } else {
        await axios.put(`${api}/admin/pillar-icons/${editing.id}`, form, { headers: headers() });
        onToast("Icon updated");
      }
      setEditing(null); reload();
    } catch (e) { onToast(e.response?.data?.detail || e.message); }
  };
  const remove = async (i) => {
    if (!window.confirm(`Delete icon "${i.name}"?`)) return;
    try { await axios.delete(`${api}/admin/pillar-icons/${i.id}`, { headers: headers() }); reload(); onToast("Deleted"); }
    catch (e) { onToast(e.response?.data?.detail || e.message); }
  };

  const filtered = pillarFilter ? icons.filter(i => i.pillar_id === pillarFilter) : icons;
  const pillarById = Object.fromEntries(pillars.map(p => [p.id, p]));

  return (
    <div>
      <Toolbar onAdd={() => setEditing("new")} onPublish={() => onPublish("all")} addLabel="Add icon">
        <select value={pillarFilter} onChange={e => setPillarFilter(e.target.value)}
          className="px-3 py-1.5 border border-[#E2E8F0] rounded text-xs bg-white">
          <option value="">All pillars</option>
          {pillars.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
        </select>
      </Toolbar>
      {editing === "new" && <IconForm initial={blank} pillars={pillars} onSave={save} onCancel={() => setEditing(null)} />}
      <table className="w-full bg-white border border-[#E2E8F0] rounded-lg overflow-hidden mt-2 text-sm">
        <thead className="bg-[#F8FAFC]">
          <tr>
            {["Pillar", "Name", "Route", "Badge", "Pos", "Published", ""].map(h =>
              <th key={h} className="text-left text-[10px] font-bold text-[#64748B] uppercase tracking-wider px-3 py-2">{h}</th>)}
          </tr>
        </thead>
        <tbody>
          {filtered.map(i => editing?.id === i.id ? (
            <tr key={i.id}><td colSpan={7} className="p-2 bg-amber-50">
              <IconForm initial={i} pillars={pillars} onSave={save} onCancel={() => setEditing(null)} />
            </td></tr>
          ) : (
            <tr key={i.id} className="border-t border-[#F1F5F9]">
              <td className="px-3 py-2 text-xs text-[#475569]">{pillarById[i.pillar_id]?.name || "—"}</td>
              <td className="px-3 py-2"><div className="font-medium text-[#0F172A]">{i.name}</div>
                {i.description && <div className="text-[10px] text-[#94A3B8] truncate max-w-md">{i.description}</div>}</td>
              <td className="px-3 py-2 text-xs text-[#64748B] font-mono">{i.route || "—"}</td>
              <td className="px-3 py-2"><Badge value={i.badge} /></td>
              <td className="px-3 py-2 text-xs tabular-nums">{i.position}</td>
              <td className="px-3 py-2"><PubDot v={i.is_published} /></td>
              <td className="px-3 py-2 text-right">
                <button onClick={() => setEditing(i)} className="p-1 text-[#475569] hover:text-[#CC0000]"><Pencil size={13} /></button>
                <button onClick={() => remove(i)} className="p-1 text-[#475569] hover:text-red-600"><Trash2 size={13} /></button>
              </td>
            </tr>
          ))}
          {filtered.length === 0 && <tr><td colSpan={7} className="text-center py-8 text-[#94A3B8] text-sm">No icons</td></tr>}
        </tbody>
      </table>
    </div>
  );
}

function IconForm({ initial, pillars, onSave, onCancel }) {
  const [f, setF] = useState(initial);
  const set = k => e => setF(p => ({ ...p, [k]: e.target.value === "" && k === "badge" ? null : e.target.value }));
  return (
    <form onSubmit={e => { e.preventDefault(); onSave(f); }} className="space-y-2">
      <div className="grid grid-cols-3 gap-2">
        <Field label="Pillar">
          <select value={f.pillar_id} onChange={set("pillar_id")} required
            className="w-full px-2 py-1.5 border border-[#E2E8F0] rounded text-sm bg-white">
            {pillars.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
          </select>
        </Field>
        <Field label="Name"><TextI value={f.name} onChange={set("name")} required /></Field>
        <Field label="Lucide icon"><TextI value={f.lucide_icon || ""} onChange={set("lucide_icon")} placeholder="Heart, Box, Award…" /></Field>
        <Field label="Route"><TextI value={f.route || ""} onChange={set("route")} placeholder="/apps/best-practices" /></Field>
        <Field label="Position"><TextI type="number" value={f.position} onChange={set("position")} /></Field>
        <Field label="Badge">
          <select value={f.badge || ""} onChange={set("badge")}
            className="w-full px-2 py-1.5 border border-[#E2E8F0] rounded text-sm bg-white">
            <option value="">none</option><option value="hot">hot</option><option value="new">new</option>
          </select>
        </Field>
        <Field label="Description" full><TextI value={f.description || ""} onChange={set("description")} /></Field>
      </div>
      <PublishToggle value={f.is_published} onChange={v => setF(p => ({ ...p, is_published: v }))} />
      <FormActions onCancel={onCancel} />
    </form>
  );
}

/* ─────────────────── EDM manager ─────────────────── */
function EdmManager({ slides, scopeFilter, setScopeFilter, api, headers, reload, onPublish, onToast }) {
  const [editing, setEditing] = useState(null);
  const blank = { scope: "home", title: "", subtitle: "", gradient_from: "#CC0000",
                  gradient_to: "#7A0000", image_url: "", link: "", position: 0, is_published: true };

  const save = async (form) => {
    try {
      if (editing === "new") {
        await axios.post(`${api}/admin/edm-slides`, form, { headers: headers() });
        onToast("Slide created");
      } else {
        await axios.put(`${api}/admin/edm-slides/${editing.id}`, form, { headers: headers() });
        onToast("Slide updated");
      }
      setEditing(null); reload();
    } catch (e) { onToast(e.response?.data?.detail || e.message); }
  };
  const remove = async (s) => {
    if (!window.confirm(`Delete slide "${s.title}"?`)) return;
    try { await axios.delete(`${api}/admin/edm-slides/${s.id}`, { headers: headers() }); reload(); onToast("Deleted"); }
    catch (e) { onToast(e.response?.data?.detail || e.message); }
  };
  const filtered = scopeFilter ? slides.filter(s => s.scope === scopeFilter) : slides;

  return (
    <div>
      <Toolbar onAdd={() => setEditing("new")} onPublish={() => onPublish(scopeFilter || "all")} addLabel="Add slide">
        <select value={scopeFilter} onChange={e => setScopeFilter(e.target.value)}
          className="px-3 py-1.5 border border-[#E2E8F0] rounded text-xs bg-white">
          <option value="">All scopes</option>
          {SCOPES.map(s => <option key={s} value={s}>{s}</option>)}
        </select>
      </Toolbar>
      {editing === "new" && <EdmForm initial={blank} onSave={save} onCancel={() => setEditing(null)} />}
      <div className="space-y-2 mt-2">
        {filtered.map(s => editing?.id === s.id ? (
          <div key={s.id} className="bg-amber-50 border border-amber-200 rounded-lg p-3">
            <EdmForm initial={s} onSave={save} onCancel={() => setEditing(null)} />
          </div>
        ) : (
          <div key={s.id} className="bg-white border border-[#E2E8F0] rounded-lg overflow-hidden flex">
            <div className="w-2 flex-shrink-0" style={{ background: `linear-gradient(180deg, ${s.gradient_from}, ${s.gradient_to})` }} />
            <div className="flex-1 px-4 py-3 min-w-0">
              <div className="flex items-center gap-2">
                <span className="text-[10px] uppercase tracking-wider font-bold text-[#94A3B8]">{s.scope}</span>
                <PubDot v={s.is_published} />
                <span className="text-[10px] tabular-nums text-[#94A3B8]">pos {s.position}</span>
              </div>
              <div className="font-semibold text-[#0F172A] mt-1">{s.title}</div>
              {s.subtitle && <div className="text-xs text-[#64748B] line-clamp-1">{s.subtitle}</div>}
              {s.link && <div className="text-[10px] text-[#94A3B8] font-mono mt-0.5">→ {s.link}</div>}
            </div>
            <div className="flex items-center gap-1 px-3">
              <button onClick={() => setEditing(s)} className="p-1.5 text-[#475569] hover:text-[#CC0000]"><Pencil size={14} /></button>
              <button onClick={() => remove(s)} className="p-1.5 text-[#475569] hover:text-red-600"><Trash2 size={14} /></button>
            </div>
          </div>
        ))}
        {filtered.length === 0 && <div className="text-center py-8 text-[#94A3B8] text-sm">No slides</div>}
      </div>
    </div>
  );
}

function EdmForm({ initial, onSave, onCancel }) {
  const [f, setF] = useState(initial);
  const set = k => e => setF(p => ({ ...p, [k]: e.target.value }));
  return (
    <form onSubmit={e => { e.preventDefault(); onSave(f); }} className="space-y-2">
      <div className="grid grid-cols-3 gap-2">
        <Field label="Scope">
          <select value={f.scope} onChange={set("scope")} required
            className="w-full px-2 py-1.5 border border-[#E2E8F0] rounded text-sm bg-white">
            {SCOPES.map(s => <option key={s} value={s}>{s}</option>)}
          </select>
        </Field>
        <Field label="Title"><TextI value={f.title} onChange={set("title")} required /></Field>
        <Field label="Position"><TextI type="number" value={f.position} onChange={set("position")} /></Field>
        <Field label="Subtitle" full><TextI value={f.subtitle || ""} onChange={set("subtitle")} /></Field>
        <Field label="Gradient from"><TextI value={f.gradient_from} onChange={set("gradient_from")} /></Field>
        <Field label="Gradient to"><TextI value={f.gradient_to} onChange={set("gradient_to")} /></Field>
        <Field label="Link / route"><TextI value={f.link || ""} onChange={set("link")} placeholder="/apps/…" /></Field>
        <Field label="Image URL" full><TextI value={f.image_url || ""} onChange={set("image_url")} placeholder="optional" /></Field>
      </div>
      <PublishToggle value={f.is_published} onChange={v => setF(p => ({ ...p, is_published: v }))} />
      <FormActions onCancel={onCancel} />
    </form>
  );
}

/* ─────────────────── Quote manager ─────────────────── */
function QuoteManager({ quotes, api, headers, reload, onPublish, onToast }) {
  const [editing, setEditing] = useState(null);
  const blank = { text: "", author: "", position: 0, is_published: true };

  const save = async (form) => {
    try {
      if (editing === "new") {
        await axios.post(`${api}/admin/quotes`, form, { headers: headers() });
        onToast("Quote created");
      } else {
        await axios.put(`${api}/admin/quotes/${editing.id}`, form, { headers: headers() });
        onToast("Quote updated");
      }
      setEditing(null); reload();
    } catch (e) { onToast(e.response?.data?.detail || e.message); }
  };
  const remove = async (q) => {
    if (!window.confirm("Delete quote?")) return;
    try { await axios.delete(`${api}/admin/quotes/${q.id}`, { headers: headers() }); reload(); onToast("Deleted"); }
    catch (e) { onToast(e.response?.data?.detail || e.message); }
  };
  return (
    <div>
      <Toolbar onAdd={() => setEditing("new")} onPublish={() => onPublish("all")} addLabel="Add quote" />
      {editing === "new" && <QuoteForm initial={blank} onSave={save} onCancel={() => setEditing(null)} />}
      <div className="space-y-2 mt-2">
        {quotes.map(q => editing?.id === q.id ? (
          <div key={q.id} className="bg-amber-50 border border-amber-200 rounded-lg p-3">
            <QuoteForm initial={q} onSave={save} onCancel={() => setEditing(null)} />
          </div>
        ) : (
          <div key={q.id} className="bg-white border border-[#E2E8F0] rounded-lg p-4 flex items-start gap-3">
            <FileText size={16} className="text-[#94A3B8] flex-shrink-0 mt-0.5" />
            <div className="flex-1 min-w-0">
              <p className="text-[#0F172A] text-sm">"{q.text}"</p>
              {q.author && <p className="text-xs text-[#64748B] mt-1">— {q.author}</p>}
              <div className="flex items-center gap-2 mt-1">
                <PubDot v={q.is_published} />
                <span className="text-[10px] tabular-nums text-[#94A3B8]">pos {q.position}</span>
              </div>
            </div>
            <div className="flex gap-1">
              <button onClick={() => setEditing(q)} className="p-1.5 text-[#475569] hover:text-[#CC0000]"><Pencil size={14} /></button>
              <button onClick={() => remove(q)} className="p-1.5 text-[#475569] hover:text-red-600"><Trash2 size={14} /></button>
            </div>
          </div>
        ))}
        {quotes.length === 0 && <div className="text-center py-8 text-[#94A3B8] text-sm">No quotes</div>}
      </div>
    </div>
  );
}

function QuoteForm({ initial, onSave, onCancel }) {
  const [f, setF] = useState(initial);
  const set = k => e => setF(p => ({ ...p, [k]: e.target.value }));
  return (
    <form onSubmit={e => { e.preventDefault(); onSave(f); }} className="space-y-2">
      <Field label="Text" full>
        <textarea value={f.text} onChange={set("text")} required rows={2}
          className="w-full px-3 py-2 border border-[#E2E8F0] rounded text-sm bg-white" />
      </Field>
      <div className="grid grid-cols-2 gap-2">
        <Field label="Author"><TextI value={f.author || ""} onChange={set("author")} /></Field>
        <Field label="Position"><TextI type="number" value={f.position} onChange={set("position")} /></Field>
      </div>
      <PublishToggle value={f.is_published} onChange={v => setF(p => ({ ...p, is_published: v }))} />
      <FormActions onCancel={onCancel} />
    </form>
  );
}

/* ─────────────────── Tiny shared form bits ─────────────────── */
function Toolbar({ onAdd, onPublish, addLabel, children }) {
  return (
    <div className="flex items-center gap-2 mb-2">
      {children}
      <div className="flex-1" />
      <button onClick={onAdd} data-testid="content-add-button"
        className="flex items-center gap-1.5 bg-[#CC0000] hover:bg-[#A30000] text-white text-xs font-semibold px-3 py-1.5 rounded">
        <Plus size={13} /><span>{addLabel}</span>
      </button>
    </div>
  );
}
function Field({ label, full, children }) {
  return <label className={`block ${full ? "col-span-full" : ""}`}>
    <span className="block text-[10px] uppercase tracking-wider font-bold text-[#64748B] mb-0.5">{label}</span>
    {children}
  </label>;
}
function TextI(props) {
  return <input {...props} className="w-full px-2 py-1.5 border border-[#E2E8F0] rounded text-sm bg-white focus:outline-none focus:ring-1 focus:ring-[#CC0000]/30 focus:border-[#CC0000]" />;
}
function PublishToggle({ value, onChange }) {
  return <label className="inline-flex items-center gap-2 text-xs text-[#475569]">
    <input type="checkbox" checked={!!value} onChange={e => onChange(e.target.checked)} className="rounded" />
    <span>Published</span>
  </label>;
}
function FormActions({ onCancel }) {
  return <div className="flex gap-2 pt-1">
    <button type="submit" className="flex items-center gap-1.5 bg-[#CC0000] hover:bg-[#A30000] text-white text-xs font-semibold px-3 py-1.5 rounded">
      <Save size={12} /><span>Save</span>
    </button>
    <button type="button" onClick={onCancel} className="flex items-center gap-1.5 text-[#475569] hover:text-[#0F172A] text-xs font-semibold px-3 py-1.5 rounded border border-[#E2E8F0]">
      <X size={12} /><span>Cancel</span>
    </button>
  </div>;
}
function PubDot({ v }) {
  return <span className={`inline-block w-1.5 h-1.5 rounded-full ${v ? "bg-emerald-500" : "bg-amber-400"}`} title={v ? "Published" : "Draft"} />;
}
function Badge({ value }) {
  if (!value) return <span className="text-xs text-[#94A3B8]">—</span>;
  const cls = value === "hot" ? "bg-red-100 text-red-700" : "bg-amber-100 text-amber-700";
  return <span className={`text-[10px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded ${cls}`}>{value}</span>;
}
