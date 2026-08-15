from collections.abc import Mapping

NORMALIZED = ("calm", "positive", "subdued", "stressed", "tired", "frustrated", "urgent", "uncertain")

LABEL_MAP = {
    "neu": "calm", "neutral": "calm", "calm": "calm",
    "happy": "positive", "joy": "positive", "hap": "positive", "positive": "positive",
    "sad": "subdued", "sadness": "subdued", "subdued": "subdued",
    "angry": "frustrated", "anger": "frustrated", "ang": "frustrated", "frustrated": "frustrated",
    "tired": "tired", "fatigue": "tired", "fatigued": "tired", "fear": "stressed", "fea": "stressed", "fearful": "stressed",
    "stress": "stressed", "stressed": "stressed", "excited": "urgent", "surprise": "urgent",
    "urgent": "urgent", "disgust": "frustrated", "unknown": "uncertain", "uncertain": "uncertain", "sur": "urgent",
}


def normalize_label(raw_label: str) -> str:
    key = raw_label.lower().strip().replace(" ", "_")
    return LABEL_MAP.get(key, "uncertain")


def normalize_scores(scores: Mapping[str, float]) -> dict[str, float]:
    result = {label: 0.0 for label in NORMALIZED}
    for raw, score in scores.items():
        result[normalize_label(raw)] += float(score)
    total = sum(result.values())
    return {key: round(value / total, 4) for key, value in result.items()} if total else result
