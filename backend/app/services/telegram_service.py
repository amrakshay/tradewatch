import html
import logging
import telegram
from zoneinfo import ZoneInfo
from datetime import datetime

logger = logging.getLogger(__name__)
IST = ZoneInfo("Asia/Kolkata")


class TelegramService:
    def __init__(self, bot_token: str, chat_id: str):
        self._bot_token = bot_token
        self._chat_id = chat_id

    def reinit(self, bot_token: str, chat_id: str):
        """Re-initialize with new credentials (called by ConfigService hook)."""
        self._bot_token = bot_token
        self._chat_id = chat_id

    async def send_message(self, text: str) -> bool:
        """
        Send a raw HTML message to the configured chat.
        Returns True on success, False on failure (logs error).
        """
        if not self._bot_token or not self._chat_id:
            logger.warning("Telegram not configured — skipping message.")
            return False
        try:
            bot = telegram.Bot(token=self._bot_token)
            await bot.send_message(
                chat_id=self._chat_id,
                text=text,
                parse_mode="HTML",
            )
            return True
        except Exception as e:
            logger.error(f"Telegram send failed: {e}")
            return False

    async def send_alert_triggered(
        self,
        symbol: str,
        signal_date: str,
        alert_price: float,
        triggered_price: float,
    ) -> bool:
        """Send the standard 'alert triggered' notification."""
        checked_at = datetime.now(IST).strftime("%-I:%M %p IST, %-d %b %Y")
        text = (
            f"🔔 <b>Pullback Alert Triggered</b>\n\n"
            f"Stock: <b>{html.escape(symbol)}</b>\n"
            f"Signal Date: {html.escape(signal_date)}\n"
            f"Alert Price Set: ₹{alert_price:,.2f}\n"
            f"Current LTP: ₹{triggered_price:,.2f}\n\n"
            f"Checked at: {html.escape(checked_at)}"
        )
        return await self.send_message(text)

    async def send_test_message(self) -> bool:
        """Send a test message to verify bot token + chat ID are correct."""
        ts = datetime.now(IST).strftime("%-d %b %Y, %-I:%M %p IST")
        text = f"✅ <b>TradeWatch</b> — connection test successful\n{html.escape(ts)}"
        return await self.send_message(text)

    async def send_token_expiry_warning(self, expires_at: str) -> bool:
        """Warn that the Dhan access token is expiring soon and auto-renew failed."""
        text = (
            f"⚠️ <b>Dhan Token Warning</b>\n\n"
            f"Token expires at: {html.escape(expires_at)}\n"
            f"Auto-renew failed. Please renew manually via Settings → Dhan API."
        )
        return await self.send_message(text)


# Module-level singleton
_telegram_service: TelegramService | None = None


def get_telegram_service(db=None) -> TelegramService:
    global _telegram_service
    if _telegram_service is None:
        if db is None:
            raise RuntimeError("TelegramService not initialized and no db provided.")
        from app.services.config_service import get_decrypted_config
        cfg = get_decrypted_config(db)
        _telegram_service = TelegramService(cfg["telegram_bot_token"], cfg["telegram_chat_id"])
    return _telegram_service


def reinit_telegram_service(db):
    """Called by ConfigService hook when telegram credentials change."""
    global _telegram_service
    from app.services.config_service import get_decrypted_config
    cfg = get_decrypted_config(db)
    if _telegram_service:
        _telegram_service.reinit(cfg["telegram_bot_token"], cfg["telegram_chat_id"])
    else:
        _telegram_service = TelegramService(cfg["telegram_bot_token"], cfg["telegram_chat_id"])
