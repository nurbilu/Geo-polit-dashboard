"""
Multimodal threat analysis via OpenRouter's chat-completions API.

Uses the hosted vision model ``meta-llama/llama-3.2-11b-vision-instruct``
(configurable via ``settings.OPENROUTER_MODEL``) and the standard ``requests``
library. Text and (optionally) an image are sent together using OpenRouter's
Vision API content structure; the model output is coerced into a strict JSON
``ThreatVerdict`` consumed by the dashboard.
"""
import base64
import json
import logging
from dataclasses import dataclass
from typing import Optional

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
REQUEST_TIMEOUT = 120  # seconds

VALID_REGIONS = {
    "judea_samaria", "golan_heights", "north", "south", "central", "unknown",
}

# Map human-friendly model labels onto our DB choice values.
_REGION_ALIASES = {
    "judea & samaria": "judea_samaria",
    "judea and samaria": "judea_samaria",
    "judea_samaria": "judea_samaria",
    "west bank": "judea_samaria",
    "golan heights": "golan_heights",
    "golan_heights": "golan_heights",
    "golan": "golan_heights",
    "north": "north",
    "northern": "north",
    "south": "south",
    "southern": "south",
    "central": "central",
    "center": "central",
}

SYSTEM_PROMPT = (
    "You are a geopolitical security analyst monitoring threats to Israel, "
    "including Judea & Samaria (the West Bank) and the Golan Heights. "
    "You receive an intelligence item that may include text and an image. "
    "Analyze BOTH the text and any visual cues in the image (weapons, fires, "
    "smoke, crowds, rockets, military vehicles, damaged buildings, maps, "
    "uniforms, flags). Respond with ONLY a single valid JSON object and no "
    "prose, markdown, or code fences. The JSON schema is:\n"
    "{\n"
    '  "is_threat": boolean,            // true if it indicates a security threat\n'
    '  "region": string,               // one of: "Judea & Samaria", "Golan Heights", "North", "South", "Central"\n'
    '  "threat_severity": integer,      // 1 (negligible) to 10 (critical/imminent)\n'
    '  "visual_summary": string         // short description of what is visible in the image, "" if no image\n'
    "}\n"
    "If unsure of the region, choose the most likely one. Never invent details "
    "that are not supported by the text or image."
)


@dataclass
class ThreatVerdict:
    is_threat: bool
    region: str
    threat_severity: int
    visual_summary: str
    raw: dict

    def as_db_fields(self) -> dict:
        return {
            "is_threat": self.is_threat,
            "region": self.region,
            "threat_severity": self.threat_severity,
            "visual_summary": self.visual_summary,
            "analysis": self.raw,
        }


def _normalize_region(value: Optional[str]) -> str:
    if not value:
        return "unknown"
    key = str(value).strip().lower()
    if key in _REGION_ALIASES:
        return _REGION_ALIASES[key]
    if key in VALID_REGIONS:
        return key
    return "unknown"


def _clamp_severity(value) -> int:
    try:
        sev = int(round(float(value)))
    except (TypeError, ValueError):
        return 1
    return max(1, min(10, sev))


def _extract_json(text: str) -> dict:
    """Best-effort parse of a JSON object from the model output."""
    text = (text or "").strip()
    if not text:
        return {}
    # Strip accidental code fences.
    if text.startswith("```"):
        text = text.strip("`")
        text = text[text.find("{"):] if "{" in text else text
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                pass
    logger.warning("Could not parse model JSON output: %s", text[:300])
    return {}


def _headers() -> dict:
    """
    OpenRouter request headers. HTTP-Referer and X-Title are required by
    OpenRouter for app ranking / usage attribution on the dashboard.
    """
    return {
        "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost:8000",
        "X-Title": "Geopolitical Threat Dashboard",
    }


def _detect_mime(data: bytes) -> str:
    """Sniff a few common image magic bytes; default to JPEG."""
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:3] == b"GIF":
        return "image/gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return "image/jpeg"


def _data_url(image_bytes: bytes) -> str:
    """Build a base64 data URL for the OpenRouter Vision ``image_url`` field."""
    mime = _detect_mime(image_bytes)
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    return f"data:{mime};base64,{b64}"


def _analyze_request(
    text: str,
    image_bytes: Optional[bytes] = None,
    title: str = "",
) -> tuple[ThreatVerdict, int, dict]:
    """Shared implementation for analyze() and analyze_with_diagnostics()."""
    if not settings.OPENROUTER_API_KEY:
        raise RuntimeError("OPENROUTER_API_KEY is not configured.")

    prompt_text = (
        f"TITLE: {title}\n\nTEXT:\n{text or '(no text provided)'}\n\n"
        "Return the JSON verdict now."
    )

    # Multimodal messages use a content array of typed parts; text-only items
    # may use a plain string. We always use the array form for consistency.
    user_parts = [{"type": "text", "text": prompt_text}]
    if image_bytes:
        user_parts.append(
            {
                "type": "image_url",
                "image_url": {"url": _data_url(image_bytes)},
            }
        )

    payload = {
        "model": settings.OPENROUTER_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_parts},
        ],
        "temperature": 0.1,
        # Enforce strict JSON-only output.
        "response_format": {"type": "json_object"},
    }

    response = requests.post(
        OPENROUTER_URL,
        headers=_headers(),
        data=json.dumps(payload),
        timeout=REQUEST_TIMEOUT,
    )

    body = {}
    try:
        body = response.json()
    except json.JSONDecodeError:
        body = {"_raw_text": response.text[:4000]}

    response.raise_for_status()

    content = (
        body.get("choices", [{}])[0].get("message", {}).get("content", "")
    )
    parsed = _extract_json(content)

    verdict = ThreatVerdict(
        is_threat=bool(parsed.get("is_threat", False)),
        region=_normalize_region(parsed.get("region")),
        threat_severity=_clamp_severity(parsed.get("threat_severity", 1)),
        visual_summary=str(parsed.get("visual_summary", "") or "")[:2000],
        raw=parsed or {"_unparsed": content[:2000]},
    )
    logger.info(
        "OpenRouter verdict (%s): threat=%s region=%s severity=%s",
        settings.OPENROUTER_MODEL,
        verdict.is_threat, verdict.region, verdict.threat_severity,
    )
    return verdict, response.status_code, body


def analyze(
    text: str,
    image_bytes: Optional[bytes] = None,
    title: str = "",
) -> ThreatVerdict:
    """
    Run multimodal analysis via OpenRouter. When ``image_bytes`` is provided it
    is base64-encoded and sent alongside the text using the Vision API content
    structure so the model can reason over visual cues.
    """
    verdict, _, _ = _analyze_request(text, image_bytes=image_bytes, title=title)
    return verdict


def analyze_with_diagnostics(
    text: str,
    image_bytes: Optional[bytes] = None,
    title: str = "",
) -> tuple[ThreatVerdict, int, dict]:
    """
    Like ``analyze`` but also returns the HTTP status code and the raw OpenRouter
    JSON body (for diagnostics / management-command telemetry).
    """
    return _analyze_request(text, image_bytes=image_bytes, title=title)


def ensure_model_available() -> bool:
    """Health/diagnostics: analysis is possible only if a key is configured."""
    return bool(settings.OPENROUTER_API_KEY)


__all__ = [
    "analyze",
    "analyze_with_diagnostics",
    "ThreatVerdict",
    "ensure_model_available",
]
