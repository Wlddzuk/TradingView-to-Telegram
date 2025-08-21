# Vercel Deployment Guide

This guide walks you through deploying the TradingView-to-Telegram signal bot to Vercel using GitHub integration.

## Overview

The bot has been converted to Vercel serverless functions architecture:
- **API Endpoints**: `api/webhook.py`, `api/health.py`
- **Database**: Vercel KV (Redis-compatible)
- **Framework**: Pure Python serverless functions

## Prerequisites

1. **GitHub Repository** (this project)
2. **Vercel Account** (free at [vercel.com](https://vercel.com))
3. **Telegram Bot Token** (from BotFather)
4. **TradingView Shared Secret** (for webhook security)

## Step 1: Create Telegram Bot with BotFather

1. Open Telegram and search for `@BotFather`
2. Start a conversation and send `/newbot`
3. Follow prompts to name your bot (e.g., "My Trading Signals Bot")
4. Choose a unique username ending in "bot" (e.g., "my_trading_signals_bot")
5. Save the **Bot Token** (looks like `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`)
6. Send `/setdescription` and add: "Receives TradingView EMA Bounce signals"
7. Send `/setcommands` and add these commands:
   ```
   start - Welcome message and bot info
   help - Show help and available commands
   status - Show active pairs and recent signals
   signals - Show recent signals (last 24h)
   chart - Generate TradingView chart link
   ```

## Step 2: Get Your Telegram Chat ID

1. Add your bot to a channel/group OR use direct messages
2. Send a test message to your bot
3. Visit: `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
4. Find your `chat_id` in the response (number like `-1001234567890` for groups, positive for users)

## Step 3: Deploy to Vercel

### Option A: Direct GitHub Connection (Recommended)

1. Push this project to your GitHub repository
2. Go to [vercel.com/new](https://vercel.com/new)
3. Import your GitHub repository
4. Vercel will automatically detect the configuration from `vercel.json`
5. Configure environment variables (see below)
6. Click "Deploy"

### Option B: Vercel CLI

```bash
npm i -g vercel
vercel login
vercel --prod
```

## Step 4: Configure Environment Variables

In Vercel dashboard → Project → Settings → Environment Variables, add:

| Variable | Value | Example |
|----------|-------|---------|
| `TELEGRAM_BOT_TOKEN` | Your bot token from BotFather | `123456789:ABCdefGHI...` |
| `TELEGRAM_CHAT_ID_DEFAULT` | Your chat ID | `-1001234567890` |
| `TV_SHARED_SECRET` | Random secure string | `your-super-secret-key-123` |
| `KV_REST_API_URL` | Auto-filled when you add KV | `https://abc-123.kv.vercel-storage.com` |
| `KV_REST_API_TOKEN` | Auto-filled when you add KV | `AaBbCc123...` |

### Optional Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PAIRS_LIST` | `BTCUSDT,ETHUSDT,ETHBTC,ADAUSDT` | Comma-separated trading pairs |
| `TIMEFRAMES_LIST` | `5m,15m,1h,4h,1D` | Supported timeframes |
| `TELEGRAM_MAX_RETRIES` | `3` | Retry attempts for failed messages |
| `IDEMPOTENCY_TTL_DAYS` | `7` | Days to store signals for duplicate detection |

## Step 5: Add Vercel KV Database

1. In Vercel dashboard → Project → Storage
2. Click "Create Database" → "KV"
3. Name it (e.g., "signal-storage")
4. Vercel auto-populates `KV_REST_API_URL` and `KV_REST_API_TOKEN`

## Step 6: Configure TradingView Webhook

1. **Get your webhook URL**: `https://your-project-name.vercel.app/api/webhook`
2. **In TradingView Pine Script**, use this webhook configuration:

```pinescript
strategy.entry("EMA Bounce Buy", strategy.long, when=signal_condition, 
    alert_message='{
        "event": "EMA_BOUNCE_BUY",
        "symbol": "' + syminfo.ticker + '",
        "timeframe": "' + timeframe.period + '",
        "bar_time": ' + str(time) + ',
        "entry": ' + str(entry_price) + ',
        "stop": ' + str(stop_price) + ',
        "target": ' + str(target_price) + ',
        "rr": ' + str(risk_reward) + ',
        "signal_id": "' + str(time) + '_' + syminfo.ticker + '_' + timeframe.period + '"
    }'
)
```

3. **Create Alert**:
   - Condition: Your strategy
   - Webhook URL: `https://your-project-name.vercel.app/api/webhook`
   - Message: `{{strategy.order.alert_message}}`
   - Add custom header: `X-TV-Secret: your-super-secret-key-123`

## Step 7: Test Your Deployment

### Test Health Endpoints

```bash
# Basic health check
curl https://your-project-name.vercel.app/healthz

# Comprehensive readiness check
curl https://your-project-name.vercel.app/readyz

# API information
curl https://your-project-name.vercel.app/api/health?info=true
```

### Test Webhook Endpoint

```bash
curl -X POST https://your-project-name.vercel.app/api/webhook \
  -H "Content-Type: application/json" \
  -H "X-TV-Secret: your-super-secret-key-123" \
  -d '{
    "event": "EMA_BOUNCE_BUY",
    "symbol": "BTCUSDT",
    "timeframe": "1h",
    "bar_time": 1640995200000,
    "entry": 47000.0,
    "stop": 46000.0,
    "target": 49000.0,
    "rr": 2.0,
    "signal_id": "test_signal_123"
  }'
```

## How the Bot Works

### Signal Analysis Frequency

The bot **does NOT analyze every minute**. Here's how it works:

1. **TradingView Pine Script** runs on TradingView's servers
2. **Bar-close execution**: Signals only trigger when a bar closes on your chosen timeframe
3. **Example**: On 1-hour timeframe, signals can only trigger once per hour (at minute 00)
4. **Manual triggers**: You can also trigger alerts manually in TradingView

### Webhook Timing

- **Not continuous**: The webhook only fires when Pine Script conditions are met
- **Bar-close based**: 5m timeframe = max once per 5 minutes, 1h = max once per hour
- **Event-driven**: No fixed schedule, only when EMA bounce conditions occur

### Signal Flow

1. TradingView detects EMA bounce → Sends webhook
2. Vercel receives webhook → Validates shared secret
3. Saves signal to database → Prevents duplicates
4. Formats message → Sends to Telegram
5. Telegram delivers → You receive trading signal

## Troubleshooting

### Common Issues

1. **"Invalid shared secret"**: Check `TV_SHARED_SECRET` matches in Vercel and TradingView
2. **"Telegram send failed"**: Verify `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID_DEFAULT`
3. **"Symbol not in enabled pairs"**: Add symbol to `PAIRS_LIST` environment variable
4. **Database errors**: Ensure Vercel KV is properly connected

### View Logs

1. Vercel dashboard → Project → Functions tab
2. Click on function invocations to see detailed logs
3. Use `vercel logs` CLI command

### Debug Commands

Test bot in Telegram:
- `/start` - Check if bot responds
- `/status` - View enabled pairs and recent signals
- `/help` - See all available commands

## Maintenance

### Auto-deployment

Every push to your main branch triggers automatic redeployment.

### Environment Updates

Change variables in Vercel dashboard → redeploy automatically.

### Database Cleanup

Signals auto-expire after `IDEMPOTENCY_TTL_DAYS` (default: 7 days).

## Security Notes

- ✅ Shared secret validation prevents unauthorized webhooks
- ✅ Input validation on all webhook payloads
- ✅ Telegram message sanitization
- ✅ Environment variables for sensitive data
- ✅ No secrets in code repository

## Support

Your bot is now ready to receive TradingView EMA bounce signals and forward them to Telegram! 

Remember: Signals only trigger when your Pine Script strategy conditions are met, not on a fixed schedule.