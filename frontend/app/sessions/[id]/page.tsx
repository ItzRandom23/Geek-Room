"use client";

import { ChangeEvent, DragEvent, useEffect, useMemo, useRef, useState } from "react";
import { useParams } from "next/navigation";
import { FileAudio, FileDown, RefreshCw, UploadCloud, X } from "lucide-react";
import { api, AnalysisJob, ApiError, Lap, Session, TimelineEvent, pollJob } from "../../../lib/api";
import { normalizeManualLaps, validateAudioFile } from "../../../lib/validation";
import { Badge, Button, ErrorBox } from "../../../components/ui";
import { ProcessingPanel } from "../../../components/processing-panel";
import { ResultsDashboard } from "../../../components/results-dashboard";

type Mode = "audio_only" | "lap_correlated";
const emptyLap = (lapNumber: number): Omit<Lap, "id"> => ({ lap_number: lapNumber, lap_time_seconds: 0, start_timestamp_seconds: 0, end_timestamp_seconds: 0 });

function errorHeading(message: string) {
  const value = message.toLowerCase();
  if (value.includes("too many requests") || value.includes("wait 60")) return "Please slow down";
  if (value.includes("lap") || value.includes("csv") || value.includes("timestamp")) return "Lap data needs correction";
  if (value.includes("audio") || value.includes("wav") || value.includes("mp3") || value.includes("m4a") || value.includes("ogg")) return "Audio needs attention";
  if (value.includes("backend") || value.includes("server") || value.includes("network")) return "Cannot reach the analysis server";
  if (value.includes("analysis") || value.includes("model") || value.includes("worker")) return "Analysis could not complete";
  if (value.includes("locked") || value.includes("progress")) return "Inputs are temporarily locked";
  return "Please check and try again";
}

export default function SessionPage() {
  const params = useParams();
  const id = Number(params.id);
  const [session, setSession] = useState<Session | null>(null);
  const [timeline, setTimeline] = useState<{ events: TimelineEvent[]; transcript: Session["transcript"] }>({ events: [], transcript: [] });
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState("");
  const [isDragging, setIsDragging] = useState(false);
  const [laps, setLaps] = useState(Array.from({ length: 8 }, (_, index) => emptyLap(index + 1)));
  const [selected, setSelected] = useState<TimelineEvent | null>(null);
  const [mode, setMode] = useState<Mode>("audio_only");
  const [job, setJob] = useState<AnalysisJob | null>(null);
  const [audioUrl, setAudioUrl] = useState("");
  const [browserDuration, setBrowserDuration] = useState<number | null>(null);
  const [pendingCsv, setPendingCsv] = useState<File | null>(null);
  const [csvPreview, setCsvPreview] = useState("");
  const audioRef = useRef<HTMLAudioElement>(null);
  const pollController = useRef<AbortController | null>(null);
  const analyseLock = useRef(false);

  const load = async () => {
    try {
      setError("");
      const found = await api.session(id);
      setSession(found);
      if (found.laps?.length) setLaps(found.laps.map(({ id: _id, ...lap }) => lap));
      if (found.analysis_mode) setMode(found.analysis_mode === "lap_correlated" ? "lap_correlated" : "audio_only");
      if (found.status === "analysed") setTimeline(await api.timeline(id));
      else setTimeline({ events: [], transcript: [] });
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : (caught as Error).message);
    }
  };

  useEffect(() => {
    if (id) void load();
    return () => pollController.current?.abort();
  }, [id]);

  const audio = session?.audio?.find((item) => item.id === session.active_clip_id) || session?.audio?.[session.audio.length - 1];
  const analysing = busy === "analyse" || job?.status === "queued" || job?.status === "running";
  const inputsLocked = Boolean(analysing);
  const showLaps = mode === "lap_correlated" || Boolean(session?.lap_count);
  const chartData = useMemo(() => session?.laps?.map((lap) => ({ lap_number: lap.lap_number, time: lap.lap_time_seconds })) || [], [session]);

  useEffect(() => {
    let revoke = "";
    setAudioUrl("");
    setBrowserDuration(null);
    if (audio) {
      api.audioBlob(id, audio.id).then((blob) => {
        revoke = URL.createObjectURL(blob);
        setAudioUrl(revoke);
      }).catch((caught) => setError(caught instanceof ApiError ? caught.message : "Audio preview unavailable."));
    }
    return () => { if (revoke) URL.revokeObjectURL(revoke); };
  }, [id, audio?.id]);

  const guardMutable = () => {
    if (!inputsLocked) return true;
    setError("Analysis is in progress. Cancel it before changing audio or lap data.");
    return false;
  };

  async function handleAudioFile(file: File) {
    if (!guardMutable()) return;
    const validationError = validateAudioFile(file);
    if (validationError) { setError(validationError); return; }
    try {
      setBusy("audio"); setError("");
      await api.uploadAudio(id, file);
      setMode("audio_only");
      setNotice("Audio uploaded. Choose an analysis mode below.");
      await load();
    } catch (caught) { setError(caught instanceof ApiError ? caught.message : (caught as Error).message); }
    finally { setBusy(""); }
  }

  async function replaceAudio(file: File) {
    if (!guardMutable()) return;
    if (!audio) { await handleAudioFile(file); return; }
    try {
      setBusy("audio"); setError("");
      await api.replaceAudio(id, audio.id, file);
      setMode("audio_only");
      setNotice("Audio replaced. Previous analysis was cleared.");
      await load();
    } catch (caught) { setError(caught instanceof ApiError ? caught.message : (caught as Error).message); }
    finally { setBusy(""); }
  }

  function uploadAudio(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (file) void handleAudioFile(file);
    event.target.value = "";
  }

  function dropAudio(event: DragEvent<HTMLDivElement>) {
    event.preventDefault(); setIsDragging(false);
    const file = event.dataTransfer.files?.[0];
    if (file) void replaceAudio(file);
  }

  async function previewCsv(event: ChangeEvent<HTMLInputElement>) {
    if (!guardMutable()) return;
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    if (!file.name.toLowerCase().endsWith(".csv")) { setError("Choose a .csv file containing lap_number and lap_time_seconds."); return; }
    if (file.size > 2 * 1024 * 1024) { setError("CSV file exceeds the 2 MB limit."); return; }
    const text = await file.text();
    const lines = text.split(/\r?\n/).filter(Boolean);
    if (!lines[0]?.includes("lap_number") || !lines[0]?.includes("lap_time_seconds")) { setError("CSV must include lap_number and lap_time_seconds columns."); return; }
    setPendingCsv(file); setCsvPreview(lines.slice(0, 5).join("\n")); setError("");
  }

  async function confirmCsv() {
    if (!pendingCsv || !guardMutable()) return;
    try {
      setBusy("csv"); setError("");
      await api.uploadCsv(id, pendingCsv);
      setPendingCsv(null); setCsvPreview(""); setMode("lap_correlated");
      setNotice(`Real lap timing imported. ${audio?.original_filename || "Your audio"} is still attached and ready for correlation.`);
      await load();
    } catch (caught) { setError(caught instanceof ApiError ? caught.message : (caught as Error).message); }
    finally { setBusy(""); }
  }

  function updateLap(index: number, key: keyof Omit<Lap, "id">, value: string) {
    setLaps((old) => old.map((lap, current) => current === index ? { ...lap, [key]: value === "" ? 0 : Number(value) } : lap));
  }

  async function saveManual() {
    if (!guardMutable()) return;
    const { rows: normalized, error: validationError } = normalizeManualLaps(laps);
    if (validationError) { setError(validationError); return; }
    try {
      setBusy("laps"); setError("");
      await api.manualLaps(id, normalized);
      setMode("lap_correlated"); setNotice(`Lap timing saved. ${audio?.original_filename || "Your audio"} is still attached and does not need to be uploaded again.`);
      await load();
    } catch (caught) { setError(caught instanceof ApiError ? caught.message : (caught as Error).message); }
    finally { setBusy(""); }
  }

  async function analyse() {
    if (analyseLock.current || analysing) return;
    analyseLock.current = true;
    try {
      setBusy("analyse"); setError("");
      pollController.current = new AbortController();
      const accepted = await api.analyse(id, mode);
      setJob(accepted);
      const completed = await pollJob(accepted.job_id, setJob, pollController.current.signal);
      if (completed.status === "completed") { setNotice("Analysis complete. Review the source-language transcript and evidence below."); await load(); }
      else setError(completed.error?.message || "Analysis did not complete.");
    } catch (caught) {
      if ((caught as Error).name !== "AbortError") setError(caught instanceof ApiError ? caught.message : (caught as Error).message);
    } finally { setBusy(""); analyseLock.current = false; }
  }

  async function cancel() {
    try {
      pollController.current?.abort();
      const cancelled = await api.cancel(id);
      setJob(cancelled); setNotice("Analysis cancelled. The uploaded audio is unchanged and ready to analyse again.");
      await load();
    } catch (caught) { setError(caught instanceof ApiError ? caught.message : (caught as Error).message); }
  }

  function seek(event: TimelineEvent) {
    setSelected(event);
    if (audioRef.current) { audioRef.current.currentTime = event.timestamp; void audioRef.current.play(); }
  }

  async function download(format: "json" | "csv" | "pdf") {
    try {
      const blob = await api.exportReport(id, format);
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url; link.download = `pitsense-${id}-report.${format}`; link.click();
      URL.revokeObjectURL(url);
    } catch (caught) { setError(caught instanceof ApiError ? caught.message : (caught as Error).message); }
  }

  if (error && !session) return <main className="mx-auto max-w-7xl px-6 py-12"><ErrorBox title={errorHeading(error)} message={error} /></main>;
  if (!session) return <main className="mx-auto max-w-7xl px-6 py-20 text-slate-400">Loading session…</main>;
  const report = session.report;

  return <main className="mx-auto max-w-7xl px-6 py-10">
    <div className="flex flex-wrap items-start justify-between gap-5"><div><div className="eyebrow">Session {String(session.id).padStart(3, "0")} / {session.status}</div><h1 className="mt-2 text-3xl font-bold tracking-tight">{session.name}</h1><p className="mt-2 text-sm text-slate-400">{session.driver_name} · {session.circuit_name} · {session.is_demo ? "Explicit demo fixture" : "Live analysis"}</p></div><div className="flex flex-wrap gap-2"><Button className="border border-line bg-transparent text-slate-200 hover:bg-panel" onClick={() => void load()}><RefreshCw size={15} className="mr-1 inline" />Refresh</Button>{report && <><Button className="border border-line bg-transparent text-slate-200 hover:bg-panel" onClick={() => void download("json")}><FileDown size={15} className="mr-1 inline" />JSON</Button><Button className="border border-line bg-transparent text-slate-200 hover:bg-panel" onClick={() => void download("pdf")}>PDF</Button></>}</div></div>
    {error && <div className="mt-6"><ErrorBox title={errorHeading(error)} message={error} /></div>}
    {notice && <div className="mt-6 rounded-lg border border-cyan/30 bg-cyan/5 px-4 py-3 text-sm text-cyan">{notice}</div>}
    {inputsLocked && <div className="mt-5 rounded-lg border border-amber/30 bg-amber/5 px-4 py-3 text-sm text-amber-200">Audio and lap inputs are locked while analysis runs. Cancel the job before changing the source data.</div>}

    <section className="mt-8 grid gap-5 lg:grid-cols-[1.35fr_.65fr]">
      <div className="panel p-5"><div className="flex items-center justify-between"><div><div className="eyebrow">Step 2 / radio input</div><h2 className="mt-1 text-lg font-bold">Driver channel</h2></div><label className={`rounded-lg border border-line px-3 py-2 text-xs font-semibold ${inputsLocked ? "cursor-not-allowed opacity-50" : "cursor-pointer hover:border-cyan"}`}><UploadCloud size={15} className="mr-1 inline" />{busy === "audio" ? "Uploading…" : audio ? "Replace audio" : "Upload audio"}<input type="file" accept=".wav,.mp3,.m4a,.ogg,audio/*" onChange={uploadAudio} disabled={inputsLocked || busy === "audio"} className="hidden" /></label></div>{audio ? <div className="mt-6" onDragOver={(event) => { if (!inputsLocked) { event.preventDefault(); setIsDragging(true); } }} onDragLeave={() => setIsDragging(false)} onDrop={dropAudio}><div className="mb-2 flex flex-wrap items-center gap-2 text-sm text-slate-300"><FileAudio size={16} className="text-cyan" /><span>{audio.original_filename}</span><span className="text-xs text-slate-500">{audio.duration_seconds != null ? `${audio.duration_seconds.toFixed(2)}s` : browserDuration ? `${browserDuration.toFixed(2)}s` : "Reading duration…"}</span><span className="text-xs text-slate-500">{audio.detected_language ? `source language: ${audio.detected_language}` : "language: detected during analysis"}</span></div>{audioUrl ? <audio ref={audioRef} controls preload="metadata" className="w-full" src={audioUrl} onLoadedMetadata={(event) => setBrowserDuration(Number.isFinite(event.currentTarget.duration) ? event.currentTarget.duration : null)} /> : <div className="rounded-lg border border-line p-5 text-sm text-slate-500">Preparing secure audio preview…</div>}<div className={`mt-3 rounded-lg border border-dashed p-3 text-center text-xs ${isDragging ? "border-cyan text-cyan" : "border-line text-slate-500"}`}>{inputsLocked ? "Audio is locked while analysis runs" : isDragging ? "Release to replace the clip" : "Drop a replacement audio clip here"}</div></div> : <div onDragOver={(event) => { event.preventDefault(); setIsDragging(true); }} onDragLeave={() => setIsDragging(false)} onDrop={dropAudio} className={`mt-6 rounded-lg border border-dashed p-9 text-center text-sm transition ${isDragging ? "border-cyan bg-cyan/10 text-cyan" : "border-line text-slate-500"}`}>{isDragging ? "Release to upload radio clip" : "Drop or select a radio clip to begin."}<div className="mt-2 text-xs text-slate-600">WAV, MP3, M4A, OGG · up to 25 MB · max 15 minutes</div></div>}</div>
      <div className="panel p-5"><div className="eyebrow">Model readiness</div><div className="mt-4 space-y-3 text-sm"><div className="flex justify-between"><span className="text-slate-400">Speech-to-text</span><Badge tone="cyan">Whisper</Badge></div><div className="flex justify-between"><span className="text-slate-400">Transcription mode</span><Badge tone="green">source language</Badge></div><div className="flex justify-between"><span className="text-slate-400">Vocal emotion</span><Badge tone="cyan">backend</Badge></div></div><p className="mt-5 text-xs leading-5 text-slate-500">Normal uploads use backend inference. English-only text signals are never applied to non-English radio.</p></div>
    </section>

    <section className="mt-5 panel p-5"><div className="eyebrow">Step 3 / choose context</div><h2 className="mt-1 text-lg font-bold">How should PitSense analyse this clip?</h2><p className="mt-2 max-w-3xl text-sm leading-6 text-slate-400">Audio-only is correct without authentic lap timing. Lap correlation is optional and never inferred from clip duration.</p><div className="mt-5 grid gap-3 md:grid-cols-2"><ModeCard active={mode === "audio_only"} disabled={inputsLocked} title="Audio-only analysis" description="Transcript, vocal state, and engineer recommendation. No performance claim." onClick={() => setMode("audio_only")} /><ModeCard active={mode === "lap_correlated"} disabled={inputsLocked} title="Add real lap data" description="Compare high-stress evidence with supplied real lap timing." onClick={() => setMode("lap_correlated")} /></div></section>

    {showLaps && <section className="mt-5 panel p-5"><div className="flex flex-wrap items-center justify-between gap-3"><div><div className="eyebrow">Optional lap context</div><h2 className="mt-1 text-lg font-bold">Real timing data</h2></div><div className="flex gap-2"><label className={`rounded-lg border border-line px-3 py-2 text-xs font-semibold ${inputsLocked ? "cursor-not-allowed opacity-50" : "cursor-pointer hover:border-cyan"}`}>Preview CSV<input type="file" accept=".csv,text/csv" onChange={(event) => void previewCsv(event)} disabled={inputsLocked} className="hidden" /></label><a href="/demo-laps.csv" download className="rounded-lg border border-line px-3 py-2 text-xs font-semibold hover:border-cyan">CSV example</a></div></div><div className="mt-3 rounded-lg border border-amber-900/60 bg-amber-950/20 p-3 text-xs leading-5 text-amber-200">Use timing from telemetry or a timing sheet. Audio duration is never used as a lap time.</div>{pendingCsv && <div className="mt-4 rounded-lg border border-cyan/40 bg-cyan/5 p-4"><div className="flex items-center justify-between"><div className="text-sm font-semibold">Preview: {pendingCsv.name}</div><button aria-label="Clear CSV preview" onClick={() => { setPendingCsv(null); setCsvPreview(""); }} disabled={inputsLocked}><X size={16} /></button></div><pre className="mt-3 overflow-x-auto text-xs text-slate-400">{csvPreview}</pre><Button className="mt-3" onClick={() => void confirmCsv()} disabled={busy === "csv" || inputsLocked}>{busy === "csv" ? "Importing…" : "Confirm import"}</Button></div>}<div className="mt-4 overflow-x-auto"><table className="w-full min-w-[650px] text-left text-sm"><thead className="text-xs uppercase tracking-wider text-slate-500"><tr><th className="pb-2">Lap</th><th className="pb-2">Lap time (s)</th><th className="pb-2">Start (s)</th><th className="pb-2">End (s)</th></tr></thead><tbody>{laps.map((lap, index) => <tr key={index} className="border-t border-line/60"><td className="py-2 text-slate-400">{lap.lap_number}</td>{(["lap_time_seconds", "start_timestamp_seconds", "end_timestamp_seconds"] as const).map((key) => <td key={key} className="py-2"><input aria-label={`Lap ${lap.lap_number} ${key}`} type="number" min="0" step="0.001" value={lap[key] ?? ""} onChange={(event) => updateLap(index, key, event.target.value)} disabled={inputsLocked} className="w-36 rounded border border-line bg-ink px-2 py-1.5 text-sm disabled:cursor-not-allowed disabled:opacity-50" /></td>)}</tr>)}</tbody></table></div><div className="mt-4 flex flex-wrap items-center gap-3"><Button className="border border-line bg-transparent text-slate-200 hover:bg-panel" onClick={() => void saveManual()} disabled={inputsLocked || busy === "laps"}>{busy === "laps" ? "Saving…" : "Save manual laps"}</Button><span className="text-xs text-slate-500">Manual values are labelled in the report and should be verified.</span></div></section>}

    {job && analysing && <div className="mt-5"><ProcessingPanel job={job} onCancel={() => void cancel()} /></div>}
    {!analysing && <section className="mt-5 panel flex flex-wrap items-center justify-between gap-5 border-signal/40 p-5"><div><div className="eyebrow">{report ? "Step 4 / refresh evidence" : "Step 4 / start analysis"}</div><h2 className="mt-1 text-xl font-bold">{report ? "Re-analyse original audio" : mode === "audio_only" ? "Analyse audio" : "Analyse with lap correlation"}</h2><p className="mt-2 text-sm text-slate-400">{report ? "Run the selected mode again after changing source data, updating models, or when a legacy report has no detected language." : mode === "audio_only" ? "Transcribe in the spoken language, classify vocal tone, and produce human-reviewable recommendations." : `Use ${audio?.original_filename || "the attached audio"} with the saved lap timestamps. You do not need to upload it again.`}</p></div><Button disabled={!audio || Boolean(busy)} onClick={() => void analyse()}>{busy === "analyse" ? "Starting…" : audio ? report ? "Re-analyse" : "Start analysis" : "Upload audio first"}</Button></section>}
    {report && <ResultsDashboard report={report} timeline={timeline} chartData={chartData} selected={selected} onSelect={seek} onDownload={download} />}
  </main>;
}

function ModeCard({ active, disabled, title, description, onClick }: { active: boolean; disabled: boolean; title: string; description: string; onClick: () => void }) {
  return <button type="button" disabled={disabled} onClick={onClick} className={`rounded-lg border p-4 text-left transition disabled:cursor-not-allowed disabled:opacity-50 ${active ? "border-cyan bg-cyan/10" : "border-line hover:border-cyan"}`}><div className="font-semibold">{title} {active && <Badge tone="cyan">selected</Badge>}</div><div className="mt-2 text-xs leading-5 text-slate-400">{description}</div></button>;
}
