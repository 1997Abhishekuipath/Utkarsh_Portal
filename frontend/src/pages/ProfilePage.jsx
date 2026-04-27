import React, { useState, useEffect, useCallback, useRef } from "react";
import TopBar from "../components/TopBar";
import {
  User, Mail, Building2, Briefcase, Calendar, Clock, Shield,
  Award, Zap, Trophy, Edit2, Save, X, CheckCircle, AlertCircle, Camera, Loader2
} from "lucide-react";
import { useAuth } from "../contexts/AuthContext";

const BACKEND = process.env.REACT_APP_BACKEND_URL;

export default function ProfilePage() {
  const { user } = useAuth();
  const [profile, setProfile] = useState(null);
  const [xpSummary, setXpSummary] = useState(null);
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState({ name: "", department: "", employee_id: "", date_of_birth: "", phone: "", designation: "" });
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState(null);
  const [uploadingAvatar, setUploadingAvatar] = useState(false);
  const fileRef = useRef(null);

  const showToast = (msg, type = "success") => { setToast({ msg, type }); setTimeout(() => setToast(null), 3500); };

  const load = useCallback(async () => {
    try {
      const [meRes, xpRes] = await Promise.all([
        fetch(`${BACKEND}/api/auth/me`, { credentials: "include" }),
        fetch(`${BACKEND}/api/xp/summary`, { credentials: "include" }),
      ]);
      if (meRes.ok) {
        const d = await meRes.json();
        setProfile(d);
        setForm({
          name: d.name || "",
          department: d.department || "",
          employee_id: d.employee_id || "",
          date_of_birth: d.date_of_birth || "",
          phone: d.phone || "",
          designation: d.designation || "",
        });
      }
      if (xpRes.ok) setXpSummary(await xpRes.json());
    } catch { /* silent */ }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleSave = async () => {
    setSaving(true);
    try {
      const res = await fetch(`${BACKEND}/api/users/me`, {
        method: "PATCH",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      if (res.ok) {
        showToast("Profile updated successfully!");
        setEditing(false);
        load();
      } else {
        const d = await res.json();
        showToast(d.detail || "Update failed", "error");
      }
    } finally { setSaving(false); }
  };

  // Sprint G — avatar upload
  const handleAvatarChange = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (file.size > 5 * 1024 * 1024) {
      showToast("Avatar must be ≤ 5 MB", "error");
      return;
    }
    setUploadingAvatar(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("category", "avatar");
      fd.append("linked_type", "user_avatar");
      fd.append("linked_id", profile?.id || "");
      const up = await fetch(`${BACKEND}/api/uploads`, {
        method: "POST", credentials: "include", body: fd,
      });
      if (!up.ok) throw new Error("upload failed");
      const { url } = await up.json();
      const patch = await fetch(`${BACKEND}/api/users/me`, {
        method: "PATCH", credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ avatar_url: url }),
      });
      if (patch.ok) {
        showToast("Avatar updated");
        load();
      } else throw new Error("save failed");
    } catch (err) {
      showToast(err.message || "Avatar upload failed", "error");
    } finally {
      setUploadingAvatar(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  const avatarSrc = profile?.avatar_url
    ? (profile.avatar_url.startsWith("http") ? profile.avatar_url : `${BACKEND}${profile.avatar_url}`)
    : null;

  const ROLE_BADGE = {
    super_admin: "bg-red-100 text-red-700 border-red-200",
    admin: "bg-orange-100 text-orange-700 border-orange-200",
    manager: "bg-blue-100 text-blue-700 border-blue-200",
    employee: "bg-gray-100 text-gray-700 border-gray-200",
  };

  const xpPct = xpSummary ? Math.min(100, Math.round(((xpSummary.total_xp % 500) / 500) * 100)) : 0;

  const InfoRow = ({ icon: Icon, label, value, placeholder = "—" }) => (
    <div className="flex items-start gap-3 py-3 border-b border-gray-50 last:border-0">
      <div className="w-8 h-8 bg-gray-50 rounded-lg flex items-center justify-center flex-shrink-0">
        <Icon size={14} className="text-gray-400" />
      </div>
      <div className="flex-1 min-w-0">
        <div className="text-[11px] text-gray-400 uppercase tracking-wider font-medium">{label}</div>
        <div className="text-sm text-gray-800 mt-0.5">{value || placeholder}</div>
      </div>
    </div>
  );

  return (
    <div className="min-h-screen bg-[#F1F5F9]">
      {toast && (
        <div className={`fixed top-4 right-4 z-50 px-4 py-3 rounded-lg shadow-lg text-sm font-medium flex items-center gap-2
          ${toast.type === "error" ? "bg-red-50 text-red-700 border border-red-200" : "bg-green-50 text-green-700 border border-green-200"}`}>
          {toast.type === "error" ? <AlertCircle size={16} /> : <CheckCircle size={16} />}
          {toast.msg}
        </div>
      )}

      <TopBar crumbs={[{ label: "Home", to: "/" }, { label: "My Profile" }]}>
        <div className="flex items-end justify-between">
          <div>
            <h1 className="text-white text-2xl font-bold">My Profile</h1>
            <p className="text-white/70 text-sm mt-1">Account details and XP overview</p>
          </div>
        </div>
      </TopBar>

      <div className="max-w-4xl mx-auto px-4 py-6 grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Avatar + XP card */}
        <div className="md:col-span-1 space-y-4">
          <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-6 text-center">
            <div className="relative w-20 h-20 mx-auto mb-3">
              {avatarSrc ? (
                <img
                  src={avatarSrc} alt={`${profile?.name} avatar`}
                  className="w-20 h-20 rounded-2xl object-cover shadow-lg"
                />
              ) : (
                <div className="w-20 h-20 bg-gradient-to-br from-[#CC0000] to-red-700 rounded-2xl flex items-center justify-center shadow-lg">
                  <span className="text-white text-3xl font-bold">{profile?.name?.[0] || "?"}</span>
                </div>
              )}
              <button
                type="button"
                onClick={() => fileRef.current?.click()}
                disabled={uploadingAvatar}
                aria-label="Upload new avatar"
                data-testid="avatar-upload-btn"
                className="absolute -bottom-1 -right-1 w-7 h-7 bg-white rounded-full shadow-md border border-gray-200 flex items-center justify-center hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-[#CC0000] focus:ring-offset-2 disabled:opacity-60"
              >
                {uploadingAvatar ? <Loader2 size={12} className="animate-spin text-gray-600" /> : <Camera size={12} className="text-gray-700" />}
              </button>
              <input
                ref={fileRef} type="file" accept="image/*"
                onChange={handleAvatarChange}
                className="hidden"
                data-testid="avatar-upload-input"
              />
            </div>
            <h2 className="text-lg font-bold text-gray-900">{profile?.name}</h2>
            <p className="text-sm text-gray-500">{profile?.email}</p>
            <span className={`inline-flex items-center mt-2 text-xs px-3 py-1 rounded-full font-medium border ${ROLE_BADGE[profile?.role] || "bg-gray-100 text-gray-600"}`}>
              <Shield size={11} className="mr-1" aria-hidden="true" />
              {profile?.role?.replace("_", " ").replace(/^./, c => c.toUpperCase())}
            </span>
          </div>

          {/* XP Summary */}
          {xpSummary && (
            <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-5">
              <h3 className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-4">XP Overview</h3>
              <div className="flex items-center gap-3 mb-4">
                <div className="w-12 h-12 bg-gradient-to-br from-amber-400 to-amber-500 rounded-xl flex items-center justify-center shadow-sm">
                  <span className="text-white text-lg font-bold">L{xpSummary.level}</span>
                </div>
                <div>
                  <div className="text-xl font-bold text-gray-900">{xpSummary.total_xp.toLocaleString()}</div>
                  <div className="text-xs text-gray-400">Total XP · Level {xpSummary.level}</div>
                </div>
              </div>
              <div className="w-full bg-gray-100 rounded-full h-2 mb-3">
                <div className="bg-gradient-to-r from-amber-400 to-amber-500 h-2 rounded-full transition-all duration-500"
                  style={{ width: `${xpPct}%` }} />
              </div>
              <div className="grid grid-cols-2 gap-3 text-center">
                <div className="bg-gray-50 rounded-lg p-2.5">
                  <Trophy size={14} className="text-amber-500 mx-auto mb-1" />
                  <div className="text-sm font-bold text-gray-800">#{xpSummary.rank}</div>
                  <div className="text-[10px] text-gray-400">Rank</div>
                </div>
                <div className="bg-gray-50 rounded-lg p-2.5">
                  <Zap size={14} className="text-[#CC0000] mx-auto mb-1" />
                  <div className="text-sm font-bold text-gray-800">{xpSummary.quarter_xp}</div>
                  <div className="text-[10px] text-gray-400">{xpSummary.quarter} XP</div>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Details card */}
        <div className="md:col-span-2">
          <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-6">
            <div className="flex items-center justify-between mb-5">
              <h3 className="text-sm font-bold text-gray-800">Employee Details</h3>
              {!editing ? (
                <button onClick={() => setEditing(true)}
                  className="flex items-center gap-1.5 text-xs text-[#CC0000] hover:underline font-medium">
                  <Edit2 size={12} />Edit Profile
                </button>
              ) : (
                <div className="flex items-center gap-2">
                  <button onClick={() => setEditing(false)} className="flex items-center gap-1 text-xs text-gray-500 hover:text-gray-700">
                    <X size={12} />Cancel
                  </button>
                  <button onClick={handleSave} disabled={saving}
                    className="flex items-center gap-1 text-xs bg-[#CC0000] text-white px-3 py-1.5 rounded-lg hover:bg-red-700 disabled:opacity-60">
                    <Save size={12} />{saving ? "Saving…" : "Save"}
                  </button>
                </div>
              )}
            </div>

            {editing ? (
              <div className="space-y-4">
                {[
                  ["Full Name", "name", "text"],
                  ["Designation", "designation", "text"],
                  ["Department", "department", "text"],
                  ["Employee ID", "employee_id", "text"],
                  ["Phone", "phone", "tel"],
                  ["Date of Birth", "date_of_birth", "date"],
                ].map(([label, field, type]) => (
                  <div key={field}>
                    <label htmlFor={`profile-${field}`} className="block text-xs font-semibold text-gray-600 mb-1">{label}</label>
                    <input
                      id={`profile-${field}`}
                      type={type}
                      value={form[field] || ""}
                      onChange={e => setForm(p => ({ ...p, [field]: e.target.value }))}
                      data-testid={`profile-input-${field}`}
                      className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-red-300 focus:border-red-400 outline-none"
                    />
                  </div>
                ))}
              </div>
            ) : (
              <div>
                <InfoRow icon={User}      label="Full Name"     value={profile?.name} />
                <InfoRow icon={Mail}      label="Email"         value={profile?.email} />
                <InfoRow icon={Briefcase} label="Designation"   value={profile?.designation} />
                <InfoRow icon={Briefcase} label="Employee ID"   value={profile?.employee_id} />
                <InfoRow icon={Building2} label="Department"    value={profile?.department} />
                <InfoRow icon={Calendar}  label="Date of Birth" value={profile?.date_of_birth} />
                <InfoRow icon={Shield}    label="Role"          value={profile?.role?.replace("_", " ")} />
                <InfoRow icon={Clock}     label="Last Login"
                  value={profile?.last_login_at
                    ? new Date(profile.last_login_at).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" })
                    : null} />
                <InfoRow icon={CheckCircle} label="Account Status"
                  value={profile?.is_active ? "Active ✓" : "Inactive"} />
              </div>
            )}
          </div>

          {/* Security section */}
          <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-6 mt-4">
            <h3 className="text-sm font-bold text-gray-800 mb-4 flex items-center gap-2">
              <Shield size={14} className="text-[#CC0000]" />Security
            </h3>
            <div className="space-y-3">
              <div className="flex items-center justify-between py-2">
                <div>
                  <div className="text-sm font-medium text-gray-800">Two-Factor Authentication (OTP)</div>
                  <div className="text-xs text-gray-500 mt-0.5">Email OTP required on every login</div>
                </div>
                <span className="text-xs bg-green-100 text-green-700 font-semibold px-2 py-1 rounded-full">Enabled</span>
              </div>
              <div className="flex items-center justify-between py-2 border-t border-gray-50">
                <div>
                  <div className="text-sm font-medium text-gray-800">Session Token</div>
                  <div className="text-xs text-gray-500 mt-0.5">15-min access token, 30-day refresh rotation</div>
                </div>
                <span className="text-xs bg-blue-100 text-blue-700 font-semibold px-2 py-1 rounded-full">Active</span>
              </div>
              <div className="flex items-center justify-between py-2 border-t border-gray-50">
                <div>
                  <div className="text-sm font-medium text-gray-800">Password Policy</div>
                  <div className="text-xs text-gray-500 mt-0.5">8+ chars · uppercase · number · symbol</div>
                </div>
                <span className="text-xs bg-gray-100 text-gray-600 font-semibold px-2 py-1 rounded-full">bcrypt rounds=12</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
