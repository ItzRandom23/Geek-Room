import statistics
from dataclasses import dataclass
from typing import Iterable, Sequence

from .labels import NORMALIZED


HIGH_STRESS = {"stressed", "frustrated", "urgent"}
URGENCY_WORDS = {"box", "smoke", "fire", "unsafe", "damage", "urgent", "now", "push", "problem", "tyre", "tire"}
RISK_ORDER = {"uncertain": 0, "calm": 1, "positive": 1, "subdued": 2, "tired": 2, "stressed": 3, "frustrated": 4, "urgent": 5}


@dataclass
class Event:
    label: str
    confidence: float
    start: float
    end: float
    transcript: str = ""
    source: str = "audio"


def urgency_score(text: str) -> float:
    words = {word.strip(".,!?;:").lower() for word in text.split()}
    return min(1.0, len(words & URGENCY_WORDS) / 2)


def active_lap(laps: Iterable, timestamp: float):
    ordered = sorted(laps, key=lambda lap: lap.lap_number)
    for lap in ordered:
        if lap.start_timestamp_seconds <= timestamp <= lap.end_timestamp_seconds:
            return lap
    return None


def interval_overlap(start_a: float, end_a: float, start_b: float, end_b: float) -> float:
    return max(0.0, min(end_a, end_b) - max(start_a, start_b))


def event_lap(laps: Iterable, event: Event):
    """Choose the real lap with the greatest overlap, not merely the window start."""
    ordered = sorted(laps, key=lambda lap: lap.lap_number)
    overlaps = [(interval_overlap(event.start, event.end, lap.start_timestamp_seconds, lap.end_timestamp_seconds), lap) for lap in ordered]
    matching = [(overlap, lap) for overlap, lap in overlaps if overlap > 0]
    if matching:
        return max(matching, key=lambda item: item[0])[1]
    return active_lap(ordered, event.start)


def _field(item, name: str, default=None):
    if isinstance(item, dict):
        return item.get(name, default)
    return getattr(item, name, default)


def overlapping_text(segments: Sequence, start: float, end: float) -> str:
    """Return the source-language transcript evidence that overlaps an event window."""
    values = []
    for segment in segments:
        segment_start = float(_field(segment, "start_seconds", 0))
        segment_end = float(_field(segment, "end_seconds", segment_start))
        if interval_overlap(start, end, segment_start, segment_end) > 0 or (start == end == segment_start):
            text = str(_field(segment, "text", "")).strip()
            if text and text not in values:
                values.append(text)
    return " ".join(values)


def merge_events(events: Sequence[Event], max_gap_seconds: float = 0.75) -> list[Event]:
    """Merge overlapping sliding-window predictions into reportable evidence events."""
    merged: list[Event] = []
    for event in sorted(events, key=lambda item: (item.label, item.start, item.end)):
        event_end = max(event.end, event.start)
        if merged and merged[-1].label == event.label and event.start <= merged[-1].end + max_gap_seconds:
            current = merged[-1]
            duration_current = max(0.05, current.end - current.start)
            duration_event = max(0.05, event_end - event.start)
            confidence = ((current.confidence * duration_current) + (event.confidence * duration_event)) / (duration_current + duration_event)
            evidence = [value for value in (current.transcript, event.transcript) if value]
            current.end = max(current.end, event_end)
            current.confidence = round(confidence, 4)
            current.transcript = " ".join(dict.fromkeys(evidence))
            current.source = "+".join(sorted(set((current.source + "+" + event.source).split("+"))))
        else:
            merged.append(Event(event.label, event.confidence, event.start, event_end, event.transcript, event.source))
    return sorted(merged, key=lambda item: (item.start, item.end, item.label))


def _next_lap(ordered_laps: list, lap):
    try:
        index = ordered_laps.index(lap)
    except ValueError:
        return None
    return ordered_laps[index + 1] if index + 1 < len(ordered_laps) else None


def correlate_events(events: list[Event], laps: list, stress_threshold: float = 0.55) -> list[dict]:
    if not laps:
        return []
    median = statistics.median(lap.lap_time_seconds for lap in laps)
    ordered = sorted(laps, key=lambda lap: lap.lap_number)
    correlations = []
    for event in events:
        if event.label not in HIGH_STRESS or event.confidence < stress_threshold:
            continue
        lap = event_lap(ordered, event)
        row = {
            "event_timestamp": round(event.start, 3),
            "event_end_timestamp": round(event.end, 3),
            "label": event.label,
            "confidence": round(event.confidence, 3),
            "matched": lap is not None,
            "lap_number": None,
            "current_lap_delta_seconds": None,
            "next_lap_number": None,
            "next_lap_delta_seconds": None,
            "deterioration": None,
            "transcript": event.transcript,
        }
        if lap is not None:
            next_lap = _next_lap(ordered, lap)
            row.update({
                "lap_number": lap.lap_number,
                "current_lap_delta_seconds": round(lap.lap_time_seconds - median, 3),
                "next_lap_number": next_lap.lap_number if next_lap else None,
                "next_lap_delta_seconds": round(next_lap.lap_time_seconds - median, 3) if next_lap else None,
                "deterioration": bool(next_lap and next_lap.lap_time_seconds > median),
            })
        correlations.append(row)
    return correlations


def performance_by_state(events: list[Event], laps: list) -> list[dict]:
    if not laps:
        return []
    median = statistics.median(lap.lap_time_seconds for lap in laps)
    merged = merge_events(events)
    buckets: dict[str, dict[int, object]] = {label: {} for label in NORMALIZED}
    event_counts: dict[str, int] = {label: 0 for label in NORMALIZED}
    for event in merged:
        lap = event_lap(laps, event)
        if lap:
            event_counts[event.label] = event_counts.get(event.label, 0) + 1
            buckets.setdefault(event.label, {})[lap.lap_number] = lap
    rows = []
    for label, lap_map in buckets.items():
        times = [lap.lap_time_seconds for lap in lap_map.values()]
        if times:
            rows.append({
                "label": label,
                "event_count": event_counts.get(label, 0),
                "lap_count": len(times),
                "average_lap_time": round(statistics.mean(times), 3),
                "delta_to_median": round(statistics.mean(times) - median, 3),
            })
    return rows


def _event_severity(event: Event) -> str:
    if event.label == "urgent":
        return "critical"
    if event.label in {"stressed", "frustrated"} and event.confidence >= 0.55:
        return "high"
    if event.label == "tired":
        return "medium"
    return "info"


def build_recommendations(events: list[Event], correlations: list[dict], transcript: str) -> list[dict]:
    recommendations = []
    if any(item["deterioration"] and item["label"] in {"stressed", "frustrated"} for item in correlations):
        recommendations.append({"type": "performance", "severity": "high", "title": "Stress event followed by lap deterioration", "explanation": "A high-stress radio event was followed by a slower-than-median next lap. This is an association, not proof of causation.", "recommendation": "Reduce non-critical radio communication and investigate the issue mentioned in the source-language transcript before the next run.", "supporting_data": correlations})
    if any(item["deterioration"] and item["label"] == "urgent" for item in correlations):
        recommendations.append({"type": "safety", "severity": "critical", "title": "Urgent radio event with performance loss", "explanation": "An urgent event coincided with a slower-than-median following lap. This is an association, not proof of causation.", "recommendation": "Prioritise immediate human review of the car condition and the driver's exact wording.", "supporting_data": correlations})
    if sum(event.label == "tired" for event in events) >= 2:
        recommendations.append({"type": "fatigue_review", "severity": "medium", "title": "Repeated tired-state detections", "explanation": "Tired-like vocal patterns recur across separate reportable windows.", "recommendation": "Flag the pattern for human review and consider a short, concise check-in.", "supporting_data": {"count": sum(event.label == "tired" for event in events)}})
    if sum(event.label == "frustrated" for event in events) >= 2:
        recommendations.append({"type": "communication", "severity": "medium", "title": "Repeated frustration across the run", "explanation": "Frustrated vocal patterns recur across separate reportable windows.", "recommendation": "Keep engineering communication concise and address the repeated issue between laps.", "supporting_data": {"count": sum(event.label == "frustrated" for event in events)}})
    uncertain_count = sum(event.label == "uncertain" or event.confidence < 0.5 for event in events)
    if uncertain_count:
        recommendations.append({"type": "review", "severity": "low", "title": "Manual review recommended", "explanation": "At least one vocal-state window was uncertain, outside model language coverage, or below the confidence gate.", "recommendation": "Use the original-language transcript and audio player to verify the event before acting.", "supporting_data": {"uncertain_or_low_confidence_events": uncertain_count}})
    if not recommendations:
        recommendations.append({"type": "monitor", "severity": "info", "title": "No immediate engineering alert", "explanation": "The baseline rules found no high-confidence urgent or repeated vocal-state pattern requiring immediate action.", "recommendation": "Continue monitoring the source-language radio evidence and verify any concerns with the audio.", "supporting_data": {"transcript_excerpt": transcript[:160]}})
    return recommendations


def _coverage_seconds(segments: Sequence) -> float:
    ranges = []
    for segment in segments:
        start = float(_field(segment, "start_seconds", 0))
        end = float(_field(segment, "end_seconds", start))
        if end > start:
            ranges.append((start, end))
    total = 0.0
    current_start = current_end = None
    for start, end in sorted(ranges):
        if current_start is None:
            current_start, current_end = start, end
        elif start <= current_end:
            current_end = max(current_end, end)
        else:
            total += current_end - current_start
            current_start, current_end = start, end
    return round(total + ((current_end - current_start) if current_start is not None else 0), 3)


def _transcript_rows(segments: Sequence) -> list[dict]:
    rows = []
    for segment in segments:
        start = float(_field(segment, "start_seconds", 0))
        end = float(_field(segment, "end_seconds", start))
        text = str(_field(segment, "text", "")).strip()
        if text:
            rows.append({"start_seconds": round(start, 3), "end_seconds": round(max(end, start), 3), "text": text})
    return rows


def _lap_summary(laps: list) -> dict | None:
    if not laps:
        return None
    ordered = sorted(laps, key=lambda lap: lap.lap_number)
    times = [lap.lap_time_seconds for lap in ordered]
    return {
        "lap_count": len(ordered),
        "median_lap_time_seconds": round(statistics.median(times), 3),
        "average_lap_time_seconds": round(statistics.mean(times), 3),
        "best_lap_time_seconds": round(min(times), 3),
        "worst_lap_time_seconds": round(max(times), 3),
        "timing_start_seconds": round(min(lap.start_timestamp_seconds for lap in ordered), 3),
        "timing_end_seconds": round(max(lap.end_timestamp_seconds for lap in ordered), 3),
    }


def build_report(
    events: list[Event],
    laps: list,
    transcript: str,
    transcript_segments: Sequence | None = None,
    audio_duration_seconds: float | None = None,
    language: str = "und",
    text_signals_applied: bool = False,
) -> dict:
    transcript_segments = transcript_segments or []
    report_events = merge_events(events)
    correlations = correlate_events(report_events, laps)
    correlation_index = {(item["event_timestamp"], item["label"]): item for item in correlations}
    state_distribution = []
    for label in NORMALIZED:
        matching = [event for event in report_events if event.label == label]
        if matching:
            duration = sum(max(0.0, event.end - event.start) for event in matching)
            weighted_confidence = sum(event.confidence * max(0.05, event.end - event.start) for event in matching) / sum(max(0.05, event.end - event.start) for event in matching)
            state_distribution.append({"label": label, "event_count": len(matching), "duration_seconds": round(duration, 3), "average_confidence": round(weighted_confidence, 3)})
    highest_risk = max(report_events, key=lambda item: (RISK_ORDER.get(item.label, 0), item.confidence, item.end - item.start), default=None)
    timestamped_events = []
    for event in report_events:
        correlation = correlation_index.get((round(event.start, 3), event.label), {})
        timestamped_events.append({
            "start_seconds": round(event.start, 3),
            "end_seconds": round(event.end, 3),
            "duration_seconds": round(max(0, event.end - event.start), 3),
            "label": event.label,
            "severity": _event_severity(event),
            "confidence": round(event.confidence, 3),
            "transcript": event.transcript,
            "source": event.source,
            "lap_number": correlation.get("lap_number"),
            "matched_lap": correlation.get("matched", False),
        })
    highest_risk_event = None
    if highest_risk:
        highest_risk_event = next((item for item in timestamped_events if item["start_seconds"] == round(highest_risk.start, 3) and item["label"] == highest_risk.label), None)
    dominant_summary = max(
        state_distribution,
        key=lambda item: (item["duration_seconds"] * item["average_confidence"], item["duration_seconds"], item["average_confidence"]),
        default=None,
    )
    dominant_state = None
    if dominant_summary:
        dominant_state = {
            "label": dominant_summary["label"],
            "confidence": dominant_summary["average_confidence"],
            "duration_seconds": dominant_summary["duration_seconds"],
        }
    transcript_rows = _transcript_rows(transcript_segments)
    speech_coverage = _coverage_seconds(transcript_segments)
    return {
        "schema_version": 2,
        "primary_state": dominant_state["label"] if dominant_state else "uncertain",
        "confidence": round(dominant_state["confidence"] if dominant_state else 0, 3),
        "transcript": transcript,
        "timestamped_transcript": transcript_rows,
        "timestamped_events": timestamped_events,
        "summary": {
            "language": language or "und",
            "dominant_state": dominant_state,
            "highest_risk_event": highest_risk_event,
            "event_count": len(report_events),
            "speech_coverage_seconds": speech_coverage,
        },
        "data_quality": {
            "audio_duration_seconds": round(audio_duration_seconds, 3) if audio_duration_seconds is not None else None,
            "transcript_segment_count": len(transcript_rows),
            "speech_coverage_seconds": speech_coverage,
            "text_signals_applied": text_signals_applied,
        },
        "state_distribution": state_distribution,
        "correlations": correlations,
        "performance_by_state": performance_by_state(report_events, laps),
        "lap_summary": _lap_summary(laps),
        "recommendations": build_recommendations(report_events, correlations, transcript),
    }
