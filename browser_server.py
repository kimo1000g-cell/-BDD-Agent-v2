"""
Pure-Python Playwright FastMCP Server for BDD Agent v2
Eliminates Node.js / npx dependency. Provides full browser automation tools.
Supports both Headless (background) and Headed (watch live on desktop) modes.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional
from fastmcp import FastMCP

# Ensure UTF-8 stdout encoding on Windows
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

mcp = FastMCP("PlaywrightBrowserServer")

# Global Browser State
_PLAYWRIGHT: Any = None
_BROWSER: Any = None
_CONTEXT: Any = None
_PAGE: Any = None

# Results directories
RESULTS_DIR = Path(__file__).parent / "test_results"
SCREENSHOTS_DIR = RESULTS_DIR / "screenshots"
VIDEOS_DIR = RESULTS_DIR / "videos"
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
VIDEOS_DIR.mkdir(parents=True, exist_ok=True)


async def _ensure_page():
    """Ensure a Playwright browser and page are initialized and active."""
    global _PLAYWRIGHT, _BROWSER, _CONTEXT, _PAGE

    if _PAGE is not None and not _PAGE.is_closed():
        return _PAGE

    from playwright.async_api import async_playwright

    if _PLAYWRIGHT is None:
        _PLAYWRIGHT = await async_playwright().start()

    headless_env = os.getenv("HEADLESS", "true").lower() in ("true", "1", "yes")

    if _BROWSER is None:
        _BROWSER = await _PLAYWRIGHT.chromium.launch(
            headless=headless_env,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )

    if _CONTEXT is None:
        record_video = os.getenv("RECORD_VIDEO", "true").lower() in ("true", "1", "yes")
        context_kwargs = {
            "viewport": {"width": 1280, "height": 800},
            "device_scale_factor": 1,
        }
        if record_video:
            context_kwargs["record_video_dir"] = str(VIDEOS_DIR)
            context_kwargs["record_video_size"] = {"width": 1280, "height": 800}

        _CONTEXT = await _BROWSER.new_context(**context_kwargs)

    _PAGE = await _CONTEXT.new_page()
    return _PAGE


@mcp.tool()
async def browser_navigate(url: str) -> Dict[str, Any]:
    """Navigate to a website URL and wait for page to load.

    Args:
        url: The complete HTTP or HTTPS URL to load.
    """
    page = await _ensure_page()
    try:
        response = await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        status = response.status if response else 200
        title = await page.title()
        return {
            "status": "success",
            "url": page.url,
            "title": title,
            "http_status": status,
        }
    except Exception as e:
        return {"status": "error", "message": f"Navigation failed: {str(e)}"}


import re


async def _resolve_locator(page: Any, selector: str, purpose: str = "click") -> Any:
    """Find a target locator using resilient multi-attribute and text fallback strategies.
    
    Prevents crashes caused by unescaped punctuation or invalid CSS syntax in selectors,
    and supports data-test attributes, placeholders, labels, and case-insensitive text.
    """
    clean_sel = selector.strip()
    candidates = []

    # 1. Direct CSS/XPath selector if valid
    try:
        loc = page.locator(clean_sel)
        candidates.append(loc)
    except Exception:
        pass

    # 2. Click-specific strategies (Button, Link, ARIA role)
    if purpose == "click":
        try:
            candidates.append(page.get_by_role("button", name=re.compile(re.escape(clean_sel), re.IGNORECASE)))
            candidates.append(page.get_by_role("link", name=re.compile(re.escape(clean_sel), re.IGNORECASE)))
        except Exception:
            pass

    # 3. Form input strategies (Placeholder, Label)
    if purpose == "fill":
        try:
            candidates.append(page.get_by_placeholder(clean_sel, exact=False))
            candidates.append(page.get_by_label(clean_sel, exact=False))
        except Exception:
            pass

    # 4. Standard QA test attributes & HTML identifier attributes
    safe_attr = clean_sel.replace('"', '\\"')
    attr_selectors = [
        f'[data-test="{safe_attr}"]',
        f'[data-testid="{safe_attr}"]',
        f'[id="{safe_attr}"]',
        f'[name="{safe_attr}"]',
        f'input[placeholder="{safe_attr}"]',
        f'[aria-label="{safe_attr}"]',
    ]
    for attr_sel in attr_selectors:
        try:
            candidates.append(page.locator(attr_sel))
        except Exception:
            pass

    # 5. Case-insensitive visible text match
    try:
        candidates.append(page.get_by_text(re.compile(re.escape(clean_sel), re.IGNORECASE)))
    except Exception:
        pass

    # 6. Secondary fallback: placeholder and label even if purpose == 'click'
    try:
        candidates.append(page.get_by_placeholder(clean_sel, exact=False))
        candidates.append(page.get_by_label(clean_sel, exact=False))
    except Exception:
        pass

    # Iterate through candidates and pick the first one that exists
    for candidate in candidates:
        try:
            if await candidate.count() > 0:
                return candidate.first
        except Exception:
            continue

    # Default fallback: return the primary candidate or text locator to allow wait_for error
    try:
        return page.get_by_text(clean_sel, exact=False).first
    except Exception:
        return page.locator(clean_sel).first


@mcp.tool()
async def browser_click(selector: str, hint: str = "") -> Dict[str, Any]:
    """Click an element on the page using a smart selector or text hint.

    Args:
        selector: CSS selector, XPath, button text, or attribute hint.
        hint: Optional contextual hint describing the element.
    """
    page = await _ensure_page()
    try:
        target = await _resolve_locator(page, selector, purpose="click")
        await target.wait_for(state="visible", timeout=10000)
        try:
            await target.scroll_into_view_if_needed(timeout=3000)
        except Exception:
            pass
        await target.click()
        return {"status": "success", "action": "clicked", "selector": selector}
    except Exception as e:
        return {"status": "error", "message": f"Failed to click '{selector}': {str(e)}"}


@mcp.tool()
async def browser_fill_input(selector: str, text: str, press_enter: bool = False) -> Dict[str, Any]:
    """Type text into an input field or textarea, optionally pressing Enter.

    Args:
        selector: CSS selector, placeholder, name, ID, or label text for the input element.
        text: The text string to enter.
        press_enter: If True, simulates pressing the Enter key after typing.
    """
    page = await _ensure_page()
    try:
        target = await _resolve_locator(page, selector, purpose="fill")
        await target.wait_for(state="visible", timeout=10000)
        try:
            await target.scroll_into_view_if_needed(timeout=3000)
        except Exception:
            pass
        await target.fill(text)

        if press_enter:
            await target.press("Enter")

        return {
            "status": "success",
            "action": "filled_input",
            "selector": selector,
            "pressed_enter": press_enter,
        }
    except Exception as e:
        return {"status": "error", "message": f"Failed to fill input '{selector}': {str(e)}"}


@mcp.tool()
async def browser_select_option(selector: str, option: str) -> Dict[str, Any]:
    """Select an option from a <select> dropdown element by label or value.

    Args:
        selector: CSS selector, name, or ID of the select element.
        option: Text label or value attribute of the option to choose.
    """
    page = await _ensure_page()
    try:
        target = await _resolve_locator(page, selector, purpose="fill")
        await target.wait_for(state="visible", timeout=10000)
        try:
            await target.scroll_into_view_if_needed(timeout=3000)
        except Exception:
            pass
        try:
            await target.select_option(label=option)
        except Exception:
            await target.select_option(value=option)

        return {
            "status": "success",
            "action": "selected_option",
            "selector": selector,
            "option": option,
        }
    except Exception as e:
        return {"status": "error", "message": f"Failed to select option '{option}' on '{selector}': {str(e)}"}


@mcp.tool()
async def browser_clear_input(selector: str) -> Dict[str, Any]:
    """Clear existing text from an input field or textarea.

    Args:
        selector: CSS selector, placeholder, name, ID, or label of the input element.
    """
    page = await _ensure_page()
    try:
        target = await _resolve_locator(page, selector, purpose="fill")
        await target.wait_for(state="visible", timeout=10000)
        await target.fill("")
        return {"status": "success", "action": "cleared_input", "selector": selector}
    except Exception as e:
        return {"status": "error", "message": f"Failed to clear input '{selector}': {str(e)}"}


@mcp.tool()
async def browser_press_key(key: str) -> Dict[str, Any]:
    """Press a keyboard key (e.g. 'Enter', 'Tab', 'Escape', 'ArrowDown').

    Args:
        key: The key name to press.
    """
    page = await _ensure_page()
    try:
        await page.keyboard.press(key)
        return {"status": "success", "action": "pressed_key", "key": key}
    except Exception as e:
        return {"status": "error", "message": f"Failed to press key '{key}': {str(e)}"}


@mcp.tool()
async def browser_take_screenshot(name: str = "step") -> Dict[str, Any]:
    """Capture a screenshot of the current browser viewport and save as PNG evidence.

    Args:
        name: A descriptive label for the screenshot (e.g. 'scenario_1_login_success').
    """
    page = await _ensure_page()
    clean_name = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in name)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:19]
    filename = f"{clean_name}_{ts}.png"
    filepath = SCREENSHOTS_DIR / filename

    try:
        await page.screenshot(path=str(filepath), full_page=False)
        return {
            "status": "success",
            "action": "screenshot_captured",
            "filename": filename,
            "filepath": str(filepath.resolve()),
        }
    except Exception as e:
        return {"status": "error", "message": f"Screenshot failed: {str(e)}"}


@mcp.tool()
async def browser_get_page_content() -> Dict[str, Any]:
    """Extract full visible text content and URL of the current page for assertions."""
    page = await _ensure_page()
    try:
        url = page.url
        title = await page.title()
        text = await page.inner_text("body")
        return {
            "status": "success",
            "url": url,
            "title": title,
            "text": text[:15000],  # Return up to 15k characters of visible text
        }
    except Exception as e:
        return {"status": "error", "message": f"Failed to get page content: {str(e)}"}


@mcp.tool()
async def browser_count_elements(selector: str) -> Dict[str, Any]:
    """Count the number of matching elements on the current page.

    Args:
        selector: CSS or text selector for the target elements.
    """
    page = await _ensure_page()
    try:
        count = await page.locator(selector).count()
        return {
            "status": "success",
            "selector": selector,
            "count": count,
        }
    except Exception as e:
        return {"status": "error", "message": f"Failed to count elements: {str(e)}"}


@mcp.tool()
async def browser_finish_scenario(scenario_name: str = "scenario") -> Dict[str, Any]:
    """Finish the current scenario page, flush and finalize its video recording, and return the video path.

    Args:
        scenario_name: Name of the scenario used to name the video file.
    """
    global _PAGE
    video_path = None
    clean_name = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in scenario_name)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    target_filename = f"{clean_name}_{ts}.webm"
    target_path = VIDEOS_DIR / target_filename

    try:
        if _PAGE and not _PAGE.is_closed():
            video_obj = _PAGE.video
            # Close page to flush video write to disk
            await _PAGE.close()
            _PAGE = None

            if video_obj:
                try:
                    await video_obj.save_as(str(target_path))
                    if target_path.exists() and target_path.stat().st_size > 0:
                        video_path = str(target_path.resolve())
                        # Safely clean up raw temporary file
                        try:
                            await video_obj.delete()
                        except Exception:
                            pass
                except Exception:
                    if target_path.exists() and target_path.stat().st_size > 0:
                        video_path = str(target_path.resolve())

        return {
            "status": "success",
            "video_path": video_path,
            "filename": target_filename if video_path else None,
        }
    except Exception as e:
        return {"status": "error", "message": f"Failed to finalize video: {str(e)}"}


@mcp.tool()
async def browser_close() -> Dict[str, Any]:
    """Close the current browser session and release system resources."""
    global _PLAYWRIGHT, _BROWSER, _CONTEXT, _PAGE
    try:
        if _PAGE and not _PAGE.is_closed():
            await _PAGE.close()
        if _CONTEXT:
            await _CONTEXT.close()
        if _BROWSER:
            await _BROWSER.close()
        if _PLAYWRIGHT:
            await _PLAYWRIGHT.stop()

        _PLAYWRIGHT = _BROWSER = _CONTEXT = _PAGE = None
        return {"status": "success", "message": "Browser session closed cleanly."}
    except Exception as e:
        return {"status": "error", "message": f"Failed to close browser: {str(e)}"}


if __name__ == "__main__":
    mcp.run(transport="stdio")
