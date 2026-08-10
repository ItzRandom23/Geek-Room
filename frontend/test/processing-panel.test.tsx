import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { AnalysisJob } from "../lib/api";
import { getProcessingState, ProcessingPanel } from "../components/processing-panel";

function job(overrides: Partial<AnalysisJob> = {}): AnalysisJob {
  return {
    job_id: "job-1",
    session_id: 1,
    mode: "audio_only",
    status: "running",
    phase: "extracting_features",
    progress: 46,
    attempts: 1,
    retryable: true,
    error: null,
    created_at: "2026-08-09T00:00:00Z",
    started_at: "2026-08-09T00:00:01Z",
    completed_at: null,
    ...overrides,
  };
}

describe("processing panel", () => {
  it("maps real job phases and clamps progress", () => {
    expect(getProcessingState(job()).activeIndex).toBe(2);
    expect(getProcessingState(job({ progress: 140 })).progress).toBe(100);
  });

  it("renders an accessible running state with cancellation", () => {
    const html = renderToStaticMarkup(<ProcessingPanel job={job()} onCancel={() => undefined} />);
    expect(html).toContain('role="status"');
    expect(html).toContain('aria-live="polite"');
    expect(html).toContain("Reading vocal and acoustic cues");
    expect(html).toContain("Cancel analysis");
  });

  it("renders failed and cancelled terminal states without a cancel action", () => {
    const failed = renderToStaticMarkup(<ProcessingPanel job={job({ status: "failed", phase: "failed", error: { code: "MODEL_UNAVAILABLE", message: "Model unavailable", retryable: true } })} onCancel={() => undefined} />);
    const cancelled = renderToStaticMarkup(<ProcessingPanel job={job({ status: "cancelled", phase: "cancelled" })} onCancel={() => undefined} />);
    expect(failed).toContain("Analysis interrupted");
    expect(failed).toContain("Model unavailable");
    expect(cancelled).toContain("Analysis cancelled");
    expect(cancelled).not.toContain("Cancel analysis</button>");
  });
});
