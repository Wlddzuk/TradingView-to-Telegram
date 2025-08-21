# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a TradingView-to-Telegram signal bot that receives webhook alerts from a Pine Script v6 strategy and forwards formatted trading signals to Telegram channels. The strategy implements an EMA Bounce + VWAP + MACD system for long-only trades with 3:1 risk-reward ratio.

### Trading Strategy Logic
The Pine Script strategy (`ema_bounce_vwap_macd_strategy.pine`) implements:
- **EMA Cross Detection**: Waits for EMA9 to cross above EMA20 while both are above EMA200
- **Bounce Pattern**: After cross, waits for price to dip to EMA9 (within 0.05% tolerance) and close back above
- **Confluence Filters**: Price must be above VWAP and MACD line above signal line
- **Risk Management**: Entry = close, Stop = signal bar low, Target = entry + 3×risk
- **State Machine**: Arms on cross, waits for bounce with configurable timeout (default 30 bars)

### Target Markets & Timeframes
- **Default Symbols**: BTCUSDT, ETHUSDT, ETHBTC, ADAUSDT (case-insensitive)
- **Timeframes**: 15m, 1h, 4h, 1D (normalized as 15, 60, 240, D)
- **Dynamic Management**: Users can add/remove coin pairs via Telegram commands

## Architecture

The system consists of three main components:

1. **Pine Script Strategy** (`ema_bounce_vwap_macd_strategy.pine`)
   - Implements trading logic and generates alerts
   - Emits JSON webhooks to server on signal generation

2. **Webhook Receiver** (to be implemented)
   - FastAPI or Express server
   - Receives TradingView alerts via POST /tv-webhook
   - Validates, deduplicates, and persists signals

3. **Telegram Bot** (to be implemented)
   - Formats and sends signals to Telegram channels
   - Handles dynamic coin pair management
   - Provides admin commands for pair management

## Pine Script Alerts Implementation

The Pine script includes the following alerts block (lines 127-145):

```pine
// ───────── Alerts ─────────
var string srcSym = syminfo.ticker
var string srcTF  = timeframe.period
signal_id = str.format("{0}_{1}_{2}", srcSym, srcTF, str.tostring(time))

var float a_entry = na, a_stop = na, a_target = na
if longSignal
    a_entry := close
    a_stop  := low
    risk    = a_entry - a_stop
    a_target := risk > 0 ? a_entry + rrMultiple * risk : na

alertcondition(longSignal, title="EMA Bounce Buy", message="BUY")

if longSignal
    payload = str.format(
      "{{\"event\":\"EMA_BOUNCE_BUY\",\"symbol\":\"{0}\",\"timeframe\":\"{1}\",\"bar_time\":{2},\"entry\":{3},\"stop\":{4},\"target\":{5},\"rr\":{6},\"signal_id\":\"{7}\"}}",
      srcSym, srcTF, time, a_entry, a_stop, a_target, rrMultiple, signal_id)
    alert(payload, alert.freq_once_per_bar_close)
```

**Critical**: Use `alert.freq_once_per_bar_close` to prevent duplicate alerts.

## Key Implementation Requirements

### Webhook Payload Format
```json
{
  "event": "EMA_BOUNCE_BUY",
  "symbol": "BTCUSDT",
  "timeframe": "15",
  "bar_time": 1734567890000,
  "entry": 65000.12,
  "stop": 64200.45,
  "target": 68999.77,
  "rr": 3,
  "signal_id": "BTCUSDT_15_1734567890000"
}
```

**Note**: TradingView sends timeframe as "15", "60", "240", "D" (not "1440" for daily).

### Enhanced Telegram Message Format

#### For USDT Pairs (BTCUSDT, ETHUSDT, ADAUSDT):
```
🚀 **EMA BOUNCE SIGNAL** 🚀

💰 **COIN PAIR**: BTC/USDT
⏰ **TIMEFRAME**: 1H
📅 **Signal Time**: 2025-08-21 10:00 (Africa/Algiers)

📈 **TRADE DETAILS**:
🔵 **ENTRY**: $65,000.12
🔴 **STOP LOSS**: $64,200.45
🟢 **TAKE PROFIT**: $68,999.77

📊 **RISK METRICS**:
💸 **Risk**: 1.23% (Entry to Stop)
🎯 **Reward**: 3.0R (3:1 Risk/Reward)

🔗 **Chart**: [View on TradingView](https://tradingview.com/chart/?symbol=BINANCE:BTCUSDT&interval=60)

🆔 Signal ID: BTCUSDT_60_1734567890000
```

#### For BTC Pairs (ETHBTC):
```
🚀 **EMA BOUNCE SIGNAL** 🚀

💰 **COIN PAIR**: ETH/BTC
⏰ **TIMEFRAME**: 4H
📅 **Signal Time**: 2025-08-21 14:00 (Africa/Algiers)

📈 **TRADE DETAILS**:
🔵 **ENTRY**: 0.05234567 BTC
🔴 **STOP LOSS**: 0.05198234 BTC
🟢 **TAKE PROFIT**: 0.05343333 BTC

📊 **RISK METRICS**:
💸 **Risk**: 0.69% (Entry to Stop)
🎯 **Reward**: 3.0R (3:1 Risk/Reward)

🔗 **Chart**: [View on TradingView](https://tradingview.com/chart/?symbol=BINANCE:ETHBTC&interval=240)

🆔 Signal ID: ETHBTC_240_1734567890000
```

### Timeframe Normalization & Message Routing

Server must normalize incoming timeframes and route to appropriate chats:

#### Timeframe Mapping:
- `"15"` → 15m
- `"60"` → 1h  
- `"240"` → 4h
- `"D"` → 1D

#### Chat Routing Priority:
1. **Symbol-specific**: `TELEGRAM_SYMBOL_CHAT_MAP` (if configured)
2. **Timeframe-specific**: `TELEGRAM_TF_CHAT_MAP` (if configured)
3. **Default**: `TELEGRAM_CHAT_ID_DEFAULT`

### Price & Currency Formatting

#### Decimal Places by Quote Asset:
- **USDT pairs**: 2 decimals, prepend `$`
- **BTC pairs**: 8 decimals, append ` BTC`
- **ETH pairs**: 6 decimals, append ` ETH` (if supported)

#### Quote Asset Detection:
```python
def get_quote_currency(symbol):
    if symbol.endswith('USDT'):
        return 'USDT'
    elif symbol.endswith('BTC'):
        return 'BTC'
    elif symbol.endswith('ETH'):
        return 'ETH'
    return 'UNKNOWN'

def format_price(price, quote):
    if quote == 'USDT':
        return f"${price:,.2f}"
    elif quote == 'BTC':
        return f"{price:.8f} BTC"
    elif quote == 'ETH':
        return f"{price:.6f} ETH"
    return f"{price}"
```

### Telegram Bot Commands

#### User Commands
```
/start - Welcome message and bot info
/help - Show available commands
/status - Show current active coin pairs and timeframes
/signals - Show recent signals (last 24h)
/chart <SYMBOL> <TF> - Get TradingView chart link
/last - Get last signal for all pairs
/last <SYMBOL> <TF> - Get last signal for specific pair/timeframe
```

#### Admin Commands (restricted to authorized users)
```
/add <SYMBOL> - Add new coin pair to monitoring
  Example: /add SOLUSDT

/remove <SYMBOL> - Remove coin pair from monitoring
  Example: /remove ADAUSDT

/list - Show all monitored pairs and their status
/stats - Show signal statistics and performance
/config - Show current bot configuration
/mute <SYMBOL|TF> - Mute signals for symbol or timeframe
/unmute <SYMBOL|TF> - Unmute signals for symbol or timeframe
```

## Development Commands

### Environment Setup
```bash
# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Server Development
```bash
# Run FastAPI server
uvicorn main:app --reload --port 8000

# Run with environment variables
PORT=8000 TV_SHARED_SECRET=your_secret TELEGRAM_BOT_TOKEN=your_token python main.py
```

### Testing
```bash
# Test webhook endpoint
curl -X POST http://localhost:8000/tv-webhook \
  -H "Content-Type: application/json" \
  -H "X-TV-Secret: your_secret" \
  -d '{"event":"EMA_BOUNCE_BUY","symbol":"BTCUSDT","timeframe":"15","bar_time":1734567890000,"entry":65000.12,"stop":64200.45,"target":68999.77,"rr":3,"signal_id":"BTCUSDT_15_1734567890000"}'

# Health check
curl http://localhost:8000/healthz

# Readiness check
curl http://localhost:8000/readyz
```

## Configuration

### Environment Variables

#### Required
- `TV_SHARED_SECRET`: TradingView webhook secret (header: X-TV-Secret)
- `TELEGRAM_BOT_TOKEN`: Telegram bot token
- `TELEGRAM_CHAT_ID_DEFAULT`: Default Telegram chat/channel ID

#### Optional Routing
- `TELEGRAM_TF_CHAT_MAP`: JSON mapping timeframes to chat IDs
  ```json
  {"15":"-100123","60":"-100456","240":"-100789","D":"-100999"}
  ```
- `TELEGRAM_SYMBOL_CHAT_MAP`: JSON mapping symbols to chat IDs (overrides TF routing)
  ```json
  {"BTCUSDT":"-100abc","ETHUSDT":"-100def"}
  ```

#### Security & Admin
- `TELEGRAM_ADMIN_IDS`: Comma-separated list of admin user IDs

#### Display & Data
- `TZ_DISPLAY`: Display timezone (default: Africa/Algiers)
- `DEFAULT_PAIRS`: Default coin pairs (default: BTCUSDT,ETHUSDT,ETHBTC,ADAUSDT)
- `SUPPORTED_TIMEFRAMES`: Supported timeframes (default: 15,60,240,D)

#### Database & Performance
- `DATABASE_URL`: Database connection string
- `PORT`: Server port (default: 8000)
- `IDEMPOTENCY_TTL_DAYS`: Signal cache TTL (default: 7)

### TradingView Alert Setup Checklist

**For each symbol (BTCUSDT, ETHUSDT, ETHBTC, ADAUSDT):**

1. **15m Chart**:
   - Create alert on strategy
   - Condition: "EMA Bounce Buy" 
   - Options: "Once per bar close"
   - Webhook URL: `https://your-server.com/tv-webhook`
   - Message: Leave empty

2. **1h Chart**: Repeat above steps
3. **4h Chart**: Repeat above steps  
4. **1D Chart**: Repeat above steps

**Total Required**: 16 alerts (4 symbols × 4 timeframes)

**When adding pairs via `/add` command**: You must manually create the 4 corresponding TradingView alerts for the new pair.

**When removing pairs via `/remove` command**: You can delete the corresponding TradingView alerts.

## Security Requirements

### Webhook Security
- **Shared Secret Validation**: Check `X-TV-Secret` header against `TV_SHARED_SECRET`
- **Constant Time Compare**: Use `secrets.compare_digest()` to prevent timing attacks
- **HTTPS Only**: Reject HTTP requests in production
- **Request Size Limits**: Limit payload size to prevent abuse
- **Rate Limiting**: Basic rate limiting per IP

### Bot Security
- **Admin Authorization**: Restrict pair management to `TELEGRAM_ADMIN_IDS`
- **Input Validation**: Validate all symbols and timeframes
- **Command Rate Limiting**: Prevent bot command spam

### Infrastructure
- **IP Allow-listing**: Optional (TradingView IPs change frequently)
- **Basic Auth**: Optional additional layer for webhook endpoint

## Database Schema

```sql
-- Signals table
CREATE TABLE signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    signal_id TEXT UNIQUE NOT NULL,
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    entry REAL NOT NULL,
    stop REAL NOT NULL,
    target REAL NOT NULL,
    rr REAL NOT NULL,
    risk_percent REAL NOT NULL,
    bar_time_utc INTEGER NOT NULL,
    received_at_utc INTEGER NOT NULL,
    processed BOOLEAN DEFAULT FALSE,
    telegram_sent BOOLEAN DEFAULT FALSE,
    chat_id TEXT,
    error_message TEXT
);

-- Active coin pairs management
CREATE TABLE coin_pairs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT UNIQUE NOT NULL,
    enabled BOOLEAN DEFAULT TRUE,
    added_by_user_id INTEGER,
    added_at_utc INTEGER NOT NULL,
    last_signal_at_utc INTEGER
);

-- Bot admin users
CREATE TABLE admin_users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_user_id INTEGER UNIQUE NOT NULL,
    username TEXT,
    added_at_utc INTEGER NOT NULL,
    is_active BOOLEAN DEFAULT TRUE
);

-- Bot state and muting
CREATE TABLE bot_state (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at_utc INTEGER NOT NULL
);

-- Idempotency cache
CREATE INDEX idx_signals_signal_id ON signals(signal_id);
CREATE INDEX idx_signals_symbol_tf ON signals(symbol, timeframe);
CREATE INDEX idx_signals_received_at ON signals(received_at_utc);
```

## Message Formatting & Chart Links

### Bar Time Conversion
```python
from datetime import datetime
import pytz

def format_bar_time(bar_time_ms, tz_name="Africa/Algiers"):
    """Convert bar_time (milliseconds since epoch) to display timezone"""
    dt_utc = datetime.fromtimestamp(bar_time_ms / 1000, tz=pytz.UTC)
    tz = pytz.timezone(tz_name)
    dt_local = dt_utc.astimezone(tz)
    return dt_local.strftime("%Y-%m-%d %H:%M")
```

### TradingView Chart Links
```python
def generate_chart_link(symbol, timeframe):
    """Generate TradingView chart link"""
    # Map timeframes for URL
    tf_map = {"15": "15", "60": "60", "240": "240", "D": "1D"}
    interval = tf_map.get(timeframe, timeframe)
    
    return f"https://tradingview.com/chart/?symbol=BINANCE:{symbol}&interval={interval}"
```

## Error Handling & Reliability

### Idempotency
- **TTL**: Cache processed `signal_id` for ≥7 days
- **Eviction**: Automatic cleanup of expired entries
- **Storage**: Use Redis or SQLite with indexed queries

### Telegram Retries
- **Retry Count**: 3 attempts maximum
- **Backoff**: Exponential backoff (1s, 2s, 4s)
- **Failure Handling**: Log failure, mark signal as failed in database
- **Dead Letter**: Store failed messages for manual review

### Health Checks
```python
# /healthz - Basic liveness
{"status": "ok", "timestamp": "2025-08-21T10:00:00Z"}

# /readyz - Comprehensive readiness
{
    "status": "ready",
    "database": "connected", 
    "telegram": "reachable",
    "timestamp": "2025-08-21T10:00:00Z"
}
```

### Structured Logging
```python
# Log format for each signal
{
    "timestamp": "2025-08-21T10:00:00Z",
    "level": "INFO",
    "event": "signal_sent",
    "signal_id": "BTCUSDT_60_1734567890000",
    "symbol": "BTCUSDT",
    "timeframe": "60",
    "chat_id": "-100123456",
    "telegram_status": 200,
    "processing_time_ms": 245
}
```

## Deployment Notes

### Render.com Deployment
- Use Python buildpack or Dockerfile
- Set all environment variables in Render dashboard
- Configure webhook URL: `https://your-app.onrender.com/tv-webhook`
- Set Telegram webhook: `https://api.telegram.org/bot<TOKEN>/setWebhook?url=https://your-app.onrender.com/telegram-webhook`

### File Structure (when implemented)
```
├── main.py                    # FastAPI server entry point
├── webhook_handler.py         # TradingView webhook processing
├── telegram_bot.py           # Telegram message formatting and sending
├── telegram_handlers.py      # Bot command handlers
├── database.py               # Database operations and schema
├── coin_pair_manager.py      # Dynamic pair management
├── config.py                 # Configuration and environment
├── formatters.py             # Message and price formatting
├── security.py               # Authentication and validation
├── utils.py                  # Utility functions
├── requirements.txt          # Python dependencies
├── Dockerfile               # Container configuration
├── .env.example             # Environment variables template
├── README.md                # Setup and deployment guide
└── tests/                   # Test files
    ├── test_webhook.py
    ├── test_telegram.py
    └── test_formatters.py
```

## Bot Command Examples

### Adding a new pair:
```
User: /add SOLUSDT
Bot: ✅ Added SOLUSDT to monitoring list. 
     📋 TODO: Create 4 TradingView alerts for SOLUSDT (15m, 1h, 4h, 1D)
     📊 Current pairs: BTCUSDT, ETHUSDT, ETHBTC, ADAUSDT, SOLUSDT
```

### Status with last signals:
```
User: /status
Bot: 📊 **Current Monitoring Status**
     
     **Active Pairs** (4):
     • BTCUSDT ✅ (Last: 2h ago, 1H @ $65,000)
     • ETHUSDT ✅ (Last: 5h ago, 4H @ $3,456) 
     • ETHBTC ✅ (No signals today)
     • ADAUSDT 🔇 (Muted)
     
     **Timeframes**: 15m, 1h, 4h, 1D
     **Total alerts needed**: 16
     **Signals today**: 12
```

### Recent signals:
```
User: /signals
Bot: 📈 **Recent Signals (Last 24h)**
     
     🟢 BTCUSDT 1H - 2h ago
     Entry: $65,000 → TP: $68,999 (3R)
     
     🟢 ETHUSDT 4H - 5h ago  
     Entry: $3,456 → TP: $3,678 (3R)
     
     🟢 SOLUSDT 15m - 6h ago
     Entry: $89.45 → TP: $95.67 (3R)
     
     📊 Total: 12 signals | 4 pairs active
```

## Important Notes

- **Do NOT recompute indicators**: Trust TradingView alerts completely
- **Bar time is UTC milliseconds**: Convert to Africa/Algiers for display
- **Manual alert management**: Adding/removing pairs requires manual TradingView alert creation/deletion
- **Timeframe normalization**: Handle "15", "60", "240", "D" from TradingView
- **Quote currency awareness**: Format prices correctly for USDT vs BTC pairs
- **Idempotency is critical**: Use signal_id to prevent duplicate messages
- **Admin security**: Validate admin user IDs on every management command
- **HTTPS only**: Never accept HTTP requests in production
- **Rate limiting**: Implement both webhook and bot command rate limits