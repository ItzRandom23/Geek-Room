import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

vi.mock("recharts", async () => {
  const React = await import("react");
  const Box = ({ children }: { children?: React.ReactNode }) => React.createElement("div", null, children);
  return { CartesianGrid: Box, ComposedChart: Box, Line: Box, ResponsiveContainer: Box, Scatter: Box, Tooltip: Box, XAxis: Box, YAxis: Box };
});

import { ResultsDashboard } from "../components/results-dashboard";
import { Report } from "../lib/api";

const report: Report = {
  schema_version: 2,
  primary_state: "stressed",
  confidence: 0.87,
  transcript: "ब्रेक ठीक नहीं है",
  timestamped_transcript: [{ start_seconds: 0, end_seconds: 1.2, text: "ब्रेक ठीक नहीं है" }],
  timestamped_events: [{ start_seconds: 0, end_seconds: 1.2, duration_seconds: 1.2, label: "stressed", severity: "high", confidence: 0.87, transcript: "ब्रेक ठीक नहीं है", source: "audio-baseline", lap_number: null, matched_lap: false }],
  summary: { language: "hi", dominant_state: { label: "stressed", confidence: 0.87, duration_seconds: 1.2 }, highest_risk_event: { start_seconds: 0, end_seconds: 1.2, duration_seconds: 1.2, label: "stressed", severity: "high", confidence: 0.87, transcript: "ब्रेक ठीक नहीं है", source: "audio-baseline", lap_number: null, matched_lap: false }, event_count: 1, speech_coverage_seconds: 1.2 },
  data_quality: { audio_duration_seconds: 3, transcript_segment_count: 1, speech_coverage_seconds: 1.2, text_signals_applied: false },
  state_distribution: [{ label: "stressed", event_count: 1, duration_seconds: 1.2, average_confidence: 0.87 }],
  correlations: [],
  performance_by_state: [],
  lap_summary: null,
  recommendations: [{ id: 1, type: "review", severity: "low", title: "Manual review", explanation: "Verify the radio.", recommendation: "Listen to the clip.", supporting_data: {} }],
  analysis_mode: "audio_only",
  correlation_available: false,
  association_notice: "Audio-only analysis: no lap-performance conclusion was made.",
  provenance: { models: { stt: "whisper-small" }, language: "hi", transcription_task: "transcribe", text_signals_applied: false, generated_at: "2026-08-10T00:00:00Z", analysis_version: "2", audio_analyzer: { candidate_id: "meralion-ser-v1", model_revision: "abc123", calibration_version: "cal-001", language_scope: ["en", "zh"], promotion_state: "signed_promoted", benchmark: { metrics: { macro_f1: 0.82, prediction_coverage: 0.8 }, baseline_metrics: { macro_f1: 0.7, prediction_coverage: 0.78 } } } },
};

describe("results dashboard", () => {
  it("renders original-language timestamped radio and no audio-only lap claim", () => {
    const html = renderToStaticMarkup(<ResultsDashboard report={report} timeline={{ events: [], transcript: [] }} chartData={[]} selected={null} onSelect={() => undefined} onDownload={() => undefined} />);
    expect(html).toContain("source language");
    expect(html).toContain("hi");
    expect(html).toContain("ब्रेक ठीक नहीं है");
    expect(html).toContain("00:00.0 - 00:01.2");
    expect(html).toContain("No performance conclusion");
    expect(html).toContain("Analyzer provenance");
    expect(html).toContain("signed_promoted");
    expect(html).toContain("82%");
    expect(html).toContain("Candidate versus production baseline");
    expect(html).toContain("not been benchmark-qualified for");
  });
});
