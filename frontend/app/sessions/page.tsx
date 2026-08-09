"use client";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ChevronRight, Plus, RadioTower, Trash2 } from "lucide-react";
import { api, ApiError, Session } from "../../lib/api";
import { Badge, Button, ErrorBox, StatusIcon } from "../../components/ui";

export default function SessionsPage() {
  const router = useRouter();
  const [sessions, setSessions] = useState<Session[]>([]);
  const [error, setError] = useState("");
  const [show, setShow] = useState(false);
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState({ name: "", driver_name: "", circuit_name: "" });

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

  useEffect(() => { load(); }, [router]);

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

  return (
    <main className="mx-auto min-h-[calc(100vh-150px)] max-w-7xl px-6 py-12">
      <div className="reveal flex flex-wrap items-end justify-between gap-5 border-b border-white/[0.07] pb-8">
        <div>
          <div className="section-badge"><RadioTower size={12} /> Operations / sessions</div>
          <h1 className="mt-4 text-4xl font-bold">Analysis sessions</h1>
          <p className="mt-2 max-w-2xl text-slate-400">Manage race runs, upload driver radio, and review the inference pipeline.</p>
        </div>
        <Button onClick={() => setShow(!show)} aria-expanded={show}><Plus size={16} />New session</Button>
      </div>

      {error && <div className="mt-6"><ErrorBox message={error} /></div>}

      {show && (
        <form onSubmit={submit} className="panel reveal mt-7 grid gap-4 p-5 md:grid-cols-3">
          <label className="text-xs text-slate-400">Session name<input required placeholder="Friday long run" value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} className="field mt-2" /></label>
          <label className="text-xs text-slate-400">Driver<input required placeholder="Driver name" value={form.driver_name} onChange={e => setForm({ ...form, driver_name: e.target.value })} className="field mt-2" /></label>
          <label className="text-xs text-slate-400">Circuit<input required placeholder="Circuit name" value={form.circuit_name} onChange={e => setForm({ ...form, circuit_name: e.target.value })} className="field mt-2" /></label>
          <div className="md:col-span-3"><Button disabled={busy}>{busy ? "Creating..." : "Create session"}</Button></div>
        </form>
      )}

      <div className="mt-7 grid gap-3">
        {sessions.length === 0 && !error ? (
          <div className="panel p-12 text-center">
            <RadioTower className="mx-auto text-slate-600" size={28} />
            <p className="mt-4 text-sm text-slate-400">No sessions yet. Create one or open the demo from the home screen.</p>
          </div>
        ) : sessions.map((session, index) => (
          <article className="glass-card glass-edge reveal flex flex-wrap items-center gap-4 overflow-hidden p-5" style={{ animationDelay: `${Math.min(index, 6) * 60}ms` }} key={session.id}>
            <span className="flex h-9 w-9 items-center justify-center rounded-lg border border-white/10 bg-black/20"><StatusIcon status={session.status} /></span>
            <div className="min-w-[220px] flex-1">
              <div className="flex flex-wrap items-center gap-3"><h2 className="font-semibold">{session.name}</h2>{session.is_demo && <Badge tone="cyan">Demo fixture</Badge>}</div>
              <div className="mt-1 text-sm text-slate-400">{session.driver_name} / {session.circuit_name}</div>
            </div>
            <div className="font-mono text-[10px] uppercase text-slate-500">{session.audio_count} audio / {session.lap_count} laps</div>
            <Badge tone={session.status === "analysed" ? "green" : "slate"}>{session.status}</Badge>
            <Link href={`/sessions/${session.id}`} className="btn-ghost text-xs">Open <ChevronRight size={14} /></Link>
            <button aria-label={`Delete ${session.name}`} title="Delete session" onClick={() => remove(session.id)} className="rounded-lg p-2.5 text-slate-500 transition hover:bg-[rgba(255,61,0,0.12)] hover:text-[#ff7840]">
              <Trash2 size={17} />
            </button>
          </article>
        ))}
      </div>
    </main>
  );
}
