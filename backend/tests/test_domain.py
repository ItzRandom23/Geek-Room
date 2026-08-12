from types import SimpleNamespace
from app.services.analysis import Event, active_lap, build_recommendations, build_report, correlate_events, overlapping_text
from app.services.labels import normalize_label, normalize_scores


def lap(number, time, start):
    return SimpleNamespace(lap_number=number, lap_time_seconds=time, start_timestamp_seconds=start, end_timestamp_seconds=start + time)


def test_label_mapping_and_fusion_shape():
    assert normalize_label("fear") == "stressed"
    assert normalize_label("happy") == "positive"
    assert normalize_label("sad") == "subdued"
    scores = normalize_scores({"angry": 0.8, "neutral": 0.2})
    assert round(sum(scores.values()), 4) == 1
    assert scores["frustrated"] > scores["calm"]


def test_correlation_flags_next_lap_deterioration():
    laps = [lap(1, 90, 0), lap(2, 100, 90), lap(3, 101, 190)]
    result = correlate_events([Event("stressed", 0.9, 95, 99, "front lock")], laps)
    assert result[0]["lap_number"] == 2
    assert result[0]["deterioration"] is True


def test_recommendation_is_deterministic():
    correlations = [{"label": "urgent", "deterioration": True}]
    result = build_recommendations([Event("urgent", 0.9, 1, 2)], correlations, "smoke")
    assert result[0]["severity"] == "critical"


def test_common_superb_aliases_and_unmatched_timestamps():
    assert normalize_label("ang") == "frustrated"
    assert normalize_label("fea") == "stressed"
    assert normalize_label("sur") == "urgent"
    laps = [lap(1, 90, 0)]
    assert active_lap(laps, 95) is None


def test_report_merges_overlapping_windows_and_preserves_unicode_evidence():
    segments = [
        SimpleNamespace(start_seconds=0, end_seconds=4, text="ब्रेक ठीक नहीं है"),
        SimpleNamespace(start_seconds=4, end_seconds=8, text="前轮锁死している"),
    ]
    laps = [lap(1, 90, 0), lap(2, 92, 90)]
    report = build_report(
        [
            Event("stressed", 0.8, 0, 6, "ब्रेक ठीक नहीं है"),
            Event("stressed", 0.9, 4, 10, "前轮锁死している"),
        ],
        laps,
        "ब्रेक ठीक नहीं है 前轮锁死している",
        transcript_segments=segments,
        audio_duration_seconds=10,
        language="hi",
        text_signals_applied=False,
    )
    assert report["schema_version"] == 2
    assert report["summary"]["language"] == "hi"
    assert report["data_quality"]["text_signals_applied"] is False
    assert report["timestamped_transcript"][0]["text"] == "ब्रेक ठीक नहीं है"
    assert report["timestamped_events"][0]["duration_seconds"] == 10
    assert report["state_distribution"][0]["event_count"] == 1
    assert report["performance_by_state"][0]["lap_count"] == 1


def test_unmatched_stress_event_is_retained_in_correlation_output():
    result = correlate_events([Event("urgent", 0.9, 95, 99, "smoke")], [lap(1, 90, 0)])
    assert result[0]["matched"] is False
    assert result[0]["lap_number"] is None


def test_interval_overlap_collects_evidence_when_event_starts_before_a_transcript_line():
    segments = [SimpleNamespace(start_seconds=0, end_seconds=2, text="source-language evidence")]
    assert overlapping_text(segments, -0.5, 0.5) == "source-language evidence"


def test_dominant_state_uses_total_merged_evidence_not_one_window():
    report = build_report(
        [
            Event("stressed", 0.9, 0, 5),
            Event("stressed", 0.9, 10, 15),
            Event("urgent", 0.9, 20, 28),
        ],
        [],
        "",
    )
    assert report["summary"]["dominant_state"]["label"] == "stressed"
    assert report["summary"]["highest_risk_event"]["label"] == "urgent"


def test_overall_state_is_not_overridden_by_one_short_risk_window():
    report = build_report(
        [
            Event("calm", 0.88, 0, 20),
            Event("frustrated", 0.72, 21, 23),
        ],
        [],
        "",
    )
    assert report["primary_state"] == "calm"
    assert report["summary"]["highest_risk_event"]["label"] == "frustrated"
