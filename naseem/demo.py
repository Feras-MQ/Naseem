"""Self-contained synthetic demo bundle. No device, service or network is used."""
from collections import Counter
from html import escape
import json
from pathlib import Path

from . import __version__
from .config import config_hash, load_config
from .service import Processor
from .simulate import make_packet
from .storage import Journal, export_csv

SAMPLES = 72
FILES = ("SYNTHETIC_demo.sqlite3", "SYNTHETIC_packets.jsonl", "SYNTHETIC_records.csv",
         "report.html", "summary.json")
STATUS_COLORS = {"UNKNOWN": "#65778c", "NORMAL": "#157b66", "WATCH": "#9b6800", "HIGH": "#bd3b45"}
NOTICE = ("Synthetic classroom demonstration only. These are generated examples, not room measurements. "
          "Rules are illustrative, not official AQI or health limits. NORMAL does not establish air safety. "
          "eCO2 is estimated equivalent CO2; MQ-7 raw values are not CO concentrations. "
          "No hardware, wiring, calibration or measurement accuracy has been verified.")


def _text(value):
    return escape(str(value), quote=True)


def _value(value):
    return "—" if value is None else f"{value:g}"


def _plot(rows, field, title, unit, limits):
    """Keep gaps visible: unavailable samples never become zero or joined lines."""
    width, height, left, top, bottom = 600, 190, 48, 22, 154
    right = width - 16
    values = [row["packet"]["readings"][field] for row in rows]
    ceiling = max([value for value in values if value is not None] + list(limits.values()) + [1]) * 1.12
    end_ms = max(row["packet"]["uptime_ms"] for row in rows) or 1
    x = lambda ms: left + (right - left) * ms / end_ms
    y = lambda value: bottom - (bottom - top) * value / ceiling
    segments, segment = [], []
    for row, value in zip(rows, values):
        if value is None:
            if segment:
                segments.append(segment)
                segment = []
        else:
            segment.append(f'{x(row["packet"]["uptime_ms"]):.2f},{y(value):.2f}')
    if segment:
        segments.append(segment)
    parts = [f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="{_text(title)} over synthetic device time; gaps mean unavailable data">',
             f'<title>{_text(title)} — {_text(unit)}; synthetic device seconds</title>']
    for fraction in (0, .5, 1):
        value = ceiling * fraction
        yy = y(value)
        parts.append(f'<line x1="{left}" y1="{yy:.2f}" x2="{right}" y2="{yy:.2f}" stroke="#dce5eb"/>')
        parts.append(f'<text x="{left - 7}" y="{yy + 4:.2f}" text-anchor="end" class="axis">{value:.0f}</text>')
    for label, value in limits.items():
        yy = y(value)
        color = STATUS_COLORS["WATCH" if label == "watch" else "HIGH"]
        parts.append(f'<line x1="{left}" y1="{yy:.2f}" x2="{right}" y2="{yy:.2f}" stroke="{color}" stroke-dasharray="5 5"/>')
        parts.append(f'<text x="{right}" y="{yy - 4:.2f}" text-anchor="end" class="axis">{_text(label.upper())} {_value(value)}</text>')
    for points in segments:
        if len(points) == 1:
            xx, yy = points[0].split(",")
            parts.append(f'<circle cx="{xx}" cy="{yy}" r="2.5" fill="#176588"/>')
        else:
            parts.append(f'<polyline points="{" ".join(points)}" fill="none" stroke="#176588" stroke-width="2.5"/>')
    for ms in (0, 90000, 180000, 270000, end_ms):
        parts.append(f'<text x="{x(ms):.2f}" y="177" text-anchor="middle" class="axis">{ms // 1000}s</text>')
    parts.append("</svg>")
    return f'<section class="chart"><h3>{_text(title)} <span>{_text(unit)}</span></h3>{"".join(parts)}</section>'


def render_report(summary, rows, config):
    """Render only the generated bundle; all textual values are HTML-escaped."""
    cards = "".join(
        f'<div class="stat"><span>{_text(status)}</span><strong style="color:{STATUS_COLORS[status]}">{summary["status_counts"].get(status, 0)}</strong><small>synthetic records</small></div>'
        for status in ("UNKNOWN", "NORMAL", "WATCH", "HIGH"))
    plots = "".join(_plot(rows, field, title, unit, config["thresholds"][field]) for field, title, unit in (
        ("pm25_ug_m3", "PM2.5", "µg/m³"), ("pm10_ug_m3", "PM10", "µg/m³"),
        ("tvoc_ppb", "TVOC indicator", "ppb"), ("eco2_ppm", "eCO2 estimate", "ppm")))
    table_rows = []
    for row in rows:
        packet, result = row["packet"], row["result"]
        status = result["prototype_status"]
        cells = [str(packet["sequence"]), f'{packet["uptime_ms"] / 1000:g}s',
                 *(_value(packet["readings"][field]) for field in ("pm25_ug_m3", "pm10_ug_m3", "tvoc_ppb", "eco2_ppm")),
                 status, result["data_quality"], "; ".join(result["reasons"])]
        table_rows.append("<tr>" + "".join(f"<td>{_text(cell)}</td>" for cell in cells) + "</tr>")
    timeline = []
    for index, row in enumerate(rows):
        status = row["result"]["prototype_status"]
        timeline.append(f'<rect x="{index * 10}" y="0" width="10" height="32" fill="{STATUS_COLORS[status]}"><title>{row["packet"]["uptime_ms"] // 1000}s: {_text(status)}, {_text(row["result"]["data_quality"])}</title></rect>')
    quality = ", ".join(f"{key}: {value}" for key, value in sorted(summary["quality_counts"].items()))
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; img-src 'none'; base-uri 'none'; form-action 'none'">
<title>Naseem — synthetic demo report</title>
<style>
:root{{font-family:system-ui,-apple-system,"Segoe UI",sans-serif;color:#172e42;background:#edf3f5;font-synthesis:none}}*{{box-sizing:border-box}}body{{margin:0}}main{{max-width:1120px;margin:auto;padding:36px 24px 60px}}header{{padding:30px;border-radius:20px;background:#143a4a;color:white}}.eyebrow{{font-size:12px;letter-spacing:2px;font-weight:700;color:#b2e0df}}h1{{font-size:clamp(30px,5vw,48px);margin:10px 0 12px;letter-spacing:-1px}}header p{{margin:0;max-width:720px;line-height:1.65;color:#d7e9ed}}.notice{{border-left:4px solid #9b6800;background:#fff6df;padding:16px 20px;line-height:1.6;margin:22px 0;border-radius:4px 12px 12px 4px}}h2{{font-size:23px;margin:30px 0 12px}}p{{line-height:1.6}}.stats{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}}.stat,.chart,.panel{{background:white;border:1px solid #dce5eb;border-radius:14px;padding:20px}}.stat span,.stat small{{display:block;font-size:12px;color:#526677}}.stat strong{{font-size:36px;display:block;margin:5px 0}}.plots{{display:grid;grid-template-columns:1fr 1fr;gap:16px}}h3{{font-size:17px;margin:0 0 10px}}h3 span{{font-size:12px;color:#526677;font-weight:400}}svg{{display:block;width:100%;height:auto}}.axis{{font-size:11px;fill:#526677}}.timeline{{margin:18px 0 8px;border-radius:5px;overflow:hidden}}.phases{{font-size:13px;color:#526677}}dl{{display:grid;grid-template-columns:160px 1fr;gap:10px;font-size:14px}}dt{{color:#526677}}dd{{margin:0;overflow-wrap:anywhere}}code{{font-size:12px}}a{{color:#125f7a}}.downloads{{display:flex;flex-wrap:wrap;gap:12px;margin-top:18px}}.downloads a{{padding:10px 14px;border:1px solid #c4d7df;border-radius:8px;text-decoration:none;background:#fff}}summary{{cursor:pointer;font-weight:600;padding:8px 0}}.table-wrap{{overflow:auto;max-height:560px;margin-top:12px}}table{{border-collapse:collapse;width:100%;font-size:12px}}th,td{{padding:10px;text-align:left;border-bottom:1px solid #dce5eb;vertical-align:top}}th{{position:sticky;top:0;background:#e8f0f3;white-space:nowrap}}td:last-child{{min-width:280px}}footer{{margin-top:28px;color:#526677;font-size:13px}}@media(max-width:700px){{main{{padding:18px 14px}}header{{padding:24px}}.stats{{grid-template-columns:1fr 1fr}}.plots{{grid-template-columns:1fr}}dl{{grid-template-columns:1fr;gap:5px}}dd{{margin-bottom:9px}}}}@media print{{body{{background:white}}main{{max-width:none;padding:0}}header{{background:white;color:#143a4a;border:1px solid #dce5eb}}header p,.eyebrow{{color:#526677}}.chart,.panel,.stat{{break-inside:avoid}}.downloads{{display:none}}}}
</style></head><body><main>
<header><div class="eyebrow">NASEEM · SOFTWARE DEMONSTRATION</div><h1>Follow a signal from reading to result.</h1><p>A generated six-minute sampling window shows the local workflow: validate a packet, explain its status, save it in SQLite, and export the evidence.</p></header>
<div class="notice"><strong>SYNTHETIC DATA — NOT A LIVE MONITOR.</strong> {_text(NOTICE)}</div>
<h2>One run, 72 generated records</h2><p>All {_text(summary["accepted"])} packets were accepted; {_text(summary["rejected"])} were rejected. Samples are spaced five seconds apart in <strong>virtual device time</strong>. The first is at 0s and the last at 355s; this demo runs quickly, without waiting six real minutes.</p>
<div class="stats">{cards}</div>
<div class="timeline"><svg viewBox="0 0 720 32" role="img" aria-label="Status sequence for all 72 synthetic samples; unknown during warm-up and missing sensor periods, normal, watch and high elsewhere">{"".join(timeline)}</svg></div>
<p class="phases">0–25s warm-up · 30–85s stable · 90–145s rising · 150–175s high · 180–205s missing PM sensor · 210–355s recovery. WATCH can begin before a threshold is crossed because the trend rule also evaluates the rise.</p>
<h2>Signals and illustrative thresholds</h2><p>Dashed lines mark the configured WATCH and HIGH rules. Gaps mean unavailable data; they are not zero readings. Device seconds are on the horizontal axis.</p>
<div class="plots">{plots}</div>
<h2>Keep quality separate from status</h2><section class="panel"><p>{_text(quality)}. Missing or warming signals cannot produce NORMAL. An available high signal can still produce HIGH while quality is incomplete.</p><p>The simulator includes synthetic MQ-7 diagnostic readiness to exercise software states. The physical MQ-7 adapter remains disabled pending circuit, heater-cycle and calibration work.</p></section>
<h2>Trace this result</h2><section class="panel"><dl><dt>Mode / source</dt><dd>simulate / synthetic</dd><dt>Software version</dt><dd>{_text(summary["software_version"])}</dd><dt>Run ID / boot ID</dt><dd><code>{_text(summary["run_id"])}</code></dd><dt>Rules</dt><dd>{_text(config["label"])}</dd><dt>Configuration SHA-256</dt><dd><code>{_text(summary["config_sha256"])}</code></dd><dt>Hardware verification</dt><dd>Not performed; no connected device required.</dd></dl>
<div class="downloads"><a href="SYNTHETIC_records.csv">Open CSV records</a><a href="SYNTHETIC_packets.jsonl">Input packets</a><a href="summary.json">Run summary</a><a href="SYNTHETIC_demo.sqlite3">SQLite journal</a></div></section>
<h2>Inspect every result</h2><details class="panel"><summary>Show all 72 records and their explanations</summary><div class="table-wrap"><table><thead><tr><th>Sequence</th><th>Device time</th><th>PM2.5 µg/m³</th><th>PM10 µg/m³</th><th>TVOC ppb</th><th>eCO2 ppm</th><th>Status</th><th>Quality</th><th>Explanation</th></tr></thead><tbody>{"".join(table_rows)}</tbody></table></div></details>
<footer>Static local export. No cloud, account, JavaScript or internet connection is needed to read it. If INCOMPLETE.txt exists in this folder, generation did not finish; use a new folder and run the demo again.</footer>
</main></body></html>'''


def create_demo(output: Path):
    """Create a new, isolated bundle; never append to or replace an earlier demo."""
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    marker = output / "INCOMPLETE.txt"
    incomplete = ("INCOMPLETE DEMO BUNDLE\nGeneration has not completed. Files in this folder may be partial.\n"
                  "Do not treat this as a finished report. Run the demo again with a new output folder.\n")
    marker.write_text(incomplete, encoding="utf-8")
    try:
        config = load_config()
        rows = []
        with Journal(output / FILES[0], "simulate", config) as journal:
            processor = Processor(journal, config, expected_source="synthetic")
            with (output / FILES[1]).open("x", encoding="utf-8", newline="\n") as packets:
                for index in range(SAMPLES):
                    packet = make_packet(index, "mixed", boot_id=journal.run_id)
                    raw = json.dumps(packet, allow_nan=False)
                    packets.write(raw + "\n")
                    rows.append({"packet": packet, "result": processor.process(raw)})
            if processor.accepted != SAMPLES or processor.rejected:
                raise RuntimeError("Synthetic demo validation failed; inspect the incomplete journal")
            summary = {
                "complete": True, "scenario": "mixed", "mode": "simulate", "source": "synthetic",
                "accepted": processor.accepted, "rejected": processor.rejected,
                "run_id": journal.run_id, "software_version": __version__,
                "config_sha256": config_hash(config), "config": config,
                "status_counts": dict(Counter(row["result"]["prototype_status"] for row in rows)),
                "quality_counts": dict(Counter(row["result"]["data_quality"] for row in rows)),
                "sample_interval_seconds": 5, "first_device_seconds": 0, "last_device_seconds": 355,
                "hardware_verified": False, "notice": NOTICE, "files": list(FILES),
                "output": str(output), "report": str(output / "report.html"),
            }
        count = export_csv(output / FILES[0], output / FILES[2], summary["run_id"])
        if count != SAMPLES:
            raise RuntimeError("Demo CSV export is incomplete")
        (output / "report.html").write_text(render_report(summary, rows, config), encoding="utf-8")
        (output / "summary.json").write_text(json.dumps(summary, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        marker.unlink()
        return summary
    except BaseException:
        # Preserve diagnostic data and mark interrupted work. Never clean up someone else's files.
        try:
            marker.write_text(incomplete, encoding="utf-8")
        except OSError:
            pass  # Keep the original I/O error; an unwritable destination cannot be marked.
        raise
