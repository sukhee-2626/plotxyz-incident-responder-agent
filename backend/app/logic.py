"""Original deterministic implementation for Incident Responder (plotxyz-incident-responder-agent)."""
from __future__ import annotations

import ast
import csv
import io
import json
import math
import os
import re
import statistics
import time
from collections import Counter, defaultdict, deque


class LogicError(ValueError):
    """Raised when supplied input cannot be processed."""


def _text(payload, key, min_len=1, max_len=20000):
    value = payload.get(key)
    if not isinstance(value, str):
        raise LogicError(f"'{key}' must be a string")
    value = value.strip()
    if len(value) < min_len:
        raise LogicError(f"'{key}' is required")
    if len(value) > max_len:
        raise LogicError(f"'{key}' exceeds {max_len} characters")
    return value


def _num(payload, key, default=None, lo=None, hi=None):
    value = payload.get(key, default)
    if value is None or value == "":
        if default is None:
            raise LogicError(f"'{key}' is required")
        return default
    if isinstance(value, bool):
        raise LogicError(f"'{key}' must be numeric")
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise LogicError(f"'{key}' must be numeric")
    if lo is not None and number < lo:
        raise LogicError(f"'{key}' must be at least {lo}")
    if hi is not None and number > hi:
        raise LogicError(f"'{key}' must be at most {hi}")
    return number


def _json(payload, key, expected=None, max_len=200000):
    raw = payload.get(key)
    if isinstance(raw, (dict, list)):
        data = raw
    elif isinstance(raw, str):
        if len(raw) > max_len:
            raise LogicError(f"'{key}' exceeds {max_len} characters")
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise LogicError(f"'{key}' is not valid JSON: {exc.msg} at line {exc.lineno}")
    else:
        raise LogicError(f"'{key}' must be JSON")
    if expected is not None and not isinstance(data, expected):
        name = expected.__name__ if hasattr(expected, "__name__") else str(expected)
        raise LogicError(f"'{key}' must be a JSON {name}")
    return data


def _csv(payload, key, max_rows=5000):
    text = _text(payload, key, max_len=2000000)
    try:
        reader = csv.DictReader(io.StringIO(text))
        if not reader.fieldnames:
            raise LogicError(f"'{key}' must include a header row")
        columns = [str(c).strip() for c in reader.fieldnames if c and str(c).strip()]
        if not columns:
            raise LogicError(f"'{key}' must include named columns")
        rows = []
        for index, raw in enumerate(reader):
            if index >= max_rows:
                raise LogicError(f"'{key}' exceeds {max_rows} rows")
            rows.append({col: (raw.get(col) or "").strip() for col in columns})
    except csv.Error as exc:
        raise LogicError(f"'{key}' is not valid CSV: {exc}")
    if not rows:
        raise LogicError(f"'{key}' must include at least one data row")
    return columns, rows


STOPWORDS = {'could', 'than', 'your', 'does', 'in', 'have', 'you', 'is', 'they', 'then', 'will', 'it', 'of', 'their', 'are', 'about', 'should', 'into', 'not', 'were', 'would', 'no', 'as', 'from', 'had', 'may', 'a', 'i', 'for', 'he', 'can', 'over', 'under', 'the', 'our', 'to', 'might', 'she', 'be', 'do', 'has', 'an', 'if', 'this', 'at', 'by', 'that', 'we', 'and', 'with', 'its', 'did', 'was', 'or', 'on'}


def _tokens(text):
    return [w for w in re.findall(r"[a-z0-9][a-z0-9_+-]{1,}", text.lower()) if w not in STOPWORDS]


def _sentences(text):
    parts = re.split(r"(?<=[.!?])\s+|\n+", text)
    return [p.strip(" -•\t") for p in parts if len(p.strip()) > 2]


def provider_status():
    """Report which optional model providers are configured (never exposes secrets)."""
    ollama = bool(os.getenv("OLLAMA_BASE_URL"))
    openai = bool(os.getenv("OPENAI_BASE_URL") and os.getenv("OPENAI_MODEL"))
    return {"ollama_compatible": ollama, "openai_compatible": openai}


def _llm(messages, temperature=0.2):
    """Call an explicitly configured OpenAI-compatible endpoint; return None when unavailable."""
    base = os.getenv("OPENAI_BASE_URL", "").rstrip("/")
    model = os.getenv("OPENAI_MODEL", "")
    if not base or not model:
        ollama = os.getenv("OLLAMA_BASE_URL", "").rstrip("/")
        if not ollama:
            return None
        base = f"{ollama}/v1"
        model = os.getenv("OLLAMA_MODEL", "")
    if not model:
        return None
    try:
        import httpx

        headers = {"Content-Type": "application/json"}
        key = os.getenv("OPENAI_API_KEY")
        if key:
            headers["Authorization"] = f"Bearer {key}"
        with httpx.Client(timeout=20) as client:
            response = client.post(
                f"{base}/chat/completions",
                headers=headers,
                json={"model": model, "messages": messages, "temperature": temperature},
            )
            response.raise_for_status()
            return str(response.json()["choices"][0]["message"]["content"]).strip()
    except Exception:
        return None


def _result(summary, result, warnings=None):
    return {"summary": summary, "result": result, "warnings": warnings or []}


def agent_incident_responder(payload):
    description = _text(payload, "description", max_len=10000)
    affected = str(payload.get("affected_services", "")).strip()
    user_reported = bool(payload.get("user_reported", False))
    lowered = description.lower()
    severity = "low"
    if any(w in lowered for w in ["outage", "down", "unavailable", "critical", "sev1"]):
        severity = "critical"
    elif any(w in lowered for w in ["slow", "degraded", "error", "sev2", "partial"]):
        severity = "high"
    elif any(w in lowered for w in ["warning", "minor", "sev3"]):
        severity = "medium"
    actions = []
    if severity == "critical":
        actions = ["Page on-call engineer immediately.", "Open incident bridge.", "Post public status page update within 15 minutes.", "Roll back recent deployments if correlated."]
    elif severity == "high":
        actions = ["Assign incident lead within 30 minutes.", "Gather logs from affected services.", "Prepare rollback plan.", "Notify stakeholders within 1 hour."]
    elif severity == "medium":
        actions = ["Create incident ticket.", "Investigate during business hours.", "Monitor for recurrence."]
    else:
        actions = ["Log as a minor event.", "Review at next team meeting."]
    if user_reported:
        actions.insert(0, "Acknowledge user report and set expectations.")
    timeline = []
    if severity in {"critical", "high"}:
        timeline = [("T+0 min", "Incident detected and severity assigned"), ("T+15 min", "Initial response and stakeholder notification"), ("T+60 min", "Mitigation or rollback decision"), ("T+24 h", "Post-incident review published")]
    else:
        timeline = [("T+0 min", "Ticket created and triaged"), ("T+24 h", "Investigation started"), ("T+3 d", "Resolution or planned work item")]
    rows = [[t, d] for t, d in timeline]
    affected_list = [s.strip() for s in affected.split(",") if s.strip()] if affected else ["not specified"]
    return _result(
        f"Incident triaged as {severity.upper()}: {len(actions)} immediate action(s), {len(affected_list)} affected service(s).",
        {
            "metrics": {"severity": severity, "actions": len(actions), "affected_services": len(affected_list), "user_reported": user_reported},
            "table": {"columns": ["Time", "Action"], "rows": rows},
            "items": actions,
            "findings": [{"title": f"Severity: {severity.upper()}", "severity": severity, "detail": f"Affected: {', '.join(affected_list)}"}],
        },
        [],
    )


run = agent_incident_responder
