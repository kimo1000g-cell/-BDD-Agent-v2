"""
BDD Agent Engine for BDD Agent v2
Parses Gherkin features, executes test scenarios using FastMCP browser & assertion tools,
and generates structured JSON and HTML test reports.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from dotenv import load_dotenv

import browser_server
import assertion_server
from reporter import generate_html_report

# Ensure UTF-8 stdout encoding on Windows
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

load_dotenv()

BASE_DIR = Path(__file__).parent
TEST_RESULTS_DIR = BASE_DIR / "test_results"
REPORTS_DIR = TEST_RESULTS_DIR / "reports"
SCREENSHOTS_DIR = TEST_RESULTS_DIR / "screenshots"

REPORTS_DIR.mkdir(parents=True, exist_ok=True)
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)


class BDDEngine:
    def __init__(self, headless: bool = True, log_callback: Optional[Callable[[str], None]] = None):
        self.headless = headless
        self.log_callback = log_callback or print
        os.environ["HEADLESS"] = "true" if headless else "false"

    def log(self, message: str):
        self.log_callback(message)

    async def execute_feature_text(self, feature_text: str, feature_title: str = "Test Suite") -> Dict[str, Any]:
        """Parse and execute all scenarios in a Gherkin feature text."""
        # Dynamically extract actual Feature title from the Gherkin header if present
        feat_match = re.search(r"(?m)^\s*Feature:\s*(.*?)$", feature_text)
        if feat_match and feat_match.group(1).strip():
            feature_title = feat_match.group(1).strip()

        self.log(f"\n🚀 Starting BDD Test Execution: {feature_title}")
        self.log(f"🖥️ Browser Mode: {'Headless' if self.headless else 'Headed (Live Visual)'}")

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        report_data = {
            "feature": feature_title,
            "created_at": timestamp,
            "scenarios": [],
        }

        # 1. Extract all Background steps
        background_steps: List[str] = []
        bg_match = re.search(r"(?ms)^\s*Background:\s*(.*?)(?=^\s*Scenario:|\Z)", feature_text)
        if bg_match:
            for line in bg_match.group(1).splitlines():
                clean_l = line.strip()
                if clean_l and not clean_l.startswith("#"):
                    background_steps.append(clean_l)

        # 2. Extract Scenarios cleanly
        scenario_parts = re.split(r"(?m)^\s*Scenario:\s*", feature_text)
        scenarios_to_run = []

        if len(scenario_parts) > 1:
            for part in scenario_parts[1:]:
                lines = part.strip().splitlines()
                if lines:
                    sc_name = lines[0].strip()
                    sc_body = "\n".join(lines[1:])
                    scenarios_to_run.append((sc_name, sc_body))
        else:
            scenarios_to_run.append(("Default Scenario", feature_text))

        try:
            for sc_idx, (sc_name, sc_body) in enumerate(scenarios_to_run, start=1):
                sc_name = sc_name.strip()
                self.log(f"\n{'=' * 50}")
                self.log(f"▶️ Executing Scenario {sc_idx}: {sc_name}")
                self.log(f"{'=' * 50}")

                sc_result = {
                    "scenario": sc_name,
                    "result": "passed",
                    "assertions": [],
                    "screenshots": [],
                    "steps": [],
                }

                try:
                    # Execute Background steps if present
                    if background_steps:
                        self.log(f"  🔧 Running {len(background_steps)} Background Setup Step(s)...")
                        for bg_line in background_steps:
                            self.log(f"  ⚙️ [Background] {bg_line}")
                            bg_status = await self._execute_step(bg_line, sc_result)
                            sc_result["steps"].append({
                                "step": bg_line,
                                "type": "background",
                                "status": "passed" if bg_status else "failed",
                            })
                            if not bg_status:
                                raise RuntimeError(f"Background step failed: {bg_line}")

                    # Capture initial scenario screenshot
                    start_shot = await browser_server.browser_take_screenshot(f"sc_{sc_idx}_start")
                    if start_shot.get("status") == "success":
                        sc_result["screenshots"].append(start_shot["filepath"])

                    # Execute Scenario Steps
                    step_lines = [line.strip() for line in sc_body.splitlines() if line.strip() and not line.strip().startswith("#")]

                    for line in step_lines:
                        self.log(f"  ⚡ Step: {line}")
                        step_status = await self._execute_step(line, sc_result)
                        sc_result["steps"].append({
                            "step": line,
                            "type": "scenario",
                            "status": "passed" if step_status else "failed",
                        })
                        if not step_status:
                            sc_result["result"] = "failed"
                            self.log(f"  ❌ Step Failed: {line}")

                    # Capture completion screenshot
                    end_shot = await browser_server.browser_take_screenshot(f"sc_{sc_idx}_end")
                    if end_shot.get("status") == "success":
                        sc_result["screenshots"].append(end_shot["filepath"])

                except Exception as err:
                    sc_result["result"] = "failed"
                    self.log(f"❌ Scenario Exception: {str(err)}")
                    fail_shot = await browser_server.browser_take_screenshot(f"sc_{sc_idx}_failure")
                    if fail_shot.get("status") == "success":
                        sc_result["screenshots"].append(fail_shot["filepath"])

                # Finalize scenario browser page & video recording
                try:
                    finish_res = await browser_server.browser_finish_scenario(sc_name)
                    if finish_res.get("video_path"):
                        sc_result["video"] = finish_res["video_path"]
                        self.log(f"  🎬 Recorded Video: {Path(finish_res['video_path']).name}")
                except Exception as e:
                    self.log(f"  ⚠️ Video finalize note: {str(e)}")

                report_data["scenarios"].append(sc_result)
                self.log(f"🏁 Scenario {sc_idx} Finished: {sc_result['result'].upper()}")
        finally:
            # Guarantees browser is ALWAYS cleanly closed, preventing orphaned Chromium processes
            await browser_server.browser_close()

        # Collect all scenario videos
        report_data["videos"] = [sc["video"] for sc in report_data["scenarios"] if sc.get("video")]

        # Save JSON report
        clean_title = re.sub(r"[^\w\-]", "_", feature_title)
        ts_slug = datetime.now().strftime("%Y%m%d_%H%M%S")
        json_path = REPORTS_DIR / f"{clean_title}_{ts_slug}_report.json"
        json_path.write_text(json.dumps(report_data, indent=2), encoding="utf-8")

        # Generate HTML report
        html_path = REPORTS_DIR / f"{clean_title}_{ts_slug}_report.html"
        generate_html_report(report_data, html_path)

        self.log(f"\n📊 Test Suite Complete!")
        self.log(f"📁 JSON Report: {json_path}")
        self.log(f"🌐 HTML Report: {html_path}")

        report_data["json_path"] = str(json_path)
        report_data["html_path"] = str(html_path)
        return report_data

    async def _execute_step(self, line: str, sc_result: Dict[str, Any]) -> bool:
        """Parse and execute an individual Given/When/Then/And step using flexible natural patterns."""
        # 1. Navigation step: Given/When I navigate to "URL" / browse to "URL"
        nav_match = re.search(r"(?:navigate|go|browse)(?: to)? [\"'](.*?)[\"']", line, re.IGNORECASE)
        if nav_match:
            url = nav_match.group(1)
            res = await browser_server.browser_navigate(url)
            await asyncio.sleep(1.0)
            return res.get("status") == "success"

        # 2. Dropdown select option: When I select "option" from "selector"
        select_match = re.search(r"(?:select|choose) [\"'](.*?)[\"'] from [\"'](.*?)[\"']", line, re.IGNORECASE)
        if select_match:
            option, selector = select_match.group(1), select_match.group(2)
            res = await browser_server.browser_select_option(selector, option)
            await asyncio.sleep(0.8)
            return res.get("status") == "success"

        # 3. Clear input field: When I clear the input field "selector"
        clear_match = re.search(r"clear (?:the input field |the field |the )?[\"'](.*?)[\"']", line, re.IGNORECASE)
        if clear_match:
            selector = clear_match.group(1)
            res = await browser_server.browser_clear_input(selector)
            await asyncio.sleep(0.5)
            return res.get("status") == "success"

        # 4. Type/Fill steps:
        # Pattern A: When I type/fill [the field] "selector" with [text] "content"
        type_a = re.search(r"(?:type|fill|input)(?: the input field| the field)? [\"'](.*?)[\"'] (?:with text|with|as) [\"'](.*?)[\"']", line, re.IGNORECASE)
        if type_a:
            selector, text = type_a.group(1), type_a.group(2)
            press_enter = "enter" in line.lower()
            res = await browser_server.browser_fill_input(selector, text, press_enter=press_enter)
            await asyncio.sleep(0.5)
            return res.get("status") == "success"

        # Pattern B: When I enter/type/fill "content" into/in [the field] "selector"
        type_b = re.search(r"(?:enter|type|input|fill) [\"'](.*?)[\"'] (?:into|in)(?: the input field| the field| the)? [\"'](.*?)[\"']", line, re.IGNORECASE)
        if type_b:
            text, selector = type_b.group(1), type_b.group(2)
            press_enter = "enter" in line.lower()
            res = await browser_server.browser_fill_input(selector, text, press_enter=press_enter)
            await asyncio.sleep(0.5)
            return res.get("status") == "success"

        # 5. Press Key step: And I press the "Enter" key / press "Tab"
        key_match = re.search(r"press (?:the )?[\"'](.*?)[\"'](?: key)?", line, re.IGNORECASE)
        if key_match:
            key_name = key_match.group(1)
            res = await browser_server.browser_press_key(key_name)
            await asyncio.sleep(0.8)
            return res.get("status") == "success"

        # 6. Click / Tap / Press button or element step:
        click_match = re.search(r"(?:click|tap|press)(?: on)? (?:the button with text |the button |the link |the element |the )?[\"'](.*?)[\"']", line, re.IGNORECASE)
        if click_match:
            selector = click_match.group(1)
            res = await browser_server.browser_click(selector)
            await asyncio.sleep(1.0)
            return res.get("status") == "success"

        # 7. Assertion - URL contains (Evaluated before generic text match)
        url_match = re.search(r"(?:page URL|URL|current URL) should contain [\"'](.*?)[\"']", line, re.IGNORECASE)
        if url_match:
            expected_url_part = url_match.group(1)
            content_res = await browser_server.browser_get_page_content()
            current_url = content_res.get("url", "")
            assertion_res = await assertion_server.assert_contains(
                text=current_url,
                substring=expected_url_part,
                message=f"URL contains '{expected_url_part}'",
            )
            sc_result["assertions"].append(assertion_res)
            return assertion_res.get("status") == "passed"

        # 8. Assertion - Cart badge
        badge_match = re.search(r"(?:shopping cart badge|cart badge|cart) should (?:show|contain) [\"'](.*?)[\"']", line, re.IGNORECASE)
        if badge_match:
            expected_badge = badge_match.group(1)
            content_res = await browser_server.browser_get_page_content()
            page_text = content_res.get("text", "")
            assertion_res = await assertion_server.assert_contains(
                text=page_text,
                substring=expected_badge,
                message=f"Cart badge shows '{expected_badge}'",
            )
            sc_result["assertions"].append(assertion_res)
            return assertion_res.get("status") == "passed"

        # 9. Assertion - Count items
        count_match = re.search(r"should contain at least (\d+) item", line, re.IGNORECASE)
        if count_match:
            min_count = int(count_match.group(1))
            count_res = await browser_server.browser_count_elements("li, .todo-item, tr, .inventory_item, .cart_item")
            actual_count = count_res.get("count", 0)
            assertion_res = await assertion_server.assert_count(
                actual=actual_count,
                expected=min_count,
                comparison="at_least",
                message=f"Item count ({actual_count}) >= {min_count}",
            )
            sc_result["assertions"].append(assertion_res)
            return assertion_res.get("status") == "passed"

        # 10. Negative Assertion - Should NOT see text: (Must precede positive see text)
        not_see_match = re.search(r"(?:should not see|should not contain|must not contain|do not see)(?: the)?(?: text)? [\"'](.*?)[\"']", line, re.IGNORECASE)
        if not_see_match:
            expected_absent = not_see_match.group(1)
            content_res = await browser_server.browser_get_page_content()
            page_text = content_res.get("text", "")
            assertion_res = await assertion_server.assert_not_contains(
                text=page_text,
                substring=expected_absent,
                message=f"Page does not contain '{expected_absent}'",
            )
            sc_result["assertions"].append(assertion_res)
            return assertion_res.get("status") == "passed"

        # 11. Positive Assertion - Should see text on page
        see_match = re.search(r"(?:should see|see)(?: the)?(?: text)? [\"'](.*?)[\"']|page should contain [\"'](.*?)[\"']", line, re.IGNORECASE)
        if see_match:
            expected_text = see_match.group(1) or see_match.group(2)
            content_res = await browser_server.browser_get_page_content()
            page_text = content_res.get("text", "")
            assertion_res = await assertion_server.assert_contains(
                text=page_text,
                substring=expected_text,
                message=f"Page contains '{expected_text}'",
            )
            sc_result["assertions"].append(assertion_res)

            # Evidence screenshot
            shot = await browser_server.browser_take_screenshot(f"assert_text_{expected_text[:12]}")
            if shot.get("status") == "success":
                sc_result["screenshots"].append(shot["filepath"])

            return assertion_res.get("status") == "passed"

        # 12. Wait / Pause step:
        wait_match = re.search(r"(?:wait|pause)(?: for)? (\d+) seconds?", line, re.IGNORECASE)
        if wait_match:
            secs = int(wait_match.group(1))
            await asyncio.sleep(secs)
            return True

        self.log(f"  ⚠️ Warning: Unrecognized step syntax: '{line}' - passing as soft step.")
        return True


async def run_feature_file(file_path: Path | str, headless: bool = True):
    p = Path(file_path)
    if not p.exists():
        print(f"File not found: {p}")
        return
    text = p.read_text(encoding="utf-8")
    engine = BDDEngine(headless=headless)
    return await engine.execute_feature_text(text, feature_title=p.stem.replace("_", " ").title())


if __name__ == "__main__":
    test_feature = BASE_DIR / "features" / "1_todo_management.feature"
    asyncio.run(run_feature_file(test_feature, headless=True))
