"""
Assertion FastMCP Server for BDD Agent v2
Provides deterministic assertion tools for BDD verification steps.
"""

from __future__ import annotations

from typing import Any, Dict
from fastmcp import FastMCP

mcp = FastMCP("AssertionServer")


@mcp.tool()
async def assert_equals(actual: str, expected: str, message: str = "") -> Dict[str, Any]:
    """Assert that actual value matches expected value.

    Args:
        actual: The actual value observed.
        expected: The expected value.
        message: Optional diagnostic context.
    """
    passed = actual.strip() == expected.strip()
    return {
        "status": "passed" if passed else "failed",
        "type": "assert_equals",
        "actual": actual,
        "expected": expected,
        "message": message or (f"Expected '{expected}', got '{actual}'"),
    }


@mcp.tool()
async def assert_contains(
    text: str, substring: str, case_sensitive: bool = False, message: str = "") -> Dict[str, Any]:
    """Assert that a block of text contains the expected substring.

    Args:
        text: The source text or page content.
        substring: The text fragment that must be present.
        case_sensitive: Whether to perform case-sensitive check (default False).
        message: Optional diagnostic context.
    """
    src = text if case_sensitive else text.lower()
    sub = substring if case_sensitive else substring.lower()
    passed = sub in src
    return {
        "status": "passed" if passed else "failed",
        "type": "assert_contains",
        "actual": text[:300] + ("..." if len(text) > 300 else ""),
        "expected": substring,
        "message": message or (f"Text {'contains' if passed else 'does not contain'} '{substring}'"),
    }


@mcp.tool()
async def assert_not_contains(text: str, substring: str, message: str = "") -> Dict[str, Any]:
    """Assert that a block of text does NOT contain a prohibited substring.

    Args:
        text: The source text or page content.
        substring: The text that should be absent.
        message: Optional diagnostic context.
    """
    passed = substring.lower() not in text.lower()
    return {
        "status": "passed" if passed else "failed",
        "type": "assert_not_contains",
        "expected_absent": substring,
        "message": message or (f"Text {'does not contain' if passed else 'contains prohibited'} '{substring}'"),
    }


@mcp.tool()
async def assert_count(
    actual: int, expected: int, comparison: str = "at_least", message: str = "") -> Dict[str, Any]:
    """Assert count of elements against expected threshold.

    Args:
        actual: The observed numeric count.
        expected: The target count.
        comparison: One of 'exact', 'at_least', 'at_most'.
        message: Optional diagnostic message.
    """
    if comparison == "at_least":
        passed = actual >= expected
    elif comparison == "at_most":
        passed = actual <= expected
    else:
        passed = actual == expected

    return {
        "status": "passed" if passed else "failed",
        "type": "assert_count",
        "actual": actual,
        "expected": expected,
        "comparison": comparison,
        "message": message or (f"Count {actual} {comparison} {expected}"),
    }


@mcp.tool()
async def assert_visible(is_visible: bool, element_name: str = "Element", message: str = "") -> Dict[str, Any]:
    """Assert that a target UI element is visible.

    Args:
        is_visible: True if visible, False otherwise.
        element_name: Identifier or description of the element.
        message: Optional diagnostic context.
    """
    return {
        "status": "passed" if is_visible else "failed",
        "type": "assert_visible",
        "element": element_name,
        "message": message or (f"{element_name} is {'visible' if is_visible else 'not visible'}"),
    }


if __name__ == "__main__":
    mcp.run(transport="stdio")
