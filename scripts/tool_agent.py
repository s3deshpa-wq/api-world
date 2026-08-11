"""
Tool-use agent built on the Anthropic SDK's Tool Runner.

Run:  python tool_agent.py
Needs: pip install anthropic python-dotenv   (and ANTHROPIC_API_KEY in venv/.env)

Unlike agentCall.py / agent_traced.py in this folder, which hand-write the
tool-call loop, this script uses client.beta.messages.tool_runner(...) — the
SDK drives the "call model, run tool, feed result back, repeat" loop for you.
Tools are plain functions decorated with @beta_tool; the schema is generated
from the function signature and docstring.
"""

import ast
import operator
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import httpx
from dotenv import load_dotenv
import anthropic
from anthropic import beta_tool

# ============================================================================
# TOOLS
# ============================================================================

_SAFE_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
}


def _safe_eval(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _SAFE_OPS:
        return _SAFE_OPS[type(node.op)](_safe_eval(node.left), _safe_eval(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _SAFE_OPS:
        return _SAFE_OPS[type(node.op)](_safe_eval(node.operand))
    raise ValueError(f"unsupported expression: {ast.dump(node)}")


@beta_tool
def calculate(expression: str) -> str:
    """Evaluate a basic arithmetic expression.

    Args:
        expression: An arithmetic expression using +, -, *, /, ** and
            parentheses, e.g. "12 * (4 + 3)".
    """
    try:
        tree = ast.parse(expression, mode="eval")
        return str(_safe_eval(tree.body))
    except Exception as e:
        return f"Error: could not evaluate '{expression}' ({e})"


@beta_tool
def get_weather(city: str) -> str:
    """Get the current weather for a city.

    Args:
        city: City name, e.g. "Tokyo".
    """
    fake_data = {
        "tokyo": "27C, partly cloudy",
        "london": "18C, light rain",
        "new york": "24C, sunny",
        "mumbai": "31C, humid with scattered showers",
    }
    return fake_data.get(city.strip().lower(), "21C, clear skies")


_GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
_GEOCODE_TIMEOUT = 5.0  # seconds


@beta_tool
def get_time(city: str) -> str:
    """Get the current time in a city, anywhere in the world.

    Resolves the city via the Open-Meteo geocoding API. If multiple
    real-world places share the name (e.g. "Paris" in France vs. Texas),
    the best-ranked match is used and its full location is included in
    the result so it's clear which place was resolved.

    Args:
        city: City name, e.g. "Tokyo" or "Springfield".
    """
    if not isinstance(city, str):
        return f"Error: city must be a string, got {type(city).__name__}."

    query = city.strip()
    if not query:
        return "Error: city name must not be empty."

    try:
        resp = httpx.get(
            _GEOCODE_URL,
            params={"name": query, "count": 1, "language": "en", "format": "json"},
            timeout=_GEOCODE_TIMEOUT,
        )
        resp.raise_for_status()
    except httpx.TimeoutException:
        return f"Error: timed out looking up '{city}'. Please try again."
    except httpx.ConnectError:
        return f"Error: could not reach the geocoding service to look up '{city}'. Check your internet connection."
    except httpx.HTTPStatusError as e:
        return f"Error: geocoding service returned {e.response.status_code} for '{city}'."
    except httpx.HTTPError as e:
        return f"Error: geocoding lookup for '{city}' failed ({e})."

    try:
        data = resp.json()
    except ValueError:
        return f"Error: geocoding service returned an unreadable response for '{city}'."

    results = data.get("results") if isinstance(data, dict) else None
    if not results:
        return f"Unknown city '{city}'. No matching location found."

    top = results[0]
    tz_name = top.get("timezone")
    if not tz_name:
        return f"Error: no timezone information available for '{city}'."

    try:
        now = datetime.now(ZoneInfo(tz_name))
    except ZoneInfoNotFoundError:
        return f"Error: unrecognized timezone '{tz_name}' for '{city}'."

    resolved_name = top.get("name", city)
    country = top.get("country")
    admin1 = top.get("admin1")
    if admin1 and country:
        where = f"{resolved_name}, {admin1}, {country}"
    elif country:
        where = f"{resolved_name}, {country}"
    else:
        where = resolved_name

    return f"{where}: {now.strftime('%Y-%m-%d %I:%M %p %Z')}"


_CURRENCY_TO_INR = {
    "inr": 1.0,
    "usd": 83.0,
    "eur": 90.0,
    "gbp": 105.0,
    "jpy": 0.55,
}


@beta_tool
def calculate_net_price(original_price: float, discount_percent: float, currency: str = "INR") -> str:
    """Calculate the net price, in INR, after applying a percentage discount.

    If original_price is given in a non-INR currency, it is first converted
    to INR using a fixed approximate exchange rate, then the discount is
    applied.

    Args:
        original_price: The original price before discount.
        discount_percent: The discount percentage to apply, e.g. 20 for 20% off.
        currency: Currency of original_price (e.g. "USD", "EUR", "GBP", "JPY", "INR"). Defaults to "INR".
    """
    if original_price < 0 or discount_percent < 0:
        return "Error: original_price and discount_percent must be non-negative"
    rate = _CURRENCY_TO_INR.get(currency.strip().lower())
    if rate is None:
        known = ", ".join(sorted(c.upper() for c in _CURRENCY_TO_INR))
        return f"Error: unsupported currency '{currency}'. Known currencies: {known}"
    price_inr = original_price * rate
    net_price = price_inr * (1 - discount_percent / 100)
    return f"INR {net_price:.2f}"


TOOLS = [calculate, get_weather, get_time, calculate_net_price]

# ============================================================================
# MAIN — multi-turn loop; each turn runs the tool-runner to completion
# ============================================================================


def main():
    load_dotenv()
    client = anthropic.Anthropic()

    print(__doc__)
    print("Try: What's the weather in Mumbai, what's 45 * (12 + 3),")
    print("     what time is it in Tokyo, and what's the net price of a")
    print("     $80 item with a 15% discount?")
    print("Type 'quit' to exit.\n")

    history = []
    while True:
        user_input = input(">>> ")
        if user_input.strip().lower() == "quit":
            break
        if not user_input.strip():
            continue

        history.append({"role": "user", "content": user_input})

        runner = client.beta.messages.tool_runner(
            model="claude-opus-5",
            max_tokens=1024,
            thinking={"type": "adaptive"},
            output_config={"effort": "medium"},
            tools=TOOLS,
            messages=history,
        )

        final_message = None
        for message in runner:
            final_message = message

        if final_message is None:
            print("(no response)")
            continue

        history.append({"role": "assistant", "content": final_message.content})
        text = "".join(b.text for b in final_message.content if b.type == "text")
        print(f"\nClaude: {text}\n")


if __name__ == "__main__":
    main()
