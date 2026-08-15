"use client";

import { useMemo, useState } from "react";
import { AlertTriangle, BarChart3, CheckCircle2, Clipboard, FileDown, Languages, Search, Waves } from "lucide-react";
import { CartesianGrid, ComposedChart, Line, ResponsiveContainer, Scatter, Tooltip, XAxis, YAxis } from "recharts";
import { Report, ReportEvent, TimelineEvent, Transcript } from "../lib/api";
import { Badge, Button } from "./ui";

const labels = ["calm", "positive", "subdued", "stressed", "tired", "frustrated", "urgent", "uncertain"];

type Props = {
  report: Report;
  timeline: { events: TimelineEvent[]; transcript?: Transcript[] };
  chartData: { lap_number: number; time: number }[];
  selected: TimelineEvent | null;
  onSelect: (event: TimelineEvent) => void;
  onDownload: (format: "json" | "csv" | "pdf") => void;
};

const formatTime = (value: number | null | undefined) => {
  const seconds = Math.max(0, Number(value || 0));
  const minutes = Math.floor(seconds / 60);
  return `${String(minutes).padStart(2, "0")}:${(seconds % 60).toFixed(1).padStart(4, "0")}`;
};

const eventToTimeline = (event: ReportEvent): TimelineEvent => ({
  timestamp: event.start_seconds,
  end_timestamp: event.end_seconds,
  label: event.label,
  confidence: event.confidence,
  transcript: event.transcript,
  lap_number: event.lap_number,
  recommendation: null,
});

export function ResultsDashboard({ report, timeline, chartData, selected, onSelect, onDownload }: Props) {
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState("all");
  const language = report.summary?.language || report.provenance?.language || "und";
  const transcript = report.timestamped_transcript?.length
    ? report.timestamped_transcript
    : (timeline.transcript || []).map((segment) => ({ start_seconds: segment.start_seconds, end_seconds: segment.end_seconds, text: segment.text }));
  const reportEvents: ReportEvent[] = report.timestamped_events?.length
    ? report.timestamped_events
    : timeline.events.map((event) => ({ start_seconds: event.timestamp, end_seconds: event.end_timestamp || event.timestamp, duration_seconds: Math.max(0, (event.end_timestamp || event.timestamp) - event.timestamp), label: event.label, severity: "info", confidence: event.confidence, transcript: event.transcript, source: "legacy", lap_number: event.lap_number, matched_lap: event.lap_number !== null }));
  const displayedTranscript = useMemo(() => transcript.filter((segment) => !search || segment.text.toLocaleLowerCase().includes(search.toLocaleLowerCase())), [search, transcript]);
  const displayedEvents = useMemo(() => reportEvents.filter((event) => (filter === "all" || event.label === filter) && (!search || event.transcript.toLocaleLowerCase().includes(search.toLocaleLowerCase()))), [filter, reportEvents, search]);
  const distribution = report.state_distribution || labels.map((label) => ({ label, event_count: reportEvents.filter((event) => event.label === label).length, duration_seconds: 0, average_confidence: 0 }));
  const risk = report.summary?.highest_risk_event;
  const dominant = report.summary?.dominant_state;
  const confidence = Math.round((report.confidence || 0) * 100);
  const riskConfidence = Math.round((risk?.confidence || 0) * 100);
  const lapSummary = report.lap_summary;
  const analyzer = report.provenance?.audio_analyzer;
  const benchmarkMetrics = analyzer?.benchmark?.metrics;
  const baselineMetrics = analyzer?.benchmark?.baseline_metrics;
  const analyzerSupportsLanguage = !analyzer || analyzer.language_scope?.includes("multilingual") || analyzer.language_scope?.includes(language.split("-", 1)[0]);
  const languageCoverage = analyzer?.benchmark?.language_coverage?.[language.split("-", 1)[0]];

  const copyRecommendation = async () => {
    const recommendation = report.recommendations[0]?.recommendation;
    if (!recommendation || !navigator.clipboard) return;
    try {
      await navigator.clipboard.writeText(recommendation);
    } catch {
      // Clipboard access is optional; the report remains fully usable without it.
    }
  };

  return <section className="mt-5 space-y-5" aria-label="Analysis report">
    <div className="flex flex-wrap items-center gap-2">
      <CheckCircle2 className="text-emerald-400" size={18} />
      <div className="eyebrow">Step 6 / operational report</div>
      <Badge tone={report.analysis_mode === "lap_correlated" ? "cyan" : "slate"}>{report.analysis_mode === "lap_correlated" ? "lap-correlated" : "audio-only"}</Badge>
      {report.schema_version !== 2 && <Badge tone="amber">legacy evidence</Badge>}
    </div>

    <div className="grid gap-4 lg:grid-cols-[1.35fr_.65fr]">
      <div className="panel overflow-hidden p-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="eyebrow">Analysis complete</div>
            <h2 className="mt-2 text-xl font-bold">Original-language radio evidence</h2>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-400">The timestamped radio below is transcribed in the driver&apos;s source language. It is never translated for display.</p>
          </div>
          <div className="rounded-lg border border-cyan/30 bg-cyan/5 px-3 py-2 text-right">
            <div className="flex items-center justify-end gap-2 text-xs uppercase tracking-wide text-cyan"><Languages size={14} />Language</div>
            <div className="mt-1 font-mono text-lg font-bold text-white">{language}</div>
          </div>
        </div>
        <div className="mt-5 grid gap-3 sm:grid-cols-3">
          <Metric label="Overall state" value={report.primary_state} detail={`${confidence}% confidence`} tone="cyan" />
          <Metric label="Highest-risk event" value={risk?.label || "none"} detail={risk ? `${riskConfidence}% confidence / ${formatTime(risk.duration_seconds)}` : "No reportable event"} tone="signal" />
          <Metric label="Speech coverage" value={formatTime(report.data_quality?.speech_coverage_seconds)} detail={`${report.summary?.event_count || 0} reportable events`} tone="green" />
        </div>
        {language === "und" && <div className="mt-4 rounded-lg border border-amber-400/35 bg-amber-400/5 p-3 text-sm text-amber-100">Source language was not available in this legacy evidence. Re-analyse the unchanged clip before relying on language-dependent signals.</div>}
        {risk && <div className="mt-5 rounded-lg border border-signal/40 bg-signal/5 p-4">
          <div className="flex flex-wrap items-center justify-between gap-3"><div className="flex items-center gap-2"><AlertTriangle size={17} className="text-signal" /><strong className="capitalize">{risk.label} evidence</strong><Badge tone={risk.severity === "critical" || risk.severity === "high" ? "red" : "amber"}>{risk.severity}</Badge></div><span className="font-mono text-xs text-slate-400">{formatTime(risk.start_seconds)} - {formatTime(risk.end_seconds)}</span></div>
          <p className="mt-3 text-sm leading-6 text-slate-200" dir="auto">{risk.transcript || "No transcript excerpt overlaps this event."}</p>
        </div>}
      </div>

      <div className="panel p-5">
        <div className="flex items-center justify-between"><div><div className="eyebrow">Data quality</div><h2 className="mt-1 text-lg font-bold">Analysis context</h2></div><Waves className="text-cyan" size={20} /></div>
        <dl className="mt-5 space-y-3 text-sm"><QualityRow label="Audio duration" value={formatTime(report.data_quality?.audio_duration_seconds)} /><QualityRow label="Transcript lines" value={String(report.data_quality?.transcript_segment_count ?? transcript.length)} /><QualityRow label="Text signals" value={report.data_quality?.text_signals_applied ? "English only" : "Audio-led"} /><QualityRow label="Processing" value={report.provenance?.processing_time_ms ? `${(report.provenance.processing_time_ms / 1000).toFixed(1)}s` : "Not recorded"} /></dl>
        <p className="mt-5 border-t border-line pt-4 text-xs leading-5 text-slate-500">Vocal-state classification supports race engineering review. It is not a medical or psychological diagnosis.</p>
      </div>
    </div>

    {analyzer && <div className="panel p-5"><div className="flex flex-wrap items-start justify-between gap-4"><div><div className="eyebrow">Analyzer provenance</div><h2 className="mt-1 text-lg font-bold">{analyzer.candidate_id}</h2><p className="mt-2 text-xs text-slate-400">{analyzer.promotion_state === "signed_promoted" ? "Activated only after signed, held-out benchmark gates passed." : "Baseline analyzer; no external candidate has been promoted."}</p></div><Badge tone={analyzer.promotion_state === "signed_promoted" ? "green" : "slate"}>{analyzer.promotion_state || "unknown"}</Badge></div><dl className="mt-5 grid gap-3 text-sm sm:grid-cols-2 xl:grid-cols-5"><QualityRow label="Backbone" value={analyzer.backbone || "not recorded"} /><QualityRow label="Revision" value={analyzer.model_revision || "configured default"} /><QualityRow label="Calibration" value={analyzer.calibration_version || "not applicable"} /><QualityRow label="Pilot coverage" value={languageCoverage ? `${languageCoverage.clips} clips / ${languageCoverage.speakers} speakers` : "not benchmarked"} /><QualityRow label="Held-out macro F1" value={analyzer.benchmark?.metrics?.macro_f1 != null ? `${Math.round(analyzer.benchmark.metrics.macro_f1 * 100)}%` : "not measured"} /></dl></div>}

    {analyzer && language !== "und" && !analyzerSupportsLanguage && <div role="alert" className="rounded-lg border border-amber-400/35 bg-amber-400/5 p-4 text-sm text-amber-100">This analyzer has not been benchmark-qualified for <strong>{language}</strong>. Treat its state labels as unverified until the language pilot reaches 100 adjudicated clips from 10 speakers.</div>}

    {benchmarkMetrics && baselineMetrics && <div className="panel p-5"><div className="eyebrow">Held-out benchmark scorecard</div><h2 className="mt-1 text-lg font-bold">Candidate versus production baseline</h2><div className="mt-4 grid gap-3 sm:grid-cols-2"><Metric label="Active candidate macro F1" value={`${Math.round((benchmarkMetrics.macro_f1 || 0) * 100)}%`} detail={`coverage ${Math.round((benchmarkMetrics.prediction_coverage || 0) * 100)}%`} tone="green" /><Metric label="Baseline macro F1" value={`${Math.round((baselineMetrics.macro_f1 || 0) * 100)}%`} detail={`coverage ${Math.round((baselineMetrics.prediction_coverage || 0) * 100)}%`} tone="slate" /></div><p className="mt-3 text-xs text-slate-500">This comparison uses the speaker-held-out race-radio test split. Public-corpus results are tracked separately and never promote a model.</p></div>}

    {report.provenance?.validation_accuracy != null && <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-emerald-400/25 bg-emerald-400/5 px-4 py-3"><div><div className="font-mono text-[10px] uppercase text-emerald-300">Promoted model benchmark</div><p className="mt-1 text-xs text-slate-400">Held-out validation accuracy, separate from this clip&apos;s confidence.</p></div><div className="flex items-baseline gap-3"><strong className="font-display text-2xl text-emerald-300">{Math.round(report.provenance.validation_accuracy * 10000) / 100}%</strong><span className="text-xs text-slate-500">coverage {Math.round((report.provenance.prediction_coverage || 0) * 100)}%</span></div></div>}

    <div className="panel p-5">
      <div className="flex flex-wrap items-center justify-between gap-3"><div><div className="eyebrow">Duration-aware state mix</div><h2 className="mt-1 text-lg font-bold">Merged vocal-state evidence</h2></div><BarChart3 className="text-cyan" size={20} /></div>
      <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">{distribution.map((item) => <div className="rounded-lg border border-line bg-ink/50 p-3" key={item.label}><div className="flex justify-between gap-3 text-xs capitalize text-slate-400"><span>{item.label}</span><span>{item.event_count} event{item.event_count === 1 ? "" : "s"}</span></div><div className="mt-2 flex items-end justify-between gap-3"><strong className="text-2xl">{formatTime(item.duration_seconds)}</strong><span className="text-xs text-slate-500">{Math.round(item.average_confidence * 100)}% avg.</span></div></div>)}</div>
    </div>

    {report.correlation_available ? <div className="panel p-5"><div className="flex flex-wrap items-center justify-between gap-3"><div><div className="eyebrow">Synchronized timeline</div><h2 className="mt-1 text-lg font-bold">Lap performance and radio evidence</h2></div><div className="text-xs text-amber-300">{report.association_notice}</div></div><div className="mt-5 h-[330px] w-full"><ResponsiveContainer width="100%" height="100%"><ComposedChart data={chartData} margin={{ top: 10, right: 20, left: 0, bottom: 5 }}><CartesianGrid stroke="#28313b" strokeDasharray="3 3" /><XAxis type="number" dataKey="lap_number" stroke="#718096" tickFormatter={(value) => `L${value}`} /><YAxis stroke="#718096" domain={["dataMin - 1", "dataMax + 1"]} tickFormatter={(value) => `${value}s`} /><Tooltip contentStyle={{ background: "#11161c", border: "1px solid #28313b", borderRadius: 8 }} /><Line type="monotone" dataKey="time" stroke="#62d5d0" strokeWidth={3} dot={{ r: 4, fill: "#62d5d0" }} /><Scatter data={displayedEvents.filter((event) => event.lap_number !== null).map((event) => ({ lap_number: event.lap_number, time: chartData.find((row) => row.lap_number === event.lap_number)?.time || 0, event }))} dataKey="time" fill="#ef4d4d" onClick={(entry) => { const event = (entry as { event?: ReportEvent })?.event; if (event) onSelect(eventToTimeline(event)); }} name="radio event" /></ComposedChart></ResponsiveContainer></div>{lapSummary && <div className="mt-4 grid gap-3 text-sm sm:grid-cols-4"><Metric label="Median lap" value={`${lapSummary.median_lap_time_seconds}s`} detail={`${lapSummary.lap_count} real laps`} tone="cyan" /><Metric label="Best lap" value={`${lapSummary.best_lap_time_seconds}s`} detail="session best" tone="green" /><Metric label="Worst lap" value={`${lapSummary.worst_lap_time_seconds}s`} detail="session worst" tone="signal" /><Metric label="Timing window" value={`${formatTime(lapSummary.timing_start_seconds)} - ${formatTime(lapSummary.timing_end_seconds)}`} detail="supplied timing" tone="slate" /></div>}</div> : <div className="panel p-5"><div className="eyebrow">Lap performance</div><h2 className="mt-1 text-lg font-bold">No performance conclusion</h2><p className="mt-2 text-sm leading-6 text-slate-400">Import authentic timing data and re-run analysis to unlock lap context. Audio-only reports intentionally do not infer lap performance.</p></div>}

    <div className="panel p-5">
      <div className="flex flex-wrap items-center justify-between gap-3"><div><div className="eyebrow">Transcript and evidence review</div><h2 className="mt-1 text-lg font-bold">Timestamped radio</h2></div><div className="flex flex-wrap gap-2"><div className="relative"><Search size={15} className="absolute left-2 top-2.5 text-slate-500" /><input aria-label="Search transcript" placeholder="Search source-language radio" value={search} onChange={(event) => setSearch(event.target.value)} className="w-56 rounded border border-line bg-ink py-2 pl-8 pr-2 text-xs" /></div><select aria-label="Filter emotion events" value={filter} onChange={(event) => setFilter(event.target.value)} className="rounded border border-line bg-ink px-2 py-2 text-xs"><option value="all">All states</option>{labels.map((label) => <option key={label} value={label}>{label}</option>)}</select></div></div>
      <div className="mt-5 grid gap-5 lg:grid-cols-[1.15fr_.85fr]"><div className="space-y-2">{displayedTranscript.length ? displayedTranscript.map((segment, index) => <button type="button" key={`${segment.start_seconds}-${index}`} onClick={() => onSelect({ timestamp: segment.start_seconds, end_timestamp: segment.end_seconds, label: "transcript", confidence: 1, transcript: segment.text, lap_number: null, recommendation: null })} className={`flex w-full gap-4 rounded-lg border p-3 text-left text-sm transition ${selected && selected.timestamp >= segment.start_seconds && selected.timestamp <= segment.end_seconds ? "border-cyan bg-cyan/5" : "border-line hover:border-cyan"}`}><span className="w-24 shrink-0 font-mono text-xs text-cyan">{formatTime(segment.start_seconds)} - {formatTime(segment.end_seconds)}</span><span dir="auto">{segment.text}</span></button>) : <div className="text-sm text-slate-500">No transcript lines match this search.</div>}</div><div className="space-y-3">{displayedEvents.length ? displayedEvents.map((event) => <button type="button" key={`${event.start_seconds}-${event.label}`} onClick={() => onSelect(eventToTimeline(event))} className="w-full rounded-lg border border-line p-4 text-left transition hover:border-cyan"><div className="flex flex-wrap items-center justify-between gap-2"><div className="flex items-center gap-2"><Badge tone={event.severity === "critical" || event.severity === "high" ? "red" : "amber"}>{event.severity}</Badge><strong className="capitalize">{event.label}</strong></div><span className="font-mono text-xs text-slate-400">{formatTime(event.start_seconds)} - {formatTime(event.end_seconds)}</span></div><p className="mt-2 text-xs leading-5 text-slate-400" dir="auto">{event.transcript || "No overlapping transcript excerpt."}</p></button>) : <div className="rounded-lg border border-line p-4 text-sm text-slate-500">No evidence events match this filter.</div>}<div className="border-t border-line pt-3">{report.recommendations.map((insight) => <article className="mb-3 rounded-lg border border-line p-4" key={insight.id || insight.title}><div className="flex items-center gap-2"><AlertTriangle size={16} className={insight.severity === "critical" || insight.severity === "high" ? "text-signal" : "text-amber"} /><strong>{insight.title}</strong></div><p className="mt-2 text-xs leading-5 text-slate-400">{insight.explanation}</p><p className="mt-2 text-sm font-semibold">{insight.recommendation}</p></article>)}</div><div className="flex flex-wrap gap-2"><Button className="border border-line bg-transparent text-slate-200 hover:bg-panel" onClick={() => onDownload("json")}><FileDown size={15} className="mr-2 inline" />JSON</Button><Button className="border border-line bg-transparent text-slate-200 hover:bg-panel" onClick={() => onDownload("csv")}>CSV</Button><Button className="border border-line bg-transparent text-slate-200 hover:bg-panel" onClick={() => onDownload("pdf")}>PDF</Button><button onClick={() => void copyRecommendation()} className="inline-flex items-center gap-2 rounded-lg border border-line px-3 py-2 text-sm text-slate-300 hover:border-cyan"><Clipboard size={14} />Copy recommendation</button></div></div></div>
    </div>
  </section>;
}

function Metric({ label, value, detail, tone }: { label: string; value: string; detail: string; tone: "signal" | "cyan" | "green" | "slate" }) {
  const toneClass = { signal: "border-signal/35 bg-signal/5", cyan: "border-cyan/30 bg-cyan/5", green: "border-emerald-400/30 bg-emerald-400/5", slate: "border-line bg-ink/40" }[tone];
  return <div className={`rounded-lg border p-3 ${toneClass}`}><div className="text-[10px] uppercase tracking-wider text-slate-400">{label}</div><div className="mt-1 truncate text-lg font-bold capitalize">{value}</div><div className="mt-1 text-xs text-slate-500">{detail}</div></div>;
}

function QualityRow({ label, value }: { label: string; value: string }) {
  return <div className="flex items-center justify-between gap-3"><dt className="text-slate-400">{label}</dt><dd className="font-mono text-xs text-slate-200">{value}</dd></div>;
}
