import json
import statistics
from dataclasses import dataclass
from typing import Iterable
from .labels import NORMALIZED

HIGH_STRESS = {"stressed", "frustrated", "urgent"}
URGENCY_WORDS = {"box", "smoke", "fire", "unsafe", "damage", "urgent", "now", "push", "problem", "tyre", "tire"}


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
    # Do not silently attach an event to the nearest supplied lap. Events
    # outside the real timing window must remain explicitly unmatched.
    return None


def correlate_events(events: list[Event], laps: list, stress_threshold: float = 0.55) -> list[dict]:
    if not laps:
        return []
    median = statistics.median(lap.lap_time_seconds for lap in laps)
    ordered = sorted(laps, key=lambda lap: lap.lap_number)
    correlations = []
    for event in events:
        if event.label not in HIGH_STRESS or event.confidence < stress_threshold:
            continue
        lap = active_lap(ordered, event.start)
        if lap is None:
            continue
        next_lap = next((item for item in ordered if item.lap_number == lap.lap_number + 1), None)
        delta_current = round(lap.lap_time_seconds - median, 3)
        delta_next = round(next_lap.lap_time_seconds - median, 3) if next_lap else None
        deterioration = bool(next_lap and next_lap.lap_time_seconds > median)
        correlations.append({
            "event_timestamp": round(event.start, 3), "label": event.label, "confidence": round(event.confidence, 3),
            "lap_number": lap.lap_number, "current_lap_delta_seconds": delta_current,
            "next_lap_number": next_lap.lap_number if next_lap else None, "next_lap_delta_seconds": delta_next,
            "deterioration": deterioration, "transcript": event.transcript,
        })
    return correlations


def performance_by_state(events: list[Event], laps: list) -> list[dict]:
    if not laps:
        return []
    median = statistics.median(lap.lap_time_seconds for lap in laps)
    buckets = {label: [] for label in NORMALIZED}
    for event in events:
        lap = active_lap(laps, event.start)
        if lap:
            buckets.setdefault(event.label, []).append(lap.lap_time_seconds)
    return [{"label": label, "event_count": len(times), "average_lap_time": round(statistics.mean(times), 3) if times else None, "delta_to_median": round(statistics.mean(times) - median, 3) if times else None} for label, times in buckets.items() if times]


def build_recommendations(events: list[Event], correlations: list[dict], transcript: str) -> list[dict]:
    recommendations = []
    high_events = [event for event in events if event.label in HIGH_STRESS]
    if any(item["deterioration"] and item["label"] in {"stressed", "frustrated"} for item in correlations):
        recommendations.append({"type": "performance", "severity": "high", "title": "Stress event followed by lap deterioration", "explanation": "A high-stress radio event was followed by a slower-than-median next lap. This is an association, not proof of causation.", "recommendation": "Reduce non-critical radio communication and investigate the issue mentioned in the transcript before the next run.", "supporting_data": correlations})
    if any(item["deterioration"] and item["label"] == "urgent" for item in correlations):
        recommendations.append({"type": "safety", "severity": "critical", "title": "Urgent radio event with performance loss", "explanation": "An urgent event coincided with a sudden performance loss.", "recommendation": "Prioritise immediate human review of the car condition and the driver's exact wording.", "supporting_data": correlations})
    if sum(event.label == "tired" for event in events) >= 2:
        recommendations.append({"type": "fatigue_review", "severity": "medium", "title": "Repeated tired-state detections", "explanation": "The audio model detected tired-like vocal patterns more than once.", "recommendation": "Flag the pattern for human review and consider a short, concise check-in.", "supporting_data": {"count": sum(event.label == "tired" for event in events)}})
    if sum(event.label == "frustrated" for event in events) >= 2:
        recommendations.append({"type": "communication", "severity": "medium", "title": "Repeated frustration across the run", "explanation": "Frustrated vocal patterns recur across multiple events.", "recommendation": "Keep engineering communication concise and address the repeated issue between laps.", "supporting_data": {"count": sum(event.label == "frustrated" for event in events)}})
    if any(event.confidence < 0.5 for event in events):
        recommendations.append({"type": "review", "severity": "low", "title": "Manual review recommended", "explanation": "At least one model event has low confidence.", "recommendation": "Use the transcript and audio player to verify the event before acting.", "supporting_data": {"low_confidence_events": sum(event.confidence < 0.5 for event in events)}})
    if not recommendations:
        recommendations.append({"type": "monitor", "severity": "info", "title": "No immediate engineering alert", "explanation": "The baseline rules found no high-confidence stress event linked to deterioration.", "recommendation": "Continue monitoring radio tone alongside lap performance.", "supporting_data": {"transcript_excerpt": transcript[:160]}})
    return recommendations


def build_report(events: list[Event], laps: list, transcript: str) -> dict:
    correlations = correlate_events(events, laps)
    primary_event = max(events, key=lambda item: (item.label in HIGH_STRESS and item.confidence >= 0.55, item.confidence), default=None)
    return {"primary_state": primary_event.label if primary_event else "uncertain", "confidence": round(primary_event.confidence if primary_event else 0, 3), "transcript": transcript, "correlations": correlations, "performance_by_state": performance_by_state(events, laps), "recommendations": build_recommendations(events, correlations, transcript)}
