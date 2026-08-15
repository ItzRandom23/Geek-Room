"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ChevronRight, Plus, RadioTower, Clock, TrendingUp, AlertTriangle, Activity, Flag } from "lucide-react";
import { api, ApiError, Session } from "../../lib/api";
import { Badge, Button, ErrorBox } from "../../components/ui";

function MetricCard({ label, value, detail, icon: Icon, tone, trend }: { label: string; value: string; detail: string; icon: React.ComponentType<{ size?: number; className?: string }>; tone: "cyan" | "green" | "amber" | "signal"; trend?: string }) {
  const toneClass = { cyan: "border-cyan/30 bg-cyan/5", green: "border-emerald-400/30 bg-emerald-400/5", amber: "border-amber-400/30 bg-amber-400/5", signal: "border-signal/30 bg-signal/5" }[tone];
  const iconClass = { cyan: "text-cyan", green: "text-emerald-400", amber: "text-amber-400", signal: "text-signal" }[tone];
  return (
    <div className={`panel p-5 ${toneClass}`}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2 text-[10px] uppercase tracking-wider text-slate-400"><Icon className={iconClass} size={12} />{label}</div>
          <div className="mt-1 truncate text-2xl font-bold">{value}</div>
          <div className="mt-1 text-xs text-slate-500">{detail}</div>
        </div>
        {trend && <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-white/5"><span className="text-xs font-mono text-slate-400">{trend}</span></div>}
      </div>
    </div>
  );
}

function ActivityItem({ session, index }: { session: Session; index: number }) {
  const statusIcon = { analysed: "text-emerald-400", audio_ready: "text-cyan", queued: "text-amber-400", analysing: "text-amber-400", error: "text-signal", ready: "text-slate-500" }[session.status] || "text-slate-500";
  const statusLabel = { analysed: "Completed", audio_ready: "Audio uploaded", queued: "Queued", analysing: "Analysing", error: "Failed", ready: "Created" }[session.status] || session.status;
  return (
    <Link href={`/sessions/${session.id}`} className="flex items-center gap-4 p-3 rounded-lg border border-line hover:border-cyan/50 transition" style={{ animationDelay: `${Math.min(index, 8) * 50}ms` }}>
      <div className="flex h-10 w-10 items-center justify-center rounded-lg border border-white/10 bg-black/20"><Activity className={statusIcon} size={16} /></div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2"><span className="font-semibold truncate">{session.name}</span>{session.is_demo && <Badge tone="cyan">Demo</Badge>}</div>
        <div className="mt-1 text-xs text-slate-400">{session.driver_name} · {session.circuit_name} · {session.audio_count} audio / {session.lap_count} laps</div>
      </div>
      <div className="text-right">
        <div className="font-mono text-xs text-slate-300">{statusLabel}</div>
        <div className="text-[10px] text-slate-500">{new Date(session.created_at).toLocaleDateString()}</div>
      </div>
      <ChevronRight className="text-slate-500" size={14} />
    </Link>
  );
}

export default function SessionsPage() {
  const router = useRouter();
  const [sessions, setSessions] = useState<Session[]>([]);
  const [error, setError] = useState("");
  const [show, setShow] = useState(false);
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState({ name: "", driver_name: "", circuit_name: "" });
  const [onboardingChecked, setOnboardingChecked] = useState(false);

  const load = () =>
    api.sessions().then(found => {
      setSessions(found);
      if (typeof window !== "undefined" && new URLSearchParams(window.location.search).get("demo") === "1") {
        const demo = found.find(item => item.is_demo);
        if (demo) window.location.href = `/sessions/${demo.id}`;
      }
    }).catch(e => {
      if (e instanceof ApiError && e.code === "UNAUTHENTICATED") {
        router.push("/login");
        return;
      }
      setError(e.message);
    });

  const checkOnboarding = async () => {
    try {
      const me = await api.me();
      if (me.authenticated && me.user && !me.user.onboarding_completed) {
        router.push("/onboarding");
        return;
      }
    } catch {
      // Ignore errors, let the sessions load handle auth
    } finally {
      setOnboardingChecked(true);
    }
  };

  useEffect(() => {
    checkOnboarding();
    if (onboardingChecked) load();
  }, [router, onboardingChecked]);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api.create(form);
      setForm({ name: "", driver_name: "", circuit_name: "" });
      setShow(false);
      await load();
    } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  }

  async function remove(id: number) {
    if (!confirm("Delete this session and its uploaded audio?")) return;
    try {
      await api.remove(id);
      await load();
    } catch (e) { setError((e as Error).message); }
  }

  const analysedSessions = useMemo(() => sessions.filter(s => s.status === "analysed"), [sessions]);
  const totalSessions = sessions.length;
  const totalAnalysed = analysedSessions.length;
  const totalLaps = useMemo(() => sessions.reduce((sum, s) => sum + s.lap_count, 0), [sessions]);
  const totalAudioMinutes = useMemo(() => Math.round(sessions.reduce((sum, s) => sum + (s.audio?.reduce((a, c) => a + (c.duration_seconds || 0), 0) || 0), 0) / 60), [sessions]);
  const totalEvents = useMemo(() => analysedSessions.reduce((sum, s) => sum + (s.report?.summary?.event_count || 0), 0), [analysedSessions]);
  const recentSessions = useMemo(() => [...sessions].sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()).slice(0, 5), [sessions]);

  if (!onboardingChecked) return <main className="mx-auto max-w-7xl px-6 py-20 text-slate-400">Loading…</main>;

  return (
    <main className="mx-auto min-h-[calc(100vh-150px)] max-w-7xl px-6 py-12">
      <div className="reveal flex flex-wrap items-end justify-between gap-5 border-b border-white/[0.07] pb-8">
        <div>
          <div className="section-badge"><RadioTower size={12} /> Operations / dashboard</div>
          <h1 className="mt-4 text-4xl font-bold">Analysis dashboard</h1>
          <p className="mt-2 max-w-2xl text-slate-400">Overview of your race-engineering workspace. Create a session to start analysing driver radio.</p>
        </div>
        <Button onClick={() => setShow(!show)} aria-expanded={show}><Plus size={16} />New session</Button>
      </div>

      {error && <div className="mt-6"><ErrorBox message={error} /></div>}

      <div className="reveal mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard label="Total sessions" value={String(totalSessions)} detail={totalAnalysed > 0 ? `${totalAnalysed} analysed` : "Create your first"} icon={Flag} tone="cyan" />
        <MetricCard label="Laps analysed" value={String(totalLaps)} detail={totalLaps > 0 ? "Across all sessions" : "Import lap data to start"} icon={TrendingUp} tone="green" />
        <MetricCard label="Radio reviewed" value={`${totalAudioMinutes}m`} detail={totalAudioMinutes > 0 ? "Of driver audio" : "Upload audio clips"} icon={Activity} tone="amber" />
        <MetricCard label="Safety events" value={String(totalEvents)} detail="High-stress detections flagged" icon={AlertTriangle} tone="signal" />
      </div>

      {show && (
        <form onSubmit={submit} className="panel reveal mt-7 grid gap-4 p-5 md:grid-cols-3">
          <label className="text-xs text-slate-400">Session name<input required placeholder="Friday long run" value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} className="field mt-2" /></label>
          <label className="text-xs text-slate-400">Driver<input required placeholder="Driver name" value={form.driver_name} onChange={e => setForm({ ...form, driver_name: e.target.value })} className="field mt-2" /></label>
          <label className="text-xs text-slate-400">Circuit<input required placeholder="Circuit name" value={form.circuit_name} onChange={e => setForm({ ...form, circuit_name: e.target.value })} className="field mt-2" /></label>
          <div className="md:col-span-3"><Button disabled={busy}>{busy ? "Creating..." : "Create session"}</Button></div>
        </form>
      )}

      <section className="mt-8 reveal">
        <div className="flex items-center justify-between mb-4">
          <div>
            <div className="section-badge">Recent activity</div>
            <h2 className="mt-2 text-2xl font-bold">Latest sessions</h2>
          </div>
          <Link href="/analytics" className="btn-ghost text-xs"><Clock size={12} className="mr-1" />View all</Link>
        </div>
        {sessions.length === 0 ? (
          <div className="panel p-12 text-center">
            <RadioTower className="mx-auto text-slate-600" size={28} />
            <p className="mt-4 text-sm text-slate-400">No sessions yet. Create one or open the demo from the home screen.</p>
          </div>
        ) : (
          <div className="panel space-y-2 p-2">
            {recentSessions.map((session, index) => (
              <ActivityItem key={session.id} session={session} index={index} />
            ))}
          </div>
        )}
      </section>

      <section className="mt-8 reveal">
        <div className="section-badge">Quick actions</div>
        <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Link href="/sessions?demo=1" className="panel p-5 text-center hover:border-cyan/50 transition">
            <Activity className="mx-auto text-cyan" size={24} />
            <h3 className="mt-3 font-semibold">Explore demo</h3>
            <p className="mt-1 text-sm text-slate-400">Pre-loaded session with transcript, emotion markers & lap correlation</p>
          </Link>
          <Link href="/sessions" className="panel p-5 text-center hover:border-cyan/50 transition" onClick={() => setShow(true)}>
            <Plus className="mx-auto text-cyan" size={24} />
            <h3 className="mt-3 font-semibold">New session</h3>
            <p className="mt-1 text-sm text-slate-400">Create a session, upload radio, add lap times</p>
          </Link>
          <Link href="/methodology" className="panel p-5 text-center hover:border-cyan/50 transition">
            <Flag className="mx-auto text-cyan" size={24} />
            <h3 className="mt-3 font-semibold">Methodology</h3>
            <p className="mt-1 text-sm text-slate-400">How the pipeline works: STT, emotion, correlation, rules</p>
          </Link>
          <Link href="/analytics" className="panel p-5 text-center hover:border-cyan/50 transition">
            <TrendingUp className="mx-auto text-cyan" size={24} />
            <h3 className="mt-3 font-semibold">Analytics</h3>
            <p className="mt-1 text-sm text-slate-400">Historical trends, driver patterns, session comparison</p>
          </Link>
        </div>
      </section>
    </main>
  );
}
