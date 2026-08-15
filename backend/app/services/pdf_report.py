"""Printable, Unicode-safe PitSense analysis reports."""

from __future__ import annotations

from html import escape
from textwrap import wrap
from typing import Any


def _text(value: Any) -> str:
    return escape("" if value is None else str(value))


def _seconds(value: Any) -> str:
    if value is None:
        return "-"
    seconds = max(0, float(value))
    minutes, remainder = divmod(seconds, 60)
    return f"{int(minutes):02d}:{remainder:04.1f}"


def _percent(value: Any) -> str:
    return "-" if value is None else f"{float(value) * 100:.0f}%"


def _table(headers: list[str], rows: list[list[str]], class_name: str = "") -> str:
    if not rows:
        return "<p class='empty'>No reportable data was produced for this section.</p>"
    head = "".join(f"<th>{_text(item)}</th>" for item in headers)
    body = "".join("<tr>" + "".join(f"<td>{value}</td>" for value in row) + "</tr>" for row in rows)
    return f"<table class='{class_name}'><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def _fallback_pdf(session, report: dict) -> bytes:
    """Return a valid lightweight PDF when the optional HTML renderer is absent."""
    summary = report.get("summary") or {}
    risk = summary.get("highest_risk_event") or {}
    lines = [
        "PitSense AI - Analysis report",
        str(getattr(session, "name", "Session")),
        f"Driver: {getattr(session, 'driver_name', '-')} | Circuit: {getattr(session, 'circuit_name', '-')}",
        f"Primary state: {report.get('primary_state', 'uncertain')} ({_percent(report.get('confidence'))})",
        f"Source language: {summary.get('language') or (report.get('provenance') or {}).get('language') or 'und'}",
        f"Evidence events: {summary.get('event_count', 0)}",
        "",
        "Highest-risk evidence",
        f"{risk.get('label', 'No reportable event')} | {_seconds(risk.get('start_seconds'))} - {_seconds(risk.get('end_seconds'))} | {_percent(risk.get('confidence'))}",
        str(risk.get("transcript") or "No overlapping transcript excerpt."),
        "",
        "Recommendations",
    ]
    for item in report.get("recommendations") or []:
        lines.extend([f"[{item.get('severity', 'info').upper()}] {item.get('title', 'Recommendation')}", str(item.get("recommendation") or "")])
    lines.extend(["", "Timestamped radio"])
    for item in report.get("timestamped_transcript") or []:
        lines.append(f"{_seconds(item.get('start_seconds'))}-{_seconds(item.get('end_seconds'))}: {item.get('text', '')}")

    content_lines = []
    for line in lines:
        safe = str(line).encode("ascii", "replace").decode("ascii")
        content_lines.extend(wrap(safe, width=92) or [""])
    pages = [content_lines[index:index + 46] for index in range(0, len(content_lines), 46)] or [[""]]

    objects: list[bytes] = []
    page_ids: list[int] = []
    font_id = 3 + len(pages) * 2
    for page in pages:
        page_id = 3 + len(page_ids) * 2
        page_ids.append(page_id)
        stream_lines = ["BT", "/F1 10 Tf", "50 790 Td", "14 TL"]
        for line in page:
            escaped = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            stream_lines.append(f"({escaped}) Tj T*" if escaped else "T*")
        stream_lines.append("ET")
        stream = "\n".join(stream_lines).encode("latin-1", "replace")
        objects.extend([
            f"{page_id} 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 {font_id} 0 R >> >> /Contents {page_id + 1} 0 R >> endobj\n".encode(),
            f"{page_id + 1} 0 obj << /Length {len(stream)} >> stream\n".encode() + stream + b"\nendstream endobj\n",
        ])
    objects.insert(0, b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n")
    kids = " ".join(f"{page_id} 0 R" for page_id in page_ids)
    objects.insert(1, f"2 0 obj << /Type /Pages /Kids [{kids}] /Count {len(page_ids)} >> endobj\n".encode())
    objects.append(f"{font_id} 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n".encode())

    output = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for obj in objects:
        offsets.append(len(output))
        output.extend(obj)
    xref = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode())
    output.extend("".join(f"{offset:010d} 00000 n \n" for offset in offsets[1:]).encode())
    output.extend(f"trailer << /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode())
    return bytes(output)


def render_pdf_report(session, report: dict) -> bytes:
    """Render a self-contained PDF with Pango font fallback and no remote assets."""
    try:
        from weasyprint import HTML
    except (ImportError, OSError):  # pragma: no cover - exercised on minimal local installs
        HTML = None

    summary = report.get("summary") or {}
    provenance = report.get("provenance") or {}
    data_quality = report.get("data_quality") or {}
    lap_summary = report.get("lap_summary") or {}
    risk = summary.get("highest_risk_event") or {}
    dominant = summary.get("dominant_state") or {}
    state_rows = [
        [
            _text(item.get("label", "uncertain").title()),
            _text(item.get("event_count", 0)),
            _seconds(item.get("duration_seconds")),
            _percent(item.get("average_confidence")),
        ]
        for item in report.get("state_distribution") or []
    ]
    transcript_rows = [
        [
            f"<span class='time'>{_seconds(item.get('start_seconds'))} - {_seconds(item.get('end_seconds'))}</span>",
            f"<span dir='auto'>{_text(item.get('text'))}</span>",
        ]
        for item in report.get("timestamped_transcript") or []
    ]
    event_rows = [
        [
            f"<span class='time'>{_seconds(item.get('start_seconds'))} - {_seconds(item.get('end_seconds'))}</span>",
            _text(item.get("label", "uncertain").title()),
            _percent(item.get("confidence")),
            _text(f"Lap {item['lap_number']}" if item.get("lap_number") is not None else "Unmatched"),
            f"<span dir='auto'>{_text(item.get('transcript'))}</span>",
        ]
        for item in report.get("timestamped_events") or []
    ]
    correlation_rows = [
        [
            _seconds(item.get("event_timestamp")),
            _text(item.get("label", "uncertain").title()),
            _text(item.get("lap_number") if item.get("matched") else "Unmatched"),
            _text(item.get("next_lap_number")),
            _text(f"{item['next_lap_delta_seconds']:+.3f}s" if item.get("next_lap_delta_seconds") is not None else "-"),
            _text("Yes" if item.get("deterioration") else "No" if item.get("deterioration") is not None else "-"),
        ]
        for item in report.get("correlations") or []
    ]
    recommendation_cards = "".join(
        "<article class='recommendation'>"
        f"<span class='severity {_text(item.get('severity', 'info'))}'>{_text(item.get('severity', 'info')).upper()}</span>"
        f"<h3>{_text(item.get('title'))}</h3>"
        f"<p>{_text(item.get('explanation'))}</p>"
        f"<p><strong>Recommendation:</strong> {_text(item.get('recommendation'))}</p>"
        "</article>"
        for item in report.get("recommendations") or []
    ) or "<p class='empty'>No recommendations were generated.</p>"
    html = f"""<!doctype html>
<html lang='{_text(summary.get("language") or provenance.get("language") or "und")}'>
<head><meta charset='utf-8'><style>
@page {{ size: A4; margin: 16mm 13mm 18mm; @bottom-left {{ content: 'PitSense AI - confidential engineering report'; color: #64748b; font-size: 8pt; }} @bottom-right {{ content: 'Page ' counter(page) ' of ' counter(pages); color: #64748b; font-size: 8pt; }} }}
* {{ box-sizing: border-box; }} body {{ color: #142033; font-family: 'Noto Sans', 'Noto Sans CJK SC', 'Noto Sans Arabic', 'Noto Sans Devanagari', sans-serif; font-size: 9.2pt; line-height: 1.45; }}
h1,h2,h3,p {{ margin-top: 0; }} h1 {{ color: #0f172a; font-size: 22pt; margin-bottom: 3mm; }} h2 {{ color: #0f766e; font-size: 12pt; border-bottom: 1px solid #cbd5e1; margin: 8mm 0 3mm; padding-bottom: 1.5mm; }} h3 {{ font-size: 10pt; margin: 2mm 0; }}
.eyebrow,.time,.severity {{ font-family: 'Noto Sans Mono', 'Noto Sans', monospace; font-size: 7.5pt; letter-spacing: .06em; text-transform: uppercase; }} .eyebrow {{ color: #0f766e; font-weight: 700; }} .muted {{ color: #64748b; }}
.summary {{ background: #f0fdfa; border: 1px solid #99f6e4; border-radius: 8px; display: grid; grid-template-columns: repeat(3, 1fr); gap: 4mm; margin-top: 5mm; padding: 4mm; }} .summary strong {{ color: #0f172a; display: block; font-size: 11pt; }}
table {{ border-collapse: collapse; margin: 2mm 0 4mm; table-layout: fixed; width: 100%; }} th {{ background: #e2e8f0; color: #334155; font-size: 7.5pt; letter-spacing: .04em; text-align: left; text-transform: uppercase; }} th,td {{ border: 1px solid #cbd5e1; padding: 2.2mm; vertical-align: top; overflow-wrap: anywhere; }} td {{ unicode-bidi: plaintext; }} .time {{ color: #0f766e; white-space: nowrap; }}
.recommendation {{ break-inside: avoid; border-left: 3px solid #14b8a6; margin: 3mm 0; padding: 3mm 4mm; background: #f8fafc; }} .severity {{ border-radius: 999px; display: inline-block; padding: .7mm 1.8mm; }} .severity.critical,.severity.high {{ background: #fee2e2; color: #b91c1c; }} .severity.medium {{ background: #fef3c7; color: #92400e; }} .severity.info,.severity.low {{ background: #e0f2fe; color: #0369a1; }}
.notice {{ background: #fff7ed; border: 1px solid #fed7aa; border-radius: 6px; margin-top: 4mm; padding: 3mm; }} .empty {{ color: #64748b; font-style: italic; }} .avoid-break {{ break-inside: avoid; }}
</style></head><body>
<div class='eyebrow'>PitSense AI / analysis report</div>
<h1>{_text(session.name)}</h1>
<p class='muted'>{_text(session.driver_name)} - {_text(session.circuit_name)} - Source language: <strong>{_text(summary.get('language') or provenance.get('language') or 'und')}</strong></p>
<section class='summary'>
<div><span class='eyebrow'>Highest risk state</span><strong>{_text(report.get('primary_state', 'uncertain')).title()} ({_percent(report.get('confidence'))})</strong></div>
<div><span class='eyebrow'>Dominant state</span><strong>{_text(dominant.get('label', 'uncertain')).title()} ({_seconds(dominant.get('duration_seconds'))})</strong></div>
<div><span class='eyebrow'>Evidence events</span><strong>{_text(summary.get('event_count', 0))} events</strong></div>
</section>
<p class='notice'>{_text(report.get('association_notice', 'Audio evidence is a decision-support signal, not a medical or psychological diagnosis.'))}</p>
<section class='avoid-break'><h2>Analysis coverage</h2><p>Audio duration: <strong>{_seconds(data_quality.get('audio_duration_seconds'))}</strong> | Speech coverage: <strong>{_seconds(data_quality.get('speech_coverage_seconds'))}</strong> | Text signals: <strong>{'Applied for English transcript' if data_quality.get('text_signals_applied') else 'Not applied for this language'}</strong></p><p class='muted'>Model: {_text((provenance.get('models') or {}).get('stt'))} | Generated: {_text(provenance.get('generated_at'))}</p></section>
<section><h2>State distribution</h2>{_table(['State','Events','Duration','Average confidence'], state_rows)}</section>
<section><h2>Timestamped radio - original language</h2>{_table(['Range','Driver radio'], transcript_rows)}</section>
<section><h2>Timestamped vocal-state evidence</h2>{_table(['Range','State','Confidence','Lap','Source-language evidence'], event_rows)}</section>
<section><h2>Recommendations</h2>{recommendation_cards}</section>
<section><h2>Lap context</h2><p>{_text('No real lap data was supplied; no performance conclusion was made.' if not lap_summary else f"{lap_summary.get('lap_count')} laps | median {lap_summary.get('median_lap_time_seconds')}s | best {lap_summary.get('best_lap_time_seconds')}s | worst {lap_summary.get('worst_lap_time_seconds')}s")}</p>{_table(['Event','State','Lap','Next lap','Next delta','Slower than median'], correlation_rows)}</section>
<section><h2>Highest-risk evidence</h2><p><strong>{_text(risk.get('label', 'No reportable event')).title()}</strong> {_seconds(risk.get('start_seconds'))} - {_seconds(risk.get('end_seconds'))}, {_percent(risk.get('confidence'))}</p><p dir='auto'>{_text(risk.get('transcript'))}</p></section>
</body></html>"""
    return HTML(string=html).write_pdf() if HTML is not None else _fallback_pdf(session, report)
