"""
Vercel KV database operations for TradingView-to-Telegram Signal Bot
"""

import json
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import aiohttp

from lib.config import settings

class DatabaseError(Exception):
    """Custom database error"""
    pass

class VercelKV:
    """Vercel KV Redis-compatible database client"""
    
    def __init__(self):
        self.base_url = settings.kv_rest_api_url
        self.token = settings.kv_rest_api_token
        
        if not self.base_url or not self.token:
            raise DatabaseError("Vercel KV credentials not configured")
    
    async def get(self, key: str) -> Optional[str]:
        """Get value by key"""
        headers = {"Authorization": f"Bearer {self.token}"}
        url = f"{self.base_url}/get/{key}"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        result = await response.json()
                        return result.get("result")
                    elif response.status == 404:
                        return None
                    else:
                        raise DatabaseError(f"KV GET error: {response.status}")
        except aiohttp.ClientError as e:
            raise DatabaseError(f"KV connection error: {e}")
    
    async def set(self, key: str, value: str, ex: Optional[int] = None) -> bool:
        """Set key-value pair with optional expiry"""
        headers = {"Authorization": f"Bearer {self.token}"}
        url = f"{self.base_url}/set/{key}"
        
        # Add expiry if provided
        if ex:
            url += f"?ex={ex}"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, data=value) as response:
                    return response.status == 200
        except aiohttp.ClientError as e:
            raise DatabaseError(f"KV connection error: {e}")
    
    async def exists(self, key: str) -> bool:
        """Check if key exists"""
        headers = {"Authorization": f"Bearer {self.token}"}
        url = f"{self.base_url}/exists/{key}"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        result = await response.json()
                        return result.get("result", 0) > 0
                    return False
        except aiohttp.ClientError as e:
            raise DatabaseError(f"KV connection error: {e}")
    
    async def delete(self, key: str) -> bool:
        """Delete key"""
        headers = {"Authorization": f"Bearer {self.token}"}
        url = f"{self.base_url}/del/{key}"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.delete(url, headers=headers) as response:
                    return response.status == 200
        except aiohttp.ClientError as e:
            raise DatabaseError(f"KV connection error: {e}")
    
    async def scan(self, pattern: str = "*", count: int = 100) -> List[str]:
        """Scan for keys matching pattern"""
        headers = {"Authorization": f"Bearer {self.token}"}
        url = f"{self.base_url}/scan/0?match={pattern}&count={count}"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        result = await response.json()
                        return result.get("result", [None, []])[1]
                    return []
        except aiohttp.ClientError as e:
            raise DatabaseError(f"KV connection error: {e}")

# Global KV instance
kv = VercelKV() if settings.has_kv_config else None

async def test_database_connection() -> bool:
    """Test database connectivity for health checks"""
    if not kv:
        raise DatabaseError("Vercel KV not configured")
    
    try:
        # Test with a simple ping
        test_key = "health_check"
        await kv.set(test_key, "ok", ex=10)  # 10 second expiry
        result = await kv.get(test_key)
        await kv.delete(test_key)
        return result == "ok"
    except Exception as e:
        raise DatabaseError(f"Database connection test failed: {e}")

async def save_signal(
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
    """Save signal to KV with idempotency check"""
    if not kv:
        raise DatabaseError("Database not configured")
    
    try:
        # Check if signal already exists
        existing = await kv.exists(f"signal:{signal_id}")
        if existing:
            return False  # Signal already exists
        
        # Create signal data
        signal_data = {
            "signal_id": signal_id,
            "symbol": symbol,
            "timeframe": timeframe,
            "event": event,
            "bar_time": bar_time,
            "entry": entry,
            "stop": stop,
            "target": target,
            "rr": rr,
            "telegram_sent": False,
            "telegram_error": None,
            "retry_count": 0,
            "created_at_utc": datetime.utcnow().isoformat(),
            "sent_at_utc": None,
            "chat_id": None
        }
        
        # Set with TTL
        ttl_seconds = settings.idempotency_ttl_days * 24 * 60 * 60
        await kv.set(
            f"signal:{signal_id}", 
            json.dumps(signal_data),
            ex=ttl_seconds
        )
        
        # Add to recent signals list (for status commands)
        await kv.set(
            f"recent:{signal_id}",
            json.dumps({
                "signal_id": signal_id,
                "symbol": symbol,
                "timeframe": timeframe,
                "created_at_utc": signal_data["created_at_utc"]
            }),
            ex=86400  # 24 hours
        )
        
        return True
        
    except Exception as e:
        raise DatabaseError(f"Failed to save signal: {e}")

async def mark_signal_sent(signal_id: str, chat_id: str, error: Optional[str] = None) -> bool:
    """Mark signal as sent (or failed) to Telegram"""
    if not kv:
        raise DatabaseError("Database not configured")
    
    try:
        # Get existing signal
        signal_json = await kv.get(f"signal:{signal_id}")
        if not signal_json:
            return False
        
        signal_data = json.loads(signal_json)
        
        # Update signal data
        if error:
            signal_data["telegram_error"] = error
            signal_data["retry_count"] = signal_data.get("retry_count", 0) + 1
        else:
            signal_data["telegram_sent"] = True
            signal_data["sent_at_utc"] = datetime.utcnow().isoformat()
            signal_data["chat_id"] = chat_id
        
        # Save updated signal
        ttl_seconds = settings.idempotency_ttl_days * 24 * 60 * 60
        await kv.set(
            f"signal:{signal_id}",
            json.dumps(signal_data),
            ex=ttl_seconds
        )
        
        return True
        
    except Exception as e:
        raise DatabaseError(f"Failed to update signal status: {e}")

async def get_pending_signals() -> List[Dict[str, Any]]:
    """Get signals that haven't been sent to Telegram yet"""
    if not kv:
        raise DatabaseError("Database not configured")
    
    try:
        # Scan for all signals
        signal_keys = await kv.scan("signal:*")
        pending_signals = []
        
        for key in signal_keys:
            signal_json = await kv.get(key)
            if signal_json:
                signal_data = json.loads(signal_json)
                
                # Check if pending and within retry limit
                if (not signal_data.get("telegram_sent", False) and 
                    signal_data.get("retry_count", 0) < settings.telegram_max_retries):
                    pending_signals.append(signal_data)
        
        # Sort by creation time
        pending_signals.sort(key=lambda x: x.get("created_at_utc", ""))
        return pending_signals
        
    except Exception as e:
        raise DatabaseError(f"Failed to get pending signals: {e}")

async def get_recent_signals(hours: int = 24, limit: int = 50) -> List[Dict[str, Any]]:
    """Get recent signals for status commands"""
    if not kv:
        raise DatabaseError("Database not configured")
    
    try:
        # Get recent signal keys
        recent_keys = await kv.scan("recent:*")
        recent_signals = []
        
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        
        for key in recent_keys[:limit]:  # Limit for performance
            recent_json = await kv.get(key)
            if recent_json:
                recent_data = json.loads(recent_json)
                
                # Check if within time range
                created_at = datetime.fromisoformat(recent_data["created_at_utc"])
                if created_at > cutoff:
                    # Get full signal data
                    signal_id = recent_data["signal_id"]
                    signal_json = await kv.get(f"signal:{signal_id}")
                    if signal_json:
                        recent_signals.append(json.loads(signal_json))
        
        # Sort by creation time (newest first)
        recent_signals.sort(key=lambda x: x.get("created_at_utc", ""), reverse=True)
        return recent_signals[:limit]
        
    except Exception as e:
        raise DatabaseError(f"Failed to get recent signals: {e}")

async def get_enabled_pairs() -> List[str]:
    """Get list of enabled trading pairs"""
    if not kv:
        # Fallback to config pairs if no KV
        return settings.pairs_list
    
    try:
        # Get custom pairs from KV
        pairs_json = await kv.get("config:enabled_pairs")
        if pairs_json:
            pairs_data = json.loads(pairs_json)
            return [pair["symbol"] for pair in pairs_data if pair.get("enabled", True)]
        
        # Fallback to default pairs
        return settings.pairs_list
        
    except Exception as e:
        # Fallback to config on error
        return settings.pairs_list

async def add_coin_pair(symbol: str, user_id: int, username: str) -> bool:
    """Add new coin pair to monitoring"""
    if not kv:
        raise DatabaseError("Database not configured")
    
    try:
        # Get existing pairs
        pairs_json = await kv.get("config:enabled_pairs")
        if pairs_json:
            pairs_data = json.loads(pairs_json)
        else:
            # Initialize with default pairs
            pairs_data = [
                {
                    "symbol": pair,
                    "enabled": True,
                    "added_by_user_id": None,
                    "added_by_username": "system",
                    "created_at_utc": datetime.utcnow().isoformat()
                }
                for pair in settings.pairs_list
            ]
        
        # Check if pair already exists
        existing_pair = next((p for p in pairs_data if p["symbol"] == symbol.upper()), None)
        
        if existing_pair:
            existing_pair["enabled"] = True
            existing_pair["updated_at_utc"] = datetime.utcnow().isoformat()
        else:
            # Add new pair
            pairs_data.append({
                "symbol": symbol.upper(),
                "enabled": True,
                "added_by_user_id": user_id,
                "added_by_username": username,
                "created_at_utc": datetime.utcnow().isoformat()
            })
        
        # Save updated pairs
        await kv.set("config:enabled_pairs", json.dumps(pairs_data))
        return True
        
    except Exception as e:
        raise DatabaseError(f"Failed to add coin pair: {e}")

async def remove_coin_pair(symbol: str) -> bool:
    """Remove coin pair from monitoring"""
    if not kv:
        raise DatabaseError("Database not configured")
    
    try:
        # Get existing pairs
        pairs_json = await kv.get("config:enabled_pairs")
        if not pairs_json:
            return False
        
        pairs_data = json.loads(pairs_json)
        
        # Find and disable pair
        pair_found = False
        for pair in pairs_data:
            if pair["symbol"] == symbol.upper():
                pair["enabled"] = False
                pair["updated_at_utc"] = datetime.utcnow().isoformat()
                pair_found = True
                break
        
        if not pair_found:
            return False
        
        # Save updated pairs
        await kv.set("config:enabled_pairs", json.dumps(pairs_data))
        return True
        
    except Exception as e:
        raise DatabaseError(f"Failed to remove coin pair: {e}")

async def is_admin_user(user_id: int) -> bool:
    """Check if user is admin (config only for serverless)"""
    return settings.is_admin(user_id)

async def get_bot_state(key: str) -> Optional[str]:
    """Get bot state value"""
    if not kv:
        return None
    
    try:
        return await kv.get(f"state:{key}")
    except Exception:
        return None

async def set_bot_state(key: str, value: str) -> bool:
    """Set bot state value"""
    if not kv:
        return False
    
    try:
        return await kv.set(f"state:{key}", value)
    except Exception:
        return False

async def get_signal_stats() -> Dict[str, Any]:
    """Get signal statistics for admin commands"""
    if not kv:
        return {
            "total_signals": 0,
            "sent_signals": 0,
            "failed_signals": 0,
            "recent_24h": 0,
            "enabled_pairs": len(settings.pairs_list)
        }
    
    try:
        # Get all signal keys for stats
        signal_keys = await kv.scan("signal:*")
        
        total = len(signal_keys)
        sent = 0
        failed = 0
        recent = 0
        
        cutoff = datetime.utcnow() - timedelta(hours=24)
        
        for key in signal_keys:
            signal_json = await kv.get(key)
            if signal_json:
                signal_data = json.loads(signal_json)
                
                if signal_data.get("telegram_sent", False):
                    sent += 1
                
                if signal_data.get("telegram_error"):
                    failed += 1
                
                created_at = datetime.fromisoformat(signal_data.get("created_at_utc", ""))
                if created_at > cutoff:
                    recent += 1
        
        enabled_pairs = len(await get_enabled_pairs())
        
        return {
            "total_signals": total,
            "sent_signals": sent,
            "failed_signals": failed,
            "recent_24h": recent,
            "enabled_pairs": enabled_pairs
        }
        
    except Exception:
        return {
            "total_signals": 0,
            "sent_signals": 0,
            "failed_signals": 0,
            "recent_24h": 0,
            "enabled_pairs": len(settings.pairs_list)
        }