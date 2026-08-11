"""
Tests for get_time() in tool_agent.py.

Run:  pytest -v test_tool_agent.py   (from inside venv/, with the venv active)

All httpx.get calls are mocked - no real network traffic hits Open-Meteo.
"""

import httpx

import tool_agent


def _fake_get(json_body, status_code=200):
    def _get(url, params=None, timeout=None):
        request = httpx.Request("GET", url, params=params)
        return httpx.Response(status_code, json=json_body, request=request)
    return _get


def _raising_get(exc):
    def _get(url, params=None, timeout=None):
        raise exc
    return _get


def _result(name, country=None, admin1=None, timezone="UTC"):
    r = {"name": name, "timezone": timezone}
    if country is not None:
        r["country"] = country
    if admin1 is not None:
        r["admin1"] = admin1
    return r


def test_known_city_tokyo(monkeypatch):
    monkeypatch.setattr(tool_agent.httpx, "get", _fake_get(
        {"results": [_result("Tokyo", country="Japan", timezone="Asia/Tokyo")]}
    ))
    out = tool_agent.get_time("Tokyo")
    assert "Tokyo" in out and "Japan" in out
    assert out.split(": ", 1)[1]  # timestamp portion present


def test_regression_hardcoded_london(monkeypatch):
    monkeypatch.setattr(tool_agent.httpx, "get", _fake_get(
        {"results": [_result("London", country="United Kingdom", timezone="Europe/London")]}
    ))
    out = tool_agent.get_time("London")
    assert "London" in out and "United Kingdom" in out


def test_regression_hardcoded_new_york(monkeypatch):
    monkeypatch.setattr(tool_agent.httpx, "get", _fake_get(
        {"results": [_result("New York", country="United States", admin1="New York", timezone="America/New_York")]}
    ))
    out = tool_agent.get_time("New York")
    assert "New York" in out and "United States" in out


def test_regression_hardcoded_mumbai(monkeypatch):
    monkeypatch.setattr(tool_agent.httpx, "get", _fake_get(
        {"results": [_result("Mumbai", country="India", admin1="Maharashtra", timezone="Asia/Kolkata")]}
    ))
    out = tool_agent.get_time("Mumbai")
    assert "Mumbai" in out and "India" in out


def test_unicode_city_sao_paulo(monkeypatch):
    monkeypatch.setattr(tool_agent.httpx, "get", _fake_get(
        {"results": [_result("São Paulo", country="Brazil", timezone="America/Sao_Paulo")]}
    ))
    out = tool_agent.get_time("São Paulo")
    assert "São Paulo" in out and "Brazil" in out


def test_unicode_city_zurich(monkeypatch):
    monkeypatch.setattr(tool_agent.httpx, "get", _fake_get(
        {"results": [_result("Zürich", country="Switzerland", timezone="Europe/Zurich")]}
    ))
    out = tool_agent.get_time("Zürich")
    assert "Zürich" in out and "Switzerland" in out


def test_ambiguous_city_paris(monkeypatch):
    monkeypatch.setattr(tool_agent.httpx, "get", _fake_get(
        {"results": [_result("Paris", country="France", admin1="Ile-de-France", timezone="Europe/Paris")]}
    ))
    out = tool_agent.get_time("Paris")
    assert "France" in out
    assert "Texas" not in out


def test_ambiguous_city_springfield(monkeypatch):
    monkeypatch.setattr(tool_agent.httpx, "get", _fake_get(
        {"results": [_result("Springfield", country="United States", admin1="Missouri", timezone="America/Chicago")]}
    ))
    out = tool_agent.get_time("Springfield")
    assert "Missouri" in out and "United States" in out


def test_nonexistent_city(monkeypatch):
    monkeypatch.setattr(tool_agent.httpx, "get", _fake_get({"generationtime_ms": 0.1}))
    out = tool_agent.get_time("Zzzznotarealplace")
    assert "Unknown city" in out


def test_misspelled_city_empty_results(monkeypatch):
    monkeypatch.setattr(tool_agent.httpx, "get", _fake_get({"results": []}))
    out = tool_agent.get_time("Zzzznotarealplace")
    assert "Unknown city" in out


def test_empty_input(monkeypatch):
    calls = []
    monkeypatch.setattr(tool_agent.httpx, "get", lambda *a, **k: calls.append(1))
    out = tool_agent.get_time("")
    assert "must not be empty" in out
    assert calls == []


def test_whitespace_only_input(monkeypatch):
    calls = []
    monkeypatch.setattr(tool_agent.httpx, "get", lambda *a, **k: calls.append(1))
    out = tool_agent.get_time("   ")
    assert "must not be empty" in out
    assert calls == []


def test_case_insensitivity(monkeypatch):
    seen_params = {}

    def _get(url, params=None, timeout=None):
        seen_params.update(params)
        request = httpx.Request("GET", url, params=params)
        return httpx.Response(200, json={"results": [_result("Tokyo", country="Japan", timezone="Asia/Tokyo")]}, request=request)

    monkeypatch.setattr(tool_agent.httpx, "get", _get)
    out = tool_agent.get_time("tOkYo")
    assert "Tokyo" in out
    assert seen_params["name"] == "tOkYo"


def test_network_timeout(monkeypatch):
    monkeypatch.setattr(tool_agent.httpx, "get", _raising_get(httpx.TimeoutException("timed out")))
    out = tool_agent.get_time("Tokyo")
    assert "timed out" in out.lower()


def test_network_connect_error(monkeypatch):
    monkeypatch.setattr(tool_agent.httpx, "get", _raising_get(httpx.ConnectError("no route")))
    out = tool_agent.get_time("Tokyo")
    assert "could not reach" in out.lower()


def test_http_status_error(monkeypatch):
    def _get(url, params=None, timeout=None):
        request = httpx.Request("GET", url, params=params)
        response = httpx.Response(500, json={}, request=request)
        return response

    monkeypatch.setattr(tool_agent.httpx, "get", _get)
    out = tool_agent.get_time("Tokyo")
    assert "500" in out


def test_malformed_json_response(monkeypatch):
    def _get(url, params=None, timeout=None):
        request = httpx.Request("GET", url, params=params)
        response = httpx.Response(200, content=b"not json", request=request)
        return response

    monkeypatch.setattr(tool_agent.httpx, "get", _get)
    out = tool_agent.get_time("Tokyo")
    assert "unreadable" in out.lower()


def test_missing_timezone_field(monkeypatch):
    monkeypatch.setattr(tool_agent.httpx, "get", _fake_get(
        {"results": [{"name": "Tokyo", "country": "Japan"}]}
    ))
    out = tool_agent.get_time("Tokyo")
    assert "no timezone information" in out.lower()


def test_numeric_city_input(monkeypatch):
    calls = []
    monkeypatch.setattr(tool_agent.httpx, "get", lambda *a, **k: calls.append(1))
    out = tool_agent.get_time(12345)
    assert "must be a string" in out.lower()
    assert calls == []


def test_timeout_param_passed(monkeypatch):
    seen = {}

    def _get(url, params=None, timeout=None):
        seen["timeout"] = timeout
        request = httpx.Request("GET", url, params=params)
        return httpx.Response(200, json={"results": [_result("Tokyo", country="Japan", timezone="Asia/Tokyo")]}, request=request)

    monkeypatch.setattr(tool_agent.httpx, "get", _get)
    tool_agent.get_time("Tokyo")
    assert seen["timeout"] == tool_agent._GEOCODE_TIMEOUT
