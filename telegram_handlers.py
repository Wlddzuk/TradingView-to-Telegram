"""
Telegram Bot command handlers and setup
"""

import asyncio
import re
from typing import Dict, Any, Optional

import aiohttp
import structlog

from config import settings
from database import (
    get_recent_signals, get_enabled_pairs, add_coin_pair, 
    remove_coin_pair, is_admin_user, get_signal_stats
)
from formatters import (
    format_help_message, format_status_message, format_stats_message,
    format_pairs_list_message, format_chart_link_message, normalize_timeframe_display
)
from telegram_bot import send_command_response

logger = structlog.get_logger()

class TelegramCommandHandler:
    """Handle incoming Telegram commands"""
    
    def __init__(self):
        self.webhook_url = None
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def __aenter__(self):
        """Async context manager entry"""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30)
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()
    
    async def set_webhook(self, webhook_url: str) -> bool:
        """Set Telegram webhook URL"""
        if not self.session:
            return False
        
        url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/setWebhook"
        payload = {
            "url": webhook_url,
            "allowed_updates": ["message", "callback_query"]
        }
        
        try:
            async with self.session.post(url, json=payload) as response:
                result = await response.json()
                
                if response.status == 200 and result.get("ok"):
                    logger.info("telegram_webhook_set", webhook_url=webhook_url)
                    self.webhook_url = webhook_url
                    return True
                else:
                    logger.error("failed_to_set_webhook", error=result.get("description"))
                    return False
                    
        except Exception as e:
            logger.error("webhook_setup_error", error=str(e))
            return False
    
    async def process_update(self, update: Dict[str, Any]) -> bool:
        """Process incoming Telegram update"""
        try:
            message = update.get("message")
            if not message:
                return True  # Not a message update, ignore
            
            text = message.get("text", "").strip()
            chat_id = str(message.get("chat", {}).get("id"))
            user_id = message.get("from", {}).get("id")
            username = message.get("from", {}).get("username", "unknown")
            
            if not text.startswith("/"):
                return True  # Not a command, ignore
            
            logger.info(
                "telegram_command_received",
                command=text,
                chat_id=chat_id,
                user_id=user_id,
                username=username
            )
            
            # Route command to appropriate handler
            await self.handle_command(text, chat_id, user_id, username)
            return True
            
        except Exception as e:
            logger.error("failed_to_process_update", error=str(e), update=update)
            return False
    
    async def handle_command(self, text: str, chat_id: str, user_id: int, username: str):
        """Route command to appropriate handler"""
        
        # Parse command and arguments
        parts = text.split()
        command = parts[0].lower()
        args = parts[1:] if len(parts) > 1 else []
        
        # Remove @botname if present
        if "@" in command:
            command = command.split("@")[0]
        
        # Route to handlers
        if command == "/start":
            await self.cmd_start(chat_id)
        elif command == "/help":
            await self.cmd_help(chat_id)
        elif command == "/status":
            await self.cmd_status(chat_id)
        elif command == "/signals":
            await self.cmd_signals(chat_id)
        elif command == "/chart":
            await self.cmd_chart(chat_id, args)
        elif command == "/add":
            await self.cmd_add_pair(chat_id, user_id, username, args)
        elif command == "/remove":
            await self.cmd_remove_pair(chat_id, user_id, args)
        elif command == "/list":
            await self.cmd_list_pairs(chat_id)
        elif command == "/stats":
            await self.cmd_stats(chat_id, user_id)
        elif command == "/config":
            await self.cmd_config(chat_id, user_id)
        else:
            await self.cmd_unknown(chat_id, command)
    
    async def cmd_start(self, chat_id: str):
        """Handle /start command"""
        message = f"""🤖 **Welcome to TradingView Signal Bot!**

I receive EMA Bounce strategy signals from TradingView and forward them here with proper London time formatting.

**📊 Current Setup:**
• **Pairs**: {', '.join(settings.pairs_list)}
• **Timeframes**: {', '.join([normalize_timeframe_display(tf) for tf in settings.timeframes_list])}
• **Timezone**: {settings.tz_display}

**🔧 Quick Commands:**
• `/help` - Show all available commands
• `/status` - Check recent signals and enabled pairs
• `/signals` - View recent signals

Ready to receive trading signals! 🚀"""
        
        await send_command_response(chat_id, message)
    
    async def cmd_help(self, chat_id: str):
        """Handle /help command"""
        message = format_help_message()
        await send_command_response(chat_id, message)
    
    async def cmd_status(self, chat_id: str):
        """Handle /status command"""
        try:
            # Get recent signals and enabled pairs
            signals = await get_recent_signals(hours=24, limit=10)
            pairs = await get_enabled_pairs()
            
            message = format_status_message(signals, pairs)
            await send_command_response(chat_id, message)
            
        except Exception as e:
            logger.error("status_command_error", error=str(e))
            await send_command_response(chat_id, "❌ Error retrieving status information")
    
    async def cmd_signals(self, chat_id: str):
        """Handle /signals command"""
        try:
            signals = await get_recent_signals(hours=24, limit=20)
            
            if not signals:
                message = "📊 No signals received in the last 24 hours."
            else:
                message = f"📊 **Recent Signals** ({len(signals)} in last 24h):\n\n"
                
                for signal in signals:
                    symbol = signal['symbol']
                    tf = normalize_timeframe_display(signal['timeframe'])
                    status = "✅" if signal['telegram_sent'] else "❌"
                    
                    # Format entry/target for quick view
                    entry = signal['entry']
                    target = signal['target']
                    rr = signal['rr']
                    
                    message += f"{status} **{symbol}** {tf} - Entry: {entry:.4f}, Target: {target:.4f} ({rr:.1f}R)\n"
                
                message += f"\n💡 Use `/status` for more detailed information"
            
            await send_command_response(chat_id, message)
            
        except Exception as e:
            logger.error("signals_command_error", error=str(e))
            await send_command_response(chat_id, "❌ Error retrieving signals")
    
    async def cmd_chart(self, chat_id: str, args: list):
        """Handle /chart command"""
        if len(args) < 2:
            message = """📊 **Chart Command Usage:**

`/chart <SYMBOL> <TIMEFRAME>`

**Examples:**
• `/chart BTCUSDT 1h`
• `/chart ETHBTC 4h`
• `/chart ADAUSDT 1D`

**Supported timeframes:** 5m, 15m, 1h, 4h, 1D"""
            await send_command_response(chat_id, message)
            return
        
        symbol = args[0].upper()
        timeframe_input = args[1].lower()
        
        # Map display format back to TradingView format
        tf_map = {
            "5m": "5", "15m": "15", "1h": "60", "4h": "240", "1d": "D"
        }
        
        timeframe = tf_map.get(timeframe_input)
        if not timeframe:
            await send_command_response(
                chat_id, 
                f"❌ Invalid timeframe: {timeframe_input}\nSupported: 5m, 15m, 1h, 4h, 1D"
            )
            return
        
        # Validate timeframe is supported
        if timeframe not in settings.timeframes_list:
            await send_command_response(
                chat_id,
                f"❌ Timeframe {timeframe_input} not supported on this bot"
            )
            return
        
        message = format_chart_link_message(symbol, timeframe)
        await send_command_response(chat_id, message)
    
    async def cmd_add_pair(self, chat_id: str, user_id: int, username: str, args: list):
        """Handle /add command (admin only)"""
        if not await is_admin_user(user_id):
            await send_command_response(chat_id, "❌ This command requires admin privileges")
            return
        
        if not args:
            await send_command_response(chat_id, "❌ Usage: `/add <SYMBOL>` (e.g., `/add ADAUSDT`)")
            return
        
        symbol = args[0].upper()
        
        # Basic validation
        if not re.match(r'^[A-Z]{3,10}(USDT|BTC|ETH|BUSD)$', symbol):
            await send_command_response(
                chat_id, 
                f"❌ Invalid symbol format: {symbol}\nExpected format: BASEUSDT, BASEBTC, etc."
            )
            return
        
        try:
            success = await add_coin_pair(symbol, user_id, username)
            
            if success:
                message = f"✅ **Pair Added Successfully**\n\n💰 **Symbol**: {symbol}\n👤 **Added by**: @{username}\n\n💡 The bot will now process signals for this pair."
            else:
                message = f"❌ Failed to add pair {symbol}"
            
            await send_command_response(chat_id, message)
            
        except Exception as e:
            logger.error("add_pair_error", symbol=symbol, error=str(e))
            await send_command_response(chat_id, "❌ Error adding pair")
    
    async def cmd_remove_pair(self, chat_id: str, user_id: int, args: list):
        """Handle /remove command (admin only)"""
        if not await is_admin_user(user_id):
            await send_command_response(chat_id, "❌ This command requires admin privileges")
            return
        
        if not args:
            await send_command_response(chat_id, "❌ Usage: `/remove <SYMBOL>` (e.g., `/remove ADAUSDT`)")
            return
        
        symbol = args[0].upper()
        
        try:
            success = await remove_coin_pair(symbol)
            
            if success:
                message = f"✅ **Pair Removed Successfully**\n\n💰 **Symbol**: {symbol}\n\n💡 The bot will no longer process signals for this pair."
            else:
                message = f"❌ Pair {symbol} not found or already disabled"
            
            await send_command_response(chat_id, message)
            
        except Exception as e:
            logger.error("remove_pair_error", symbol=symbol, error=str(e))
            await send_command_response(chat_id, "❌ Error removing pair")
    
    async def cmd_list_pairs(self, chat_id: str):
        """Handle /list command"""
        try:
            pairs = await get_enabled_pairs()
            message = format_pairs_list_message(pairs)
            await send_command_response(chat_id, message)
            
        except Exception as e:
            logger.error("list_pairs_error", error=str(e))
            await send_command_response(chat_id, "❌ Error retrieving pairs list")
    
    async def cmd_stats(self, chat_id: str, user_id: int):
        """Handle /stats command (admin only)"""
        if not await is_admin_user(user_id):
            await send_command_response(chat_id, "❌ This command requires admin privileges")
            return
        
        try:
            stats = await get_signal_stats()
            message = format_stats_message(stats)
            await send_command_response(chat_id, message)
            
        except Exception as e:
            logger.error("stats_command_error", error=str(e))
            await send_command_response(chat_id, "❌ Error retrieving statistics")
    
    async def cmd_config(self, chat_id: str, user_id: int):
        """Handle /config command (admin only)"""
        if not await is_admin_user(user_id):
            await send_command_response(chat_id, "❌ This command requires admin privileges")
            return
        
        message = f"""⚙️ **Bot Configuration**

**🔧 Core Settings:**
• Port: {settings.port}
• Debug: {settings.debug}
• Timezone: {settings.tz_display}

**📊 Trading:**
• Supported Timeframes: {', '.join(settings.timeframes_list)}
• Default Chat: {settings.telegram_chat_id_default}

**🔄 Retry Logic:**
• Max Retries: {settings.telegram_max_retries}
• Retry Delays: {', '.join(map(str, settings.retry_delays_list))}s

**💾 Database:**
• URL: {settings.database_url}
• TTL: {settings.idempotency_ttl_days} days

**🔒 Security:**
• Rate Limit: {settings.rate_limit_per_minute}/min
• Max Request Size: {settings.max_request_size / 1024:.0f}KB"""
        
        await send_command_response(chat_id, message)
    
    async def cmd_unknown(self, chat_id: str, command: str):
        """Handle unknown commands"""
        message = f"❓ Unknown command: `{command}`\n\nUse `/help` to see available commands."
        await send_command_response(chat_id, message)

# Global handler instance
_telegram_handler = TelegramCommandHandler()

async def setup_telegram_bot():
    """Initialize Telegram bot and webhook"""
    logger.info("Setting up Telegram bot")
    
    # For now, we'll skip webhook setup since we're focusing on signal sending
    # In production, you would set up webhook endpoint for receiving commands
    
    logger.info("Telegram bot setup completed (webhook mode disabled)")

async def process_telegram_update(update: Dict[str, Any]) -> bool:
    """Process incoming Telegram webhook update"""
    return await _telegram_handler.process_update(update)

async def handle_telegram_webhook(update_data: Dict[str, Any]):
    """Handle incoming Telegram webhook (for future command processing)"""
    try:
        await process_telegram_update(update_data)
    except Exception as e:
        logger.error("telegram_webhook_error", error=str(e))