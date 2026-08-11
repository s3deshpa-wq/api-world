"""
Test that get_time() (venv/tool_agent.py) rejects non-string city input.

Run:  pytest -v tests/test_get_time_numeric_city.py   (from the repo root)

get_time() validates that city is a string before calling .strip() on it,
so a numeric input returns a graceful "Error: ..." message instead of
crashing with AttributeError.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "venv"))

import tool_agent


def test_numeric_city_input():
    result = tool_agent.get_time(12345)
    assert isinstance(result, str) and result.startswith("Error"), (
        f"Expected a graceful 'Error: ...' message for a numeric city input, "
        f"but got: {result!r}"
    )
