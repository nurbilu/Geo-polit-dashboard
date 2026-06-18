"""
Llama 4 Scout multimodal analysis via Ollama.

Sends BOTH text and (optionally) a base64-encoded image to the model and
coerces the response into a strict JSON verdict used by the dashboard.
"""
import base64
import json
import logging
from dataclasses import asdict, dataclass
from typing import Optional

from django.conf import settings
from ollama import Client

logger = logging.getLogger(__name__)

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


def _client() -> Client:
    return Client(host=settings.OLLAMA_HOST, timeout=settings.OLLAMA_TIMEOUT)


def encode_image_bytes(data: bytes) -> str:
    """Base64-encode raw image bytes for the Ollama images payload."""
    return base64.b64encode(data).decode("utf-8")


def analyze(
    text: str,
    image_bytes: Optional[bytes] = None,
    title: str = "",
) -> ThreatVerdict:
    """
    Run multimodal analysis. `image_bytes` is optional; when present it is sent
    alongside the text so Llama 4 Scout can reason over visual cues too.
    """
    client = _client()

    user_content = (
        f"TITLE: {title}\n\nTEXT:\n{text or '(no text provided)'}\n\n"
        "Return the JSON verdict now."
    )
    message = {"role": "user", "content": user_content}

    if image_bytes:
        # Ollama expects base64 strings (or raw bytes) in `images`.
        message["images"] = [encode_image_bytes(image_bytes)]

    response = client.chat(
        model=settings.OLLAMA_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            message,
        ],
        format="json",  # Ask Ollama to constrain output to JSON.
        keep_alive=settings.OLLAMA_KEEP_ALIVE,
        options={"temperature": 0.1},
    )

    content = response.get("message", {}).get("content", "")
    parsed = _extract_json(content)

    verdict = ThreatVerdict(
        is_threat=bool(parsed.get("is_threat", False)),
        region=_normalize_region(parsed.get("region")),
        threat_severity=_clamp_severity(parsed.get("threat_severity", 1)),
        visual_summary=str(parsed.get("visual_summary", "") or "")[:2000],
        raw=parsed or {"_unparsed": content[:2000]},
    )
    logger.info(
        "Llama4 verdict: threat=%s region=%s severity=%s",
        verdict.is_threat, verdict.region, verdict.threat_severity,
    )
    return verdict


def ensure_model_available() -> bool:
    """Check the configured model is pulled; used by health/diagnostics."""
    try:
        models = _client().list().get("models", [])
        names = {m.get("model") or m.get("name") for m in models}
        return settings.OLLAMA_MODEL in names
    except Exception:
        logger.exception("Ollama not reachable for model check.")
        return False


__all__ = ["analyze", "ThreatVerdict", "encode_image_bytes", "ensure_model_available"]
