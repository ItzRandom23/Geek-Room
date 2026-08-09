from io import BytesIO
import pandas as pd
from fastapi import HTTPException, UploadFile


async def parse_lap_csv(upload: UploadFile) -> list[dict]:
    if not (upload.filename or "").lower().endswith(".csv"):
        raise HTTPException(415, "Lap data must be a CSV file.")
    data = await upload.read(2 * 1024 * 1024 + 1)
    if len(data) > 2 * 1024 * 1024:
        raise HTTPException(413, "CSV file is too large.")
    try:
        frame = pd.read_csv(BytesIO(data))
    except Exception as exc:
        raise HTTPException(422, "Could not parse the CSV file.") from exc
    required = {"lap_number", "lap_time_seconds"}
    if not required.issubset(set(frame.columns)) or frame.empty:
        raise HTTPException(422, "CSV requires lap_number and lap_time_seconds columns.")
    rows = []
    elapsed = 0.0
    try:
        for record in frame.to_dict("records"):
            number = int(record["lap_number"])
            lap_time = float(record["lap_time_seconds"])
            if number <= 0 or lap_time <= 0 or lap_time > 1000:
                raise ValueError
            start = float(record.get("start_timestamp_seconds", elapsed))
            end = float(record.get("end_timestamp_seconds", start + lap_time))
            if start < 0 or end <= start:
                raise ValueError
            rows.append({"lap_number": number, "lap_time_seconds": lap_time, "start_timestamp_seconds": start, "end_timestamp_seconds": end})
            elapsed = end
    except (TypeError, ValueError, OverflowError, KeyError) as exc:
        raise HTTPException(422, "CSV contains invalid lap values.") from exc
    if len({row["lap_number"] for row in rows}) != len(rows):
        raise HTTPException(422, "CSV contains duplicate lap numbers.")
    ordered = sorted(rows, key=lambda row: row["lap_number"])
    previous_end = -1.0
    for index, row in enumerate(ordered):
        if index and row["start_timestamp_seconds"] < previous_end:
            raise HTTPException(422, "CSV lap timestamps overlap.")
        if index and row["start_timestamp_seconds"] > previous_end:
            raise HTTPException(422, "CSV lap timestamps contain a gap; provide contiguous timing windows.")
        previous_end = row["end_timestamp_seconds"]
    return rows


def validate_lap_rows(rows: list[dict]) -> None:
    numbers = [int(row["lap_number"]) for row in rows]
    if len(numbers) != len(set(numbers)):
        raise HTTPException(422, "Lap numbers must be unique.")
    ordered = sorted(rows, key=lambda row: row["lap_number"])
    previous_end = -1.0
    for index, row in enumerate(ordered):
        if row["lap_number"] <= 0 or row["lap_time_seconds"] <= 0:
            raise HTTPException(422, "Lap numbers and lap times must be positive.")
        if row["end_timestamp_seconds"] <= row["start_timestamp_seconds"]:
            raise HTTPException(422, "Lap end timestamps must be after their start timestamps.")
        if index and row["start_timestamp_seconds"] < previous_end:
            raise HTTPException(422, "Lap timestamps overlap.")
        if index and row["start_timestamp_seconds"] > previous_end:
            raise HTTPException(422, "Lap timestamps contain a gap; provide contiguous timing windows.")
        previous_end = row["end_timestamp_seconds"]
