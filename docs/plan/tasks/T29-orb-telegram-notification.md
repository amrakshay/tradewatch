# T29 — TelegramService ORB Notification

**Phase:** ORB Phase 1
**Depends on:** T11 (TelegramService base), T23 (ORBSignal model)
**Blocks:** T25 (ORBScannerService uses it)

---

## Goal

Add an ORB-specific notification method to the existing `TelegramService`. Sends a formatted Telegram message immediately when an ORB signal fires.

---

## Files to Modify

| Action | File |
|--------|------|
| Modify | `backend/app/services/telegram_service.py` |

---

## Implementation

Add the following method to the existing `TelegramService` class:

```python
import html

async def send_orb_signal(self, signal) -> bool:
    """
    Sends an ORB signal notification. signal is an ORBSignal ORM object.
    Returns True if sent successfully, False otherwise.
    """
    try:
        message = self._format_orb_signal(signal)
        await self._send(message)
        # Mark telegram_sent on the signal
        signal.telegram_sent = 1
        return True
    except Exception as e:
        logger.error(f"Failed to send ORB Telegram notification: {e}")
        return False

def _format_orb_signal(self, signal) -> str:
    direction_emoji = "🟢" if signal.signal_direction == "LONG" else "🔴"
    strength_badge  = "⚡ Strong Setup" if signal.first_candle_strong else "〰 Weak Setup"
    fc_dir          = signal.first_candle_direction.title()   # Bullish / Bearish

    return (
        f"{direction_emoji} <b>ORB Signal: {html.escape(signal.symbol)}</b>\n\n"
        f"Direction: <b>{html.escape(signal.signal_direction)}</b>  ({strength_badge})\n"
        f"Signal Price: <b>₹{signal.signal_price:,.2f}</b>\n"
        f"Breakout Time: {html.escape(signal.breakout_time)} IST\n\n"
        f"Opening Range: ₹{signal.orb_low:,.2f} – ₹{signal.orb_high:,.2f}\n"
        f"Breakout Vol: {signal.breakout_candle_volume:,} "
        f"(prev: {signal.prev_candle_volume:,})\n\n"
        f"First Candle ({html.escape(fc_dir)}): "
        f"body {signal.first_candle_body_pct:.0%}, "
        f"vol ratio {signal.first_candle_volume_ratio:.1f}×\n"
        f"Date: {html.escape(signal.signal_date)}"
    )
```

---

## Example Output

**Long (strong setup):**
```
🟢 ORB Signal: NIFTY 50

Direction: LONG  (⚡ Strong Setup)
Signal Price: ₹22,150.75
Breakout Time: 10:05 IST

Opening Range: ₹21,980.00 – ₹22,130.00
Breakout Vol: 1,25,000 (prev: 82,000)

First Candle (Bullish): body 72%, vol ratio 1.8×
Date: 2024-01-15
```

**Short (weak setup):**
```
🔴 ORB Signal: BANKNIFTY

Direction: SHORT  (〰 Weak Setup)
Signal Price: ₹47,890.00
Breakout Time: 11:25 IST

Opening Range: ₹47,950.00 – ₹48,210.00
Breakout Vol: 98,000 (prev: 61,000)

First Candle (Bearish): body 45%, vol ratio 1.1×
Date: 2024-01-15
```

---

## Done When

- [ ] `send_orb_signal()` sends a properly formatted HTML Telegram message
- [ ] `html.escape()` applied to all user-sourced string fields
- [ ] No `parse_mode="Markdown"` used — HTML only
- [ ] `signal.telegram_sent` set to 1 after successful send
- [ ] Send failure is logged but does not raise (signal is already persisted to DB)
- [ ] Manual test: call `send_orb_signal()` with a mock signal object, confirm message received on Telegram
