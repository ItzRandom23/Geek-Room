"use client";

import { useEffect, useMemo, useState } from "react";
import { AudioWaveform, BrainCircuit, Check, CircleDashed, Clock3, Gauge, Radio, ScanLine, ShieldCheck, XCircle } from "lucide-react";
import { AnalysisJob } from "../lib/api";
import { GhostButton } from "./ui";

export const processingPhases = [
  { id: "decoding", label: "Decode", detail: "Preparing the radio signal", icon: Radio },
  { id: "transcribing", label: "Transcript", detail: "Resolving spoken context", icon: AudioWaveform },
  { id: "extracting_features", label: "Features", detail: "Reading vocal and acoustic cues", icon: ScanLine },
  { id: "classifying", label: "Classify", detail: "Comparing trained driver states", icon: BrainCircuit },
  { id: "calibrating", label: "Calibrate", detail: "Applying the confidence gate", icon: Gauge },
  { id: "correlating", label: "Correlate", detail: "Aligning events with lap context", icon: ShieldCheck },
] as const;

export function getProcessingState(job: AnalysisJob) {
  const progress = Math.max(0, Math.min(100, job.progress ?? 0));
  const phaseIndex = processingPhases.findIndex((phase) => phase.id === job.phase);
  const activeIndex = phaseIndex >= 0 ? phaseIndex : job.status === "queued" ? -1 : processingPhases.length - 1;
  const terminal = ["completed", "failed", "cancelled"].includes(job.status);
  return { progress, activeIndex, terminal };
}

const phaseCeilings: Record<string, number> = {
  queued: 9,
  decoding: 23,
  transcribing: 45,
  extracting_features: 67,
  classifying: 81,
  calibrating: 89,
  correlating: 99,
};

function elapsedLabel(startedAt: string | null, now: number) {
  if (!startedAt) return "Waiting for worker";
  const hasTimezone = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(startedAt);
  const started = new Date(hasTimezone ? startedAt : `${startedAt}Z`).getTime();
  const elapsed = Math.max(0, Math.floor((now - started) / 1000));
  const minutes = Math.floor(elapsed / 60);
  const seconds = elapsed % 60;
  return minutes ? `${minutes}m ${String(seconds).padStart(2, "0")}s elapsed` : `${seconds}s elapsed`;
}

export function ProcessingPanel({ job, onCancel }: { job: AnalysisJob; onCancel: () => void }) {
  const { progress, activeIndex } = getProcessingState(job);
  const running = job.status === "queued" || job.status === "running";
  const failed = job.status === "failed";
  const cancelled = job.status === "cancelled";
  const activePhase = processingPhases[activeIndex];
  const statusTitle = failed ? "Analysis interrupted" : cancelled ? "Analysis cancelled" : activePhase?.detail || "Waiting for the analysis worker";
  const [displayProgress, setDisplayProgress] = useState(progress);
  const [now, setNow] = useState(() => Date.now());
  const ceiling = phaseCeilings[job.phase] ?? progress;

  useEffect(() => {
    setDisplayProgress((current) => job.status === "completed" ? 100 : Math.max(current, progress));
  }, [job.job_id, job.status, progress]);

  useEffect(() => {
    if (!running) return;
    const timer = window.setInterval(() => {
      setNow(Date.now());
      setDisplayProgress((current) => {
        const floor = Math.max(current, progress);
        if (floor >= ceiling) return floor;
        return Math.min(ceiling, floor + Math.max(0.18, (ceiling - floor) * 0.045));
      });
    }, 650);
    return () => window.clearInterval(timer);
  }, [ceiling, progress, running]);

  const displayedPercent = Math.round(displayProgress);
  const confirmedSteps = Math.max(0, activeIndex);
  const duration = useMemo(() => elapsedLabel(job.started_at, now), [job.started_at, now]);
  const waitingOnModel = running && ["transcribing", "extracting_features"].includes(job.phase);

  useEffect(() => {
    setDisplayProgress(progress);
  }, [job.job_id]);

  return (
    <section
      role="status"
      aria-live="polite"
      aria-atomic="true"
      className={`analysis-processing panel glass-edge mt-5 overflow-hidden ${failed ? "analysis-processing-error" : ""}`}
    >
      <div className="analysis-processing-head">
        <div className="min-w-0">
          <div className="eyebrow">Live radio analysis</div>
          <div className="mt-3 flex flex-wrap items-center gap-3">
            {failed || cancelled ? <XCircle size={22} className={failed ? "text-signal" : "text-slate-400"} /> : null}
            <h2 className="text-2xl font-bold">{statusTitle}</h2>
            {running && <span className="analysis-live-pill"><span />Worker active</span>}
          </div>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-400">
            {failed
              ? job.error?.message || "The worker could not complete this analysis."
              : cancelled
                ? "The uploaded audio is unchanged and ready to analyse again."
                : waitingOnModel
                  ? "The models are reading speech and vocal cues. A first run can take longer while Hugging Face weights initialise."
                  : "Transcript, vocal state, confidence, and optional lap context are assembled into one reviewable result."}
          </p>
        </div>
        <div className="flex shrink-0 flex-wrap items-center gap-3">
          <div className="analysis-clock"><Clock3 size={14} />{duration}</div>
          {running && <GhostButton onClick={onCancel}>Cancel analysis</GhostButton>}
        </div>
      </div>

      <div className="analysis-progress-card" aria-label={`${displayedPercent}% estimated complete`}>
        <div className="analysis-progress-copy">
          <strong>{displayedPercent}%</strong>
          <span>Estimated overall progress</span>
        </div>
        <div className="analysis-progress-track" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={displayedPercent} aria-valuetext={`${activePhase?.label || "Queued"}, ${displayedPercent}% estimated`}>
          <div className="analysis-progress" style={{ width: `${displayProgress}%` }}><span /></div>
        </div>
        <div className="analysis-progress-meta"><span>{confirmedSteps} of {processingPhases.length} stages complete</span></div>
      </div>

      <ol className="analysis-phases" aria-label="Analysis phases">
        {processingPhases.map((phase, index) => {
          const complete = job.status === "completed" || index < activeIndex;
          const active = running && index === activeIndex;
          const Icon = phase.icon;
          return (
            <li key={phase.id} className={`analysis-phase ${complete ? "is-complete" : ""} ${active ? "is-active" : ""}`}>
              <span className="analysis-phase-icon">{complete ? <Check size={14} /> : active ? <Icon size={14} /> : <CircleDashed size={14} />}</span>
              <span className="min-w-0"><strong>{phase.label}</strong><small>{phase.detail}</small></span>
            </li>
          );
        })}
      </ol>
      <p className="analysis-progress-note">The percentage between worker checkpoints is an estimate. The highlighted stage is the confirmed backend state.</p>
    </section>
  );
}
