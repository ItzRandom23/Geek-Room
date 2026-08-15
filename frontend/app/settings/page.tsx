"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Bell, Eye, EyeOff, LockKeyhole, Mail, Shield, UserRound, LogOut, Save } from "lucide-react";
import { api, ApiError, setToken } from "../../lib/api";
import { Badge, Button, ErrorBox } from "../../components/ui";

type Tab = "profile" | "preferences" | "security" | "session";

export default function SettingsPage() {
  const router = useRouter();
  const [tab, setTab] = useState<Tab>("profile");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [user, setUser] = useState<{ id: number; email: string; full_name: string; onboarding_completed: boolean } | null>(null);
  const [org, setOrg] = useState<{ id: number; name: string; role: string } | null>(null);
  const [form, setForm] = useState({ full_name: "", email: "", current_password: "", new_password: "", confirm_password: "" });
  const [prefs, setPrefs] = useState({ email_notifications: true, analysis_complete: true, weekly_digest: false });
  const [showCurrent, setShowCurrent] = useState(false);
  const [showNew, setShowNew] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);

  const load = async () => {
    try {
      const me = await api.me();
      if (!me.authenticated || !me.user) { router.push("/login"); return; }
      setUser(me.user);
      setForm({ ...form, full_name: me.user.full_name, email: me.user.email });
      if (me.organizations?.length) {
        const primary = me.organizations[0];
        setOrg({ id: primary.id, name: primary.name, role: primary.role });
      }
    } catch (e) {
      if (e instanceof ApiError && e.code === "UNAUTHENTICATED") router.push("/login");
      else setError((e as Error).message);
    }
  };

  useEffect(() => {
    const stored = window.localStorage.getItem("pitsense_preferences");
    if (stored) {
      try {
        const parsed = JSON.parse(stored) as Partial<typeof prefs>;
        setPrefs(current => ({ ...current, ...parsed }));
      } catch {
        window.localStorage.removeItem("pitsense_preferences");
      }
    }
    void load();
  }, [router]);

  async function updateProfile(e: FormEvent) {
    e.preventDefault();
    setBusy(true); setError(""); setSuccess("");
    try {
      const updated = await api.updateMe({ full_name: form.full_name, email: form.email });
      setUser(u => u ? { ...u, ...updated } : null);
      setForm(current => ({ ...current, full_name: updated.full_name, email: updated.email }));
      setSuccess("Profile changes saved.");
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }

  async function updatePassword(e: FormEvent) {
    e.preventDefault();
    setBusy(true); setError(""); setSuccess("");
    if (form.new_password !== form.confirm_password) { setError("New passwords do not match."); setBusy(false); return; }
    if (form.new_password.length < 8) { setError("Password must be at least 8 characters."); setBusy(false); return; }
    try {
      await api.updatePassword({ current_password: form.current_password, new_password: form.new_password });
      setSuccess("Password updated. Use the new password on your next sign-in.");
      setForm({ ...form, current_password: "", new_password: "", confirm_password: "" });
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }

  async function updatePrefs(e: FormEvent) {
    e.preventDefault();
    setBusy(true); setError(""); setSuccess("");
    try {
      window.localStorage.setItem("pitsense_preferences", JSON.stringify(prefs));
      setSuccess("Preferences saved on this browser.");
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }

  function logout() {
    setToken(null);
    router.push("/login");
  }

  if (!user) return <main className="mx-auto max-w-7xl px-6 py-20 text-slate-400">Loading…</main>;

  return (
    <main className="mx-auto min-h-[calc(100vh-150px)] max-w-7xl px-6 py-12">
      <div className="reveal flex flex-wrap items-end justify-between gap-5 border-b border-white/[0.07] pb-8">
        <div>
          <div className="section-badge"><Shield size={12} /> Account / settings</div>
          <h1 className="mt-4 text-4xl font-bold">Settings</h1>
          <p className="mt-2 max-w-2xl text-slate-400">Manage your profile, preferences, and security.</p>
        </div>
        <Link href="/sessions" className="btn-ghost"><ArrowLeft size={14} className="mr-1" />Back to dashboard</Link>
      </div>

      {error && <div className="mt-6"><ErrorBox message={error} /></div>}
      {success && <div className="mt-6 rounded-lg border border-emerald-400/30 bg-emerald-400/5 px-4 py-3 text-sm text-emerald-300">{success}</div>}

      <div className="mt-8 grid items-start gap-6 lg:grid-cols-[260px_1fr]">
        <aside className="settings-sidebar panel h-fit self-start p-4">
          <nav className="space-y-1" aria-label="Settings sections">
            {[
              { id: "profile", label: "Profile", icon: UserRound },
              { id: "preferences", label: "Preferences", icon: Bell },
              { id: "security", label: "Security", icon: LockKeyhole },
              { id: "session", label: "Session", icon: LogOut },
            ].map(({ id, label, icon: Icon }) => (
              <button key={id} onClick={() => setTab(id as Tab)} className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition ${tab === id ? "bg-cyan/10 border border-cyan/30 text-cyan" : "text-slate-300 hover:bg-white/5 hover:text-white"}`}>
                <Icon size={16} />
                {label}
              </button>
            ))}
          </nav>
          {org && (
            <div className="mt-6 pt-6 border-t border-line">
              <p className="text-xs text-slate-500">Active organization</p>
              <p className="mt-1 font-semibold">{org.name}</p>
              <Badge tone={org.role === "owner" ? "cyan" : "slate"} className="mt-2 inline-block">{org.role}</Badge>
            </div>
          )}
        </aside>

        <section className="panel p-6 space-y-6" aria-labelledby="settings-content">
          {tab === "profile" && (
            <form onSubmit={updateProfile}>
              <h2 id="settings-content" className="text-xl font-bold">Profile</h2>
              <p className="mt-1 text-sm text-slate-400">Your public name and contact email.</p>
              <label className="block mt-6 text-xs text-slate-400"><span className="flex items-center gap-2"><UserRound size={13} />Full name</span><input value={form.full_name} onChange={e => setForm({ ...form, full_name: e.target.value })} className="field mt-2" /></label>
              <label className="block mt-4 text-xs text-slate-400"><span className="flex items-center gap-2"><Mail size={13} />Email</span><input type="email" value={form.email} onChange={e => setForm({ ...form, email: e.target.value })} className="field mt-2" /></label>
              <div className="mt-6 pt-6 border-t border-line"><Button type="submit" disabled={busy}><Save size={15} className="mr-1" />{busy ? "Saving..." : "Save changes"}</Button></div>
            </form>
          )}

          {tab === "preferences" && (
            <form onSubmit={updatePrefs}>
              <h2 id="settings-content" className="text-xl font-bold">Preferences</h2>
              <p className="mt-1 text-sm text-slate-400">Control how PitSense communicates with you.</p>
              <fieldset className="mt-6 space-y-4">
                <legend className="text-xs text-slate-400">Notifications</legend>
                <label className="flex items-center justify-between gap-4 cursor-pointer"><div><p className="font-medium">Analysis complete</p><p className="text-xs text-slate-400">Email me when a session finishes analysing</p></div><input type="checkbox" checked={prefs.analysis_complete} onChange={e => setPrefs({ ...prefs, analysis_complete: e.target.checked })} className="rounded border-line bg-ink accent-cyan h-4 w-4" /></label>
                <label className="flex items-center justify-between gap-4 cursor-pointer"><div><p className="font-medium">Weekly digest</p><p className="text-xs text-slate-400">Summary of team activity every Monday</p></div><input type="checkbox" checked={prefs.weekly_digest} onChange={e => setPrefs({ ...prefs, weekly_digest: e.target.checked })} className="rounded border-line bg-ink accent-cyan h-4 w-4" /></label>
              </fieldset>
              <div className="mt-6 pt-6 border-t border-line"><Button type="submit" disabled={busy}><Save size={15} className="mr-1" />{busy ? "Saving..." : "Save preferences"}</Button></div>
            </form>
          )}

          {tab === "security" && (
            <form onSubmit={updatePassword}>
              <h2 id="settings-content" className="text-xl font-bold">Security</h2>
              <p className="mt-1 text-sm text-slate-400">Update your password. Minimum 8 characters.</p>
              <label className="block mt-6 text-xs text-slate-400">Current password<div className="relative mt-2"><input type={showCurrent ? "text" : "password"} value={form.current_password} onChange={e => setForm({ ...form, current_password: e.target.value })} className="field pr-12" /><button type="button" onClick={() => setShowCurrent(!showCurrent)} className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-white">{showCurrent ? <EyeOff size={18} /> : <Eye size={18} />}</button></div></label>
              <label className="block mt-4 text-xs text-slate-400">New password<div className="relative mt-2"><input type={showNew ? "text" : "password"} value={form.new_password} onChange={e => setForm({ ...form, new_password: e.target.value })} className="field pr-12" /><button type="button" onClick={() => setShowNew(!showNew)} className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-white">{showNew ? <EyeOff size={18} /> : <Eye size={18} />}</button></div></label>
              <label className="block mt-4 text-xs text-slate-400">Confirm new password<div className="relative mt-2"><input type={showConfirm ? "text" : "password"} value={form.confirm_password} onChange={e => setForm({ ...form, confirm_password: e.target.value })} className="field pr-12" /><button type="button" onClick={() => setShowConfirm(!showConfirm)} className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-white">{showConfirm ? <EyeOff size={18} /> : <Eye size={18} />}</button></div></label>
              <div className="mt-6 pt-6 border-t border-line"><Button type="submit" disabled={busy}><Save size={15} className="mr-1" />{busy ? "Updating..." : "Update password"}</Button></div>
            </form>
          )}

          {tab === "session" && (
            <div>
              <h2 id="settings-content" className="text-xl font-bold">Session</h2>
              <p className="mt-1 text-sm text-slate-400">End the current browser session when you leave the workstation.</p>
              <div className="mt-6 pt-6 border-t border-line">
                <div className="flex items-center justify-between gap-4 p-4 rounded-lg border border-line">
                  <div><p className="font-semibold">Sign out this browser</p><p className="mt-1 text-sm text-slate-400">Remove the local access token and return to team access.</p></div>
                  <Button onClick={logout}>Sign out</Button>
                </div>
              </div>
            </div>
          )}
        </section>
      </div>
    </main>
  );
}
