# Automated Polling Setup Guide

This guide helps you set up automated polling for your TradingView email signal bot using multiple methods for redundancy.

## 🎯 Overview

Your signal bot needs continuous polling because:
- Vercel serverless functions don't run continuously  
- TradingView emails need to be checked regularly
- Signals should be processed within 1-2 minutes of arrival

## 📋 Polling Methods

### Method 1: GitHub Actions (Primary) ✅ IMPLEMENTED

**Advantages:**
- ✅ Free (2000 minutes/month for free accounts)
- ✅ Reliable GitHub infrastructure  
- ✅ Built-in logging and monitoring
- ✅ Easy to modify and maintain
- ✅ Runs every 60 seconds

**Setup:**
1. **Automatic** - GitHub Actions are already configured in this repository
2. **Workflows created:**
   - `email-poll.yml` - Polls email endpoint every minute
   - `health-check.yml` - Monitors system health every 5 minutes

**Monitoring:**
- Go to: https://github.com/Wlddzuk/TradingView-to-Telegram/actions
- View real-time logs and success/failure status
- Get email notifications if workflows fail

### Method 2: UptimeRobot (Backup) 

**Advantages:**
- ✅ Free tier: 50 monitors, 5-minute intervals
- ✅ Independent of GitHub
- ✅ Email/SMS alerts on failures
- ✅ Easy web-based setup

**Setup Steps:**

1. **Create UptimeRobot Account**
   - Go to: https://uptimerobot.com
   - Sign up for free account

2. **Add HTTP Monitor**
   - Click "Add New Monitor"
   - **Monitor Type**: HTTP(s)
   - **Friendly Name**: TradingView Email Polling
   - **URL**: `https://walid3rbot-git-main-walids-projects-fd231c7c.vercel.app/api/email_check`
   - **Monitoring Interval**: 5 minutes (free tier)
   - **Alert Contacts**: Your email

3. **Configure Alerts**
   - Add email notifications for down/up events
   - Optional: Add SMS alerts (requires credit)

### Method 3: Cronitor (Alternative)

**Setup:**
1. Go to: https://cronitor.io
2. Create free account (5 monitors free)
3. Add HTTP monitor with same URL
4. Set to ping every 60 seconds

### Method 4: EasyCron (Alternative)

**Setup:**
1. Go to: https://www.easycron.com
2. Free account: 20 cron jobs
3. Create cron job calling the email endpoint
4. Set to run every minute

## 🚀 GitHub Actions Details

### Current Configuration

**Email Polling Workflow** (`email-poll.yml`):
```yaml
# Runs every minute
- cron: '* * * * *'
# Calls: /api/email_check
# Logs: Signal counts, errors, HTTP status
```

**Health Check Workflow** (`health-check.yml`):
```yaml  
# Runs every 5 minutes
- cron: '*/5 * * * *'
# Checks: Main app + Email endpoint health
# Monitors: Response times, error rates
```

### Monitoring Your GitHub Actions

1. **View Workflow Runs:**
   - Go to: https://github.com/Wlddzuk/TradingView-to-Telegram/actions
   - Click on workflow name to see recent runs

2. **Check Logs:**
   - Click on any run to see detailed logs
   - Look for "✅ Signals processed" messages
   - Check for "❌ Error detected" warnings

3. **Manual Triggering:**
   - Click "Run workflow" to test manually
   - Useful for immediate testing

## 📊 Expected Behavior

### Normal Operation
```
✅ Signals processed: 0 (successful: 0)  # No new signals
✅ Email polling completed successfully
```

### With New Signals  
```
✅ Signals processed: 1 (successful: 1)  # Found 1 signal
✅ Email polling completed successfully
```

### Error Conditions
```
❌ Error detected in response  # IMAP/parsing issues
❌ HTTP error: 500            # Server errors  
```

## 🔧 Troubleshooting

### GitHub Actions Not Running

**Check:**
1. Repository must be public or have GitHub Pro
2. Workflows enabled in Settings → Actions
3. No syntax errors in YAML files

**Fix:**
- Go to Actions tab → Enable workflows
- Check workflow file syntax
- Push a commit to trigger workflows

### High Usage Warnings

**GitHub Actions Limits:**
- Free: 2000 minutes/month
- Current usage: ~1440 minutes/month (24/7 polling)
- **You have sufficient free tier limits**

**If approaching limits:**
1. Reduce polling frequency to every 2-3 minutes
2. Use UptimeRobot as primary method
3. Upgrade to GitHub Pro ($4/month)

### UptimeRobot Setup Issues

**Common problems:**
- URL must be publicly accessible ✅
- Free tier limited to 5-minute intervals
- Need to configure alert contacts

**Solutions:**
- Test URL manually first: `curl "https://your-url/api/email_check"`
- Add multiple contact methods
- Consider paid plan for 1-minute intervals

## 🎯 Recommended Setup

**For Maximum Reliability:**

1. **Primary**: GitHub Actions (every 60 seconds)
2. **Backup**: UptimeRobot (every 5 minutes) 
3. **Monitoring**: Both services send alerts on failures

This ensures:
- ✅ Signals processed within 1-2 minutes
- ✅ Redundancy if one service fails
- ✅ Email alerts if system goes down
- ✅ Free operation within tier limits

## 📈 Monitoring Dashboard

**Key Metrics to Watch:**
- ✅ Workflow success rate (should be >99%)
- ✅ Signal processing count (matches TradingView alerts)
- ✅ Response times (should be <30 seconds)
- ✅ Error frequency (should be near zero)

**Alert Conditions:**
- ❌ Workflow fails 3+ times in a row
- ❌ No signals processed when market is active
- ❌ HTTP errors or IMAP connection failures

## 🚀 Production Ready

Your automated polling is now configured and ready for production! The system will:

1. **Poll every 60 seconds** via GitHub Actions
2. **Process TradingView email signals** automatically  
3. **Send Telegram messages** within 1-2 minutes
4. **Monitor system health** every 5 minutes
5. **Alert you** if any issues occur

**Next step:** Set up your TradingView email alerts and let the system run! 🎉