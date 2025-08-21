"""
Message formatting utilities for Telegram signals (Vercel compatible)
"""

import re
from datetime import datetime
from typing import Optional

import pytz

from lib.config import settings

def detect_quote_currency(symbol: str) -> str:
    """Detect quote currency from trading pair symbol"""
    symbol = symbol.upper()
    
    # Known quote currencies in order of preference (longer first to avoid USDT matching as USD)
    quote_currencies = ["USDT", "BUSD", "USDC", "BTC", "ETH", "BNB", "USD"]
    
    for quote in quote_currencies:
        if symbol.endswith(quote):
            return quote
    
    # Default fallback
    return "USDT"

def format_price(price: float, quote_currency: str) -> str:
    """Format price based on quote currency"""
    if quote_currency in ["USDT", "BUSD", "USDC", "USD"]:
        # USD-based pairs: 2 decimal places with $ symbol
        return f"${price:,.2f}"
    elif quote_currency == "BTC":
        # BTC pairs: 8 decimal places with BTC suffix
        return f"{price:.8f} BTC"
    elif quote_currency == "ETH":
        # ETH pairs: 6 decimal places with ETH suffix
        return f"{price:.6f} ETH"
    else:
        # Default: 4 decimal places with suffix
        return f"{price:.4f} {quote_currency}"

def calculate_risk_percentage(entry: float, stop: float) -> float:
    """Calculate risk percentage: (entry - stop) / entry * 100"""
    if entry <= 0:
        return 0.0
    
    risk_pct = abs(entry - stop) / entry * 100
    return round(risk_pct, 2)

def convert_timestamp_to_london(timestamp_ms: int) -> str:
    """Convert timestamp from milliseconds to London time string"""
    try:
        # Convert milliseconds to seconds
        timestamp_s = timestamp_ms / 1000
        
        # Create UTC datetime
        utc_dt = datetime.fromtimestamp(timestamp_s, tz=pytz.UTC)
        
        # Convert to London timezone
        london_tz = pytz.timezone(settings.tz_display)
        london_dt = utc_dt.astimezone(london_tz)
        
        # Format as readable string
        return london_dt.strftime("%Y-%m-%d %H:%M (%Z)")
        
    except Exception as e:
        return "Unknown time"

def normalize_timeframe_display(timeframe: str) -> str:
    """Convert TradingView timeframe to display format"""
    normalized = settings.normalize_timeframe(timeframe)
    if normalized:
        return normalized
    
    # Fallback for unknown timeframes
    return timeframe

def get_tradingview_chart_url(symbol: str, timeframe: str) -> str:
    """Generate TradingView chart URL"""
    # Convert symbol to TradingView format (add exchange prefix)
    tv_symbol = f"BINANCE:{symbol}"
    
    # Get chart interval
    interval = settings.get_chart_interval(timeframe)
    
    return f"https://tradingview.com/chart/?symbol={tv_symbol}&interval={interval}"

def format_signal_message(
    signal_id: str,
    symbol: str,
    timeframe: str,
    event: str,
    bar_time: int,
    entry: float,
    stop: float,
    target: float,
    rr: float
) -> str:
    """Format complete signal message for Telegram"""
    
    # Detect quote currency and format prices
    quote_currency = detect_quote_currency(symbol)
    entry_formatted = format_price(entry, quote_currency)
    stop_formatted = format_price(stop, quote_currency)
    target_formatted = format_price(target, quote_currency)
    
    # Calculate risk percentage
    risk_pct = calculate_risk_percentage(entry, stop)
    
    # Convert timestamp to London time
    signal_time = convert_timestamp_to_london(bar_time)
    
    # Normalize timeframe
    tf_display = normalize_timeframe_display(timeframe)
    
    # Extract base and quote from symbol for display
    base_symbol = symbol.replace(quote_currency, "")
    pair_display = f"{base_symbol}/{quote_currency}"
    
    # Generate chart URL
    chart_url = get_tradingview_chart_url(symbol, timeframe)
    
    # Build message
    message = f"""🚀 **EMA BOUNCE SIGNAL** 🚀

💰 **COIN PAIR**: {pair_display}
⏰ **TIMEFRAME**: {tf_display}
📅 **Signal Time**: {signal_time}

📈 **TRADE DETAILS**:
🔵 **ENTRY**: {entry_formatted}
🔴 **STOP LOSS**: {stop_formatted}
🟢 **TAKE PROFIT**: {target_formatted}

📊 **RISK METRICS**:
💸 **Risk**: {risk_pct}% (Entry to Stop)
🎯 **Reward**: {rr:.1f}R ({rr:.0f}:1 Risk/Reward)

🔗 **Chart**: [View on TradingView]({chart_url})

🆔 Signal ID: {signal_id}"""

    return message

def format_status_message(signals: list, enabled_pairs: list) -> str:
    """Format status message showing recent signals and enabled pairs"""
    
    if not signals:
        recent_text = "No recent signals in the last 24 hours"
    else:
        recent_text = f"📊 **Recent Signals** ({len(signals)} in last 24h):\n"
        
        for signal in signals[:5]:  # Show last 5
            symbol = signal['symbol']
            tf = normalize_timeframe_display(signal['timeframe'])
            time_str = convert_timestamp_to_london(signal['bar_time'])
            status = "✅ Sent" if signal['telegram_sent'] else "⏳ Pending"
            
            recent_text += f"• {symbol} {tf} - {time_str} {status}\n"
        
        if len(signals) > 5:
            recent_text += f"... and {len(signals) - 5} more\n"
    
    pairs_text = f"🔧 **Enabled Pairs** ({len(enabled_pairs)}):\n"
    pairs_text += ", ".join(enabled_pairs)
    
    return f"""{recent_text}

{pairs_text}

⏰ **Timezone**: {settings.tz_display}
📈 **Timeframes**: {', '.join([normalize_timeframe_display(tf) for tf in settings.timeframes_list])}"""

def format_help_message() -> str:
    """Format help message with available commands"""
    
    return """🤖 **TradingView Signal Bot Help**

**📊 User Commands:**
/start - Welcome message and bot info
/help - Show this help message
/status - Show active pairs and recent signals  
/signals - Show recent signals (last 24h)
/chart <SYMBOL> <TF> - Generate TradingView chart link

**⚙️ Admin Commands:**
/add <SYMBOL> - Add new coin pair to monitoring
/remove <SYMBOL> - Remove coin pair from monitoring
/list - Show all monitored pairs
/stats - Show detailed signal statistics
/config - Show current bot configuration

**📝 Examples:**
• `/chart BTCUSDT 1h` - Get BTC 1h chart
• `/add ADAUSDT` - Add ADA pair (admin only)
• `/remove ETHBTC` - Remove ETH/BTC pair (admin only)

**🔧 Supported Pairs:**
BTCUSDT, ETHUSDT, ETHBTC, ADAUSDT (+ admin additions)

**⏰ Supported Timeframes:** 
5m, 15m, 1h, 4h, 1D

**🌍 Timezone:** Europe/London (GMT/BST)"""

def format_stats_message(stats: dict) -> str:
    """Format statistics message for admin commands"""
    
    return f"""📊 **Bot Statistics**

**📈 Signal Metrics:**
• Total Signals: {stats.get('total_signals', 0)}
• Successfully Sent: {stats.get('sent_signals', 0)}
• Failed Sends: {stats.get('failed_signals', 0)}
• Recent (24h): {stats.get('recent_24h', 0)}

**⚙️ Configuration:**
• Enabled Pairs: {stats.get('enabled_pairs', 0)}
• Supported Timeframes: {len(settings.timeframes_list)}
• Timezone: {settings.tz_display}
• Max Retries: {settings.telegram_max_retries}

**🔧 System:**
• Database TTL: {settings.idempotency_ttl_days} days"""

def format_pairs_list_message(pairs: list) -> str:
    """Format enabled pairs list message"""
    
    if not pairs:
        return "❌ **No enabled pairs found**"
    
    message = f"📋 **Enabled Pairs** ({len(pairs)}):\n\n"
    
    for i, pair in enumerate(pairs, 1):
        quote = detect_quote_currency(pair)
        base = pair.replace(quote, "")
        message += f"{i}. **{base}/{quote}** (`{pair}`)\n"
    
    message += f"\n💡 Use `/add <SYMBOL>` or `/remove <SYMBOL>` to manage pairs"
    
    return message

def format_chart_link_message(symbol: str, timeframe: str) -> str:
    """Format chart link message"""
    
    tf_display = normalize_timeframe_display(timeframe)
    chart_url = get_tradingview_chart_url(symbol, timeframe)
    
    quote = detect_quote_currency(symbol)
    base = symbol.replace(quote, "")
    pair_display = f"{base}/{quote}"
    
    return f"""📊 **Chart Link Generated**

💰 **Pair**: {pair_display}
⏰ **Timeframe**: {tf_display}

🔗 [View on TradingView]({chart_url})"""

def sanitize_message_text(text: str) -> str:
    """Sanitize message text for Telegram (escape special characters)"""
    # Telegram MarkdownV2 requires escaping certain characters
    # For now, we'll use basic HTML mode which is more forgiving
    
    # Remove any potential injection attempts
    text = re.sub(r'[<>]', '', text)
    
    # Limit message length
    if len(text) > 4096:
        text = text[:4090] + "..."
    
    return text