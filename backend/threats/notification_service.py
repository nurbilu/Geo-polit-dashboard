"""
Zero-cost critical-threat notifications via the Telegram Bot API.

Credentials are read from the environment (``TELEGRAM_BOT_TOKEN`` and
``TELEGRAM_CHAT_ID``) with ``os.getenv``. All network calls use a short timeout
and never raise into the caller — failures are logged and surfaced only through
the boolean return value, so the backend/Celery loop is never blocked or broken
by a slow or unreachable Telegram endpoint.
"""
import html
import logging
import os

import requests

logger = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"
REQUEST_TIMEOUT = 10  # seconds — keep short so a stall never delays the worker.

# Hebrew region labels, explicitly calling out the sensitive zones.
_REGION_HE = {
    "judea_samaria": "יהודה ושומרון (איו״ש)",
    "golan_heights": "רמת הגולן",
    "north": "צפון",
    "south": "דרום",
    "central": "מרכז",
    "unknown": "לא ידוע",
}

# Hebrew country / macro-area labels (expanded Middle East coverage).
_COUNTRY_HE = {
    "israel": "ישראל",
    "lebanon": "לבנון",
    "syria": "סוריה",
    "jordan": "ירדן",
    "egypt": "מצרים",
    "iraq": "עיראק",
    "arabian_peninsula": "חצי האי ערב",
    "gulf_states": "מדינות המפרץ הפרסי",
    "iran": "איראן",
    "turkey": "טורקיה",
    "mediterranean": "אזור הים התיכון",
    "unknown": "לא ידוע",
}


def is_configured() -> bool:
    """True only when both the bot token and target chat id are present."""
    return bool(os.getenv("TELEGRAM_BOT_TOKEN") and os.getenv("TELEGRAM_CHAT_ID"))


def build_critical_message(
    *,
    severity,
    country,
    region,
    summary_hebrew: str,
    title: str = "",
    alert_id=None,
    url: str = "",
) -> str:
    """
    Compose the professional Hebrew critical-threat message using Telegram HTML
    parse mode. HTML tags (rather than Markdown) keep RTL Hebrew, hashtags and
    numbers rendering cleanly. All interpolated values are HTML-escaped.
    """
    country_he = _COUNTRY_HE.get(country, country or "לא ידוע")
    region_he = _REGION_HE.get(region, region or "לא ידוע")
    summary = (summary_hebrew or title or "אין תקציר זמין.").strip()

    try:
        sev_int = int(severity)
    except (TypeError, ValueError):
        sev_int = 0

    lines = [
        "🚨 <b>התראת איום קריטי</b>",
        "",
        f"🔴 <b>רמת חומרה:</b> {sev_int}/10",
        f"🌍 <b>מדינה:</b> {html.escape(country_he)}",
        f"📍 <b>אזור גיאוגרפי:</b> {html.escape(region_he)}",
        "",
        "📝 <b>תקציר מודיעיני:</b>",
        html.escape(summary),
    ]
    if url:
        lines.append("")
        lines.append(f'🔗 <a href="{html.escape(url, quote=True)}">מקור ההתראה</a>')
    if alert_id is not None:
        lines.append("")
        lines.append(f"#מזהה_{alert_id}")
    return "\n".join(lines)


def send_telegram_message(text: str) -> bool:
    """
    POST a message to the Telegram Bot API. Returns True on success, False on
    any misconfiguration or network/API error (never raises).
    """
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        logger.warning(
            "Telegram notify skipped: TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID not set."
        )
        return False

    try:
        resp = requests.post(
            TELEGRAM_API.format(token=token),
            json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        logger.info("Telegram critical alert dispatched (chat=%s).", chat_id)
        return True
    except requests.RequestException as exc:
        logger.warning("Telegram notify failed: %s", exc)
        return False


def notify_critical_alert(alert) -> bool:
    """Build and send a critical-threat notification for an Alert instance."""
    text = build_critical_message(
        severity=alert.threat_severity or 0,
        country=getattr(alert, "country", "unknown"),
        region=alert.region,
        summary_hebrew=alert.summary_hebrew,
        title=alert.title,
        alert_id=alert.id,
        url=alert.url,
    )
    return send_telegram_message(text)


__all__ = [
    "is_configured",
    "build_critical_message",
    "send_telegram_message",
    "notify_critical_alert",
]
