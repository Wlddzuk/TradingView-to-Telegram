Got it—first I’ll unpack your Pine v6 strategy line-by-line so an AI dev (or “code cloud”) can reproduce its behavior exactly outside TradingView. After that, I’ll give you a clean, copy-paste prompt for the AI programmer to build the Telegram signal bot for your four pairs across the 15m / 1h / 4h / 1D timeframes.

1) What your code does (deep dive)

Purpose

A long-only strategy that:
	•	Waits for a fresh bullish EMA cross (EMA9 crossing above EMA20 while both are above EMA200).
	•	After that cross, waits for a dip (“bounce”) to EMA9 within a tolerance window, with price above VWAP and MACD line above signal.
	•	When all conditions align on a bar (“signal bar”), it triggers one long entry on the next bar open, sets stop = signal bar low, and take profit = entry + 3× risk (risk = entry − stop).
	•	Optionally draws 3:1 RR guide lines/labels/boxes for visualization.
	•	Uses 100% of equity per trade, no pyramiding, backtestable in TV.

Inputs (user-tunable)
	•	EMAs: fastLen=9, medLen=20, slowLen=200.
	•	MACD: fast=12, slow=26, signal=9.
	•	Bounce tolerance: tolPct=0.05 (% above EMA9 low threshold—see below).
	•	Max bars to wait for bounce after cross: maxWait=30 (0 = unlimited).
	•	Risk/Reward: rrMultiple=3.0, guide length rrHorizon=40, and drawRR=true.

Core series
	•	ema9, ema20, ema200 via ta.ema.
	•	vwap on hlc3.
	•	MACD: macdLine, signalLine via ta.macd.

Trend / cross logic
	•	Bullish stack: ema9 > ema20 > ema200. (Full alignment in uptrend.)
	•	Fresh cross up: ta.crossover(ema9, ema20) and ema9 > ema200.
This is the event that arms the system to look for a bounce.

“Bounce” definition (pullback to EMA9)
	•	tolPrice = ema9 * (1 + tolPct/100).
With default 0.05, that’s +0.05% above EMA9 (tiny window).
	•	bounce = (low <= tolPrice) and (close > ema9).
Interpretation: within the signal bar, price traded down to (or below) a level very close to EMA9 (within tol), then closed back above EMA9. That’s your “tag and reclaim” bounce.

Extra filters (confluence)
	•	Price above VWAP: close > vwap (strength).
	•	MACD bullish: macdLine > signalLine (momentum).

State machine (the “wait for bounce” window)
	•	Variables: waitBounce (bool), barsWaited (int).
	•	When a fresh cross up occurs: set waitBounce=true, barsWaited=0.
	•	While waiting, increment barsWaited each bar.
	•	Abort waiting if either:
	•	Bullish stack breaks (ema9 > ema20 > ema200 no longer true), or
	•	maxWait bars elapsed (if maxWait > 0).
	•	The long signal is generated once when all are true on a bar:
	•	waitBounce == true
	•	bounce == true
	•	close > vwap
	•	macdLine > signalLine
Then it resets the state (waitBounce=false, barsWaited=na).

Orders & risk management
	•	On the signal bar, it computes:
	•	entry = close (entry price reference, but the actual order fills on next bar by TV engine),
	•	stop = low (of the signal bar),
	•	risk = entry - stop (must be > 0),
	•	target = entry + rrMultiple * risk.
	•	Then it submits:
	•	strategy.entry("Long", strategy.long)
	•	strategy.exit("Exit Long", from_entry="Long", stop=stop, limit=target)
That attaches an OCO (stop & limit) to the position.
	•	Visuals (if drawRR): draws 3 horizontal lines (SL/Entry/TP), labels (SL/Entry/“3.00R TP”), and two shaded boxes (risk/return) across rrHorizon future bars.

Plots
	•	Context plots for EMA9/20/200, VWAP (circles), MACD & signal in the same pane, and a BUY shape on the signal bar (plotshape(longSignal, "Long Signal")).

TL;DR of the signal:

Exactly one BUY event after a fresh EMA9/EMA20 cross up (above EMA200), followed by a quick retest of EMA9 that closes back above it, while price is above VWAP and MACD line is above its signal. Entry on next bar open; SL = signal-bar low; TP = 3R.

⸻

2) Implementation notes for a Telegram signal bot (so nothing is lost in translation)

Because Pine strategies cannot send Telegram messages directly, the standard architecture is:
	1.	TradingView Alerts → Webhook
	•	Add alertcondition() + alert() in your script to emit a JSON payload containing everything you need (symbol, timeframe, entry/stop/target, R multiple, and a unique key per signal).
	•	Create one alert per symbol per timeframe in TradingView with “Webhook URL” pointing to your server.
	2.	Webhook receiver (server)
	•	Tiny web service (e.g., FastAPI or Express) with a secret token.
	•	Validates the request, de-duplicates by signal_id, and forwards a formatted message to Telegram Bot API (sendMessage) to your chat/channel.
	3.	Telegram bot
	•	Use a single bot with environment-based chat ID routing (e.g., one channel per timeframe, or one channel for all, your choice).
	•	Add nice formatting (pair, TF, time of bar close, entry/SL/TP, risk %, links).
	4.	Multi-pair & multi-TF
	•	Create a chart (or multiple tabs) for each of: BTCUSDT, ETHUSDT, ETHBTC, ADAUSDT
	•	For each, create alerts on timeframes: 15m, 1h, 4h, 1D.
	•	TV will call your webhook whenever a bar closes that meets longSignal.
	5.	Timestamps & timezone
	•	Use the bar close time you embed from TV; format in Africa/Algiers (UTC+1, no DST) for your display.
	6.	Safety & hygiene
	•	HMAC or shared secret on the webhook.
	•	Idempotency (ignore repeats), logging, small DB/Redis/SQLite for history.
	•	Retry on Telegram API failures.

⸻

3) Minimal Pine edits to emit alerts (you/AI can include this or generate equivalent)

Add these lines near the bottom of your script:

// ───────── Alerts ─────────
// Build fields only when we truly have a signal on this bar.
var string srcSym = syminfo.ticker
var string srcTF  = timeframe.period

signal_id = str.format("{0}_{1}_{2}", srcSym, srcTF, str.tostring(time))  // unique per signal bar

entry = na
stop  = na
target = na
if longSignal
    entry := close
    stop  := low
    risk  = entry - stop
    target := risk > 0 ? entry + rrMultiple * risk : na

// Make an alertcondition so TradingView lets you create an alert on this strategy.
alertcondition(longSignal, title="EMA Bounce Buy", message="BUY")

// Optional: structured JSON payload for webhook alerts.
if longSignal
    payload = str.format(
      "{{\"event\":\"EMA_BOUNCE_BUY\",\"symbol\":\"{0}\",\"timeframe\":\"{1}\",\"bar_time\":{2},\"entry\":{3},\"stop\":{4},\"target\":{5},\"rr\":{6},\"signal_id\":\"{7}\"}}",
      srcSym, srcTF, time, entry, stop, target, rrMultiple, signal_id)
    alert(payload, alert.freq_once_per_bar_close)

Then in TradingView, when you Create Alert:
	•	Condition: your strategy → “EMA Bounce Buy”
	•	Options: “Once per bar close”
	•	Webhook URL: your server endpoint (e.g., https://your-server.com/tv-webhook)
	•	Message: leave empty (we already set it in alert()), or keep a fallback.

⸻

4) The prompt for the AI programmer (ready to copy-paste)

Here’s a concise, implementation-grade prompt you can give to an AI/dev:

You are an expert backend/devops engineer building a Telegram signal bot fed by TradingView webhooks.

Goal:
- Build a production-ready Telegram bot that receives webhook alerts from TradingView and posts formatted signals.
- Markets: BTCUSDT, ETHUSDT, ETHBTC, ADAUSDT (Binance symbols; case-insensitive).
- Timeframes: 15m, 1h, 4h, 1D.
- Only long signals coming from my Pine v6 strategy (EMA Bounce • VWAP + MACD Strategy with 3:1 RR).

What the Pine strategy does (must be mirrored in alert handling, not recomputed server-side):
- It arms on a fresh bullish EMA9/EMA20 cross while both are above EMA200.
- After the cross, it waits up to `maxWait` bars for a “bounce” to EMA9:
  - The bar’s low tags EMA9 within `tolPct` (default 0.05%) and closes back above EMA9.
- Additional filters must be true on the signal bar: close > VWAP and MACD line > MACD signal.
- When it triggers, on the signal bar we compute:
  - entry = close (order fills next bar in TV backtest; we only need numbers for messaging),
  - stop = bar’s low,
  - risk = entry - stop,
  - target = entry + rrMultiple * risk (default rrMultiple = 3.0).
- The Pine code emits a JSON alert with: event, symbol, timeframe, bar_time (ms), entry, stop, target, rr, signal_id (symbol_tf_time).

Deliverables:
1) Webhook Receiver
   - Tech: FastAPI (Python) or Express (Node). Choose one and justify briefly.
   - POST /tv-webhook with a shared secret (header or HMAC). Reject invalid signatures quickly.
   - Accept TradingView JSON payload exactly as sent by alert(), e.g.:
     {
       "event": "EMA_BOUNCE_BUY",
       "symbol": "BINANCE:BTCUSDT",
       "timeframe": "15",
       "bar_time": 1734567890000,
       "entry": 65000.12,
       "stop": 64200.45,
       "target": 68999.77,
       "rr": 3,
       "signal_id": "BINANCE:BTCUSDT_15_1734567890000"
     }
   - Validate fields, coerce numbers, and discard any symbol/timeframe not in the allowed lists.
   - Idempotency: store processed signal_id in SQLite/Redis; ignore duplicates.
   - Persist signals in a small DB table (signal_id, symbol, timeframe, entry, stop, target, rr, bar_time_utc, received_at_utc).

2) Telegram Bot
   - Use TELEGRAM_BOT_TOKEN and per-destination CHAT_IDs from environment.
   - One channel/chat is fine; if easy, support optional routing by timeframe (e.g., TF→chat map).
   - Format message (Markdown) like:
     🟢 *EMA Bounce BUY*
     *Pair*: BTCUSDT
     *TF*: 1H
     *Bar Close*: 2025-08-21 10:00 (Africa/Algiers)
     *Entry*: 65,000.12
     *Stop*: 64,200.45  (Risk: 1.23%)
     *Target (3.0R)*: 68,999.77
     *R:R*: 3.0
     ID: BINANCE:BTCUSDT_60_1734567890000
   - Compute Risk% = (entry - stop) / entry * 100, 2 decimals.

3) Configuration
   - ENV vars: PORT, TV_SHARED_SECRET or TV_HMAC_KEY, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID_DEFAULT, OPTIONAL_TF_CHAT_MAP (JSON), TZ_DISPLAY=Africa/Algiers.
   - Allowed symbols/timeframes via ENV (defaults to BTCUSDT, ETHUSDT, ETHBTC, ADAUSDT and 15m/1h/4h/1D).
   - Robust logging (JSON logs), healthcheck route GET /healthz.

4) Security & Reliability
   - HMAC verification of TradingView payloads OR shared-secret header.
   - Rate limiting (basic), request size limit.
   - Retries to Telegram with exponential backoff.
   - Idempotency cache TTL >= 7 days.

5) Developer UX
   - README with:
     - How to set ENV.
     - How to set TradingView alerts (one per symbol per TF, “once per bar close”, Webhook URL = https://<host>/tv-webhook).
     - Example TV alert JSON and curl test command.
     - How to deploy on Render.com (preferred), including a free-tier friendly Procfile / start command.
   - Include Dockerfile.

6) Nice-to-haves (if time allows)
   - /last?symbol=BTCUSDT&tf=1h endpoint to fetch the last signal as JSON.
   - Emoji/status icons, link to TradingView chart if possible (symbol + interval).
   - Optional aggregation: if multiple signals arrive in <5s, send a single grouped Telegram message.

Constraints:
- Do NOT recompute indicators on the server—trust TradingView alerts.
- Assume TradingView sends alerts only on bar close.
- Code should be concise, readable, and production-ready.

Output:
- Provide the full code (server, Telegram client, Dockerfile), sample .env, and a step-by-step Render deployment guide.
- Provide a short section with instructions for creating the 16 TV alerts (4 symbols × 4 TFs) and the exact JSON emitted by Pine.

If you want, I can also generate the server code + Render deploy files in one go and a Pine variant with the alert() block already inserted.