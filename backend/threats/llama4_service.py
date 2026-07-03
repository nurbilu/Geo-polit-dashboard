"""
Threat analysis via Llama 4 Scout.

Two interchangeable providers (selected by ``settings.AI_PROVIDER``):
  - ``groq``       : Llama 4 Scout (``meta-llama/llama-4-scout-17b-16e-instruct``)
                     on Groq Cloud, called through the OpenAI-compatible client.
  - ``openrouter`` : legacy hosted vision model via raw ``requests``.

Both coerce the model output into a strict JSON ``ThreatVerdict`` consumed by
the dashboard, including a concise Hebrew summary (``summary_hebrew``).
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

VALID_COUNTRIES = {
    "israel", "lebanon", "syria", "jordan", "egypt", "iraq",
    "arabian_peninsula", "gulf_states", "iran", "turkey", "mediterranean",
    "unknown",
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

_COUNTRY_ALIASES = {
    "israel": "israel",
    "lebanon": "lebanon",
    "syria": "syria",
    "jordan": "jordan",
    "egypt": "egypt",
    "iraq": "iraq",
    "arabian peninsula": "arabian_peninsula",
    "arabian_peninsula": "arabian_peninsula",
    "saudi arabia": "arabian_peninsula",
    "yemen": "arabian_peninsula",
    "gulf states": "gulf_states",
    "gulf_states": "gulf_states",
    "persian gulf states": "gulf_states",
    "persian gulf": "gulf_states",
    "uae": "gulf_states",
    "qatar": "gulf_states",
    "bahrain": "gulf_states",
    "kuwait": "gulf_states",
    "oman": "gulf_states",
    "iran": "iran",
    "turkey": "turkey",
    "turkiye": "turkey",
    "mediterranean": "mediterranean",
    "mediterranean region": "mediterranean",
    "mediterranean sea": "mediterranean",
}

SYSTEM_PROMPT = (
    "You are a Senior OSINT (Open Source Intelligence) Analyst specializing in "
    "Middle East security. You monitor and triage threats across the entire "
    "region: Israel (including Judea & Samaria / the West Bank and the Golan "
    "Heights), Lebanon, Syria, Jordan, Egypt, Iraq, the Arabian Peninsula, the "
    "Persian Gulf States, Iran, Turkey, and the Mediterranean Region.\n"
    "You receive an intelligence item that may include text and an image. "
    "Analyze BOTH the text and any visual cues in the image (weapons, fires, "
    "smoke, crowds, rockets, drones, missiles, military vehicles, naval assets, "
    "damaged buildings, maps, uniforms, flags).\n"
    "Respond with ONLY a single valid JSON object — no prose, markdown, or code "
    "fences. The JSON schema is:\n"
    "{\n"
    '  "is_threat": boolean,            // true if it indicates a security threat\n'
    '  "country": string,              // one of: "Israel", "Lebanon", "Syria", "Jordan", "Egypt", "Iraq", "Arabian Peninsula", "Persian Gulf States", "Iran", "Turkey", "Mediterranean Region"\n'
    '  "region": string,               // one of: "Judea & Samaria", "Golan Heights", "North", "South", "Central"\n'
    '  "threat_severity": integer,      // 1 (negligible) to 10 (critical/imminent)\n'
    '  "visual_summary": string,        // short description of what is visible in the image, "" if no image\n'
    '  "summary_hebrew": string         // intelligence-grade summary, see rules below\n'
    "}\n"
    "STRICT RULES FOR summary_hebrew:\n"
    "1. It MUST be written in pure, grammatically perfect, professional "
    "military/intelligence-grade Modern Hebrew (עברית תקנית).\n"
    "2. It MUST be a concise, factual assessment (1-3 sentences) of the event.\n"
    "3. It is STRICTLY FORBIDDEN to output placeholders, lorem-ipsum, repeated "
    "or looping characters, mojibake/broken encodings, or any non-Hebrew "
    "gibberish (e.g. 'בייוי היוווי'). If you cannot summarize confidently, "
    'write exactly: "אין מספיק מידע לניתוח מודיעיני".\n'
    "4. Do NOT mix languages inside summary_hebrew; Hebrew only (digits and "
    "proper nouns are allowed).\n"
    "If unsure of the country or region, choose the single most likely value. "
    "Never invent details that are not supported by the text or image."
)


@dataclass
class ThreatVerdict:
    is_threat: bool
    country: str
    region: str
    threat_severity: int
    visual_summary: str
    summary_hebrew: str
    raw: dict

    def as_db_fields(self) -> dict:
        return {
            "is_threat": self.is_threat,
            "country": self.country,
            "region": self.region,
            "threat_severity": self.threat_severity,
            "visual_summary": self.visual_summary,
            "summary_hebrew": self.summary_hebrew,
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


def _normalize_country(value: Optional[str]) -> str:
    if not value:
        return "unknown"
    key = str(value).strip().lower()
    if key in _COUNTRY_ALIASES:
        return _COUNTRY_ALIASES[key]
    if key in VALID_COUNTRIES:
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
    """Build a base64 data URL for the Vision ``image_url`` field."""
    mime = _detect_mime(image_bytes)
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    return f"data:{mime};base64,{b64}"


def _build_prompt(text: str, title: str = "") -> str:
    return (
        f"TITLE: {title}\n\nTEXT:\n{text or '(no text provided)'}\n\n"
        "Return the JSON verdict now."
    )


def _build_verdict(parsed: dict, content: str) -> ThreatVerdict:
    """Coerce a parsed model JSON object into a normalized ThreatVerdict."""
    return ThreatVerdict(
        is_threat=bool(parsed.get("is_threat", False)),
        country=_normalize_country(parsed.get("country")),
        region=_normalize_region(parsed.get("region")),
        threat_severity=_clamp_severity(parsed.get("threat_severity", 1)),
        visual_summary=str(parsed.get("visual_summary", "") or "")[:2000],
        summary_hebrew=str(parsed.get("summary_hebrew", "") or "")[:2000],
        raw=parsed or {"_unparsed": content[:2000]},
    )


# ---------------------------------------------------------------------------
# Groq Cloud (Llama 4 Scout) via the OpenAI-compatible client
# ---------------------------------------------------------------------------
def _groq_request(
    text: str,
    image_bytes: Optional[bytes] = None,
    title: str = "",
) -> tuple[ThreatVerdict, int, dict]:
    """Run analysis on Groq Cloud using the openai client spec."""
    if not settings.GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY is not configured.")

    from openai import OpenAI  # lazy import keeps module import light

    client = OpenAI(
        api_key=settings.GROQ_API_KEY,
        base_url=settings.GROQ_BASE_URL,
        timeout=REQUEST_TIMEOUT,
    )

    prompt_text = _build_prompt(text, title)
    if image_bytes:
        # Llama 4 Scout is multimodal: send a typed content array with the image.
        user_content = [
            {"type": "text", "text": prompt_text},
            {"type": "image_url", "image_url": {"url": _data_url(image_bytes)}},
        ]
    else:
        user_content = prompt_text

    completion = client.chat.completions.create(
        model=settings.GROQ_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        temperature=0.1,
        response_format={"type": "json_object"},
    )

    content = (completion.choices[0].message.content or "") if completion.choices else ""
    parsed = _extract_json(content)
    verdict = _build_verdict(parsed, content)

    try:
        body = completion.model_dump()
    except Exception:
        body = {"_content": content[:4000]}

    logger.info(
        "Groq Llama4 Scout verdict (%s): threat=%s region=%s severity=%s",
        settings.GROQ_MODEL,
        verdict.is_threat, verdict.region, verdict.threat_severity,
    )
    return verdict, 200, body


# ---------------------------------------------------------------------------
# OpenRouter (legacy / fallback vision model) via raw requests
# ---------------------------------------------------------------------------
def _analyze_request(
    text: str,
    image_bytes: Optional[bytes] = None,
    title: str = "",
) -> tuple[ThreatVerdict, int, dict]:
    """OpenRouter implementation (used when AI_PROVIDER == 'openrouter')."""
    if not settings.OPENROUTER_API_KEY:
        raise RuntimeError("OPENROUTER_API_KEY is not configured.")

    prompt_text = _build_prompt(text, title)

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
    verdict = _build_verdict(parsed, content)
    logger.info(
        "OpenRouter verdict (%s): threat=%s region=%s severity=%s",
        settings.OPENROUTER_MODEL,
        verdict.is_threat, verdict.region, verdict.threat_severity,
    )
    return verdict, response.status_code, body


# ---------------------------------------------------------------------------
# Provider dispatch
# ---------------------------------------------------------------------------
def _provider_request(
    text: str,
    image_bytes: Optional[bytes] = None,
    title: str = "",
) -> tuple[ThreatVerdict, int, dict]:
    if getattr(settings, "AI_PROVIDER", "groq") == "openrouter":
        return _analyze_request(text, image_bytes=image_bytes, title=title)
    return _groq_request(text, image_bytes=image_bytes, title=title)


def analyze(
    text: str,
    image_bytes: Optional[bytes] = None,
    title: str = "",
) -> ThreatVerdict:
    """
    Run analysis via the configured provider (Groq by default). When
    ``image_bytes`` is provided it is base64-encoded and sent alongside the
    text so a multimodal model can reason over visual cues.
    """
    verdict, _, _ = _provider_request(text, image_bytes=image_bytes, title=title)
    return verdict


def analyze_with_diagnostics(
    text: str,
    image_bytes: Optional[bytes] = None,
    title: str = "",
) -> tuple[ThreatVerdict, int, dict]:
    """
    Like ``analyze`` but also returns the HTTP status code and the raw provider
    response body (for diagnostics / management-command telemetry).
    """
    return _provider_request(text, image_bytes=image_bytes, title=title)


def active_model() -> str:
    """Return the model id for the currently selected provider."""
    if getattr(settings, "AI_PROVIDER", "groq") == "openrouter":
        return settings.OPENROUTER_MODEL
    return settings.GROQ_MODEL


def ensure_model_available() -> bool:
    """Health/diagnostics: analysis is possible only if a key is configured."""
    if getattr(settings, "AI_PROVIDER", "groq") == "openrouter":
        return bool(settings.OPENROUTER_API_KEY)
    return bool(settings.GROQ_API_KEY)


__all__ = [
    "analyze",
    "analyze_with_diagnostics",
    "active_model",
    "ThreatVerdict",
    "ensure_model_available",
]
