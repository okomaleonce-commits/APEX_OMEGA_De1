"""
APEX_OMEGA_De1 · Telegram Bot — envoi rapports formatés
"""
from __future__ import annotations
import asyncio
import logging
from telegram import Bot
from telegram.constants import ParseMode
from config.settings import BOT_TOKEN, CHAT_ID

logger = logging.getLogger(__name__)
_bot   = Bot(token=BOT_TOKEN)


async def send_message(text: str) -> bool:
    """Envoie un message Markdown dans le canal APEX."""
    try:
        await _bot.send_message(
            chat_id=CHAT_ID,
            text=text,
            parse_mode=ParseMode.MARKDOWN,
            disable_web_page_preview=True,
        )
        return True
    except Exception as e:
        logger.error(f"Telegram send error: {e}")
        return False


async def send_analysis(report: str) -> None:
    """Publie une analyse pré-match."""
    await send_message(report)


async def send_audit(report: str) -> None:
    """Publie un audit post-match."""
    await send_message(report)


async def send_no_bet_summary(home: str, away: str, matchday: int, reason: str) -> None:
    msg = (
        f"🚫 *NO BET — J{matchday}*\n"
        f"*{home}* vs *{away}*\n"
        f"_{reason}_"
    )
    await send_message(msg)


async def send_error_alert(context: str, error: str) -> None:
    msg = f"⚠️ *APEX BOT ERROR*\n`{context}`\n`{error}`"
    await send_message(msg)


def sync_send(text: str) -> None:
    """Wrapper synchrone (hors contexte async)."""
    asyncio.run(send_message(text))


async def send_no_bet_summary(matchday: int, passes: int) -> None:
    """Résumé quand aucun signal n'est retenu pour la journée."""
    msg = (
        f"🚫 *APEX BUNDESLIGA · J{matchday}*\n"
        f"Aucun signal retenu pour cette journée\\.\n"
        f"{passes} match\\(s\\) analysé\\(s\\) · NO BET\n\n"
        f"_Prochain scan : 07:00 UTC_"
    )
    await send(msg)


async def send_analysis(text: str) -> None:
    """Alias pour compatibilité pipeline.py → send()"""
    await send(text)


async def send_audit(text: str) -> None:
    """Alias audit post-match → send()"""
    await send(text)
