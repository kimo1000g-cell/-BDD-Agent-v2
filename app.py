"""
BDD Agent v2: Interactive Gradio Test Runner & Visual Verification Dashboard
Powered by FastMCP, Python Playwright, and Behavior-Driven Development (Gherkin).
"""

from __future__ import annotations

import asyncio
import html
from pathlib import Path
from typing import AsyncGenerator, Dict, List, Optional
import gradio as gr

from bdd_engine import BDDEngine

BASE_DIR = Path(__file__).parent
FEATURES_DIR = BASE_DIR / "features"

# Cache for scenario videos from the latest test run
_LATEST_VIDEOS: Dict[str, str] = {}


def list_feature_files() -> List[str]:
    """List all available .feature test suites."""
    if not FEATURES_DIR.exists():
        return []
    return [f.name for f in sorted(FEATURES_DIR.glob("*.feature"))]


def load_feature_content(feature_name: str) -> str:
    """Load text content of selected feature file."""
    if not feature_name:
        return ""
    p = FEATURES_DIR / feature_name
    if p.exists():
        return p.read_text(encoding="utf-8")
    return ""


# Preset prompt templates for 1-click generation
PROMPT_PRESETS = {
    "🛒 SauceDemo Storefront": (
        "Test logging in to SauceDemo with standard_user, verifying product catalog, and adding a backpack to cart",
        """Feature: E-Commerce Storefront Navigation & Cart
  As an online shopper
  I want to log in and add items to my cart
  So that I can verify e-commerce functionality

  Background:
    Given I navigate to "https://www.saucedemo.com/"
    When I type the input field "Username" with text "standard_user"
    And I type the input field "Password" with text "secret_sauce"
    And I click the button with text "Login"

  Scenario: Verify storefront products catalog loaded
    Then I should see text "Products" on the page
    And the page URL should contain "inventory.html"

  Scenario: Add item to shopping cart and verify badge
    When I click the button with text "Add to cart"
    Then the shopping cart badge should show "1"
    And I should see text "Remove" on the button
"""
    ),
    "📝 Todo List Management": (
        "Test adding multiple todo tasks to simple todo list and verifying count",
        """Feature: Todo Application Workflow
  As a user
  I want to add and complete tasks in the todo list
  So that I can manage my daily productivity

  Background:
    Given I navigate to "https://eviltester.github.io/simpletodolist/todo.html"

  Scenario: Add a single task to the todo list
    When I type the input field "Enter new todo text here" with text "Complete AI Engineer Assignment"
    And I press the "Enter" key
    Then I should see text "Complete AI Engineer Assignment" on the page
    And the todo list should contain at least 1 item

  Scenario: Add multiple tasks and verify item count
    When I type the input field "Enter new todo text here" with text "Write comprehensive test cases"
    And I press the "Enter" key
    And I type the input field "Enter new todo text here" with text "Record portfolio video demo"
    And I press the "Enter" key
    Then I should see text "Write comprehensive test cases" on the page
    And I should see text "Record portfolio video demo" on the page
    And the todo list should contain at least 2 items
"""
    ),
    "🔒 Form Error Validation": (
        "Test authentication form rejection on empty inputs and locked out users",
        """Feature: Authentication & Form Error Validation
  As a QA engineer
  I want to verify that login forms reject invalid credentials
  So that customer accounts remain secure

  Background:
    Given I navigate to "https://www.saucedemo.com/"

  Scenario: Attempt login with empty credentials
    When I click the button with text "Login"
    Then I should see text "Epic sadface: Username is required" on the page

  Scenario: Attempt login with locked out user
    When I type the input field "Username" with text "locked_out_user"
    And I type the input field "Password" with text "secret_sauce"
    And I click the button with text "Login"
    Then I should see text "Epic sadface: Sorry, this user has been locked out." on the page
"""
    ),
}


def load_preset(preset_key: str):
    """Load a prompt preset into input box and editor."""
    if preset_key in PROMPT_PRESETS:
        prompt_text, gherkin_code = PROMPT_PRESETS[preset_key]
        return prompt_text, gherkin_code
    return "", ""


def generate_gherkin_from_prompt(user_prompt: str) -> str:
    """Convert a plain English test description into a valid Gherkin .feature specification."""
    if not user_prompt or not user_prompt.strip():
        return "# Please enter a description above to generate Gherkin."

    import os
    openai_key = os.getenv("OPENAI_API_KEY")
    groq_key = os.getenv("GROQ_API_KEY")
    openrouter_key = os.getenv("OPENROUTER_API_KEY")

    client = None
    model_name = "gpt-4o-mini"

    try:
        from openai import OpenAI
        if openai_key:
            client = OpenAI(api_key=openai_key)
            model_name = "gpt-4o-mini"
        elif groq_key:
            client = OpenAI(api_key=groq_key, base_url="https://api.groq.com/openai/v1")
            model_name = "llama-3.3-70b-versatile"
        elif openrouter_key:
            client = OpenAI(api_key=openrouter_key, base_url="https://openrouter.ai/api/v1")
            model_name = "openai/gpt-4o-mini"
    except Exception:
        client = None

    if client:
        system_instruction = """You are an expert QA Automation Engineer specialized in BDD and Playwright.
Convert the user's plain-English test request into a syntactically valid Gherkin feature.

Supported step patterns in our engine:
- Given I navigate to "<url>"
- When I type the input field "<selector or placeholder>" with text "<text>"
- When I enter "<text>" into "<selector>"
- And I press the "Enter" key
- When I click the button with text "<button_text>" (or click "<selector>")
- Then I should see text "<expected_text>" on the page
- And the page URL should contain "<url_fragment>"
- And the todo list should contain at least <N> items
- And the shopping cart badge should show "<N>"
- And I wait <N> seconds

Return ONLY the raw Gherkin text, no markdown backticks, no commentary."""
        try:
            res = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.1,
            )
            raw = res.choices[0].message.content.strip()
            if raw.startswith("```"):
                lines = raw.splitlines()
                raw = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:])
            return raw
        except Exception:
            pass

    # Intelligent deterministic semantic heuristic generator (when no LLM API key is configured)
    p_lower = user_prompt.lower()

    # 1. Todo list application workflow
    if "todo" in p_lower or "task" in p_lower:
        return f"""Feature: AI Generated Todo Application Test Suite
  As a QA engineer
  I want to automatically test: {user_prompt.strip()}

  Background:
    Given I navigate to "https://eviltester.github.io/simpletodolist/todo.html"

  Scenario: Add task and verify item in todo list
    # Generated from prompt: "{user_prompt.strip()}"
    When I type the input field "Enter new todo text here" with text "AI Generated QA Task"
    And I press the "Enter" key
    Then I should see text "AI Generated QA Task" on the page
    And the todo list should contain at least 1 item
"""

    # 2. Form error validation & rejection
    if any(w in p_lower for w in ("error", "locked", "invalid", "fail", "empty", "require")):
        return f"""Feature: AI Generated Form Error Validation
  As a QA engineer
  I want to automatically test: {user_prompt.strip()}

  Background:
    Given I navigate to "https://www.saucedemo.com/"

  Scenario: Verify login validation rejection
    # Generated from prompt: "{user_prompt.strip()}"
    When I click the button with text "Login"
    Then I should see text "Epic sadface: Username is required" on the page
"""

    # 3. Shopping cart / checkout workflow
    if any(w in p_lower for w in ("cart", "buy", "add to cart", "checkout", "shopping", "badge")):
        return f"""Feature: AI Generated E-Commerce Shopping Cart Test Suite
  As a QA engineer
  I want to automatically test: {user_prompt.strip()}

  Background:
    Given I navigate to "https://www.saucedemo.com/"
    When I type the input field "Username" with text "standard_user"
    And I type the input field "Password" with text "secret_sauce"
    And I click the button with text "Login"

  Scenario: Add item to cart and verify cart badge
    # Generated from prompt: "{user_prompt.strip()}"
    When I click the button with text "Add to cart"
    Then the shopping cart badge should show "1"
    And I should see text "Remove" on the button
"""

    # 4. General Storefront & Authentication (Default)
    return f"""Feature: AI Generated Storefront Verification
  As a QA engineer
  I want to automatically test: {user_prompt.strip()}

  Background:
    Given I navigate to "https://www.saucedemo.com/"
    When I type the input field "Username" with text "standard_user"
    And I type the input field "Password" with text "secret_sauce"
    And I click the button with text "Login"

  Scenario: Verify storefront products catalog loaded
    # Generated from prompt: "{user_prompt.strip()}"
    Then I should see text "Products" on the page
    And the page URL should contain "inventory.html"
"""


def select_scenario_video(scenario_name: str) -> Optional[str]:
    """Retrieve the video file for a specific scenario."""
    if scenario_name and scenario_name in _LATEST_VIDEOS:
        path_str = _LATEST_VIDEOS[scenario_name]
        if Path(path_str).exists():
            return path_str
    return None


async def run_bdd_ui(feature_name: str, custom_text: str, browser_mode: str) -> AsyncGenerator:
    """Run selected BDD scenarios and stream real-time logs and results to dashboard."""
    global _LATEST_VIDEOS
    _LATEST_VIDEOS.clear()

    content = custom_text.strip() if custom_text and custom_text.strip() else load_feature_content(feature_name)
    if not content:
        yield (
            """<div style="padding:14px; background:rgba(239,68,68,0.15); border-radius:10px; border:1px solid rgba(239,68,68,0.3); color:#ef4444; font-weight:600;">
                ⚠️ Please select or write a Gherkin feature scenario first.
            </div>""",
            "0 / 0",
            "N/A",
            [],
            [],
            "No execution log available.",
            None,
            gr.update(choices=[], value=None),
            None,
            "<div style='padding:20px; color:#94a3b8;'>No report generated yet.</div>",
        )
        return

    headless = "Headless" in browser_mode
    logs: List[str] = []
    logs_queue = asyncio.Queue()

    def log_handler(msg: str):
        logs.append(msg)
        logs_queue.put_nowait(msg)

    # Dynamically extract actual suite title from Gherkin header if present
    import re
    feat_match = re.search(r"(?m)^\s*Feature:\s*(.*?)$", content)
    if feat_match and feat_match.group(1).strip():
        suite_title = feat_match.group(1).strip()
    else:
        suite_title = feature_name.replace(".feature", "").replace("_", " ").title() if feature_name else "Custom Feature"

    engine = BDDEngine(headless=headless, log_callback=log_handler)

    # Initial Progress State
    yield (
        f"""<div style="display:flex; align-items:center; gap:16px; padding:14px; background:rgba(59,130,246,0.15); border-radius:10px; border:1px solid rgba(59,130,246,0.3);">
            <div style="font-size:24px;">⏳</div>
            <div>
                <div style="font-size:16px; font-weight:700; color:#60a5fa;">EXECUTING TEST SUITE</div>
                <div style="font-size:13px; opacity:0.8;">Feature: <b>{suite_title}</b> • Browser: {'Headless' if headless else 'Headed Live'}</div>
            </div>
        </div>""",
        "Running...",
        "...",
        [],
        [],
        [],
        f"🚀 Initializing Playwright browser engine for '{suite_title}'...\n",
        None,
        gr.update(choices=[], value=None),
        None,
        "<div style='padding:20px; color:#94a3b8;'>Running tests and generating visual report...</div>",
    )

    # Run execution task
    exec_task = asyncio.create_task(engine.execute_feature_text(content, feature_title=suite_title))

    # Stream logs to UI while execution runs
    while not exec_task.done():
        await asyncio.sleep(0.3)
        current_logs = "\n".join(logs)
        yield (
            f"""<div style="display:flex; align-items:center; gap:16px; padding:14px; background:rgba(59,130,246,0.15); border-radius:10px; border:1px solid rgba(59,130,246,0.3);">
                <div style="font-size:24px;">⚡</div>
                <div>
                    <div style="font-size:16px; font-weight:700; color:#60a5fa;">TEST IN PROGRESS</div>
                    <div style="font-size:13px; opacity:0.8;">Feature: <b>{suite_title}</b> • Recording live evidence...</div>
                </div>
            </div>""",
            "Running...",
            "...",
            [],
            [],
            [],
            current_logs,
            None,
            gr.update(),
            None,
            "<div style='padding:20px; color:#94a3b8;'>Running tests...</div>",
        )

    try:
        report_data = await exec_task
    except Exception as e:
        yield (
            f"""<div style="padding:14px; background:rgba(239,68,68,0.15); border-radius:10px; border:1px solid rgba(239,68,68,0.3); color:#ef4444; font-weight:600;">
                ❌ Execution error: {html.escape(str(e))}
            </div>""",
            "0 / 0",
            "ERROR",
            [],
            [],
            [],
            "\n".join(logs),
            None,
            gr.update(choices=[], value=None),
            None,
            "<div style='padding:20px; color:#ef4444;'>Execution encountered an error.</div>",
        )
        return

    scenarios = report_data.get("scenarios", [])
    total = len(scenarios)
    passed = sum(1 for s in scenarios if s.get("result", "").lower() == "passed")
    pass_pct = f"{round((passed / total) * 100)}%" if total > 0 else "0%"

    status_color = "#10b981" if passed == total else "#ef4444"
    status_text = "ALL TESTS PASSED" if passed == total else f"{total - passed} SCENARIO(S) FAILED"

    status_banner = f"""
    <div style="display:flex; align-items:center; gap:16px; padding:14px; background:rgba(255,255,255,0.04); border-radius:10px; border:1px solid rgba(255,255,255,0.1);">
        <div style="font-size:28px; font-weight:800; color:{status_color}; min-width:90px; text-align:center;">{pass_pct}</div>
        <div>
            <div style="font-size:16px; font-weight:700; color:{status_color};">{status_text}</div>
            <div style="font-size:13px; opacity:0.8;">Feature: <b>{suite_title}</b> • {passed} of {total} scenarios passed.</div>
        </div>
    </div>
    """

    assertion_rows = []
    step_rows = []
    screenshot_paths = []

    for sc in scenarios:
        sc_title = sc.get("scenario", "Scenario")
        if sc.get("video") and Path(sc["video"]).exists():
            _LATEST_VIDEOS[sc_title] = sc["video"]

        # Step breakdown
        for st in sc.get("steps", []):
            step_rows.append([
                sc_title,
                st.get("status", "passed").upper(),
                st.get("type", "scenario").capitalize(),
                st.get("step", ""),
            ])

        # Assertions
        for a in sc.get("assertions", []):
            assertion_rows.append([
                sc_title,
                a.get("status", "passed").upper(),
                a.get("type", "assert"),
                a.get("message", ""),
                str(a.get("expected", "")),
            ])
        screenshot_paths.extend(sc.get("screenshots", []))

    valid_screenshots = [p for p in screenshot_paths if Path(p).exists()]
    html_file = report_data.get("html_path")
    full_log = "\n".join(logs)

    video_choices = list(_LATEST_VIDEOS.keys())
    initial_video = _LATEST_VIDEOS[video_choices[0]] if video_choices else None
    initial_video_name = video_choices[0] if video_choices else None

    # Embed HTML Report preview via iframe
    preview_html = "<div style='padding:20px; color:#94a3b8;'>Report not found.</div>"
    if html_file and Path(html_file).exists():
        raw_html = Path(html_file).read_text(encoding="utf-8")
        escaped_doc = html.escape(raw_html)
        preview_html = f"""
        <iframe srcdoc="{escaped_doc}" style="width:100%; height:620px; border:1px solid rgba(255,255,255,0.1); border-radius:10px; background:#020617;"></iframe>
        """

    yield (
        status_banner,
        f"{passed} / {total}",
        pass_pct,
        step_rows,
        assertion_rows,
        valid_screenshots,
        full_log,
        html_file,
        gr.update(choices=video_choices, value=initial_video_name),
        initial_video,
        preview_html,
    )


def get_artifact_stats() -> str:
    """Calculate current storage count of test evidence."""
    sc_dir = BASE_DIR / "test_results" / "screenshots"
    vid_dir = BASE_DIR / "test_results" / "videos"
    rep_dir = BASE_DIR / "test_results" / "reports"
    sc_cnt = len(list(sc_dir.glob("*.png"))) if sc_dir.exists() else 0
    vid_cnt = len(list(vid_dir.glob("*.webm"))) if vid_dir.exists() else 0
    rep_cnt = len(list(rep_dir.glob("*.html"))) if rep_dir.exists() else 0
    return f"📊 **Current Storage:** `{sc_cnt}` screenshots • `{vid_cnt}` video recordings • `{rep_cnt}` reports"


def clear_old_artifacts() -> str:
    """Clean up old screenshots, videos, and reports to free up disk space."""
    sc_dir = BASE_DIR / "test_results" / "screenshots"
    vid_dir = BASE_DIR / "test_results" / "videos"
    rep_dir = BASE_DIR / "test_results" / "reports"
    del_count = 0
    for d in (sc_dir, vid_dir, rep_dir):
        if d.exists():
            for f in d.glob("*.*"):
                try:
                    f.unlink()
                    del_count += 1
                except Exception:
                    pass
    return f"🧹 Cleaned up {del_count} old test artifact files!"


CUSTOM_CSS = """
.gradio-container {
    max-width: 1400px !important;
    margin: auto !important;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important;
}
.preset-btn {
    border-radius: 8px !important;
    font-size: 12px !important;
    padding: 6px 12px !important;
}
"""

with gr.Blocks(title="BDD Agent v2 — Autonomous AI QA Engineer") as demo:
    gr.Markdown(
        """
        # 🤖 BDD Agent v2: Autonomous AI QA Testing Platform
        *Pure-Python Playwright FastMCP Engine • Gherkin BDD • Video Replay • Self-Contained HTML Reports*
        """
    )

    with gr.Row():
        # LEFT COLUMN: Scenario Configuration & Prompts
        with gr.Column(scale=5):
            gr.Markdown("#### 📝 Test Scenario Specification")

            with gr.Tabs():
                with gr.Tab("📁 Preloaded Suites"):
                    feature_dropdown = gr.Dropdown(
                        choices=list_feature_files(),
                        value=list_feature_files()[0] if list_feature_files() else None,
                        label="Select Test Suite",
                    )
                with gr.Tab("✨ AI Test Prompt (Natural Language)"):
                    test_prompt_input = gr.Textbox(
                        label="Describe test workflow in plain English",
                        placeholder="e.g. Test logging in to SauceDemo with standard_user and adding an item to the cart",
                        lines=3,
                    )
                    gr.Markdown("**Quick Presets (1-Click Fill):**")
                    with gr.Row():
                        btn_preset_sauce = gr.Button("🛒 SauceDemo Storefront", size="sm", elem_classes="preset-btn")
                        btn_preset_todo = gr.Button("📝 Simple Todo List", size="sm", elem_classes="preset-btn")
                        btn_preset_form = gr.Button("🔒 Form Validation", size="sm", elem_classes="preset-btn")

                    btn_generate = gr.Button("🪄 Generate Gherkin from Description", variant="secondary")

            feature_editor = gr.Code(
                label="Gherkin Feature (.feature) — Editable",
                language="markdown",
                lines=14,
                value=load_feature_content(list_feature_files()[0]) if list_feature_files() else "",
            )

            with gr.Row():
                btn_reset = gr.Button("🔄 Reload Selected Suite", size="sm")
                btn_clear = gr.Button("🧹 Clear Editor", size="sm")

            browser_mode_radio = gr.Radio(
                choices=["Headless (Fast / Background)", "Headed (Watch Chromium Live on Desktop)"],
                value="Headless (Fast / Background)",
                label="Browser Execution Mode",
            )

            with gr.Accordion("⚙️ Test Storage & Clean Up", open=False):
                storage_stats_text = gr.Markdown(value=get_artifact_stats())
                btn_clear_artifacts = gr.Button("🗑️ Clear Stored Screenshots & Videos", size="sm", variant="stop")
                storage_status_msg = gr.Markdown("")

            btn_run = gr.Button("🚀 Run BDD Test Suite", variant="primary", size="lg")

        # RIGHT COLUMN: Live Execution & Evidence Results
        with gr.Column(scale=6):
            gr.Markdown("#### 📊 Execution Results & Live Evidence")

            status_banner_output = gr.HTML(
                value="""
                <div style="padding:14px; background:rgba(255,255,255,0.04); border-radius:10px; border:1px solid rgba(255,255,255,0.1);">
                    Select a test scenario and click <b>Run BDD Test Suite</b>.
                </div>
                """
            )

            with gr.Row():
                metric_passed = gr.Textbox(label="Scenarios Passed", value="0 / 0", interactive=False)
                metric_pct = gr.Textbox(label="Pass Rate", value="N/A", interactive=False)

            with gr.Tabs():
                with gr.Tab("👣 Scenario Steps"):
                    steps_df = gr.Dataframe(
                        headers=["Scenario", "Status", "Phase", "Step Instruction"],
                        datatype=["str", "str", "str", "str"],
                        wrap=True,
                    )

                with gr.Tab("📋 Assertion Table"):
                    assertions_df = gr.Dataframe(
                        headers=["Scenario", "Status", "Type", "Details", "Expected"],
                        datatype=["str", "str", "str", "str", "str"],
                        wrap=True,
                    )

                with gr.Tab("📷 Captured Screenshots"):
                    screenshot_gallery = gr.Gallery(
                        label="Step Screenshots",
                        show_label=False,
                        columns=2,
                        height="auto",
                    )

                with gr.Tab("📜 Live Execution Logs"):
                    log_output = gr.Code(label="Agent Step Log (Live Streaming)", language="shell", lines=15)

                with gr.Tab("🎬 Video Replay"):
                    video_scenario_dropdown = gr.Dropdown(
                        label="Select Scenario Video to Watch",
                        choices=[],
                        value=None,
                        interactive=True,
                    )
                    video_player = gr.Video(label="Recorded Scenario Session", autoplay=True)

                with gr.Tab("🌐 HTML Report Preview"):
                    report_preview_html = gr.HTML(
                        value="<div style='padding:20px; color:#94a3b8;'>Execute a test suite to view the embedded interactive HTML report.</div>"
                    )

                with gr.Tab("💾 Download HTML Report"):
                    report_download = gr.File(label="Single-File HTML Report (.html)")

    # Event Wireups
    feature_dropdown.change(fn=load_feature_content, inputs=[feature_dropdown], outputs=[feature_editor])
    btn_reset.click(fn=load_feature_content, inputs=[feature_dropdown], outputs=[feature_editor])
    btn_clear.click(fn=lambda: "", outputs=[feature_editor])

    # Storage cleanup wireups
    btn_clear_artifacts.click(
        fn=clear_old_artifacts,
        outputs=[storage_status_msg],
    ).then(
        fn=get_artifact_stats,
        outputs=[storage_stats_text],
    )

    # Preset buttons
    btn_preset_sauce.click(
        fn=lambda: load_preset("🛒 SauceDemo Storefront"),
        outputs=[test_prompt_input, feature_editor],
    )
    btn_preset_todo.click(
        fn=lambda: load_preset("📝 Simple Todo List"),
        outputs=[test_prompt_input, feature_editor],
    )
    btn_preset_form.click(
        fn=lambda: load_preset("🔒 Form Validation"),
        outputs=[test_prompt_input, feature_editor],
    )

    btn_generate.click(fn=generate_gherkin_from_prompt, inputs=[test_prompt_input], outputs=[feature_editor])
    video_scenario_dropdown.change(fn=select_scenario_video, inputs=[video_scenario_dropdown], outputs=[video_player])

    btn_run.click(
        fn=run_bdd_ui,
        inputs=[feature_dropdown, feature_editor, browser_mode_radio],
        outputs=[
            status_banner_output,
            metric_passed,
            metric_pct,
            steps_df,
            assertions_df,
            screenshot_gallery,
            log_output,
            report_download,
            video_scenario_dropdown,
            video_player,
            report_preview_html,
        ],
    )


if __name__ == "__main__":
    demo.launch(server_name="127.0.0.1", server_port=7861, theme=gr.themes.Soft(), css=CUSTOM_CSS)
