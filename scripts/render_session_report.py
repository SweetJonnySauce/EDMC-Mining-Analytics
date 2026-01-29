#!/usr/bin/env python3
"""Generate a standalone HTML report for session_data JSON files."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timedelta, timezone
from html import escape
from pathlib import Path
from typing import Any, Iterable, Optional


def _parse_iso(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    cleaned = value.strip()
    if cleaned.endswith("Z"):
        cleaned = f"{cleaned[:-1]}+00:00"
    try:
        return datetime.fromisoformat(cleaned)
    except ValueError:
        return None


def _fmt_dt(dt: Optional[datetime]) -> str:
    if not dt:
        return "-"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def _fmt_duration(seconds: Optional[float]) -> str:
    if seconds is None:
        return "-"
    total = int(round(seconds))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}h {minutes}m {secs}s"
    if minutes:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


def _fmt_number(value: Optional[float], digits: int = 0) -> str:
    if value is None:
        return "-"
    try:
        return f"{value:,.{digits}f}" if digits else f"{value:,}"
    except (TypeError, ValueError):
        return "-"


def _safe_float(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _escape(value: Any) -> str:
    if value is None:
        return "-"
    return escape(str(value))


def _collect_json_inputs(inputs: Iterable[str]) -> list[Path]:
    paths: list[Path] = []
    for raw in inputs:
        path = Path(raw)
        if path.is_dir():
            paths.extend(sorted(path.glob("*.json")))
        else:
            paths.append(path)
    return [path for path in paths if path.is_file()]


def _build_bars(items: list[dict[str, Any]], total_value: float) -> str:
    rows: list[str] = []
    for item in items:
        name = _escape(item.get("label"))
        value = item.get("value", 0.0) or 0.0
        if total_value > 0:
            pct = min(100.0, (value / total_value) * 100.0)
        else:
            pct = 0.0
        label = item.get("caption") or f"{_fmt_number(value, 2)}"
        rows.append(
            f"""
            <div class="bar-row">
                <div class="bar-label">{name}</div>
                <div class="bar-track">
                    <div class="bar-fill" style="width:{pct:.1f}%"></div>
                </div>
                <div class="bar-value">{_escape(label)}</div>
            </div>
            """
        )
    return "\n".join(rows) if rows else "<div class=\"muted\">No data.</div>"


def _fmt_offset(seconds: Optional[float]) -> str:
    if seconds is None:
        return "-"
    total = max(0, int(round(seconds)))
    minutes, secs = divmod(total, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours:d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:d}:{secs:02d}"


def _build_timeline_chart(
    events: list[dict[str, Any]],
    start_dt: Optional[datetime],
    end_dt: Optional[datetime],
) -> str:
    parsed_events: list[tuple[datetime, dict[str, Any]]] = []
    for event in events:
        ts = _parse_iso(event.get("timestamp"))
        if ts:
            parsed_events.append((ts, event))
    parsed_events.sort(key=lambda item: item[0])

    if not parsed_events:
        return "<div class=\"muted\">No event timeline data.</div>"

    start = start_dt or parsed_events[0][0]
    end = end_dt or parsed_events[-1][0]
    if end <= start:
        end = start + timedelta(seconds=1)
    total_seconds = (end - start).total_seconds()

    prospector_count = 0
    refined_count = 0
    prospector_points: list[tuple[float, int]] = [(0.0, 0)]
    refined_points: list[tuple[float, int]] = [(0.0, 0)]
    refinement_marks: list[dict[str, Any]] = []

    for ts, event in parsed_events:
        elapsed = (ts - start).total_seconds()
        event_type = event.get("type")
        details = event.get("details", {}) or {}

        if event_type == "launch_drone" and details.get("type") == "Prospector":
            prospector_count += 1

        if event_type == "mining_refined":
            refined_count += 1
            commodity = details.get("type_localised") or details.get("type") or "Unknown"
            refinement_marks.append(
                {
                    "time": elapsed,
                    "commodity": commodity,
                    "count": refined_count,
                }
            )

        if event_type in {"launch_drone", "mining_refined"}:
            x = max(0.0, min(1.0, elapsed / total_seconds))
            prospector_points.append((x, prospector_count))
            refined_points.append((x, refined_count))

    prospector_points.append((1.0, prospector_count))
    refined_points.append((1.0, refined_count))

    max_count = max(
        [count for _, count in prospector_points + refined_points] + [1]
    )
    width = 1000.0
    height = 220.0
    padding = 24.0
    x_span = width - (padding * 2)
    y_span = height - (padding * 2)

    def point_to_svg(point: tuple[float, int]) -> tuple[float, float]:
        x_frac, count = point
        x = padding + (x_frac * x_span)
        y = padding + (y_span - ((count / max_count) * y_span))
        return x, y

    prospector_path = " ".join(
        f"{x:.1f},{y:.1f}" for x, y in map(point_to_svg, prospector_points)
    )
    refined_path = " ".join(
        f"{x:.1f},{y:.1f}" for x, y in map(point_to_svg, refined_points)
    )

    palette = [
        "#f6b042",
        "#3bd3c6",
        "#f38a36",
        "#7ad0ff",
        "#ff8aa5",
        "#9a7bff",
        "#6fe39a",
        "#f2d45c",
    ]
    commodity_colors: dict[str, str] = {}
    for mark in refinement_marks:
        commodity = mark["commodity"]
        if commodity not in commodity_colors:
            commodity_colors[commodity] = palette[len(commodity_colors) % len(palette)]
        mark["color"] = commodity_colors[commodity]

    marker_svg = []
    for mark in refinement_marks:
        x = padding + ((mark["time"] / total_seconds) * x_span)
        y = padding + (y_span - ((mark["count"] / max_count) * y_span))
        marker_svg.append(
            f"<circle cx=\"{x:.1f}\" cy=\"{y:.1f}\" r=\"4\" fill=\"{mark['color']}\">"
            f"<title>{_escape(mark['commodity'])} at {_fmt_offset(mark['time'])}</title>"
            "</circle>"
        )

    legend_items = []
    for commodity, color in commodity_colors.items():
        legend_items.append(
            f"<span class=\"legend-pill\"><span class=\"legend-swatch\" "
            f"style=\"background:{color}\"></span>{_escape(commodity)}</span>"
        )

    refinement_log = []
    for mark in refinement_marks:
        refinement_log.append(
            f"<span class=\"refinement-pill\" style=\"border-color:{mark['color']}\">"
            f"{_escape(_fmt_offset(mark['time']))} · {_escape(mark['commodity'])}</span>"
        )

    legend_html = "".join(legend_items) or "<span class=\"muted\">No refinements.</span>"
    log_html = "".join(refinement_log) or "<span class=\"muted\">No refinements logged.</span>"

    svg = f"""
    <div class="chart-wrap">
        <div class="chart-legend">
            <span><span class="legend-line" style="background: var(--accent-3);"></span>Prospectors</span>
            <span><span class="legend-line" style="background: var(--accent);"></span>Refinements</span>
        </div>
        <svg viewBox="0 0 {int(width)} {int(height)}" class="timeline-chart" role="img" aria-label="Prospectors and refinements over time">
            <defs>
                <linearGradient id="refineLine" x1="0" x2="1">
                    <stop offset="0%" stop-color="var(--accent)" />
                    <stop offset="100%" stop-color="var(--accent-2)" />
                </linearGradient>
            </defs>
            <rect x="{padding}" y="{padding}" width="{x_span}" height="{y_span}" fill="rgba(255,255,255,0.02)" rx="12"></rect>
            <polyline points="{prospector_path}" fill="none" stroke="var(--accent-3)" stroke-width="3" stroke-linecap="round"></polyline>
            <polyline points="{refined_path}" fill="none" stroke="url(#refineLine)" stroke-width="3" stroke-linecap="round"></polyline>
            {''.join(marker_svg)}
        </svg>
        <div class="chart-axis">
            <span>{_escape(_fmt_dt(start))}</span>
            <span>{_escape(_fmt_dt(end))}</span>
        </div>
        <div class="legend-wrap">{legend_html}</div>
        <div class="refinement-log">{log_html}</div>
    </div>
    """
    return svg


def _render_report(data: dict[str, Any], source_name: str) -> str:
    meta = data.get("meta", {}) or {}
    commodities = data.get("commodities", {}) or {}
    events = data.get("events", []) or []

    start_dt = _parse_iso(meta.get("start_time"))
    end_dt = _parse_iso(meta.get("end_time"))
    duration = _fmt_duration(_safe_float(meta.get("duration_seconds")))

    overall = meta.get("overall_tph", {}) or {}
    total_tons = _safe_float(overall.get("tons"))
    total_tons = total_tons if total_tons is not None else 0.0
    tph_value = _safe_float(overall.get("tons_per_hour"))

    location = meta.get("location", {}) or {}
    location_line = " / ".join(
        part for part in [
            location.get("system"),
            location.get("body"),
            location.get("ring"),
        ]
        if part
    ) or "-"

    ship = meta.get("ship") or "-"
    commander = meta.get("commander") or "-"

    cargo_capacity = _safe_float(meta.get("cargo_capacity"))
    inventory_tonnage = _safe_float(meta.get("inventory_tonnage"))
    cargo_line = (
        f"{_fmt_number(inventory_tonnage)} / {_fmt_number(cargo_capacity)} t"
        if cargo_capacity is not None
        else _fmt_number(inventory_tonnage)
    )

    content_summary = meta.get("content_summary", {}) or {}
    content_items = [
        {"label": key, "value": float(content_summary.get(key, 0) or 0)}
        for key in ("High", "Medium", "Low")
    ]
    content_total = sum(item["value"] for item in content_items)

    prospecting = meta.get("prospected", {}) or {}
    prospected_total = _safe_float(prospecting.get("total"))
    prospected_dupes = _safe_float(prospecting.get("duplicates"))
    prospected_mined = _safe_float(prospecting.get("already_mined"))

    rpm_info = meta.get("refinement_activity", {}) or {}
    timeline_chart = _build_timeline_chart(events, start_dt, end_dt)

    commodity_items: list[dict[str, Any]] = []
    for name, info in commodities.items():
        gathered = info.get("gathered", {}) or {}
        tons = _safe_float(gathered.get("tons")) or 0.0
        commodity_items.append(
            {
                "label": name,
                "value": tons,
                "caption": f"{_fmt_number(tons)} t",
                "tph": _safe_float(info.get("tons_per_hour")),
                "stats": info.get("percentage_stats") or {},
                "asteroids": info.get("asteroids_prospected"),
            }
        )
    commodity_items.sort(key=lambda item: item["value"], reverse=True)

    event_counts = Counter(event.get("type") for event in events if event.get("type"))
    event_items = [
        {"label": event_type.replace("_", " ").title(), "value": float(count)}
        for event_type, count in event_counts.most_common()
    ]
    event_total = sum(item["value"] for item in event_items)

    commodity_stats_rows: list[str] = []
    for item in commodity_items:
        stats = item.get("stats") or {}
        commodity_stats_rows.append(
            f"""
            <div class="stat-row">
                <div class="stat-label">{_escape(item.get("label"))}</div>
                <div class="stat-value">{_fmt_number(stats.get("min"), 3)}</div>
                <div class="stat-value">{_fmt_number(stats.get("avg"), 3)}</div>
                <div class="stat-value">{_fmt_number(stats.get("max"), 3)}</div>
            </div>
            """
        )

    materials = meta.get("materials", []) or []
    materials_line = ", ".join(
        f"{_escape(material.get('name'))} x{_fmt_number(material.get('count'))}"
        for material in materials
        if material.get("name")
    ) or "-"

    html = f"""<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Mining Session Report</title>
    <style>
        :root {{
            --ink: #e9f1f3;
            --muted: #aac0c5;
            --panel: rgba(14, 28, 36, 0.68);
            --panel-border: rgba(255, 255, 255, 0.12);
            --accent: #f6b042;
            --accent-2: #f38a36;
            --accent-3: #3bd3c6;
            --shadow: 0 18px 38px rgba(0, 0, 0, 0.28);
        }}

        * {{ box-sizing: border-box; }}

        body {{
            margin: 0;
            font-family: "Iowan Old Style", "Palatino Linotype", "Book Antiqua", "Garamond", serif;
            color: var(--ink);
            background: radial-gradient(circle at top, #172b35 0%, #0b1b24 55%, #071018 100%);
        }}

        body::before {{
            content: "";
            position: fixed;
            inset: -20% 0 auto 0;
            height: 60%;
            background: radial-gradient(circle at 20% 20%, rgba(59, 211, 198, 0.25), transparent 55%),
                        radial-gradient(circle at 80% 10%, rgba(246, 176, 66, 0.25), transparent 45%);
            z-index: 0;
            pointer-events: none;
        }}

        .page {{
            position: relative;
            z-index: 1;
            padding: 40px 6vw 60px;
            max-width: 1200px;
            margin: 0 auto;
        }}

        .hero {{
            display: grid;
            gap: 10px;
            margin-bottom: 28px;
        }}

        .title {{
            font-size: clamp(2rem, 4vw, 3.5rem);
            letter-spacing: 0.02em;
        }}

        .subtitle {{
            color: var(--muted);
            font-size: 1.1rem;
        }}

        .meta-strip {{
            display: flex;
            flex-wrap: wrap;
            gap: 16px;
            color: var(--muted);
            font-size: 0.95rem;
        }}

        .grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 16px;
        }}

        .card {{
            background: var(--panel);
            border: 1px solid var(--panel-border);
            border-radius: 18px;
            padding: 18px 20px;
            box-shadow: var(--shadow);
            backdrop-filter: blur(6px);
            animation: rise 0.6s ease both;
        }}

        .card h2 {{
            margin: 0 0 12px 0;
            font-size: 1.1rem;
            letter-spacing: 0.04em;
            text-transform: uppercase;
            color: var(--muted);
        }}

        .kpi {{
            font-size: 1.6rem;
            margin-bottom: 6px;
        }}

        .kpi-label {{
            color: var(--muted);
            font-size: 0.85rem;
            letter-spacing: 0.08em;
            text-transform: uppercase;
        }}

        .bar-row {{
            display: grid;
            grid-template-columns: 1fr 3fr auto;
            align-items: center;
            gap: 12px;
            margin-bottom: 10px;
            font-size: 0.95rem;
        }}

        .bar-track {{
            position: relative;
            height: 10px;
            background: rgba(255, 255, 255, 0.1);
            border-radius: 999px;
            overflow: hidden;
        }}

        .bar-fill {{
            height: 100%;
            background: linear-gradient(90deg, var(--accent), var(--accent-2));
            border-radius: 999px;
            box-shadow: 0 0 12px rgba(246, 176, 66, 0.5);
        }}

        .bar-value {{
            color: var(--muted);
            font-size: 0.9rem;
            min-width: 70px;
            text-align: right;
        }}

        .split {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 18px;
            margin-top: 18px;
        }}

        .stat-grid {{
            display: grid;
            grid-template-columns: 1.6fr repeat(3, 1fr);
            gap: 6px 12px;
            font-size: 0.9rem;
        }}

        .stat-header {{
            color: var(--muted);
            text-transform: uppercase;
            font-size: 0.75rem;
            letter-spacing: 0.1em;
        }}

        .stat-row {{
            display: contents;
        }}

        .stat-label {{
            color: var(--ink);
        }}

        .stat-value {{
            color: var(--muted);
            text-align: right;
        }}

        .muted {{
            color: var(--muted);
        }}

        .chart-wrap {{
            display: grid;
            gap: 10px;
        }}

        .timeline-chart {{
            width: 100%;
            height: 220px;
        }}

        .chart-legend {{
            display: flex;
            flex-wrap: wrap;
            gap: 14px;
            font-size: 0.9rem;
            color: var(--muted);
        }}

        .legend-line {{
            display: inline-block;
            width: 22px;
            height: 4px;
            border-radius: 999px;
            margin-right: 6px;
            vertical-align: middle;
        }}

        .legend-wrap {{
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            font-size: 0.85rem;
            color: var(--muted);
        }}

        .legend-pill {{
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 3px 8px;
            border-radius: 999px;
            border: 1px solid rgba(255, 255, 255, 0.12);
            background: rgba(255, 255, 255, 0.04);
        }}

        .legend-swatch {{
            width: 10px;
            height: 10px;
            border-radius: 999px;
            display: inline-block;
        }}

        .chart-axis {{
            display: flex;
            justify-content: space-between;
            font-size: 0.8rem;
            color: var(--muted);
        }}

        .refinement-log {{
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            max-height: 120px;
            overflow: auto;
            padding-right: 6px;
        }}

        .refinement-pill {{
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 4px 10px;
            border-radius: 999px;
            border: 1px solid rgba(255, 255, 255, 0.2);
            background: rgba(255, 255, 255, 0.05);
            font-size: 0.8rem;
        }}

        @keyframes rise {{
            from {{
                opacity: 0;
                transform: translateY(10px);
            }}
            to {{
                opacity: 1;
                transform: translateY(0);
            }}
        }}

        @media (max-width: 720px) {{
            .bar-row {{
                grid-template-columns: 1fr;
                gap: 6px;
            }}
            .bar-value {{
                text-align: left;
            }}
        }}
    </style>
</head>
<body>
    <div class="page">
        <header class="hero">
            <div class="title">Mining Session Report</div>
            <div class="subtitle">{_escape(location_line)}</div>
            <div class="meta-strip">
                <div>Commander: {_escape(commander)}</div>
                <div>Ship: {_escape(ship)}</div>
                <div>Start: {_escape(_fmt_dt(start_dt))}</div>
                <div>End: {_escape(_fmt_dt(end_dt))}</div>
                <div>Source: {_escape(source_name)}</div>
            </div>
        </header>

        <section class="grid">
            <div class="card" style="animation-delay: 0.05s;">
                <div class="kpi">{_fmt_number(total_tons)}</div>
                <div class="kpi-label">Total Tons</div>
            </div>
            <div class="card" style="animation-delay: 0.1s;">
                <div class="kpi">{_fmt_number(tph_value, 2)}</div>
                <div class="kpi-label">Tons Per Hour</div>
            </div>
            <div class="card" style="animation-delay: 0.15s;">
                <div class="kpi">{_escape(duration)}</div>
                <div class="kpi-label">Session Duration</div>
            </div>
            <div class="card" style="animation-delay: 0.2s;">
                <div class="kpi">{_escape(cargo_line)}</div>
                <div class="kpi-label">Cargo Load</div>
            </div>
            <div class="card" style="animation-delay: 0.25s;">
                <div class="kpi">{_fmt_number(meta.get("limpets_remaining"))}</div>
                <div class="kpi-label">Limpets Remaining</div>
            </div>
            <div class="card" style="animation-delay: 0.3s;">
                <div class="kpi">{_fmt_number(rpm_info.get("max_rpm"), 1)}</div>
                <div class="kpi-label">Max RPM</div>
            </div>
        </section>

        <section class="split">
            <div class="card" style="animation-delay: 0.35s;">
                <h2>Commodity Yield</h2>
                {_build_bars(commodity_items, total_tons)}
            </div>
            <div class="card" style="animation-delay: 0.4s;">
                <h2>Prospecting Content</h2>
                {_build_bars(content_items, content_total)}
                <div class="muted" style="margin-top: 12px;">
                    Prospected: {_fmt_number(prospected_total)} |
                    Duplicates: {_fmt_number(prospected_dupes)} |
                    Already mined: {_fmt_number(prospected_mined)}
                </div>
            </div>
        </section>

        <section class="split">
            <div class="card" style="animation-delay: 0.45s;">
                <h2>Event Activity</h2>
                {_build_bars(event_items, event_total)}
            </div>
            <div class="card" style="animation-delay: 0.5s;">
                <h2>Prospecting Quality</h2>
                <div class="stat-grid">
                    <div class="stat-header">Commodity</div>
                    <div class="stat-header" style="text-align:right;">Min %</div>
                    <div class="stat-header" style="text-align:right;">Avg %</div>
                    <div class="stat-header" style="text-align:right;">Max %</div>
                    {''.join(commodity_stats_rows) if commodity_stats_rows else '<div class="muted">No stats.</div>'}
                </div>
            </div>
        </section>

        <section class="split">
            <div class="card" style="animation-delay: 0.52s;">
                <h2>Session Timeline</h2>
                {timeline_chart}
            </div>
        </section>

        <section class="split">
            <div class="card" style="animation-delay: 0.55s;">
                <h2>Operational Notes</h2>
                <div class="muted">Collectors launched: {_fmt_number(meta.get("collectors_launched"))}</div>
                <div class="muted">Collectors abandoned: {_fmt_number(meta.get("collectors_abandoned"))}</div>
                <div class="muted">Prospectors launched: {_fmt_number(meta.get("prospectors_launched"))}</div>
                <div class="muted">Prospectors lost: {_fmt_number(meta.get("prospectors_lost"))}</div>
                <div class="muted">Materials: {materials_line}</div>
            </div>
        </section>
    </div>
</body>
</html>
"""
    return html


def _render_index(entries: list[dict[str, Any]]) -> str:
    ordered = sorted(
        entries,
        key=lambda item: item.get("start_dt") or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )
    trend_chart = _build_index_trend_chart(ordered)
    rows = []
    for entry in ordered:
        session_id = _escape(entry["session_id"])
        rows.append(
            f"""
            <div class="card wide">
                <div>
                    <div class="title">{_escape(entry['title'])}</div>
                    <div class="muted">{_escape(entry['subtitle'])}</div>
                </div>
                <div class="meta">{_escape(entry['meta'])}</div>
                <div class="actions">
                    <label class="selector-item">
                        <input type="checkbox" class="session-toggle" data-session-id="{session_id}" checked>
                        <span>Show on graph</span>
                    </label>
                    <button type="button" class="only-button" data-session-id="{session_id}">Only</button>
                    <a class="button" href="{_escape(entry['href'])}">Open Report</a>
                </div>
            </div>
            """
        )
    cards = "\n".join(rows) if rows else "<p class=\"muted\">No reports found.</p>"
    return f"""<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Mining Session Reports</title>
    <style>
        :root {{
            --ink: #f0efe8;
            --muted: #b9b6aa;
            --panel: rgba(24, 22, 18, 0.75);
            --panel-border: rgba(255, 255, 255, 0.08);
            --accent: #f2a44a;
        }}
        * {{ box-sizing: border-box; }}
        body {{
            margin: 0;
            font-family: "Iowan Old Style", "Palatino Linotype", "Book Antiqua", "Garamond", serif;
            background: linear-gradient(160deg, #2a241b 0%, #15110c 100%);
            color: var(--ink);
        }}
        .page {{
            max-width: 1100px;
            margin: 0 auto;
            padding: 40px 6vw 60px;
        }}
        h1 {{
            font-size: clamp(2rem, 4vw, 3.2rem);
            margin-bottom: 8px;
        }}
        .sub {{
            color: var(--muted);
            margin-bottom: 24px;
        }}
        .grid {{
            display: grid;
            gap: 18px;
        }}
        .section {{
            margin-bottom: 28px;
        }}
        .section-title {{
            font-size: 1rem;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            color: var(--muted);
            margin: 10px 0 12px;
        }}
        .card {{
            background: var(--panel);
            border: 1px solid var(--panel-border);
            border-radius: 16px;
            padding: 18px 20px;
        }}
        .card.wide {{
            display: grid;
            grid-template-columns: 2fr 2fr auto;
            gap: 16px;
            align-items: center;
        }}
        .actions {{
            display: flex;
            flex-wrap: wrap;
            gap: 10px 12px;
            justify-content: flex-end;
            align-items: center;
        }}
        .selector-item {{
            display: inline-flex;
            align-items: center;
            gap: 6px;
            font-size: 0.9rem;
            color: var(--muted);
        }}
        .only-button {{
            background: transparent;
            color: var(--muted);
            border: 1px solid var(--panel-border);
            border-radius: 999px;
            padding: 6px 12px;
            cursor: pointer;
        }}
        .title {{
            font-size: 1.2rem;
            margin-bottom: 6px;
        }}
        .meta {{
            color: var(--muted);
            font-size: 0.9rem;
            margin: 6px 0 14px;
        }}
        .button {{
            display: inline-block;
            padding: 8px 14px;
            border-radius: 999px;
            background: var(--accent);
            color: #1f140b;
            text-decoration: none;
            font-weight: 600;
        }}
        .muted {{ color: var(--muted); }}
        .trend-wrap {{
            display: grid;
            gap: 12px;
        }}
        .trend-chart {{
            width: 100%;
            height: 240px;
        }}
        .bar-group .bar-tip {{
            opacity: 0;
            font-size: 10px;
            fill: #f0efe8;
            pointer-events: none;
        }}
        .bar-group:hover .bar-tip {{
            opacity: 1;
        }}
        .trend-legend {{
            display: flex;
            flex-wrap: wrap;
            gap: 14px;
            font-size: 0.9rem;
            color: var(--muted);
        }}
        .trend-line {{
            display: inline-block;
            width: 22px;
            height: 4px;
            border-radius: 999px;
            margin-right: 6px;
            vertical-align: middle;
        }}
        .trend-axis {{
            display: flex;
            justify-content: space-between;
            font-size: 0.8rem;
            color: var(--muted);
        }}
        @media (max-width: 900px) {{
            .card.wide {{
                grid-template-columns: 1fr;
                align-items: start;
            }}
            .actions {{
                justify-content: flex-start;
            }}
        }}
    </style>
</head>
<body>
    <div class="page">
        <h1>Mining Session Reports</h1>
        <div class="sub">Generated reports from session_data.</div>
        <div class="section">
            <div class="section-title">Session Trends</div>
            {trend_chart}
        </div>
        <div class="section">
            <div class="section-title">Session Reports</div>
            <div class="grid">{cards}</div>
        </div>
    </div>
    <script>
        const toggles = Array.from(document.querySelectorAll('.session-toggle'));
        const setVisibility = (sessionId, visible) => {{
            document.querySelectorAll(`[data-session-id="${{sessionId}}"]`).forEach((el) => {{
                el.style.display = visible ? '' : 'none';
            }});
        }};

        const applySelection = () => {{
            toggles.forEach((toggle) => {{
                setVisibility(toggle.dataset.sessionId, toggle.checked);
            }});
        }};

        toggles.forEach((toggle) => {{
            toggle.addEventListener('change', applySelection);
        }});

        document.querySelectorAll('.only-button').forEach((button) => {{
            button.addEventListener('click', () => {{
                const targetId = button.dataset.sessionId;
                toggles.forEach((toggle) => {{
                    toggle.checked = toggle.dataset.sessionId === targetId;
                }});
                applySelection();
            }});
        }});

        applySelection();
    </script>
</body>
</html>
"""


def _build_index_trend_chart(entries: list[dict[str, Any]]) -> str:
    if not entries:
        return "<div class=\"muted\">No session data.</div>"

    ordered = sorted(
        entries,
        key=lambda item: item.get("start_dt") or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )

    tph_values = [item.get("tph") for item in ordered]
    rpm_values = [item.get("max_rpm") for item in ordered]
    if not any(value is not None for value in tph_values + rpm_values):
        return "<div class=\"muted\">No trend data available.</div>"

    tph_max = max([value for value in tph_values if value is not None] or [0.0])
    rpm_max = max([value for value in rpm_values if value is not None] or [0.0])
    tph_max = tph_max if tph_max > 0 else 1.0
    rpm_max = rpm_max if rpm_max > 0 else 1.0

    width = 1000.0
    height = 260.0
    padding = 40.0
    x_span = width - (padding * 2)
    y_span = height - (padding * 2)

    session_count = len(ordered)
    group_width = x_span / max(1, session_count)
    bar_gap = min(16.0, group_width * 0.2)
    bar_width = max(10.0, (group_width - bar_gap) / 2)

    bars = []
    labels = []
    for idx, item in enumerate(ordered):
        group_start = padding + (idx * group_width)
        x_tph = group_start + (bar_gap / 2)
        x_rpm = x_tph + bar_width
        tph_value = item.get("tph") or 0.0
        rpm_value = item.get("max_rpm") or 0.0

        tph_height = (tph_value / tph_max) * y_span
        rpm_height = (rpm_value / rpm_max) * y_span
        tph_y = padding + (y_span - tph_height)
        rpm_y = padding + (y_span - rpm_height)

        session_id = item.get("session_id") or f"session-{idx}"
        bars.append(
            f"<g class=\"bar-group\" data-session-id=\"{_escape(session_id)}\">"
            f"<rect x=\"{x_tph:.1f}\" y=\"{tph_y:.1f}\" width=\"{bar_width:.1f}\" height=\"{tph_height:.1f}\" "
            f"fill=\"#f6b042\" rx=\"6\"></rect>"
            f"<text class=\"bar-tip\" x=\"{x_tph + (bar_width / 2):.1f}\" y=\"{tph_y - 6:.1f}\" text-anchor=\"middle\">"
            f"{_escape(_fmt_number(tph_value, 2))} TPH</text>"
            f"<title>{_escape(item.get('meta'))} · TPH {_fmt_number(tph_value, 2)}</title>"
            f"</g>"
        )
        bars.append(
            f"<g class=\"bar-group\" data-session-id=\"{_escape(session_id)}\">"
            f"<rect x=\"{x_rpm:.1f}\" y=\"{rpm_y:.1f}\" width=\"{bar_width:.1f}\" height=\"{rpm_height:.1f}\" "
            f"fill=\"#3bd3c6\" rx=\"6\"></rect>"
            f"<text class=\"bar-tip\" x=\"{x_rpm + (bar_width / 2):.1f}\" y=\"{rpm_y - 6:.1f}\" text-anchor=\"middle\">"
            f"{_escape(_fmt_number(rpm_value, 1))} RPM</text>"
            f"<title>{_escape(item.get('meta'))} · Max RPM {_fmt_number(rpm_value, 1)}</title>"
            f"</g>"
        )

        label_x = group_start + (group_width / 2)
        label = item.get("short_label") or f"S{idx + 1}"
        labels.append(
            f"<text data-session-id=\"{_escape(session_id)}\" x=\"{label_x:.1f}\" y=\"{height - 8}\" "
            f"text-anchor=\"middle\" fill=\"rgba(255,255,255,0.7)\" font-size=\"10\">"
            f"{_escape(label)}</text>"
        )

    tick_count = 4
    tick_labels = []
    for idx in range(tick_count + 1):
        frac = idx / tick_count
        y = padding + (y_span - (frac * y_span))
        tph_tick = tph_max * frac
        rpm_tick = rpm_max * frac
        tick_labels.append(
            f"<text x=\"{padding - 6:.1f}\" y=\"{y + 4:.1f}\" text-anchor=\"end\" fill=\"#f6b042\" font-size=\"10\">"
            f"{_escape(_fmt_number(tph_tick, 1))}</text>"
        )
        tick_labels.append(
            f"<text x=\"{width - padding + 6:.1f}\" y=\"{y + 4:.1f}\" text-anchor=\"start\" fill=\"#3bd3c6\" font-size=\"10\">"
            f"{_escape(_fmt_number(rpm_tick, 1))}</text>"
        )

    return f"""
    <div class="trend-wrap">
        <div class="trend-legend">
            <span><span class="trend-line" style="background: #f6b042;"></span> Tons/Hour (max {_fmt_number(tph_max, 1)})</span>
            <span><span class="trend-line" style="background: #3bd3c6;"></span> Max RPM (max {_fmt_number(rpm_max, 1)})</span>
        </div>
        <svg viewBox="0 0 {int(width)} {int(height)}" class="trend-chart" role="img" aria-label="Session trends">
            <rect x="{padding}" y="{padding}" width="{x_span}" height="{y_span}" fill="rgba(255,255,255,0.04)" rx="12"></rect>
            {''.join(tick_labels)}
            {''.join(bars)}
            {''.join(labels)}
        </svg>
        <div class="trend-axis">
            <span>{_escape(ordered[0].get("meta", "Start"))}</span>
            <span>{_escape(ordered[-1].get("meta", "End"))}</span>
        </div>
    </div>
    """


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate HTML reports from session_data JSON files.")
    parser.add_argument(
        "inputs",
        nargs="*",
        default=["session_data"],
        help="Session JSON file(s) or a directory containing JSON files.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(Path.home() / "Public" / "session_reports"),
        help="Directory to write HTML reports into.",
    )
    args = parser.parse_args()

    json_paths = _collect_json_inputs(args.inputs)
    if not json_paths:
        print("No session JSON files found.")
        return 1

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    index_entries: list[dict[str, Any]] = []
    for path in json_paths:
        try:
            with path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except (OSError, json.JSONDecodeError) as exc:
            print(f"Skipping {path}: {exc}")
            continue

        report_html = _render_report(payload, path.name)
        report_name = f"{path.stem}.html"
        report_path = output_dir / report_name
        report_path.write_text(report_html, encoding="utf-8")

        meta = payload.get("meta", {}) or {}
        overall = meta.get("overall_tph", {}) or {}
        tph_value = _safe_float(overall.get("tons_per_hour"))
        max_rpm = _safe_float(meta.get("max_rpm"))
        if max_rpm is None:
            max_rpm = _safe_float((meta.get("refinement_activity") or {}).get("max_rpm"))
        location = meta.get("location", {}) or {}
        subtitle = " / ".join(
            part for part in [location.get("system"), location.get("body"), location.get("ring")] if part
        ) or "-"
        start_dt = _parse_iso(meta.get("start_time"))
        end_dt = _parse_iso(meta.get("end_time"))
        time_range = f"{_fmt_dt(start_dt)} to {_fmt_dt(end_dt)}"
        short_label = _fmt_dt(start_dt).split(" ")[0] if start_dt else path.stem

        index_entries.append(
            {
                "title": meta.get("ship") or "Mining Session",
                "subtitle": subtitle,
                "meta": time_range,
                "href": report_name,
                "start_dt": start_dt,
                "end_dt": end_dt,
                "tph": tph_value,
                "max_rpm": max_rpm,
                "short_label": short_label,
                "session_id": path.stem,
            }
        )

    index_path = output_dir / "index.html"
    index_path.write_text(_render_index(index_entries), encoding="utf-8")
    print(f"Wrote {len(index_entries)} report(s) to {output_dir}")
    print(f"Open {index_path} in your browser.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
