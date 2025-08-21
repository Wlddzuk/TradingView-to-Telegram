# TradingView-to-Telegram Signal Bot - Implementation Tasks

## Overview
Building a production-ready FastAPI server that receives TradingView webhook alerts from the EMA Bounce strategy and forwards formatted signals to Telegram channels with London timezone display and 5m timeframe support.

## Phase 1: Core Infrastructure ✅

### 1.1 Project Structure & Dependencies
- [ ] Create requirements.txt with FastAPI, aiohttp, SQLite, pytz dependencies
- [ ] Set up main.py as FastAPI entry point
- [ ] Create directory structure for organized code

### 1.2 FastAPI Server Setup
- [ ] Initialize FastAPI app with metadata
- [ ] Create /healthz endpoint (basic liveness check)
- [ ] Create /readyz endpoint (database + Telegram connectivity)
- [ ] Add CORS middleware if needed

### 1.3 Database Schema
- [ ] Create database.py with SQLite connection
- [ ] Define signals table (id, signal_id, symbol, timeframe, entry, stop, target, etc.)
- [ ] Define coin_pairs table (id, symbol, enabled, added_by_user_id, etc.)
- [ ] Define admin_users table (id, telegram_user_id, username, is_active)
- [ ] Define bot_state table (key, value, updated_at_utc)
- [ ] Add database indexes for performance

### 1.4 Configuration Management
- [ ] Create config.py with environment variable handling
- [ ] Support required vars: TV_SHARED_SECRET, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID_DEFAULT
- [ ] Support optional routing: TELEGRAM_TF_CHAT_MAP, TELEGRAM_SYMBOL_CHAT_MAP
- [ ] Add validation for configuration values

### 1.5 Logging Setup
- [ ] Configure structured JSON logging
- [ ] Add request/response logging middleware
- [ ] Include signal_id, symbol, timeframe in all relevant logs

## Phase 2: Webhook Processing ✅

### 2.1 Webhook Endpoint
- [ ] Create webhook_handler.py with POST /tv-webhook endpoint
- [ ] Implement X-TV-Secret shared secret validation using secrets.compare_digest()
- [ ] Add request size limits and basic rate limiting
- [ ] Return appropriate HTTP status codes

### 2.2 Payload Validation
- [ ] Create pydantic models for TradingView webhook payload
- [ ] Validate required fields: event, symbol, timeframe, bar_time, entry, stop, target, rr, signal_id
- [ ] Handle parsing errors gracefully

### 2.3 Timeframe Normalization & Filtering
- [ ] Map TradingView timeframes: 5→5m, 15→15m, 60→1h, 240→4h, D→1D
- [ ] Validate against SUPPORTED_TIMEFRAMES (5,15,60,240,D)
- [ ] Filter allowed symbols (BTCUSDT, ETHUSDT, ETHBTC, ADAUSDT + dynamic additions)

### 2.4 Idempotency & Persistence
- [ ] Check signal_id against database to prevent duplicates
- [ ] Store processed signals with 7-day TTL cleanup
- [ ] Handle database connection errors

### 2.5 Signal Processing Pipeline
- [ ] Parse and validate incoming webhook data
- [ ] Store signal in database with metadata
- [ ] Queue for Telegram sending with error handling

## Phase 3: Telegram Integration ✅

### 3.1 Telegram Bot Client
- [ ] Create telegram_bot.py with aiohttp-based Telegram API client
- [ ] Implement authentication with TELEGRAM_BOT_TOKEN
- [ ] Add connection testing for /readyz endpoint

### 3.2 Message Formatting
- [ ] Create formatters.py with quote currency detection
- [ ] Format USDT pairs: $65,000.12 (2 decimals)
- [ ] Format BTC pairs: 0.05234567 BTC (8 decimals)
- [ ] Calculate risk percentage: (entry - stop) / entry * 100

### 3.3 Timezone & Chart Links
- [ ] Convert bar_time from UTC milliseconds to Europe/London display
- [ ] Handle GMT/BST DST transitions correctly
- [ ] Generate TradingView chart links with correct intervals (5, 15, 60, 240, 1D)

### 3.4 Chat Routing
- [ ] Implement routing priority: symbol-specific → timeframe-specific → default
- [ ] Parse TELEGRAM_SYMBOL_CHAT_MAP and TELEGRAM_TF_CHAT_MAP JSON configs
- [ ] Route messages to appropriate chat IDs

### 3.5 Retry Logic
- [ ] Implement exponential backoff (1s, 2s, 4s)
- [ ] Maximum 3 retry attempts
- [ ] Log failures and mark signals as failed in database

## Phase 4: Bot Commands ✅

### 4.1 Basic User Commands
- [ ] Create telegram_handlers.py for command processing
- [ ] /start - Welcome message with bot info
- [ ] /help - Show available commands
- [ ] /status - Show active pairs and recent signals
- [ ] /signals - Show recent signals (last 24h)
- [ ] /chart <SYMBOL> <TF> - Generate TradingView chart link

### 4.2 Admin Commands
- [ ] Create coin_pair_manager.py for dynamic pair management
- [ ] /add <SYMBOL> - Add new coin pair (admin only)
- [ ] /remove <SYMBOL> - Remove coin pair (admin only)
- [ ] /list - Show all monitored pairs
- [ ] /stats - Show signal statistics

### 4.3 Security & Authorization
- [ ] Create security.py with admin ID validation
- [ ] Check TELEGRAM_ADMIN_IDS for management commands
- [ ] Add command rate limiting

### 4.4 Mute/Unmute Functionality
- [ ] /mute <SYMBOL|TF> - Mute signals
- [ ] /unmute <SYMBOL|TF> - Unmute signals
- [ ] Store mute state in bot_state table

### 4.5 Advanced Features
- [ ] /last - Get last signal for all pairs
- [ ] /last <SYMBOL> <TF> - Get specific last signal
- [ ] /config - Show current bot configuration (admin only)

## Phase 5: Deployment & Documentation ✅

### 5.1 Containerization
- [ ] Create Dockerfile with Python 3.11+ base
- [ ] Install requirements and copy source code
- [ ] Set proper entrypoint for FastAPI server
- [ ] Optimize image size

### 5.2 Environment Configuration
- [ ] Create .env.example with all required variables
- [ ] Document required vs optional environment variables
- [ ] Add validation for missing critical variables

### 5.3 Documentation
- [ ] Create comprehensive README.md with setup instructions
- [ ] Document TradingView alert setup (20 alerts: 4 symbols × 5 timeframes)
- [ ] Add curl examples for testing webhook endpoint
- [ ] Include Render.com deployment guide

### 5.4 Deployment Files
- [ ] Create render.yaml for Render.com deployment
- [ ] Add startup command and health check configuration
- [ ] Document environment variable setup in Render dashboard

## Phase 6: Testing & Polish ✅

### 6.1 Unit Tests
- [ ] Create tests/ directory structure
- [ ] test_webhook.py - Test webhook payload validation and processing
- [ ] test_telegram.py - Test message formatting and sending
- [ ] test_formatters.py - Test price formatting and timezone conversion

### 6.2 Integration Testing
- [ ] Test complete webhook-to-Telegram flow
- [ ] Verify all 5 timeframes work correctly
- [ ] Test quote currency formatting (USDT vs BTC)
- [ ] Verify London timezone display

### 6.3 Command Testing
- [ ] Test all user commands (/start, /help, /status, /signals)
- [ ] Test admin commands (/add, /remove, /list, /stats)
- [ ] Verify admin authorization works
- [ ] Test mute/unmute functionality

### 6.4 Error Handling
- [ ] Test webhook with invalid payloads
- [ ] Test Telegram API failures and retries
- [ ] Test database connection failures
- [ ] Verify idempotency with duplicate signals

### 6.5 Performance & Security
- [ ] Test rate limiting on webhook endpoint
- [ ] Verify shared secret validation
- [ ] Test with high volume of signals
- [ ] Validate SQL injection protection

## Configuration Summary

### Target Setup
- **Symbols**: BTCUSDT, ETHUSDT, ETHBTC, ADAUSDT (4 pairs)
- **Timeframes**: 5m, 15m, 1h, 4h, 1D (5 timeframes)
- **Total Alerts**: 20 TradingView alerts required
- **Timezone**: Europe/London (GMT+0/+1 with DST)

### Sample Environment Variables
```bash
# Required
TV_SHARED_SECRET=your_webhook_secret_here
TELEGRAM_BOT_TOKEN=1234567890:your_bot_token_here
TELEGRAM_CHAT_ID_DEFAULT=-1001234567890

# Optional
TELEGRAM_ADMIN_IDS=123456789,987654321
TZ_DISPLAY=Europe/London
PORT=8000
DATABASE_URL=sqlite:///./signals.db
```

### Sample Telegram Message (London Time)
```
🚀 **EMA BOUNCE SIGNAL** 🚀

💰 **COIN PAIR**: BTC/USDT
⏰ **TIMEFRAME**: 5M
📅 **Signal Time**: 2025-08-21 09:00 (London)

📈 **TRADE DETAILS**:
🔵 **ENTRY**: $65,000.12
🔴 **STOP LOSS**: $64,200.45
🟢 **TAKE PROFIT**: $68,999.77

📊 **RISK METRICS**:
💸 **Risk**: 1.23% (Entry to Stop)
🎯 **Reward**: 3.0R (3:1 Risk/Reward)

🔗 **Chart**: [View on TradingView](https://tradingview.com/chart/?symbol=BINANCE:BTCUSDT&interval=5)

🆔 Signal ID: BTCUSDT_5_1734567890000
```

## Review Section

### Changes Implemented
- [ ] All core infrastructure components created
- [ ] Webhook processing with 5-timeframe support implemented
- [ ] Telegram integration with London timezone
- [ ] Bot commands and admin features added
- [ ] Deployment files and documentation completed
- [ ] Testing suite implemented

### Key Features Delivered
- [ ] **5-timeframe support**: 5m, 15m, 1h, 4h, 1D
- [ ] **London timezone**: Europe/London with DST support
- [ ] **Quote currency formatting**: $ for USDT, BTC suffix for BTC pairs
- [ ] **Dynamic pair management**: Add/remove pairs via Telegram commands
- [ ] **Chat routing**: Symbol → timeframe → default chat mapping
- [ ] **Idempotency**: 7-day signal deduplication
- [ ] **Retry logic**: Exponential backoff for Telegram failures
- [ ] **Admin security**: Restricted management commands
- [ ] **Production ready**: Docker, health checks, structured logging

### Technical Stack
- **FastAPI**: Async webhook server
- **SQLite**: Signal and configuration persistence
- **aiohttp**: Telegram API client
- **pytz**: London timezone handling
- **pydantic**: Request/response validation
- **Render.com**: Cloud deployment platform

### Files Created
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
├── tasks/todo.md            # This checklist
└── tests/                   # Test files
    ├── test_webhook.py
    ├── test_telegram.py
    └── test_formatters.py
```

### Success Metrics
- [ ] Webhook receives and processes TradingView alerts correctly
- [ ] Messages formatted properly for all quote currencies
- [ ] London timezone displayed accurately with DST
- [ ] All 5 timeframes (5m, 15m, 1h, 4h, 1D) supported
- [ ] Admin commands work securely
- [ ] Bot handles failures gracefully with retries
- [ ] Deployment successful on Render.com
- [ ] 20 TradingView alerts configured and working