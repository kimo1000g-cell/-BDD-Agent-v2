"""
Visual HTML Test Report Generator for BDD Agent v2
Generates a modern, single-file HTML report with embedded screenshots and pass/fail metrics.
"""

from __future__ import annotations

import base64
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List


def image_to_base64(image_path: Path | str) -> str:
    """Convert an image file to a base64 data URI for single-file embedding."""
    p = Path(image_path)
    if p.exists() and p.is_file():
        try:
            raw = p.read_bytes()
            b64 = base64.b64encode(raw).decode("utf-8")
            ext = p.suffix.lower().replace(".", "")
            mime = "image/png" if ext == "png" else f"image/{ext}"
            return f"data:{mime};base64,{b64}"
        except Exception:
            return ""
    return ""


def video_to_base64(video_path: Path | str) -> str:
    """Convert a WebM video file to a base64 data URI for single-file HTML embedding."""
    p = Path(video_path)
    if p.exists() and p.is_file():
        try:
            raw = p.read_bytes()
            b64 = base64.b64encode(raw).decode("utf-8")
            return f"data:video/webm;base64,{b64}"
        except Exception:
            return ""
    return ""


def generate_html_report(report_data: Dict[str, Any], output_path: Path | str) -> Path:
    """Generate a responsive HTML report file from BDD test run data."""
    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    feature_name = report_data.get("feature", "BDD Test Suite")
    created_at = report_data.get("created_at", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    scenarios: List[Dict[str, Any]] = report_data.get("scenarios", [])

    total_scenarios = len(scenarios)
    passed_scenarios = sum(1 for s in scenarios if s.get("result", "").lower() == "passed")
    failed_scenarios = total_scenarios - passed_scenarios
    pass_percentage = round((passed_scenarios / total_scenarios * 100)) if total_scenarios > 0 else 0

    status_color = "#10b981" if failed_scenarios == 0 else "#ef4444"

    # Build Scenario Cards HTML
    scenario_cards_html = []
    for idx, sc in enumerate(scenarios, start=1):
        sc_name = sc.get("scenario", f"Scenario {idx}")
        sc_res = sc.get("result", "passed").upper()
        badge_class = "badge-passed" if sc_res == "PASSED" else "badge-failed"

        assertions = sc.get("assertions", [])
        screenshots = sc.get("screenshots", [])

        # Executed Steps Timeline
        steps = sc.get("steps", [])
        step_items = []
        for s in steps:
            s_text = s.get("step", "")
            s_status = s.get("status", "passed").lower()
            s_color = "#10b981" if s_status == "passed" else "#ef4444"
            s_icon = "✓" if s_status == "passed" else "✗"
            s_bg = "rgba(16,185,129,0.06)" if s_status == "passed" else "rgba(239,68,68,0.12)"

            import re
            formatted_step = re.sub(
                r"^(Given|When|Then|And|But)\b",
                r'<span style="color:#818cf8; font-weight:700;">\1</span>',
                s_text,
                flags=re.IGNORECASE,
            )

            step_items.append(f"""
            <div style="display:flex; align-items:center; gap:10px; padding:6px 12px; margin-bottom:4px; border-radius:6px; background:{s_bg}; font-family:ui-monospace,SFMono-Regular,Consolas,monospace; font-size:12.5px;">
                <span style="color:{s_color}; font-weight:900; font-size:14px;">{s_icon}</span>
                <span style="color:#e2e8f0;">{formatted_step}</span>
            </div>
            """)
        steps_html = "".join(step_items) if step_items else "<div style='color:#9ca3af; font-size:12px; padding:4px;'>No discrete steps recorded.</div>"

        # Assertion Rows
        assertion_rows = []
        for a in assertions:
            a_status = a.get("status", "passed").upper()
            a_color = "#10b981" if a_status == "PASSED" else "#ef4444"
            assertion_rows.append(f"""
            <tr style="border-bottom: 1px solid rgba(255,255,255,0.06);">
                <td style="padding: 8px 12px;"><span style="color: {a_color}; font-weight:700;">{a_status}</span></td>
                <td style="padding: 8px 12px; font-family: monospace; color: #93c5fd;">{a.get('type', 'assertion')}</td>
                <td style="padding: 8px 12px;">{a.get('message', '')}</td>
                <td style="padding: 8px 12px; font-family: monospace; color: #d1d5db;">Expected: {a.get('expected', 'N/A')}</td>
            </tr>
            """)
        assertions_table_html = "".join(assertion_rows) if assertion_rows else "<tr><td colspan='4' style='padding:10px; color:#9ca3af;'>No assertions recorded.</td></tr>"

        # Screenshot Thumbnails with interactive Lightbox Modal
        screenshot_cards = []
        for img_path in screenshots:
            p = Path(img_path)
            b64_uri = image_to_base64(p)
            caption = p.name
            if b64_uri:
                screenshot_cards.append(f"""
                <div onclick="openLightbox('{b64_uri}', '{caption}')" style="display:inline-block; margin:8px; text-align:center; background:#1e293b; padding:8px; border-radius:8px; border:1px solid #334155; cursor:zoom-in; transition:transform 0.15s ease;" onmouseover="this.style.transform='scale(1.03)'" onmouseout="this.style.transform='scale(1)'">
                    <img src="{b64_uri}" alt="{caption}" style="max-width:280px; max-height:180px; border-radius:4px; object-fit:cover; display:block;" />
                    <div style="font-size:11px; color:#94a3b8; margin-top:4px; max-width:280px; word-break:break-all;">🔍 {caption}</div>
                </div>
                """)
            else:
                screenshot_cards.append(f"<div style='color:#94a3b8; font-size:12px; margin:4px;'>📷 {caption}</div>")

        screenshots_html = "".join(screenshot_cards) if screenshot_cards else "<div style='color:#9ca3af; font-size:13px;'>No screenshots captured.</div>"

        # Video section
        video_html = ""
        video_path = sc.get("video")
        if video_path and Path(video_path).exists():
            v_b64 = video_to_base64(video_path)
            if v_b64:
                video_html = f"""
                <div style="margin-top: 18px;">
                    <div style="font-size: 13px; font-weight: 600; text-transform: uppercase; color: #64748b; letter-spacing: 0.5px; margin-bottom: 8px;">🎬 Scenario Video Replay ({Path(video_path).name})</div>
                    <video controls width="100%" style="max-width: 680px; border-radius: 8px; border: 1px solid #334155; background: #000; display: block;">
                        <source src="{v_b64}" type="video/webm">
                        Your browser does not support HTML5 video.
                    </video>
                </div>
                """

        card_html = f"""
        <div class="card" style="margin-bottom: 20px; background: #0f172a; border-radius: 12px; border: 1px solid rgba(255,255,255,0.08); overflow:hidden;">
            <div style="padding: 16px 20px; background: rgba(255,255,255,0.03); display: flex; justify-content: space-between; align-items:center; border-bottom: 1px solid rgba(255,255,255,0.06);">
                <div style="font-size: 16px; font-weight: 600; color: #f8fafc;">Scenario {idx}: {sc_name}</div>
                <span class="badge {badge_class}">{sc_res}</span>
            </div>
            <div style="padding: 18px 20px;">
                <div style="font-size: 13px; font-weight: 600; text-transform: uppercase; color: #64748b; letter-spacing: 0.5px; margin-bottom: 8px;">Executed Step Sequence</div>
                <div style="margin-bottom: 18px;">
                    {steps_html}
                </div>

                <div style="font-size: 13px; font-weight: 600; text-transform: uppercase; color: #64748b; letter-spacing: 0.5px; margin-bottom: 8px;">Assertions</div>
                <table style="width: 100%; border-collapse: collapse; font-size: 13px; margin-bottom: 16px;">
                    <thead>
                        <tr style="text-align: left; color: #64748b; border-bottom: 1px solid rgba(255,255,255,0.1);">
                            <th style="padding: 6px 12px;">Status</th>
                            <th style="padding: 6px 12px;">Assertion Type</th>
                            <th style="padding: 6px 12px;">Details</th>
                            <th style="padding: 6px 12px;">Parameters</th>
                        </tr>
                    </thead>
                    <tbody>
                        {assertions_table_html}
                    </tbody>
                </table>

                <div style="font-size: 13px; font-weight: 600; text-transform: uppercase; color: #64748b; letter-spacing: 0.5px; margin-bottom: 8px;">Captured Evidence (Click to Zoom)</div>
                <div style="display:flex; flex-wrap:wrap; gap:8px;">
                    {screenshots_html}
                </div>
                {video_html}
            </div>
        </div>
        """
        scenario_cards_html.append(card_html)

    body_content = "".join(scenario_cards_html)
    header_badge_class = "badge-passed" if failed_scenarios == 0 else "badge-failed"

    html_template = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>BDD Agent Test Report - {feature_name}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            background-color: #020617;
            color: #f1f5f9;
            margin: 0;
            padding: 30px 20px;
        }}
        .container {{
            max-width: 1100px;
            margin: 0 auto;
        }}
        .header {{
            background: linear-gradient(135deg, #1e1b4b 0%, #0f172a 100%);
            border: 1px solid rgba(99, 102, 241, 0.2);
            border-radius: 16px;
            padding: 28px;
            margin-bottom: 24px;
            box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.5);
        }}
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
            gap: 16px;
            margin-top: 20px;
        }}
        .stat-card {{
            background: rgba(255, 255, 255, 0.04);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 12px;
            padding: 14px 18px;
            text-align: center;
        }}
        .stat-value {{
            font-size: 26px;
            font-weight: 700;
            margin-bottom: 4px;
        }}
        .stat-label {{
            font-size: 12px;
            color: #94a3b8;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        .badge {{
            padding: 4px 10px;
            border-radius: 6px;
            font-size: 12px;
            font-weight: 700;
            letter-spacing: 0.5px;
        }}
        .badge-passed {{
            background: rgba(16, 185, 129, 0.15);
            color: #10b981;
            border: 1px solid rgba(16, 185, 129, 0.3);
        }}
        .badge-failed {{
            background: rgba(239, 68, 68, 0.15);
            color: #ef4444;
            border: 1px solid rgba(239, 68, 68, 0.3);
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div style="display:flex; justify-content:space-between; align-items:flex-start;">
                <div>
                    <h1 style="margin:0 0 8px 0; font-size:26px; font-weight:800; color:#f8fafc;">🤖 BDD Agent Autonomous Test Report</h1>
                    <div style="color:#94a3b8; font-size:14px;">Feature: <b style="color:#e2e8f0;">{feature_name}</b> • Executed at: {created_at}</div>
                </div>
                <span class="badge {header_badge_class}" style="font-size:14px; padding:6px 14px; background:{'rgba(16,185,129,0.2)' if failed_scenarios == 0 else 'rgba(239,68,68,0.2)'}; color:{status_color};">
                    {pass_percentage}% PASS RATE
                </span>
            </div>

            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-value" style="color: #60a5fa;">{total_scenarios}</div>
                    <div class="stat-label">Total Scenarios</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value" style="color: #34d399;">{passed_scenarios}</div>
                    <div class="stat-label">Passed</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value" style="color: #f87171;">{failed_scenarios}</div>
                    <div class="stat-label">Failed</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value" style="color: #a78bfa;">FastMCP</div>
                    <div class="stat-label">Browser Engine</div>
                </div>
            </div>
        </div>

        <h2 style="font-size:18px; font-weight:700; color:#e2e8f0; margin: 28px 0 16px 0;">Test Execution Details</h2>
        {body_content}

        <!-- Lightbox Modal for Screenshots -->
        <div id="lightbox" onclick="closeLightbox()" style="display:none; position:fixed; z-index:9999; inset:0; background:rgba(0,0,0,0.88); backdrop-filter:blur(4px); justify-content:center; align-items:center; flex-direction:column; padding:20px; cursor:zoom-out;">
            <img id="lightbox-img" src="" style="max-width:92%; max-height:82vh; border-radius:8px; box-shadow:0 25px 50px -12px rgba(0,0,0,0.9); border:1px solid rgba(255,255,255,0.1);" />
            <div id="lightbox-caption" style="color:#f8fafc; margin-top:14px; font-size:14px; font-weight:600;"></div>
            <div style="color:#94a3b8; font-size:12px; margin-top:4px;">(Click anywhere to close)</div>
        </div>

        <script>
            function openLightbox(src, cap) {{
                document.getElementById('lightbox-img').src = src;
                document.getElementById('lightbox-caption').innerText = cap;
                document.getElementById('lightbox').style.display = 'flex';
            }}
            function closeLightbox() {{
                document.getElementById('lightbox').style.display = 'none';
            }}
            document.addEventListener('keydown', function(e) {{
                if (e.key === 'Escape') closeLightbox();
            }});
        </script>

        <footer style="text-align:center; color:#64748b; font-size:12px; margin-top:40px; padding-top:20px; border-top:1px solid rgba(255,255,255,0.06);">
            Generated autonomously by BDD Agent v2 • Model Context Protocol (MCP) Test Engine
        </footer>
    </div>
</body>
</html>
"""
    out_file.write_text(html_template, encoding="utf-8")
    return out_file


if __name__ == "__main__":
    sample_data = {
        "feature": "Todo App Management",
        "created_at": "2026-09-19 05:30:00",
        "scenarios": [
            {
                "scenario": "Add a new todo item",
                "result": "passed",
                "assertions": [
                    {
                        "type": "assert_equals",
                        "actual": "Buy groceries",
                        "expected": "Buy groceries",
                        "message": "The new todo should be visible on the page."
                    },
                    {
                        "type": "assert_count",
                        "actual": 1,
                        "expected": 1,
                        "message": "The todo list should contain exactly 1 item."
                    }
                ],
                "screenshots": []
            }
        ]
    }
    out = generate_html_report(sample_data, "test_results/reports/sample_report.html")
    print(f"Report generated: {out}")
