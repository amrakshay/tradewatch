# ADR-008 — Alert Trigger Condition: LTP ≤ Alert Price

| Field | Value |
|-------|-------|
| Date | 2024-01 |
| Status | Accepted |
| Deciders | Akshay |

## Context

TradeWatch implements a "pullback" strategy: the scanner finds stocks that have risen significantly (e.g. 10% in 4 days). The alert is set at a price *below* the current close — the user wants to buy when the stock "pulls back" to a lower entry price.

The alert trigger direction must be defined: does it fire when LTP **rises above** or **falls to/below** the alert price?

## Decision

Trigger when `LTP <= alert_price` (price drops to or below the alert).

## Rationale

The pullback strategy workflow:
1. Scanner finds stock that rose 10%+ → signal created
2. User sets alert at a target entry price below current close (e.g. close is ₹2,450; user sets alert at ₹2,200)
3. Alert fires when LTP falls to ₹2,200 — the pullback has reached the target

This is the "buy the dip after a momentum run" pattern.

## Consequences

- Alert price should always be *below* the close price at signal time — no system validation enforces this, but the SetAlertModal defaults the input placeholder to `close * 0.95` to guide the user
- If a user accidentally sets alert_price > close_price (e.g. a breakout entry), the alert would trigger on the next LTP check — this is intentional; the user is responsible for the price they set

## Alternatives Considered

- **LTP ≥ alert_price (breakout alert)**: valid for a different strategy (buy the breakout). Can be added as a future `alert_type` field with `gt`/`lt` modes.
- **Range alerts (price between X and Y)**: out of scope for v1
