"""
Telegram Bot API client for Vercel serverless functions
"""

import asyncio
from typing import Optional

import aiohttp

from lib.config import settings
from lib.database import mark_signal_sent
from lib.formatters import format_signal_message, sanitize_message_text

class TelegramError(Exception):
    """Custom Telegram API error"""
    pass

async def send_message(
    chat_id: str, 
    text: str, 
    parse_mode: str = "Markdown",
    disable_web_page_preview: bool = True
) -> dict:
    """Send message to Telegram chat"""
    
    # Sanitize message text
    text = sanitize_message_text(text)
    
    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": disable_web_page_preview
    }
    
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
            async with session.post(url, json=payload) as response:
                result = await response.json()
                
                if response.status == 200 and result.get("ok"):
                    return result
                else:
                    error_desc = result.get("description", "Unknown error")
                    raise TelegramError(f"Telegram API error: {error_desc}")
                    
    except aiohttp.ClientError as e:
        raise TelegramError(f"Network error: {e}")
    except Exception as e:
        raise TelegramError(f"Send error: {e}")

async def get_bot_info() -> dict:
    """Get bot info for health checks"""
    
    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/getMe"
    
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
            async with session.get(url) as response:
                result = await response.json()
                
                if response.status == 200 and result.get("ok"):
                    return result
                else:
                    error_desc = result.get("description", "Unknown error")
                    raise TelegramError(f"getMe failed: {error_desc}")
                    
    except aiohttp.ClientError as e:
        raise TelegramError(f"Network error in getMe: {e}")

async def send_signal_message(
    signal_id: str,
    symbol: str,
    timeframe: str,
    event: str,
    bar_time: int,
    entry: float,
    stop: float,
    target: float,
    rr: float
) -> bool:
    """Send formatted signal message to appropriate Telegram chat"""
    
    # Determine target chat ID using routing rules
    chat_id = settings.get_chat_id_for_signal(symbol, timeframe)
    
    # Format the message
    message_text = format_signal_message(
        signal_id=signal_id,
        symbol=symbol,
        timeframe=timeframe,
        event=event,
        bar_time=bar_time,
        entry=entry,
        stop=stop,
        target=target,
        rr=rr
    )
    
    # Send with retry logic
    success = await send_with_retry(signal_id, chat_id, message_text)
    
    if success:
        # Mark signal as sent in database
        await mark_signal_sent(signal_id, chat_id)
    else:
        # Mark signal as failed in database
        await mark_signal_sent(signal_id, chat_id, error="Failed after all retries")
    
    return success

async def send_with_retry(signal_id: str, chat_id: str, message_text: str) -> bool:
    """Send message with exponential backoff retry logic"""
    
    for attempt in range(settings.telegram_max_retries):
        try:
            await send_message(chat_id, message_text)
            return True
            
        except TelegramError as e:
            retry_delay = settings.retry_delays_list[min(attempt, len(settings.retry_delays_list) - 1)]
            
            # Don't retry on the last attempt
            if attempt < settings.telegram_max_retries - 1:
                await asyncio.sleep(retry_delay)
    
    return False

async def send_command_response(chat_id: str, message_text: str) -> bool:
    """Send response to bot command"""
    
    try:
        await send_message(chat_id, message_text)
        return True
        
    except TelegramError:
        return False

async def test_telegram_connection() -> bool:
    """Test Telegram API connectivity for health checks"""
    
    try:
        result = await get_bot_info()
        bot_info = result.get("result", {})
        return bool(bot_info.get("username"))
        
    except TelegramError:
        return False

async def send_notification(message: str, priority: str = "normal") -> bool:
    """Send notification message to default chat"""
    
    chat_id = settings.telegram_chat_id_default
    
    # Add priority prefix
    if priority == "high":
        message = f"🚨 **HIGH PRIORITY** 🚨\n\n{message}"
    elif priority == "low":
        message = f"ℹ️ {message}"
    
    return await send_command_response(chat_id, message)