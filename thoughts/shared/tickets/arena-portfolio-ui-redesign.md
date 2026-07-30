# Arena Portfolio UI Redesign

## Problem

The Arena setup form is getting cluttered. Portfolio selection strategy is buried at the bottom of a long form alongside basic config (symbols, dates, capital). Strategy names like "Enriched Score" and "Enriched Score + High ATR" are meaningless to users. "MA20 Sweet Spot %" is a technical implementation detail, not a user-facing concept.

## What We Want

1. **Separate tab/section for Portfolio Management** — Split the Arena setup into logical sections (e.g., tabs or accordion):
   - Basic setup (symbols, dates, capital, position size)
   - Agent configuration (agent type, scoring, min buy score)
   - Portfolio strategy (selection strategy, constraints, tuning parameters)

2. **User-friendly strategy names** — Names should describe *what* the strategy does, not *how* it works:
   - "None (symbol order)" → fine as-is
   - "Score + Low ATR" → something like "Best Score, Calmest Stocks"
   - "Score + High ATR" → "Best Score, Most Volatile"
   - "Score + Moderate ATR" → "Best Score, Balanced Volatility"
   - "Enriched Score" → needs a name that conveys "multi-factor ranking with momentum + volume + pattern quality"
   - "Enriched Score + High ATR" → same but preferring volatile stocks

3. **Meaningful parameter labels** — "MA20 Sweet Spot %" should describe what the user is controlling in plain language, e.g., "Ideal pullback depth (%)" or similar — the concept is "how far below the moving average is the sweet spot for entry."

## Constraints

- Must remain a single-page form (no multi-step wizard)
- Strategy descriptions should be visible on hover or as subtitles
- Advanced tuning parameters (like the sweet spot) should feel optional, not mandatory

## Priority

Low — cosmetic/UX improvement. Current UI is functional but not intuitive.
