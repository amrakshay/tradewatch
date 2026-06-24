# ADR-009 — Telegram HTML Parse Mode

| Field | Value |
|-------|-------|
| Date | 2024-01 |
| Status | Accepted |
| Deciders | Akshay |

## Context

Telegram Bot API supports three parse modes for message formatting: `Markdown` (legacy), `MarkdownV2`, and `HTML`. The choice affects how message text is formatted and how special characters in user-generated content (stock symbols, notes) are handled.

## Decision

Use `parse_mode="HTML"` with `html.escape()` on all user-controlled string values before embedding them in the message template.

## Rationale

- **Legacy Markdown fragility**: symbols like `_`, `*`, `.` in stock names or user notes silently break formatting or cause Telegram to return an error. NSE stock symbols (e.g. `BAJAJ-AUTO`) contain `-` which breaks legacy Markdown.
- **MarkdownV2 complexity**: requires escaping 18+ special characters (`_`, `*`, `[`, `]`, `(`, `)`, `~`, `` ` ``, `>`, `#`, `+`, `-`, `=`, `|`, `{`, `}`, `.`, `!`) — easy to forget one and get a 400 error.
- **HTML simplicity**: only 3 characters need escaping (`<`, `>`, `&`). Python's `html.escape()` handles all three. Bold is `<b>text</b>`. No surprises.

## Implementation

```python
import html

text = (
    f"🔔 <b>Pullback Alert Triggered</b>\n\n"
    f"Stock: <b>{html.escape(symbol)}</b>\n"
    f"Signal Date: {html.escape(signal_date)}\n"
    f"Alert Price Set: ₹{alert_price:,.2f}\n"
    f"Current LTP: ₹{triggered_price:,.2f}\n"
)
bot.send_message(chat_id=..., text=text, parse_mode="HTML")
```

## Rule

Every string that comes from user input or external data (symbol name, notes, dates from config) MUST pass through `html.escape()`. Numeric values formatted with Python format strings (`{price:,.2f}`) do not need escaping.

## Consequences

- ₹ (Rupee sign) and emoji characters are safe in HTML parse mode — no escaping needed
- If a future message type needs code blocks, use `<code>text</code>` not backticks

## Alternatives Rejected

- **Legacy Markdown**: rejected — fragile with special characters common in financial data
- **MarkdownV2**: rejected — too many escape rules; easy to introduce hard-to-debug formatting errors
- **No parse mode (plain text)**: rejected — no bold formatting for the alert header and stock name
