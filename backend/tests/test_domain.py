from types import SimpleNamespace
from app.services.analysis import Event, active_lap, build_recommendations, correlate_events
from app.services.labels import normalize_label, normalize_scores


def lap(number, time, start):
    return SimpleNamespace(lap_number=number, lap_time_seconds=time, start_timestamp_seconds=start, end_timestamp_seconds=start + time)


def test_label_mapping_and_fusion_shape():
    assert normalize_label("fear") == "stressed"
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
