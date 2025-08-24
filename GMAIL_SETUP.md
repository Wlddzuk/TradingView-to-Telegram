# Gmail Setup for TradingView Email Alerts

## Overview

This guide helps you set up Gmail to receive and process TradingView email alerts for the EMA Bounce signal bot. The system uses the email-based architecture: **TradingView → Gmail → IMAP → Vercel → Telegram**.

## Prerequisites

- Gmail account
- Gmail App Password (for IMAP access)
- TradingView Free account

## Step 1: Enable Gmail IMAP

1. **Go to Gmail Settings**:
   - Open Gmail → Click the gear icon → "See all settings"

2. **Enable IMAP**:
   - Go to "Forwarding and POP/IMAP" tab
   - In the "IMAP Access" section, select "Enable IMAP"
   - Click "Save Changes"

## Step 2: Create Gmail App Password

1. **Enable 2-Step Verification** (if not already enabled):
   - Go to [Google Account Security](https://myaccount.google.com/security)
   - Turn on "2-Step Verification"

2. **Generate App Password**:
   - In Google Account Security, go to "App passwords"
   - Select "Mail" and "Other (custom name)"
   - Enter: "TradingView Signal Bot"
   - Click "Generate"
   - **Copy the 16-character password** (you'll need this for environment variables)

## Step 3: Create TradingView Label/Folder

1. **Create Label in Gmail**:
   - In Gmail, go to "Settings" → "Labels"
   - Click "Create new label"
   - Name it: **"TradingView"**
   - Click "Create"

2. **Create Filter Rule**:
   - In Gmail, click the search box and then "Show search options" (filter icon)
   - Set the following criteria:
     - **From**: `noreply@tradingview.com`
     - **Subject**: leave blank (will catch all TradingView emails)
   - Click "Create filter"
   - In the next dialog, check:
     - ✅ "Apply the label: TradingView"
     - ✅ "Never send it to Spam"
     - ✅ "Also apply filter to matching conversations"
   - Click "Create filter"

## Step 4: Configure Environment Variables

Add these environment variables to your Vercel deployment:

```bash
# Gmail IMAP Configuration
GMAIL_EMAIL=your-email@gmail.com
GMAIL_APP_PASSWORD=your-16-character-app-password
GMAIL_FOLDER_NAME=TradingView

# Telegram Configuration (existing)
TELEGRAM_BOT_TOKEN=your-telegram-bot-token
TELEGRAM_CHAT_ID_DEFAULT=your-telegram-chat-id

# Optional: TradingView secret for security
TV_SHARED_SECRET=your-secret-key
```

## Step 5: Set Up TradingView Alert

1. **Open TradingView** and load your chart with the EMA Bounce Pine script

2. **Create Alert**:
   - Click the "Alert" button (bell icon)
   - **Condition**: Select "Any alert() function call" 
   - **Options**: ✅ "Once Per Bar Close"
   - **Notifications**: ✅ "Send email"
   - **Message**: Leave empty (the Pine script generates structured messages)
   - Click "Create"

## Step 6: Test the Setup

1. **Trigger a test signal** by creating a condition where your EMA bounce strategy fires

2. **Check Gmail**:
   - Look for the email in your "TradingView" label
   - Email should contain structured data like:
   ```
   action:ENTRY|symbol:ETHUSDT|tf:60|entry:4787.12|stop:4720.45|target:4987.13|rr:3|signal_id:ETHUSDT_60_1734567890000|secret:walid-ema-bounce-2025
   ```

3. **Test the endpoint**:
   - Visit: `https://your-vercel-app.vercel.app/api/email_check`
   - Should return JSON with signal processing results

4. **Check Telegram**:
   - Your Telegram bot should send a formatted message with the signal details

## Troubleshooting

### Email Not Received
- Check TradingView alert is set to "Send email"
- Verify email is going to the correct Gmail account
- Check Gmail spam folder

### IMAP Connection Issues
- Verify App Password is correct (16 characters, no spaces)
- Ensure IMAP is enabled in Gmail settings
- Check that 2-Step Verification is enabled

### Filter Not Working
- Verify the Gmail filter is active
- Check that the "TradingView" label exists
- Ensure emails are from `noreply@tradingview.com`

### Structured Data Missing
- Verify the Pine script contains the email alert payload
- Check that the TradingView alert uses "Any alert() function call"
- Ensure the alert message is left empty

## Pine Script Configuration

Your Pine script should contain this alert structure:

```pinescript
// Create structured email message for IMAP parsing
emailPayload = 
    "action:ENTRY" +
    "|symbol:" + cleanSym +
    "|tf:" + tf +
    "|bar_time:" + str.tostring(tstamp) +
    "|entry:" + str.tostring(e) +
    "|stop:" + str.tostring(s) +
    "|target:" + str.tostring(t) +
    "|rr:" + str.tostring(rrMultiple) +
    "|signal_id:" + cleanSym + "_" + tf + "_" + str.tostring(tstamp) +
    "|secret:walid-ema-bounce-2025"

// Send structured message via TradingView email alert
alert(emailPayload, alert.freq_once_per_bar_close)
```

## Email Polling Frequency

The system checks for new emails every 5 minutes by default when the `/api/email_check` endpoint is called. For automated polling, you can:

1. **Use a cron service** to call the endpoint every 60 seconds:
   ```bash
   curl "https://your-vercel-app.vercel.app/api/email_check"
   ```

2. **Use GitHub Actions** with a scheduled workflow

3. **Use a monitoring service** like UptimeRobot or Cronitor

## Security Notes

- Never share your Gmail App Password
- Use a dedicated Gmail account for trading signals
- The Pine script includes a secret (`walid-ema-bounce-2025`) for validation
- Consider using IP restrictions for the webhook endpoint

## Architecture Flow

```
TradingView Alert
       ↓ (email)
   Gmail IMAP
       ↓ (polls every 60s)
   Vercel /api/email_check
       ↓ (processes structured message)
   Telegram Bot API
       ↓ (formatted signal)
   Telegram Channel/Chat
```

This email-based approach works with **TradingView Free** and provides reliable signal delivery without needing TradingView Premium webhooks.