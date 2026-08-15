"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { ChevronRight, TrendingUp, AlertTriangle, Activity, Flag, Search, BarChart3, Plus } from "lucide-react";
import Link from "next/link";
import { api, ApiError, Session } from "../../lib/api";
import { Badge, Button, ErrorBox } from "../../components/ui";

function MetricCard({ label, value, detail, icon: Icon, tone }: { label: string; value: string; detail: string; icon: React.ComponentType<{ size?: number; className?: string }>; tone: "cyan" | "green" | "amber" | "signal" }) {
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
      </div>
    </div>
  );
}

function SessionRow({ session }: { session: Session }) {
  const statusIcon = { analysed: "text-emerald-400", audio_ready: "text-cyan", queued: "text-amber-400", analysing: "text-amber-400", error: "text-signal", ready: "text-slate-500" }[session.status] || "text-slate-500";
  const statusLabel = { analysed: "Analysed", audio_ready: "Audio ready", queued: "Queued", analysing: "Analysing", error: "Error", ready: "Created" }[session.status] || session.status;
  const eventCount = session.report?.summary?.event_count || 0;
  const primaryState = session.report?.primary_state || "—";
  const correlation = session.report?.correlation_available ? "Lap-correlated" : "Audio-only";
  return (
    <tr className="border-t border-line/60 hover:bg-white/[0.02]">
      <td className="py-4"><Link href={`/sessions/${session.id}`} className="font-semibold hover:text-cyan transition">{session.name}</Link></td>
      <td className="py-4 text-sm text-slate-400">{session.driver_name}</td>
      <td className="py-4 text-sm text-slate-400">{session.circuit_name}</td>
      <td className="py-4 text-sm text-slate-400">{session.audio_count} clips / {session.lap_count} laps</td>
      <td className="py-4"><Badge tone={session.status === "analysed" ? "green" : session.status === "error" ? "red" : "slate"}>{statusLabel}</Badge></td>
      <td className="py-4 text-sm text-slate-400">{eventCount}</td>
      <td className="py-4 text-sm text-slate-400 capitalize">{primaryState}</td>
      <td className="py-4 text-sm text-slate-400">{correlation}</td>
      <td className="py-4 text-[10px] text-slate-500">{new Date(session.created_at).toLocaleDateString()}</td>
      <td className="py-4"><Link href={`/sessions/${session.id}`} className="btn-ghost text-xs"><ChevronRight size={12} /></Link></td>
    </tr>
  );
}

export default function AnalyticsPage() {
  const router = useRouter();
  const [sessions, setSessions] = useState<Session[]>([]);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [sortField, setSortField] = useState<keyof Session | "event_count">("created_at");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");
  const [onboardingChecked, setOnboardingChecked] = useState(false);

  const load = () =>
    api.sessions().then(found => setSessions(found)).catch(e => {
      if (e instanceof ApiError && e.code === "UNAUTHENTICATED") router.push("/login");
      else setError(e.message);
    });

  const checkOnboarding = async () => {
    try {
      const me = await api.me();
      if (me.authenticated && me.user && !me.user.onboarding_completed) router.push("/onboarding");
    } catch {} finally { setOnboardingChecked(true); }
  };

  useEffect(() => { checkOnboarding(); if (onboardingChecked) load(); }, [router, onboardingChecked]);

  if (!onboardingChecked) return <main className="mx-auto max-w-7xl px-6 py-20 text-slate-400">Loading…</main>;

  const filtered = useMemo(() => {
    let result = sessions.filter(s => {
      if (statusFilter !== "all" && s.status !== statusFilter) return false;
      if (search) {
        const q = search.toLowerCase();
        if (!s.name.toLowerCase().includes(q) && !s.driver_name.toLowerCase().includes(q) && !s.circuit_name.toLowerCase().includes(q)) return false;
      }
      return true;
    });
    result.sort((a, b) => {
      let va: unknown;
      let vb: unknown;
      if (sortField === "event_count") {
        va = a.report?.summary?.event_count || 0;
        vb = b.report?.summary?.event_count || 0;
      } else {
        va = a[sortField];
        vb = b[sortField];
      }
      if (va instanceof Date) va = va.getTime();
      if (vb instanceof Date) vb = vb.getTime();
      if (typeof va === "string" && typeof vb === "string") return sortDir === "asc" ? va.localeCompare(vb) : vb.localeCompare(va);
      if (typeof va === "number" && typeof vb === "number") return sortDir === "asc" ? va - vb : vb - va;
      return 0;
    });
    return result;
  }, [sessions, search, statusFilter, sortField, sortDir]);

  const analysedSessions = sessions.filter(s => s.status === "analysed");
  const totalSessions = sessions.length;
  const totalAnalysed = analysedSessions.length;
  const totalLaps = sessions.reduce((sum, s) => sum + s.lap_count, 0);
  const totalEvents = analysedSessions.reduce((sum, s) => sum + (s.report?.summary?.event_count || 0), 0);
  const avgEventsPerSession = totalAnalysed > 0 ? (totalEvents / totalAnalysed).toFixed(1) : "0";
  const mostCommonState = useMemo(() => {
    const counts: Record<string, number> = {};
    analysedSessions.forEach(s => {
      const state = s.report?.primary_state;
      if (state) counts[state] = (counts[state] || 0) + 1;
    });
    return Object.entries(counts).sort((a, b) => b[1] - a[1])[0]?.[0] || "—";
  }, [analysedSessions]);

  return (
    <main className="mx-auto min-h-[calc(100vh-150px)] max-w-7xl px-6 py-12">
      <div className="reveal flex flex-wrap items-end justify-between gap-5 border-b border-white/[0.07] pb-8">
        <div>
          <div className="section-badge"><BarChart3 size={12} /> Analytics / sessions</div>
          <h1 className="mt-4 text-4xl font-bold">Session analytics</h1>
          <p className="mt-2 max-w-2xl text-slate-400">Track historical trends, compare sessions, and measure team impact over time.</p>
        </div>
        <Link href="/sessions" className="btn-ghost"><Plus size={14} className="mr-1" />New session</Link>
      </div>

      {error && <div className="mt-6"><ErrorBox message={error} /></div>}

      <div className="reveal mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
        <MetricCard label="Total sessions" value={String(totalSessions)} detail={totalAnalysed > 0 ? `${totalAnalysed} analysed` : "Start your first"} icon={Flag} tone="cyan" />
        <MetricCard label="Analysed sessions" value={String(totalAnalysed)} detail={totalAnalysed > 0 ? `${totalSessions - totalAnalysed} pending` : "No analyses yet"} icon={Activity} tone="green" />
        <MetricCard label="Total laps" value={String(totalLaps)} detail="Across all sessions" icon={TrendingUp} tone="amber" />
        <MetricCard label="Events detected" value={String(totalEvents)} detail={`Avg ${avgEventsPerSession} per analysed session`} icon={AlertTriangle} tone="signal" />
        <MetricCard label="Dominant state" value={mostCommonState} detail="Across analysed sessions" icon={Flag} tone="cyan" />
      </div>

      <section className="mt-8 reveal panel p-5">
        <div className="flex flex-wrap items-center gap-4">
          <div className="relative flex-1 max-w-md"><Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" size={16} /><input type="text" placeholder="Search sessions, drivers, circuits..." value={search} onChange={e => setSearch(e.target.value)} className="field w-full pl-10 pr-4" /></div>
          <select value={statusFilter} onChange={e => setStatusFilter(e.target.value)} className="field w-40"><option value="all">All statuses</option><option value="analysed">Analysed</option><option value="audio_ready">Audio ready</option><option value="ready">Created</option><option value="queued">Queued</option><option value="analysing">Analysing</option><option value="error">Error</option></select>
          <div className="flex items-center gap-2 text-xs text-slate-400">Sort by <select value={sortField} onChange={e => setSortField(e.target.value as any)} className="field w-36"><option value="created_at">Date</option><option value="name">Name</option><option value="driver_name">Driver</option><option value="circuit_name">Circuit</option><option value="event_count">Events</option></select> <button onClick={() => setSortDir(d => d === "asc" ? "desc" : "asc")} className="btn-ghost text-xs">{sortDir === "asc" ? "↑ Asc" : "↓ Desc"}</button></div>
        </div>
      </section>

      <section className="mt-6 reveal">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[1100px] text-left text-sm">
            <thead className="text-xs uppercase tracking-wider text-slate-500">
              <tr className="border-b border-line">
                <th className="pb-3 pr-4 cursor-pointer hover:text-cyan" onClick={() => { if (sortField === "name") setSortDir(d => d === "asc" ? "desc" : "asc"); else setSortField("name"); }}>Session</th>
                <th className="pb-3 pr-4 cursor-pointer hover:text-cyan" onClick={() => { if (sortField === "driver_name") setSortDir(d => d === "asc" ? "desc" : "asc"); else setSortField("driver_name"); }}>Driver</th>
                <th className="pb-3 pr-4 cursor-pointer hover:text-cyan" onClick={() => { if (sortField === "circuit_name") setSortDir(d => d === "asc" ? "desc" : "asc"); else setSortField("circuit_name"); }}>Circuit</th>
                <th className="pb-3 pr-4">Audio / Laps</th>
                <th className="pb-3 pr-4">Status</th>
                <th className="pb-3 pr-4 cursor-pointer hover:text-cyan" onClick={() => { if (sortField === "event_count") setSortDir(d => d === "asc" ? "desc" : "asc"); else setSortField("event_count"); }}>Events</th>
                <th className="pb-3 pr-4">Primary state</th>
                <th className="pb-3 pr-4">Mode</th>
                <th className="pb-3 pr-4 cursor-pointer hover:text-cyan" onClick={() => { if (sortField === "created_at") setSortDir(d => d === "asc" ? "desc" : "asc"); else setSortField("created_at"); }}>Date</th>
                <th className="pb-3 pr-4"></th>
              </tr>
            </thead>
            <tbody>
              {filtered.length === 0 ? (
                <tr><td colSpan={10} className="py-12 text-center text-slate-400">No sessions match your filters.</td></tr>
              ) : filtered.map(session => (
                <SessionRow key={session.id} session={session} />
              ))}
            </tbody>
          </table>
        </div>
        {filtered.length > 0 && (
          <div className="mt-4 flex items-center justify-between text-sm text-slate-400">
            <span>Showing {filtered.length} of {sessions.length} sessions</span>
            <Button disabled>Export filtered (CSV)</Button>
          </div>
        )}
      </section>
    </main>
  );
}